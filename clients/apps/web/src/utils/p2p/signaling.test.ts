import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SignalingClient } from './signaling'

/** MockWebSocket that lets tests drive server-side behaviour explicitly:
 *  open the socket, receive messages, trigger errors, trigger close.
 *  Every instantiation is captured on ``mockSockets`` so tests can
 *  retrieve the live socket. */
const mockSockets: MockWebSocket[] = []

class MockWebSocket {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3

  readyState = MockWebSocket.CONNECTING
  url: string
  binaryType: string = 'blob'

  onopen: (() => void) | null = null
  onmessage: ((e: { data: unknown }) => void) | null = null
  onerror: (() => void) | null = null
  onclose: (() => void) | null = null

  sent: unknown[] = []

  constructor(url: string) {
    this.url = url
    mockSockets.push(this)
  }

  // Sending queues a record but doesn't actually deliver anywhere.
  send(data: unknown) {
    this.sent.push(data)
  }

  // Real WebSocket fires onclose asynchronously after close() — tests
  // that want to simulate the close event drive ``_closeEvent()``
  // explicitly so they control the order of events (important for the
  // timeout test where close() is called before the timeout-reject).
  close() {
    this.readyState = MockWebSocket.CLOSED
  }

  _closeEvent() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.()
  }

  // Test helpers — drive the mock from the server's perspective.
  _open() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.()
  }

  _recv(data: unknown) {
    this.onmessage?.({ data })
  }

  _error() {
    this.onerror?.()
  }

  _closeWithoutCallback() {
    this.readyState = MockWebSocket.CLOSED
  }
}

// ── Test harness ──

beforeEach(() => {
  mockSockets.length = 0
  vi.stubGlobal('WebSocket', MockWebSocket)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

const SIGNAL_PATH = '/api/file-sharing/signal'

async function waitFor(cond: () => boolean, max = 100) {
  for (let i = 0; i < max; i++) {
    if (cond()) return
    await new Promise((r) => setTimeout(r, 1))
  }
  throw new Error('waitFor timed out')
}

describe('SignalingClient — connect', () => {
  it('sends an auth message with "secret" for host role', async () => {
    const client = new SignalingClient(SIGNAL_PATH)
    const promise = client.connect('slug-1', 'host', 'secret-abc')

    await waitFor(() => mockSockets.length === 1)
    const sock = mockSockets[0]!
    sock._open()

    await waitFor(() => sock.sent.length === 1)
    const auth = JSON.parse(sock.sent[0] as string)
    expect(auth).toEqual({ type: 'auth', role: 'host', secret: 'secret-abc' })

    sock._recv(
      JSON.stringify({
        type: 'welcome',
        peerId: 'peer-1',
        iceServers: [{ urls: 'stun:x' }],
      }),
    )

    const welcome = await promise
    expect(welcome.peerId).toBe('peer-1')
    expect(welcome.iceServers).toEqual([{ urls: 'stun:x' }])
    expect(client.connected).toBe(true)
    expect(client.peerId).toBe('peer-1')
    client.close()
  })

  it('sends "secret" for the legacy "uploader" role too', async () => {
    const client = new SignalingClient(SIGNAL_PATH)
    const promise = client.connect('slug', 'uploader', 'sec')
    await waitFor(() => mockSockets.length === 1)
    const sock = mockSockets[0]!
    sock._open()
    await waitFor(() => sock.sent.length === 1)
    expect(JSON.parse(sock.sent[0] as string)).toEqual({
      type: 'auth',
      role: 'uploader',
      secret: 'sec',
    })
    sock._recv(JSON.stringify({ type: 'welcome', peerId: 'p', iceServers: [] }))
    await promise
    client.close()
  })

  it('sends "token" for guest role (not "secret")', async () => {
    const client = new SignalingClient(SIGNAL_PATH)
    const promise = client.connect('slug', 'guest', 'tok-xyz')
    await waitFor(() => mockSockets.length === 1)
    const sock = mockSockets[0]!
    sock._open()
    await waitFor(() => sock.sent.length === 1)
    expect(JSON.parse(sock.sent[0] as string)).toEqual({
      type: 'auth',
      role: 'guest',
      token: 'tok-xyz',
    })
    sock._recv(JSON.stringify({ type: 'welcome', peerId: 'p', iceServers: [] }))
    await promise
    client.close()
  })

  it('sends "token" for the legacy "downloader" role too', async () => {
    const client = new SignalingClient(SIGNAL_PATH)
    const promise = client.connect('slug', 'downloader', 'tok')
    await waitFor(() => mockSockets.length === 1)
    const sock = mockSockets[0]!
    sock._open()
    await waitFor(() => sock.sent.length === 1)
    const msg = JSON.parse(sock.sent[0] as string)
    expect(msg.role).toBe('downloader')
    expect(msg.token).toBe('tok')
    expect(msg.secret).toBeUndefined()
    sock._recv(JSON.stringify({ type: 'welcome', peerId: 'p', iceServers: [] }))
    await promise
    client.close()
  })

  it('includes paymentToken in auth when provided', async () => {
    const client = new SignalingClient(SIGNAL_PATH)
    const promise = client.connect('slug', 'guest', 'tok', {
      paymentToken: 'pay-123',
    })
    await waitFor(() => mockSockets.length === 1)
    const sock = mockSockets[0]!
    sock._open()
    await waitFor(() => sock.sent.length === 1)
    expect(JSON.parse(sock.sent[0] as string)).toEqual({
      type: 'auth',
      role: 'guest',
      token: 'tok',
      paymentToken: 'pay-123',
    })
    sock._recv(JSON.stringify({ type: 'welcome', peerId: 'p', iceServers: [] }))
    await promise
    client.close()
  })

  it('rejects when server sends an error message', async () => {
    const client = new SignalingClient(SIGNAL_PATH)
    const promise = client.connect('slug', 'host', 'bad-secret')
    await waitFor(() => mockSockets.length === 1)
    const sock = mockSockets[0]!
    sock._open()
    sock._recv(JSON.stringify({ type: 'error', message: 'Invalid secret' }))
    await expect(promise).rejects.toThrow(/Invalid secret/)
  })

  it('rejects when welcome has no peerId', async () => {
    const client = new SignalingClient(SIGNAL_PATH)
    const promise = client.connect('slug', 'host', 'sec')
    await waitFor(() => mockSockets.length === 1)
    const sock = mockSockets[0]!
    sock._open()
    sock._recv(JSON.stringify({ type: 'welcome', iceServers: [] }))
    await expect(promise).rejects.toThrow(/missing peerId/)
  })

  it('rejects when welcome has no iceServers array', async () => {
    const client = new SignalingClient(SIGNAL_PATH)
    const promise = client.connect('slug', 'host', 'sec')
    await waitFor(() => mockSockets.length === 1)
    const sock = mockSockets[0]!
    sock._open()
    sock._recv(JSON.stringify({ type: 'welcome', peerId: 'p' }))
    await expect(promise).rejects.toThrow(/missing iceServers/)
  })

  it('rejects on websocket error', async () => {
    const client = new SignalingClient(SIGNAL_PATH)
    const promise = client.connect('slug', 'host', 'sec')
    await waitFor(() => mockSockets.length === 1)
    const sock = mockSockets[0]!
    sock._error()
    await expect(promise).rejects.toThrow(/WebSocket connection failed/)
  })

  it('rejects when the socket closes before auth completes', async () => {
    const client = new SignalingClient(SIGNAL_PATH)
    const promise = client.connect('slug', 'host', 'sec')
    await waitFor(() => mockSockets.length === 1)
    const sock = mockSockets[0]!
    sock._closeEvent()
    await expect(promise).rejects.toThrow(/closed before authentication/)
  })

  it('rejects on 15s timeout', async () => {
    vi.useFakeTimers()
    const client = new SignalingClient(SIGNAL_PATH)
    const promise = client.connect('slug', 'host', 'sec')
    // Attach the rejection handler up-front so Node doesn't flag the
    // rejection as "unhandled" in the gap between when it fires and
    // when ``await expect`` attaches.
    const assertion = expect(promise).rejects.toThrow(/timeout/)
    // Let the constructor run.
    await vi.advanceTimersByTimeAsync(0)
    expect(mockSockets.length).toBe(1)
    // Advance past the 15s timeout without driving the socket.
    await vi.advanceTimersByTimeAsync(15_001)
    await assertion
  })
})

describe('SignalingClient — post-welcome message routing', () => {
  async function connected() {
    const client = new SignalingClient(SIGNAL_PATH)
    const promise = client.connect('slug', 'host', 'sec')
    await waitFor(() => mockSockets.length === 1)
    const sock = mockSockets[0]!
    sock._open()
    sock._recv(JSON.stringify({ type: 'welcome', peerId: 'p', iceServers: [] }))
    await promise
    return { client, sock }
  }

  it('routes text relay messages to onMessage after welcome', async () => {
    const { client, sock } = await connected()
    const received: unknown[] = []
    client.onMessage = (m) => received.push(m)
    sock._recv(JSON.stringify({ type: 'relay', foo: 1 }))
    expect(received).toEqual([{ type: 'relay', foo: 1 }])
    client.close()
  })

  it('routes binary relay messages as "relay:binary" with ArrayBuffer data', async () => {
    const { client, sock } = await connected()
    const received: unknown[] = []
    client.onMessage = (m) => received.push(m)
    const buffer = new Uint8Array([1, 2, 3]).buffer
    sock._recv(buffer)
    expect(received).toHaveLength(1)
    const msg = received[0] as { type: string; data: ArrayBuffer }
    expect(msg.type).toBe('relay:binary')
    expect(msg.data).toBe(buffer)
    client.close()
  })

  it('silently drops malformed text relay messages without throwing', async () => {
    const { client, sock } = await connected()
    const received: unknown[] = []
    client.onMessage = (m) => received.push(m)
    expect(() => sock._recv('not-json')).not.toThrow()
    expect(received).toHaveLength(0)
    client.close()
  })
})

describe('SignalingClient — send helpers', () => {
  async function connected() {
    const client = new SignalingClient(SIGNAL_PATH)
    const promise = client.connect('slug', 'host', 'sec')
    await waitFor(() => mockSockets.length === 1)
    const sock = mockSockets[0]!
    sock._open()
    sock._recv(JSON.stringify({ type: 'welcome', peerId: 'p', iceServers: [] }))
    await promise
    // Drop the auth frame from ``sent`` so tests see only new frames.
    sock.sent = []
    return { client, sock }
  }

  it('send() serialises and returns true when connected', async () => {
    const { client, sock } = await connected()
    const ok = client.send({ type: 'offer', sdp: 'x' })
    expect(ok).toBe(true)
    expect(sock.sent).toHaveLength(1)
    expect(JSON.parse(sock.sent[0] as string)).toEqual({
      type: 'offer',
      sdp: 'x',
    })
    client.close()
  })

  it('send() returns false when socket is closed', async () => {
    const client = new SignalingClient(SIGNAL_PATH)
    expect(client.send({ type: 'foo' })).toBe(false)
  })

  it('sendRelayText wraps in a relay:data envelope', async () => {
    const { client, sock } = await connected()
    client.sendRelayText('peer-2', 'hello')
    expect(JSON.parse(sock.sent[0] as string)).toEqual({
      type: 'relay:data',
      targetId: 'peer-2',
      data: 'hello',
    })
    client.close()
  })

  it('sendBinary writes a framed ArrayBuffer: [4-byte len][header JSON][payload]', async () => {
    const { client, sock } = await connected()
    const payload = new Uint8Array([10, 20, 30]).buffer
    const ok = client.sendBinary('peer-2', payload)
    expect(ok).toBe(true)
    expect(sock.sent).toHaveLength(1)
    const frame = sock.sent[0] as ArrayBuffer
    expect(frame).toBeInstanceOf(ArrayBuffer)

    const view = new DataView(frame)
    const headerLen = view.getUint32(0, false)
    const headerBytes = new Uint8Array(frame, 4, headerLen)
    const header = JSON.parse(new TextDecoder().decode(headerBytes))
    expect(header).toEqual({ type: 'relay:chunk', targetId: 'peer-2' })

    const payloadOut = new Uint8Array(frame, 4 + headerLen)
    expect(Array.from(payloadOut)).toEqual([10, 20, 30])
    client.close()
  })

  it('sendBinary returns false when socket is closed', () => {
    const client = new SignalingClient(SIGNAL_PATH)
    expect(client.sendBinary('peer', new ArrayBuffer(0))).toBe(false)
  })
})

describe('SignalingClient — close()', () => {
  it('invokes the onClose callback once', async () => {
    const client = new SignalingClient(SIGNAL_PATH)
    const promise = client.connect('slug', 'host', 'sec')
    await waitFor(() => mockSockets.length === 1)
    const sock = mockSockets[0]!
    sock._open()
    sock._recv(JSON.stringify({ type: 'welcome', peerId: 'p', iceServers: [] }))
    await promise
    const onClose = vi.fn()
    client.onClose = onClose
    client.close()
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('is safe to call during an in-flight connect() — rejects the promise', async () => {
    const client = new SignalingClient(SIGNAL_PATH)
    const promise = client.connect('slug', 'host', 'sec')
    await waitFor(() => mockSockets.length === 1)
    // Don't drive welcome; just close. The pending promise must reject.
    client.close()
    await expect(promise).rejects.toThrow(/closed/)
  })

  it('clears peerId + iceServers', async () => {
    const client = new SignalingClient(SIGNAL_PATH)
    const promise = client.connect('slug', 'host', 'sec')
    await waitFor(() => mockSockets.length === 1)
    const sock = mockSockets[0]!
    sock._open()
    sock._recv(
      JSON.stringify({
        type: 'welcome',
        peerId: 'p',
        iceServers: [{ urls: 'stun:x' }],
      }),
    )
    await promise
    expect(client.peerId).toBe('p')
    expect(client.iceServers).toHaveLength(1)
    client.close()
    expect(client.peerId).toBeNull()
    expect(client.iceServers).toEqual([])
    expect(client.connected).toBe(false)
  })
})
