/**
 * Unit tests for the media-track surface added in PR 6.
 *
 * RTCPeerConnection is not implemented in the jsdom/happy-dom environment
 * these tests run in, so we inject a minimal stub via globalThis. The stub
 * records enough to assert the PeerDataConnection wiring (addTrack forwards,
 * ontrack delivers to the callback, onnegotiationneeded gates on remote
 * description, close() stops tracks).
 *
 * The wider data-channel path (send/onData/framing) is exercised end-to-end
 * by the app and has its own test coverage in file-sharing; this file
 * focuses on what PR 6 actually changed.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// ── Minimal RTCPeerConnection stub ──

interface RecordedSender {
  track: MediaStreamTrack | null
  _id: number
}

class FakePeerConnection {
  static instances: FakePeerConnection[] = []

  iceConnectionState = 'new'
  connectionState = 'new'

  onicecandidate: ((ev: { candidate: unknown }) => void) | null = null
  onconnectionstatechange: (() => void) | null = null
  ontrack:
    | ((ev: { track: MediaStreamTrack; streams: MediaStream[] }) => void)
    | null = null
  onnegotiationneeded: (() => void) | null = null
  ondatachannel: ((ev: { channel: unknown }) => void) | null = null

  private _senders: RecordedSender[] = []
  private _nextId = 1
  localDescription: { sdp: string; type: string } | null = null

  addTrackCalls: Array<{ track: MediaStreamTrack; stream: MediaStream }> = []
  removeTrackCalls: RecordedSender[] = []
  closeCalls = 0
  setLocalCalls: Array<{ sdp: string; type: string }> = []

  constructor(_config?: RTCConfiguration) {
    FakePeerConnection.instances.push(this)
  }

  addTrack(track: MediaStreamTrack, stream: MediaStream): RecordedSender {
    this.addTrackCalls.push({ track, stream })
    const sender: RecordedSender = { track, _id: this._nextId++ }
    this._senders.push(sender)
    // Simulate the browser firing negotiationneeded after any track change.
    queueMicrotask(() => this.onnegotiationneeded?.())
    return sender
  }

  removeTrack(sender: RecordedSender): void {
    this.removeTrackCalls.push(sender)
    sender.track = null
    queueMicrotask(() => this.onnegotiationneeded?.())
  }

  getSenders(): RecordedSender[] {
    return this._senders
  }

  async createOffer(): Promise<{ sdp: string; type: string }> {
    return { sdp: 'v=0\r\n', type: 'offer' }
  }

  async setLocalDescription(desc: {
    sdp: string
    type: string
  }): Promise<void> {
    this.localDescription = desc
    this.setLocalCalls.push(desc)
  }

  createDataChannel(
    _label: string,
    _opts?: unknown,
  ): {
    close(): void
  } {
    return { close() {} }
  }

  close(): void {
    this.closeCalls++
  }

  /** Test helper: simulate the remote peer adding a track. */
  _emitTrack(track: MediaStreamTrack, streams: MediaStream[]): void {
    this.ontrack?.({ track, streams })
  }
}

// ── Minimal MediaStreamTrack stub ──

function makeTrack(kind: 'video' | 'audio' = 'video'): MediaStreamTrack {
  const stop = vi.fn()
  return {
    kind,
    id: `track-${Math.random().toString(36).slice(2)}`,
    stop,
    // The DOM type demands a few more fields; the wrapper only reads .stop,
    // so a partial cast through `unknown` is safe here.
  } as unknown as MediaStreamTrack & { stop: typeof stop }
}

function makeStream(): MediaStream {
  return { id: 'stream-1' } as unknown as MediaStream
}

// ── Minimal SignalingClient stub ──

function makeSignaling() {
  const sent: Array<Record<string, unknown>> = []
  return {
    send: (msg: Record<string, unknown>) => {
      sent.push(msg)
    },
    sent,
  }
}

// ── Setup ──

let originalPC: unknown

beforeEach(() => {
  originalPC = globalThis.RTCPeerConnection
  ;(globalThis as unknown as { RTCPeerConnection: unknown }).RTCPeerConnection =
    FakePeerConnection
  FakePeerConnection.instances = []
})

afterEach(() => {
  ;(globalThis as unknown as { RTCPeerConnection: unknown }).RTCPeerConnection =
    originalPC
})

async function importWrapper() {
  const mod = await import('./peer-connection')
  return mod
}

// ── Tests ──

describe('PeerDataConnection: media track surface (PR 6)', () => {
  it('exposes the documented media-track API', async () => {
    const { PeerDataConnection } = await importWrapper()
    const sig = makeSignaling()
    const conn = new PeerDataConnection(sig as never, [], 'remote-peer')
    expect(typeof conn.addTrack).toBe('function')
    expect(typeof conn.removeTrack).toBe('function')
    expect(typeof conn.getLocalSenders).toBe('function')
    expect(conn.onTrack).toBeNull()
  })

  it('addTrack forwards to RTCPeerConnection and returns the sender', async () => {
    const { PeerDataConnection } = await importWrapper()
    const sig = makeSignaling()
    const conn = new PeerDataConnection(sig as never, [], 'remote-peer')
    const pc = FakePeerConnection.instances[0]!

    const track = makeTrack('video')
    const stream = makeStream()
    const sender = conn.addTrack(track, stream)

    expect(pc.addTrackCalls).toHaveLength(1)
    expect(pc.addTrackCalls[0]!.track).toBe(track)
    expect(pc.addTrackCalls[0]!.stream).toBe(stream)
    expect(sender).toBeDefined()
    expect(conn.getLocalSenders()).toHaveLength(1)
  })

  it('onTrack fires when the remote peer publishes a track', async () => {
    const { PeerDataConnection } = await importWrapper()
    const sig = makeSignaling()
    const conn = new PeerDataConnection(sig as never, [], 'remote-peer')
    const pc = FakePeerConnection.instances[0]!

    const received: Array<{
      track: MediaStreamTrack
      streams: readonly MediaStream[]
    }> = []
    conn.onTrack = (track, streams) => {
      received.push({ track, streams })
    }

    const remoteTrack = makeTrack('video')
    const remoteStream = makeStream()
    pc._emitTrack(remoteTrack, [remoteStream])

    expect(received).toHaveLength(1)
    expect(received[0]!.track).toBe(remoteTrack)
    expect(received[0]!.streams).toEqual([remoteStream])
  })

  it('removeTrack forwards to RTCPeerConnection', async () => {
    const { PeerDataConnection } = await importWrapper()
    const sig = makeSignaling()
    const conn = new PeerDataConnection(sig as never, [], 'remote-peer')
    const pc = FakePeerConnection.instances[0]!

    const sender = conn.addTrack(makeTrack(), makeStream())
    conn.removeTrack(sender)

    expect(pc.removeTrackCalls).toHaveLength(1)
    expect(pc.removeTrackCalls[0]).toBe(sender)
  })

  it('close() stops every local track and pc.close is called', async () => {
    const { PeerDataConnection } = await importWrapper()
    const sig = makeSignaling()
    const conn = new PeerDataConnection(sig as never, [], 'remote-peer')
    const pc = FakePeerConnection.instances[0]!

    const t1 = makeTrack('video') as MediaStreamTrack & {
      stop: ReturnType<typeof vi.fn>
    }
    const t2 = makeTrack('audio') as MediaStreamTrack & {
      stop: ReturnType<typeof vi.fn>
    }
    conn.addTrack(t1, makeStream())
    conn.addTrack(t2, makeStream())

    conn.close()

    expect(t1.stop).toHaveBeenCalledTimes(1)
    expect(t2.stop).toHaveBeenCalledTimes(1)
    expect(pc.closeCalls).toBe(1)
  })
})

describe('PeerDataConnection: renegotiation gating (PR 6)', () => {
  it('ignores onnegotiationneeded before the initial remote description is set', async () => {
    const { PeerDataConnection } = await importWrapper()
    const sig = makeSignaling()
    const conn = new PeerDataConnection(sig as never, [], 'remote-peer')
    const pc = FakePeerConnection.instances[0]!

    conn.addTrack(makeTrack(), makeStream())
    // Let the queued microtask fire.
    await new Promise((r) => queueMicrotask(() => r(null)))

    // No offer should have been sent — addTrack before the initial SDP
    // exchange must not trigger a renegotiation round trip.
    const offers = sig.sent.filter((m) => m.type === 'offer')
    expect(offers).toHaveLength(0)
    expect(pc.setLocalCalls).toHaveLength(0)
  })

  it('sends a fresh offer when addTrack fires after the connection is established', async () => {
    const { PeerDataConnection } = await importWrapper()
    const sig = makeSignaling()
    const conn = new PeerDataConnection(sig as never, [], 'remote-peer')
    const pc = FakePeerConnection.instances[0]!

    // Force the connection into "has remote description" state via the
    // public handleAnswer() path — the cheapest way to flip the internal
    // gate without running the whole SDP dance.
    // (The stub's setRemoteDescription is not implemented; we simulate by
    // poking the private flag directly. Intentional test-only escape hatch.)
    ;(
      conn as unknown as { _hasRemoteDescription: boolean }
    )._hasRemoteDescription = true

    conn.addTrack(makeTrack(), makeStream())
    // Drain the microtask queue enough times for the async _renegotiate
    // chain (negotiationneeded → createOffer → setLocalDescription → send)
    // to complete. Five ticks is comfortably more than the two awaits
    // _renegotiate performs.
    for (let i = 0; i < 5; i++) await Promise.resolve()

    const offers = sig.sent.filter((m) => m.type === 'offer')
    expect(offers).toHaveLength(1)
    expect(offers[0]).toMatchObject({
      type: 'offer',
      targetId: 'remote-peer',
    })
    expect(pc.setLocalCalls).toHaveLength(1)
  })
})
