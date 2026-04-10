/**
 * WebSocket signaling client for P2P file sharing.
 *
 * Replaces PeerJS signaling (0.peerjs.com) with a self-hosted WebSocket
 * endpoint. The client authenticates, receives ICE servers and a peer ID,
 * then relays SDP offers/answers and ICE candidates between peers.
 */

import { FILE_SHARING_SIGNAL_PATH } from './constants'
import { logger } from './logger'

// ── Types ──

export interface SignalingMessage {
  type: string
  [key: string]: unknown
}

export interface WelcomeMessage {
  type: 'welcome'
  peerId: string
  iceServers: RTCIceServer[]
}

export type SignalingMessageHandler = (msg: SignalingMessage) => void

// ── SignalingClient ──

export class SignalingClient {
  private ws: WebSocket | null = null
  private _peerId: string | null = null
  private _iceServers: RTCIceServer[] = []
  private _onMessage: SignalingMessageHandler | null = null
  private _onClose: (() => void) | null = null
  private _connectTimeout: ReturnType<typeof setTimeout> | null = null
  private _pendingReject: ((reason: Error) => void) | null = null

  get peerId(): string | null {
    return this._peerId
  }

  get iceServers(): RTCIceServer[] {
    return this._iceServers
  }

  set onMessage(handler: SignalingMessageHandler | null) {
    this._onMessage = handler
  }

  set onClose(handler: (() => void) | null) {
    this._onClose = handler
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  /**
   * Connect to the signaling server and authenticate.
   *
   * @param slug Channel slug
   * @param role "uploader" or "downloader"
   * @param credential Channel secret (for uploader) or reader token (for downloader)
   */
  async connect(
    slug: string,
    role: 'uploader' | 'downloader',
    credential: string,
    options?: { paymentToken?: string },
  ): Promise<WelcomeMessage> {
    // Build WebSocket URL from current origin
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}${FILE_SHARING_SIGNAL_PATH}/${slug}`

    logger.log('[Signaling] connecting to', url)

    return new Promise<WelcomeMessage>((resolve, reject) => {
      const ws = new WebSocket(url)
      this.ws = ws
      let settled = false

      // Allow close() to settle the promise if called before auth completes
      this._pendingReject = (reason) => {
        if (!settled) {
          settled = true
          reject(reason)
        }
      }

      const timeout = setTimeout(() => {
        this._connectTimeout = null
        ws.close()
        if (!settled) {
          settled = true
          reject(new Error('Signaling connection timeout'))
        }
      }, 15_000)
      this._connectTimeout = timeout

      ws.onopen = () => {
        logger.log('[Signaling] connected, authenticating as', role)
        const authMsg: Record<string, string> = { type: 'auth', role }
        if (role === 'uploader') {
          authMsg.secret = credential
        } else {
          authMsg.token = credential
        }
        if (options?.paymentToken) {
          authMsg.paymentToken = options.paymentToken
        }
        ws.send(JSON.stringify(authMsg))
      }

      ws.onmessage = (event) => {
        let msg: SignalingMessage
        try {
          msg = JSON.parse(event.data)
        } catch {
          logger.error('[Signaling] invalid JSON from server')
          return
        }

        if (msg.type === 'welcome') {
          clearTimeout(timeout)
          this._connectTimeout = null
          // Narrow from SignalingMessage (index-signature values are `unknown`)
          // to WelcomeMessage after validating the required fields below.
          const welcome: WelcomeMessage = {
            type: 'welcome',
            peerId: msg.peerId as string,
            iceServers: msg.iceServers as RTCIceServer[],
          }
          if (typeof welcome.peerId !== 'string' || !welcome.peerId) {
            if (!settled) {
              settled = true
              reject(
                new Error(
                  'Signaling server sent invalid welcome (missing peerId)',
                ),
              )
            }
            ws.close()
            return
          }
          if (!Array.isArray(welcome.iceServers)) {
            if (!settled) {
              settled = true
              reject(
                new Error(
                  'Signaling server sent invalid welcome (missing iceServers)',
                ),
              )
            }
            ws.close()
            return
          }
          // Guard: if timeout already rejected the promise, don't set internal state
          if (settled) return
          settled = true
          this._pendingReject = null
          this._peerId = welcome.peerId
          this._iceServers = welcome.iceServers
          logger.log('[Signaling] authenticated, peerId:', welcome.peerId)

          // Switch to relay mode — handles both text and binary messages
          ws.binaryType = 'arraybuffer'
          ws.onmessage = (evt) => {
            if (typeof evt.data === 'string') {
              try {
                const relayMsg = JSON.parse(evt.data) as SignalingMessage
                this._onMessage?.(relayMsg)
              } catch {
                logger.error('[Signaling] invalid relay message')
              }
            } else if (evt.data instanceof ArrayBuffer) {
              // Binary relay data from server — route to relay handler
              this._onMessage?.({
                type: 'relay:binary',
                data: evt.data,
              })
            }
          }

          resolve(welcome)
        } else if (msg.type === 'error') {
          clearTimeout(timeout)
          const errMsg =
            typeof msg.message === 'string'
              ? msg.message
              : 'Signaling auth failed'
          logger.error('[Signaling] error:', errMsg)
          if (!settled) {
            settled = true
            reject(new Error(errMsg))
          }
        }
      }

      ws.onerror = () => {
        clearTimeout(timeout)
        if (!settled) {
          settled = true
          reject(new Error('WebSocket connection failed'))
        }
      }

      ws.onclose = () => {
        clearTimeout(timeout)
        logger.log('[Signaling] connection closed')
        if (!settled) {
          settled = true
          reject(new Error('WebSocket closed before authentication completed'))
        }
        this._onClose?.()
      }
    })
  }

  /** Expose the raw WebSocket for relay backpressure checking. */
  get rawWs(): WebSocket | null {
    return this.ws
  }

  send(msg: SignalingMessage): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      logger.error('[Signaling] cannot send - not connected')
      return false
    }
    this.ws.send(JSON.stringify(msg))
    return true
  }

  /**
   * Send a binary relay frame to a target peer via the signaling server.
   * The server forwards the binary frame to the target's WebSocket.
   */
  sendBinary(targetId: string, data: ArrayBuffer): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      logger.error('[Signaling] cannot send binary - not connected')
      return false
    }
    // Prefix the binary frame with a JSON header identifying the target
    const header = JSON.stringify({
      type: 'relay:chunk',
      targetId,
    })
    const headerBytes = new TextEncoder().encode(header)
    // Frame: [4-byte header len][header JSON][binary payload]
    const frame = new ArrayBuffer(4 + headerBytes.byteLength + data.byteLength)
    const view = new DataView(frame)
    view.setUint32(0, headerBytes.byteLength, false)
    new Uint8Array(frame, 4, headerBytes.byteLength).set(headerBytes)
    new Uint8Array(frame, 4 + headerBytes.byteLength).set(new Uint8Array(data))
    this.ws.send(frame)
    return true
  }

  /**
   * Send a text relay message to a target peer via the signaling server.
   */
  sendRelayText(targetId: string, text: string): boolean {
    return this.send({
      type: 'relay:data',
      targetId,
      data: text,
    })
  }

  close(): void {
    if (this._connectTimeout) {
      clearTimeout(this._connectTimeout)
      this._connectTimeout = null
    }
    // Reject any pending connect() promise so callers don't hang forever
    const pendingReject = this._pendingReject
    this._pendingReject = null
    // Capture onClose before clearing state to handle reentrant calls
    // (e.g., if the onClose callback calls close() again)
    const onClose = this._onClose
    this._onClose = null
    this._onMessage = null
    if (this.ws) {
      this.ws.onclose = null
      this.ws.close()
      this.ws = null
    }
    this._peerId = null
    this._iceServers = []
    pendingReject?.(new Error('Signaling client closed'))
    try {
      onClose?.()
    } catch {
      /* ignore callback errors during teardown */
    }
  }
}
