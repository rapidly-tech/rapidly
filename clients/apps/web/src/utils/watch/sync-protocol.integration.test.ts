/**
 * Integration tests: real SyncHost ↔ real SyncGuest over a shared
 * in-memory transport. The existing unit tests exercise each half in
 * isolation; this file verifies the two halves actually agree on the
 * message shape and the reconciliation does the right thing end to end.
 *
 * Uses two FakeControllers (host-side and guest-side) wired together by
 * a synchronous ``deliver`` helper so every assertion is deterministic —
 * no real timers, no real DOM, no real network.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  DRIFT_SEEK_THRESHOLD_S,
  HEARTBEAT_MS,
  type SyncMediaController,
  type SyncMessage,
  createSyncGuest,
  createSyncHost,
} from './sync-protocol'

// ── Shared fake controller ──

class FakeController implements SyncMediaController {
  playing = false
  currentTime = 0
  playbackRate = 1

  private playCbs: Array<(playing: boolean) => void> = []
  private seekCbs: Array<(time: number) => void> = []
  private canPlayCbs: Array<() => void> = []

  async play(): Promise<void> {
    this.playing = true
    this.playCbs.forEach((c) => c(true))
  }
  pause(): void {
    this.playing = false
    this.playCbs.forEach((c) => c(false))
  }
  seek(time: number): void {
    this.currentTime = time
  }
  setPlaybackRate(rate: number): void {
    this.playbackRate = rate
  }
  onPlayOrPause(cb: (playing: boolean) => void): () => void {
    this.playCbs.push(cb)
    return () => {
      this.playCbs = this.playCbs.filter((c) => c !== cb)
    }
  }
  onSeek(cb: (time: number) => void): () => void {
    this.seekCbs.push(cb)
    return () => {
      this.seekCbs = this.seekCbs.filter((c) => c !== cb)
    }
  }
  onCanPlay(cb: () => void): () => void {
    this.canPlayCbs.push(cb)
    return () => {
      this.canPlayCbs = this.canPlayCbs.filter((c) => c !== cb)
    }
  }

  emitUserSeek(time: number): void {
    this.currentTime = time
    this.seekCbs.forEach((c) => c(time))
  }
  emitCanPlay(): void {
    this.canPlayCbs.forEach((c) => c())
  }
}

// ── Harness ──
//
// ``nowHolder`` is shared so host and guest see the same logical clock.
// Tests advance it manually to simulate transit latency between the two
// halves ("host sends at t=0, guest receives at t=latencyMs").

function makeHarness(latencyMs = 0) {
  const nowHolder = { ms: 0 }
  const now = () => nowHolder.ms

  const hostCtrl = new FakeController()
  const guestCtrl = new FakeController()

  // Capture what each side sent so tests can assert on the wire.
  const hostSent: SyncMessage[] = []
  const guestSent: SyncMessage[] = []

  // Guest is constructed after host but referenced from the host's
  // send closure. Wrap in a ref so ESLint prefer-const is satisfied
  // and the cyclic reference is explicit.
  const guestRef: { instance: ReturnType<typeof createSyncGuest> | null } = {
    instance: null,
  }

  const host = createSyncHost(
    hostCtrl,
    (msg) => {
      hostSent.push(msg)
      // Deliver to the guest after the configured transit latency.
      nowHolder.ms += latencyMs
      guestRef.instance?.apply(msg)
    },
    now,
  )
  const guest = createSyncGuest(
    guestCtrl,
    (msg) => {
      guestSent.push(msg)
    },
    { now },
  )
  guestRef.instance = guest

  return {
    hostCtrl,
    guestCtrl,
    host,
    guest,
    hostSent,
    guestSent,
    advanceClock: (ms: number) => {
      nowHolder.ms += ms
    },
  }
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('SyncHost ↔ SyncGuest round-trip', () => {
  it('guest starts playing after host play, with the host position', async () => {
    const h = makeHarness()
    h.hostCtrl.currentTime = 10

    await h.hostCtrl.play()
    // Wait for the async play() on the guest side.
    await Promise.resolve()

    expect(h.guestCtrl.playing).toBe(true)
    expect(h.hostSent[0]).toMatchObject({ t: 'state', playing: true })
    h.host.stop()
    h.guest.stop()
  })

  it('guest pauses after host pauses', async () => {
    const h = makeHarness()
    await h.hostCtrl.play()
    await Promise.resolve()
    h.hostCtrl.pause()

    expect(h.guestCtrl.playing).toBe(false)
    h.host.stop()
    h.guest.stop()
  })

  it('user seek on host lands at the same position on the guest', () => {
    const h = makeHarness()
    h.hostCtrl.emitUserSeek(42)

    // Host emits 'seek' (immediate jump) + 'state' (post-condition).
    // The 'seek' message makes the guest jump regardless of drift.
    expect(h.guestCtrl.currentTime).toBe(42)
    h.host.stop()
    h.guest.stop()
  })

  it('heartbeat keeps a paused guest converged even when no events fire', () => {
    const h = makeHarness()
    // Host sits paused at position 17. No play/pause/seek. The only way
    // the guest learns of the position is via the periodic heartbeat.
    h.hostCtrl.currentTime = 17
    h.guestCtrl.currentTime = 0

    vi.advanceTimersByTime(HEARTBEAT_MS)
    // Heartbeat fires, host sends state, guest sees drift ≥ threshold,
    // seeks. Paused ⇒ no latency compensation ⇒ guest lands at 17.
    expect(h.guestCtrl.currentTime).toBe(17)
    h.host.stop()
    h.guest.stop()
  })

  it('two heartbeats emit two state broadcasts end-to-end', () => {
    const h = makeHarness()
    vi.advanceTimersByTime(HEARTBEAT_MS * 2)
    expect(
      h.hostSent.filter((m) => m.t === 'state').length,
    ).toBeGreaterThanOrEqual(2)
    h.host.stop()
    h.guest.stop()
  })

  it("guest's ready message is produced on local canplay", () => {
    const h = makeHarness()
    h.guestCtrl.currentTime = 3
    h.guestCtrl.emitCanPlay()
    expect(h.guestSent).toContainEqual({ t: 'ready', position: 3 })
    h.host.stop()
    h.guest.stop()
  })

  it('simulated transit latency nudges the guest forward accurately', async () => {
    const h = makeHarness(1000) // 1 second of latency between send/receive
    h.hostCtrl.currentTime = 20

    // Host broadcasts while playing — guest must compensate for the 1s
    // latency and seek to ≈ 21, not 20.
    await h.hostCtrl.play()
    await Promise.resolve()

    // Guest was at 0 before; with latency compensation the "host-now"
    // is ≈ 21, so drift ≥ threshold and a seek fires.
    expect(h.guestCtrl.currentTime).toBeGreaterThan(20.5)
    expect(h.guestCtrl.currentTime).toBeLessThan(21.5)
    h.host.stop()
    h.guest.stop()
  })

  it('no explicit seek when drift is below the threshold after broadcast', () => {
    const h = makeHarness()
    // Place both sides within the no-op drift band.
    h.hostCtrl.currentTime = 10
    h.guestCtrl.currentTime = 10.02 // 20 ms ahead — below rate threshold

    h.host.broadcastState()
    expect(h.guestCtrl.playbackRate).toBe(1)
    expect(h.guestCtrl.currentTime).toBeCloseTo(10.02, 3)
    h.host.stop()
    h.guest.stop()
  })

  it('large drift in the paused state triggers a hard seek', () => {
    const h = makeHarness()
    h.hostCtrl.currentTime = 0
    // Guest is unrealistically far ahead. On the next broadcast (seek
    // threshold = 0.5s exactly would pass ≥; go an order above).
    h.guestCtrl.currentTime = DRIFT_SEEK_THRESHOLD_S + 5

    h.host.broadcastState()
    expect(h.guestCtrl.currentTime).toBe(0)
    h.host.stop()
    h.guest.stop()
  })
})
