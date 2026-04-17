/**
 * Thin wrapper around RTCPeerConnection + RTCDataChannel.
 *
 * Replaces the PeerJS client library. Provides a send/onData API
 * compatible with the existing hooks (useUploaderConnections, useDownloader).
 *
 * Message framing (replaces PeerJS binarypack):
 * - JSON messages: dc.send(JSON.stringify(msg))
 * - Binary messages (Chunk, EncryptedInfo): length-prefixed frame:
 *   [4-byte header length (big-endian)][UTF-8 JSON header][raw binary payload]
 * - Decode: typeof data === 'string' → JSON.parse, ArrayBuffer → unframe
 */

import { BUFFER_THRESHOLD, MAX_FRAME_SIZE, MAX_HEADER_SIZE } from './constants'
import { logger } from './logger'
import { SignalingClient } from './signaling'

// ── Constants ──

/** Timeout for backpressure wait (ms). Generous for slow TURN relay connections. */
const BACKPRESSURE_TIMEOUT = 60_000

/**
 * SCTP maxMessageSize (256 KB). Each dc.send() call must produce a message
 * no larger than this, or Chrome silently drops it and kills the channel.
 */
const SCTP_MAX_SIZE = 262_144

/**
 * Max payload bytes per fragment. Each fragment is a binary frame:
 * [4-byte header length][~100-byte JSON header][payload]
 * Total must fit within SCTP_MAX_SIZE.
 */
const FRAG_PAYLOAD_MAX = SCTP_MAX_SIZE - 4 - 128 // 262,012 bytes

/** Maximum concurrent fragment reassembly sets (prevents memory exhaustion). */
const MAX_FRAG_SETS = 16

/** Fragment reassembly timeout in ms (prevents leaks from incomplete transfers). */
const FRAG_TIMEOUT = 30_000

// ── Types ──

export type DataHandler = (data: unknown) => void

// ── PeerDataConnection ──

export class PeerDataConnection {
  private pc: RTCPeerConnection
  private dc: RTCDataChannel | null = null
  private signaling: SignalingClient
  private remotePeerId: string
  private _open = false
  private _closeFired = false
  private _metadata: Record<string, unknown> = {}
  private _hasRemoteDescription = false
  private _iceCandidateBuffer: RTCIceCandidateInit[] = []
  private _fragBuf = new Map<
    string,
    {
      total: number
      type: string
      parts: Map<number, ArrayBuffer>
      timer: ReturnType<typeof setTimeout>
    }
  >()

  onData: DataHandler | null = null
  onOpen: (() => void) | null = null
  onClose: (() => void) | null = null
  onError: ((err: Error) => void) | null = null

  get open(): boolean {
    return this._open
  }

  get peer(): string {
    return this.remotePeerId
  }

  get metadata(): Record<string, unknown> {
    return this._metadata
  }

  set metadata(m: Record<string, unknown>) {
    this._metadata = m
  }

  constructor(
    signaling: SignalingClient,
    iceServers: RTCIceServer[],
    remotePeerId: string,
  ) {
    this.signaling = signaling
    this.remotePeerId = remotePeerId
    this.pc = new RTCPeerConnection({
      iceServers,
      iceCandidatePoolSize: 1,
    })

    this.pc.onicecandidate = (event) => {
      if (event.candidate) {
        // Send ICE candidate fields as flat top-level properties so the
        // signaling relay can validate each one individually (candidate is
        // a string, sdpMid/sdpMLineIndex are nullable primitives).
        const init = event.candidate.toJSON()
        this.signaling.send({
          type: 'ice-candidate',
          targetId: remotePeerId,
          candidate: init.candidate,
          sdpMid: init.sdpMid,
          sdpMLineIndex: init.sdpMLineIndex,
          usernameFragment: init.usernameFragment,
        })
      }
    }

    this.pc.onconnectionstatechange = () => {
      const state = this.pc.connectionState
      logger.log('[PeerDataConnection] connection state:', state)
      if (state === 'failed' || state === 'closed') {
        // Full teardown: close DataChannel + RTCPeerConnection to release
        // TURN allocations and prevent resource leaks (not just fire onClose)
        this.close()
      }
    }
  }

  /**
   * Uploader side: create a DataChannel and generate an SDP offer.
   * The offer is sent to the remote peer via signaling.
   */
  async createOffer(): Promise<void> {
    this.dc = this.pc.createDataChannel('file-sharing', {
      ordered: true,
    })
    this._setupDataChannel(this.dc)

    const offer = await this.pc.createOffer()
    await this.pc.setLocalDescription(offer)

    const offerSdp = this.pc.localDescription?.sdp
    if (!offerSdp) throw new Error('Failed to get local SDP after createOffer')

    this.signaling.send({
      type: 'offer',
      targetId: this.remotePeerId,
      sdp: offerSdp,
    })
  }

  /**
   * Downloader side: handle an incoming SDP offer.
   * Creates an answer and sends it back via signaling.
   */
  async handleOffer(sdp: string): Promise<void> {
    // Listen for data channel created by remote (uploader)
    this.pc.ondatachannel = (event) => {
      this.dc = event.channel
      this._setupDataChannel(this.dc)
    }

    await this.pc.setRemoteDescription({ type: 'offer', sdp })
    this._hasRemoteDescription = true
    await this._flushIceCandidateBuffer()

    const answer = await this.pc.createAnswer()
    await this.pc.setLocalDescription(answer)

    const answerSdp = this.pc.localDescription?.sdp
    if (!answerSdp)
      throw new Error('Failed to get local SDP after createAnswer')

    this.signaling.send({
      type: 'answer',
      targetId: this.remotePeerId,
      sdp: answerSdp,
    })
  }

  /** Handle an incoming SDP answer from the remote peer. */
  async handleAnswer(sdp: string): Promise<void> {
    await this.pc.setRemoteDescription({ type: 'answer', sdp })
    this._hasRemoteDescription = true
    await this._flushIceCandidateBuffer()
  }

  /** Handle an incoming ICE candidate from the remote peer.
   *  Buffers candidates until remoteDescription is set to prevent InvalidStateError.
   */
  async handleIceCandidate(candidate: RTCIceCandidateInit): Promise<void> {
    if (!this._hasRemoteDescription) {
      // Cap buffer to prevent memory exhaustion from malicious peers flooding ICE candidates
      if (this._iceCandidateBuffer.length < 100) {
        this._iceCandidateBuffer.push(candidate)
      }
      return
    }
    await this.pc.addIceCandidate(candidate)
  }

  /** Flush any buffered ICE candidates after remoteDescription is set. */
  private async _flushIceCandidateBuffer(): Promise<void> {
    const buffered = this._iceCandidateBuffer.splice(0)
    for (const candidate of buffered) {
      try {
        await this.pc.addIceCandidate(candidate)
      } catch (err) {
        logger.error(
          '[PeerDataConnection] failed to add buffered ICE candidate:',
          err,
        )
      }
    }
  }

  /**
   * Send a message over the data channel.
   *
   * JSON-only messages are sent as strings.
   * Messages with binary payloads (bytes/payload fields) use length-prefixed framing.
   * Messages exceeding the SCTP limit are automatically fragmented.
   */
  async send(data: Record<string, unknown>): Promise<void> {
    if (!this.dc || this.dc.readyState !== 'open') {
      const err = new Error('Cannot send: DataChannel is not open')
      logger.error('[PeerDataConnection]', err.message)
      throw err
    }

    // Wait for backpressure to clear
    if (this.dc.bufferedAmount > BUFFER_THRESHOLD) {
      await this._waitForBuffer()
    }

    // Re-check state after async wait — DataChannel may have closed during backpressure
    if (!this.dc || this.dc.readyState !== 'open') {
      throw new Error(
        'Cannot send: DataChannel closed during backpressure wait',
      )
    }

    // Build raw payload (string for JSON-only, ArrayBuffer for binary frames)
    let rawPayload: ArrayBuffer | string

    const binaryField = data.bytes ?? data.payload
    if (
      binaryField instanceof ArrayBuffer ||
      (ArrayBuffer.isView(binaryField) && !(binaryField instanceof DataView))
    ) {
      const binaryData =
        binaryField instanceof ArrayBuffer
          ? binaryField
          : binaryField.buffer.slice(
              binaryField.byteOffset,
              binaryField.byteOffset + binaryField.byteLength,
            )

      // Create header without the binary field
      const header = { ...data }
      if ('bytes' in header) {
        delete header.bytes
        ;(header as Record<string, unknown>)._hasBinary = 'bytes'
      } else {
        delete header.payload
        ;(header as Record<string, unknown>)._hasBinary = 'payload'
      }

      const headerJson = new TextEncoder().encode(JSON.stringify(header))
      const headerLen = headerJson.byteLength

      // Frame: [4-byte header length][header JSON][binary payload]
      const frame = new ArrayBuffer(4 + headerLen + binaryData.byteLength)
      const view = new DataView(frame)
      view.setUint32(0, headerLen, false) // big-endian
      new Uint8Array(frame, 4, headerLen).set(headerJson)
      new Uint8Array(frame, 4 + headerLen).set(new Uint8Array(binaryData))

      rawPayload = frame
    } else {
      rawPayload = JSON.stringify(data)
    }

    await this._sendPayload(rawPayload)
  }

  /**
   * Send a raw payload, fragmenting automatically if it exceeds the SCTP limit.
   *
   * Fragment protocol (binary frames with _frag header):
   *   header: {_frag:1, id:<8-char-id>, i:<0-based-index>, n:<total>, t:'s'|'b', _hasBinary:'bytes'}
   *   payload: slice of the original message bytes
   *   t:'s' = original was a JSON string, t:'b' = original was a binary frame
   */
  private async _sendPayload(payload: ArrayBuffer | string): Promise<void> {
    if (!this.dc || this.dc.readyState !== 'open') {
      throw new Error('DataChannel not open')
    }

    // Convert strings to bytes once (avoids encoding twice for size check + fragmentation)
    const isString = typeof payload === 'string'
    const bytes = isString
      ? new TextEncoder().encode(payload)
      : new Uint8Array(payload)

    if (bytes.byteLength <= SCTP_MAX_SIZE) {
      // Small enough to send directly — use original string for JSON (avoids copy)
      if (isString) {
        this.dc.send(payload as string)
      } else {
        this.dc.send(payload as ArrayBuffer)
      }
      return
    }
    const idBytes = new Uint8Array(6)
    crypto.getRandomValues(idBytes)
    const id = Array.from(idBytes, (b) => b.toString(36).padStart(2, '0'))
      .join('')
      .slice(0, 8)
    const totalFrags = Math.ceil(bytes.byteLength / FRAG_PAYLOAD_MAX)

    logger.log(
      `[PeerDataConnection] fragmenting ${bytes.byteLength} bytes into ${totalFrags} fragments`,
    )

    for (let i = 0; i < totalFrags; i++) {
      const start = i * FRAG_PAYLOAD_MAX
      const end = Math.min(start + FRAG_PAYLOAD_MAX, bytes.byteLength)
      const slice = bytes.slice(start, end)

      const fragHeader = new TextEncoder().encode(
        JSON.stringify({
          _frag: 1,
          id,
          i,
          n: totalFrags,
          t: isString ? 's' : 'b',
          _hasBinary: 'bytes',
        }),
      )
      const frame = new ArrayBuffer(
        4 + fragHeader.byteLength + slice.byteLength,
      )
      const view = new DataView(frame)
      view.setUint32(0, fragHeader.byteLength, false)
      new Uint8Array(frame, 4, fragHeader.byteLength).set(fragHeader)
      new Uint8Array(frame, 4 + fragHeader.byteLength).set(slice)

      // Backpressure check between fragments
      if (this.dc && this.dc.bufferedAmount > BUFFER_THRESHOLD) {
        await this._waitForBuffer()
      }
      if (!this.dc || this.dc.readyState !== 'open') {
        throw new Error('DataChannel closed during fragment send')
      }
      this.dc.send(frame)
    }
  }

  close(): void {
    this._open = false
    this._iceCandidateBuffer = []
    // Clean up fragment reassembly timers
    for (const entry of this._fragBuf.values()) {
      clearTimeout(entry.timer)
    }
    this._fragBuf.clear()
    // Save onClose before nulling so timers/state get cleaned up after teardown
    const alreadyFired = this._closeFired
    this._closeFired = true
    const savedOnClose = this.onClose
    this.onData = null
    this.onOpen = null
    this.onClose = null
    this.onError = null
    if (this.dc) {
      try {
        this.dc.close()
      } catch {
        /* ignore */
      }
    }
    try {
      this.pc.close()
    } catch {
      /* ignore */
    }
    // Fire onClose after teardown so the caller can clean up timers and state
    if (!alreadyFired) {
      savedOnClose?.()
    }
  }

  private _setupDataChannel(dc: RTCDataChannel): void {
    dc.binaryType = 'arraybuffer'

    dc.onopen = () => {
      logger.log('[PeerDataConnection] data channel open')
      this._open = true
      this.onOpen?.()
    }

    dc.onclose = () => {
      logger.log('[PeerDataConnection] data channel closed')
      this._open = false
      if (!this._closeFired) {
        this._closeFired = true
        this.onClose?.()
      }
    }

    dc.onerror = () => {
      // DataChannel errors are typically benign teardown events (remote peer closed).
      // For data-only channels, onerror fires before onclose during normal shutdown.
      logger.log('[PeerDataConnection] data channel error')
      this.onError?.(new Error('DataChannel error'))
    }

    dc.onmessage = (event) => {
      const raw = event.data
      if (typeof raw === 'string') {
        // JSON message
        try {
          this.onData?.(JSON.parse(raw))
        } catch {
          logger.error('[PeerDataConnection] invalid JSON message')
        }
      } else if (raw instanceof ArrayBuffer) {
        // Binary framed message — may be a fragment or a complete message
        try {
          const parsed = this._unframe(raw)
          if (
            parsed &&
            typeof parsed === 'object' &&
            (parsed as Record<string, unknown>)._frag === 1
          ) {
            this._handleFragment(
              parsed as {
                _frag: 1
                id: string
                i: number
                n: number
                t: string
                bytes: ArrayBuffer
              },
            )
          } else {
            this.onData?.(parsed)
          }
        } catch (err) {
          logger.error('[PeerDataConnection] invalid binary frame:', err)
          this.onError?.(new Error('Received malformed binary frame'))
        }
      }
    }
  }

  /** Decode a length-prefixed binary frame back into a message object. */
  private _unframe(frame: ArrayBuffer): unknown {
    if (frame.byteLength < 4) {
      throw new Error(`Frame too small: ${frame.byteLength} bytes`)
    }

    if (frame.byteLength > MAX_FRAME_SIZE) {
      throw new Error(
        `Frame too large: ${frame.byteLength} bytes (max ${MAX_FRAME_SIZE})`,
      )
    }

    const view = new DataView(frame)
    const headerLen = view.getUint32(0, false)

    if (headerLen > MAX_HEADER_SIZE) {
      throw new Error(
        `Header too large: ${headerLen} bytes (max ${MAX_HEADER_SIZE})`,
      )
    }

    if (headerLen > frame.byteLength - 4) {
      throw new Error(
        `Invalid frame: header length ${headerLen} exceeds frame size ${frame.byteLength}`,
      )
    }

    const headerBytes = new Uint8Array(frame, 4, headerLen)
    const header = JSON.parse(new TextDecoder().decode(headerBytes)) as Record<
      string,
      unknown
    >

    const binaryStart = 4 + headerLen
    const binary = frame.slice(binaryStart)

    const rawFieldName = (header._hasBinary as string) || 'bytes'
    delete header._hasBinary
    // Validate field name to prevent prototype pollution from malicious peers
    const fieldName = rawFieldName === 'payload' ? 'payload' : 'bytes'
    header[fieldName] = binary

    return header
  }

  /** Reassemble a received fragment. Delivers the complete message via onData when all parts arrive. */
  private _handleFragment(frag: {
    _frag: 1
    id: string
    i: number
    n: number
    t: string
    bytes: ArrayBuffer
  }): void {
    const { id, i, n, t, bytes } = frag

    if (n < 1 || n > 10_000 || i < 0 || i >= n) {
      logger.error('[PeerDataConnection] invalid fragment indices:', {
        id,
        i,
        n,
      })
      return
    }

    let entry = this._fragBuf.get(id)
    if (!entry) {
      if (this._fragBuf.size >= MAX_FRAG_SETS) {
        // Evict the oldest fragment set to make room (prevents stalling
        // legitimate downloads when many concurrent transfers are active)
        const oldestId = this._fragBuf.keys().next().value
        if (oldestId !== undefined) {
          const evicted = this._fragBuf.get(oldestId)
          if (evicted) clearTimeout(evicted.timer)
          this._fragBuf.delete(oldestId)
          logger.warn(
            `[PeerDataConnection] evicted oldest fragment set ${oldestId} to make room`,
          )
        }
      }
      entry = {
        total: n,
        type: t,
        parts: new Map(),
        timer: setTimeout(() => {
          this._fragBuf.delete(id)
          logger.warn(`[PeerDataConnection] fragment set ${id} timed out`)
        }, FRAG_TIMEOUT),
      }
      this._fragBuf.set(id, entry)
    }

    // Reject mismatched total or duplicate indices (malicious or buggy peer)
    if (entry.total !== n || entry.parts.has(i)) {
      logger.error('[PeerDataConnection] fragment mismatch or duplicate:', {
        id,
        i,
        n,
      })
      return
    }

    entry.parts.set(i, bytes)

    if (entry.parts.size < entry.total) return

    // All fragments received — reassemble
    clearTimeout(entry.timer)
    this._fragBuf.delete(id)

    let totalLen = 0
    for (let j = 0; j < n; j++) {
      const part = entry.parts.get(j)
      if (!part) throw new Error(`Missing fragment ${j} of ${n}`)
      totalLen += part.byteLength
    }

    const assembled = new ArrayBuffer(totalLen)
    const view = new Uint8Array(assembled)
    let offset = 0
    for (let j = 0; j < n; j++) {
      const part = entry.parts.get(j)! // safe: verified above
      view.set(new Uint8Array(part), offset)
      offset += part.byteLength
    }

    try {
      if (entry.type === 's') {
        // Original was a JSON string
        this.onData?.(JSON.parse(new TextDecoder().decode(assembled)))
      } else {
        // Original was a binary frame — decode it
        this.onData?.(this._unframe(assembled))
      }
    } catch (err) {
      logger.error(
        '[PeerDataConnection] failed to decode reassembled message:',
        err,
      )
    }
  }

  /** Wait for bufferedAmount to drop below threshold. */
  private _waitForBuffer(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.dc) {
        resolve()
        return
      }
      const dc = this.dc
      let settled = false
      // Track the current bufferedamountlow handler so cleanup can remove it
      let currentBufferHandler: (() => void) | null = null

      const cleanup = () => {
        clearTimeout(timeout)
        dc.removeEventListener('close', onClose)
        if (currentBufferHandler) {
          dc.removeEventListener('bufferedamountlow', currentBufferHandler)
          currentBufferHandler = null
        }
      }

      // Timeout to prevent permanent hang if channel dies
      const timeout = setTimeout(() => {
        if (settled) return
        settled = true
        cleanup()
        reject(new Error('Backpressure wait timeout'))
      }, BACKPRESSURE_TIMEOUT)

      const done = () => {
        if (settled) return
        settled = true
        cleanup()
        resolve()
      }

      // Escape hatch: reject if channel closes while waiting
      const onClose = () => {
        if (settled) return
        settled = true
        cleanup()
        reject(new Error('DataChannel closed while waiting for backpressure'))
      }
      dc.addEventListener('close', onClose, { once: true })

      const check = () => {
        if (settled) return
        if (dc.bufferedAmount <= BUFFER_THRESHOLD) {
          done()
        } else {
          dc.bufferedAmountLowThreshold = BUFFER_THRESHOLD
          const onBufferLow = () => {
            currentBufferHandler = null
            if (dc.bufferedAmount <= BUFFER_THRESHOLD) {
              done()
            } else {
              check() // re-register if still above threshold
            }
          }
          currentBufferHandler = onBufferLow
          dc.addEventListener('bufferedamountlow', onBufferLow, { once: true })
          // Double-check: buffer may have drained between the if-check and addEventListener
          if (dc.bufferedAmount <= BUFFER_THRESHOLD) {
            done()
          }
        }
      }
      check()
    })
  }
}
