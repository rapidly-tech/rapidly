/**
 * WebSocket relay transport for file sharing.
 *
 * Fallback when WebRTC DataChannel fails (restrictive firewalls, symmetric NATs).
 * Matches PeerDataConnection's send()/onData interface so the rest of the
 * chunk processing pipeline works identically.
 *
 * Architecture: Uploader ──WS──> Signaling Server ──WS──> Downloader
 * All data is already encrypted — server sees only ciphertext.
 */

import { BUFFER_THRESHOLD, MAX_FRAME_SIZE, MAX_HEADER_SIZE } from './constants'
import { logger } from './logger'
import { SignalingClient } from './signaling'

// ── Constants ──

/** Backpressure wait timeout (ms). */
const WS_BACKPRESSURE_TIMEOUT = 60_000

// ── Types ──

export type RelayDataHandler = (data: unknown) => void

// ── WebSocketRelay ──

export class WebSocketRelay {
  private signaling: SignalingClient
  private remotePeerId: string
  private _open = false

  onData: RelayDataHandler | null = null
  onOpen: (() => void) | null = null
  onClose: (() => void) | null = null
  onError: ((err: Error) => void) | null = null

  get open(): boolean {
    return this._open
  }

  get peer(): string {
    return this.remotePeerId
  }

  constructor(signaling: SignalingClient, remotePeerId: string) {
    this.signaling = signaling
    this.remotePeerId = remotePeerId
  }

  /**
   * Start the relay by sending a relay:start message.
   * The remote peer should respond by creating its own WebSocketRelay.
   */
  start(): void {
    this._open = true
    this.signaling.send({
      type: 'relay:start',
      targetId: this.remotePeerId,
    })
    this.onOpen?.()
  }

  /**
   * Accept an incoming relay (called when receiving relay:start).
   */
  accept(): void {
    this._open = true
    this.signaling.send({
      type: 'relay:ack',
      targetId: this.remotePeerId,
    })
    this.onOpen?.()
  }

  /**
   * Handle an incoming relay message from the signaling WebSocket.
   * Called by the hook when relay messages arrive.
   */
  handleRelayData(data: ArrayBuffer | string): void {
    if (!this._open) return

    if (typeof data === 'string') {
      try {
        this.onData?.(JSON.parse(data))
      } catch {
        logger.error('[WebSocketRelay] invalid JSON relay data')
      }
    } else if (data instanceof ArrayBuffer) {
      try {
        const parsed = this._unframe(data)
        this.onData?.(parsed)
      } catch (err) {
        logger.error('[WebSocketRelay] invalid binary relay frame:', err)
        this.onError?.(new Error('Received malformed relay frame'))
      }
    }
  }

  /**
   * Send a message via the signaling WebSocket relay.
   * Matches PeerDataConnection.send() interface.
   */
  async send(data: Record<string, unknown>): Promise<void> {
    if (!this._open) {
      throw new Error('Cannot send: WebSocketRelay is not open')
    }

    // Wait for backpressure
    const ws = this.signaling.rawWs
    if (ws && ws.bufferedAmount > BUFFER_THRESHOLD) {
      await this._waitForBuffer(ws)
    }

    if (!this._open) {
      throw new Error('WebSocketRelay closed during backpressure wait')
    }

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

      // Build frame: [4-byte header length][JSON header][binary payload]
      const header = { ...data }
      if ('bytes' in header) {
        delete header.bytes
        ;(header as Record<string, unknown>)._hasBinary = 'bytes'
      } else {
        delete header.payload
        ;(header as Record<string, unknown>)._hasBinary = 'payload'
      }

      const headerJson = new TextEncoder().encode(JSON.stringify(header))
      const frame = new ArrayBuffer(
        4 + headerJson.byteLength + binaryData.byteLength,
      )
      const view = new DataView(frame)
      view.setUint32(0, headerJson.byteLength, false)
      new Uint8Array(frame, 4, headerJson.byteLength).set(headerJson)
      new Uint8Array(frame, 4 + headerJson.byteLength).set(
        new Uint8Array(binaryData),
      )

      // Send as relay:chunk binary message via signaling
      this.signaling.sendBinary(this.remotePeerId, frame)
    } else {
      // JSON-only message — send as relay text
      this.signaling.sendRelayText(this.remotePeerId, JSON.stringify(data))
    }
  }

  /** Signal relay completion. */
  done(): void {
    if (!this._open) return
    this.signaling.send({
      type: 'relay:done',
      targetId: this.remotePeerId,
    })
  }

  close(): void {
    if (!this._open) return
    this._open = false
    this.onClose?.()
    this.onData = null
    this.onOpen = null
    this.onClose = null
    this.onError = null
  }

  /** Decode a length-prefixed binary frame. Same logic as PeerDataConnection. */
  private _unframe(frame: ArrayBuffer): unknown {
    if (frame.byteLength < 4) {
      throw new Error(`Frame too small: ${frame.byteLength} bytes`)
    }
    if (frame.byteLength > MAX_FRAME_SIZE) {
      throw new Error(`Frame too large: ${frame.byteLength} bytes`)
    }

    const view = new DataView(frame)
    const headerLen = view.getUint32(0, false)

    if (headerLen > MAX_HEADER_SIZE || headerLen > frame.byteLength - 4) {
      throw new Error(`Invalid frame header length: ${headerLen}`)
    }

    const headerBytes = new Uint8Array(frame, 4, headerLen)
    const header = JSON.parse(new TextDecoder().decode(headerBytes)) as Record<
      string,
      unknown
    >

    const binary = frame.slice(4 + headerLen)
    const rawFieldName = (header._hasBinary as string) || 'bytes'
    delete header._hasBinary
    const fieldName = rawFieldName === 'payload' ? 'payload' : 'bytes'
    header[fieldName] = binary

    return header
  }

  /** Wait for WS buffer to drain below threshold using a drain-check interval. */
  private _waitForBuffer(ws: WebSocket): Promise<void> {
    return new Promise((resolve, reject) => {
      if (ws.bufferedAmount <= BUFFER_THRESHOLD) {
        resolve()
        return
      }

      let settled = false
      const cleanup = () => {
        settled = true
        clearTimeout(timeout)
        clearInterval(interval)
        ws.removeEventListener('close', onClose)
      }

      const timeout = setTimeout(() => {
        if (settled) return
        cleanup()
        reject(new Error('WebSocket backpressure timeout'))
      }, WS_BACKPRESSURE_TIMEOUT)

      const onClose = () => {
        if (settled) return
        cleanup()
        reject(new Error('WebSocket closed while waiting for backpressure'))
      }
      ws.addEventListener('close', onClose, { once: true })

      // WebSocket API has no 'drain' event; poll at a reasonable interval.
      // 200ms balances responsiveness with CPU usage (vs. previous 50ms).
      const interval = setInterval(() => {
        if (settled) return
        if (ws.bufferedAmount <= BUFFER_THRESHOLD) {
          cleanup()
          resolve()
        }
      }, 200)
    })
  }
}
