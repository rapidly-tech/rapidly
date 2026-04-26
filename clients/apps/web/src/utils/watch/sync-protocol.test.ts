/**
 * Unit tests for the Watch sync protocol.
 *
 * Uses a hand-rolled FakeController and a deterministic clock so the
 * drift-correction branches can be exercised without a real <video> or
 * JS timers. Covers:
 *
 *   - SyncMessage type narrowing
 *   - Host broadcasts on play/pause, on seek, on heartbeat
 *   - Guest plays / pauses to match state
 *   - Guest corrects drift via seek vs rate nudge vs no-op
 *   - Guest echoes 'ready' on canplay
 *   - Explicit 'seek' message short-circuits drift comparison
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  DRIFT_SEEK_THRESHOLD_S,
  HEARTBEAT_MS,
  RATE_NUDGE_DELTA,
  type SyncMediaController,
  type SyncMessage,
  createSyncGuest,
  createSyncHost,
  isSyncMessage,
} from './sync-protocol'

// ── Fakes ──

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

  // Test helpers: trigger user-driven events the real <video> emits.
  emitUserSeek(time: number): void {
    this.currentTime = time
    this.seekCbs.forEach((c) => c(time))
  }
  emitCanPlay(): void {
    this.canPlayCbs.forEach((c) => c())
  }
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

// ── isSyncMessage ──

describe('isSyncMessage', () => {
  it('accepts a well-formed state message', () => {
    expect(
      isSyncMessage({ t: 'state', playing: true, position: 10, at: 1234 }),
    ).toBe(true)
  })

  it('accepts ready and seek messages', () => {
    expect(isSyncMessage({ t: 'ready', position: 5 })).toBe(true)
    expect(isSyncMessage({ t: 'seek', position: 5 })).toBe(true)
  })

  it('rejects bad or unknown tags', () => {
    expect(isSyncMessage(null)).toBe(false)
    expect(isSyncMessage({})).toBe(false)
    expect(isSyncMessage({ t: 'unknown', position: 0 })).toBe(false)
    expect(isSyncMessage({ t: 'state', playing: true })).toBe(false)
    expect(
      isSyncMessage({ t: 'state', playing: true, position: '0', at: 0 }),
    ).toBe(false)
  })
})

// ── Host ──

describe('createSyncHost', () => {
  it('broadcasts state on play and on pause', async () => {
    const c = new FakeController()
    const sent: SyncMessage[] = []
    const host = createSyncHost(
      c,
      (m) => sent.push(m),
      () => 0,
    )

    await c.play()
    c.pause()

    // 2 play/pause transitions → 2 broadcasts (heartbeat not yet fired).
    expect(sent.filter((m) => m.t === 'state')).toHaveLength(2)
    expect(sent[0]).toMatchObject({ t: 'state', playing: true })
    expect(sent[1]).toMatchObject({ t: 'state', playing: false })
    host.stop()
  })

  it('emits both a seek and a state message on user seek', async () => {
    const c = new FakeController()
    const sent: SyncMessage[] = []
    const host = createSyncHost(
      c,
      (m) => sent.push(m),
      () => 0,
    )
    await c.play()
    sent.length = 0 // reset noise from the play broadcast

    c.emitUserSeek(42)

    const seeks = sent.filter((m) => m.t === 'seek')
    const states = sent.filter((m) => m.t === 'state')
    expect(seeks).toHaveLength(1)
    expect(seeks[0]).toMatchObject({ t: 'seek', position: 42 })
    expect(states).toHaveLength(1)
    expect(states[0]).toMatchObject({ t: 'state', position: 42 })
    host.stop()
  })

  it('emits a heartbeat every HEARTBEAT_MS ms until stopped', () => {
    const c = new FakeController()
    const sent: SyncMessage[] = []
    const host = createSyncHost(
      c,
      (m) => sent.push(m),
      () => 0,
    )

    vi.advanceTimersByTime(HEARTBEAT_MS)
    expect(sent.filter((m) => m.t === 'state')).toHaveLength(1)
    vi.advanceTimersByTime(HEARTBEAT_MS * 2)
    expect(sent.filter((m) => m.t === 'state')).toHaveLength(3)

    host.stop()
    vi.advanceTimersByTime(HEARTBEAT_MS * 5)
    // No additional broadcasts after stop.
    expect(sent.filter((m) => m.t === 'state')).toHaveLength(3)
  })

  it('broadcastState is callable manually (e.g. on new guest)', () => {
    const c = new FakeController()
    const sent: SyncMessage[] = []
    const host = createSyncHost(
      c,
      (m) => sent.push(m),
      () => 0,
    )

    host.broadcastState()
    host.broadcastState()
    expect(sent.filter((m) => m.t === 'state')).toHaveLength(2)
    host.stop()
  })
})

// ── Guest ──

describe('createSyncGuest', () => {
  it('starts playback when host says playing', async () => {
    const c = new FakeController()
    const sent: SyncMessage[] = []
    const g = createSyncGuest(c, (m) => sent.push(m), { now: () => 0 })

    g.apply({ t: 'state', playing: true, position: 0, at: 0 })
    await Promise.resolve()
    expect(c.playing).toBe(true)
    g.stop()
  })

  it('pauses when host says not playing', async () => {
    const c = new FakeController()
    await c.play() // enter playing state first
    const g = createSyncGuest(c, () => {}, { now: () => 0 })

    g.apply({ t: 'state', playing: false, position: 3, at: 0 })
    expect(c.playing).toBe(false)
    g.stop()
  })

  it('issues a visible seek when drift is large', () => {
    const c = new FakeController()
    c.currentTime = 10
    const g = createSyncGuest(c, () => {}, { now: () => 1000 })

    // Host was at position 20 when it sent 'at=0'. At now=1000ms playing,
    // host has advanced ~1s in transit → ~21s now. Guest is at 10s → ~11s
    // drift → seek to the latency-compensated host position.
    g.apply({ t: 'state', playing: true, position: 20, at: 0 })
    expect(c.currentTime).toBeCloseTo(21, 1)
    g.stop()
  })

  it('nudges rate for small drift and resets afterwards', () => {
    const c = new FakeController()
    c.currentTime = 10.1 // 0.1 s ahead of host → slow down
    const g = createSyncGuest(c, () => {}, { now: () => 0 })

    g.apply({ t: 'state', playing: true, position: 10, at: 0 })
    expect(c.playbackRate).toBeCloseTo(1 - RATE_NUDGE_DELTA, 5)

    vi.advanceTimersByTime(500)
    expect(c.playbackRate).toBe(1)
    g.stop()
  })

  it('does nothing for drift below the rate threshold', () => {
    const c = new FakeController()
    c.currentTime = 10.02 // 20 ms ahead — below threshold
    const g = createSyncGuest(c, () => {}, { now: () => 0 })

    g.apply({ t: 'state', playing: true, position: 10, at: 0 })
    expect(c.playbackRate).toBe(1)
    // No seek either — currentTime unchanged.
    expect(c.currentTime).toBeCloseTo(10.02, 3)
    g.stop()
  })

  it("applies a 'seek' message immediately, short-circuiting drift math", () => {
    const c = new FakeController()
    c.currentTime = 0
    const g = createSyncGuest(c, () => {}, { now: () => 0 })

    g.apply({ t: 'seek', position: 42 })
    expect(c.currentTime).toBe(42)
    g.stop()
  })

  it("sends 'ready' when the media signals canplay", () => {
    const c = new FakeController()
    c.currentTime = 5
    const sent: SyncMessage[] = []
    const g = createSyncGuest(c, (m) => sent.push(m), { now: () => 0 })

    c.emitCanPlay()
    expect(sent).toContainEqual({ t: 'ready', position: 5 })
    g.stop()
  })

  it('ignores echoed ready messages', () => {
    const c = new FakeController()
    c.currentTime = 3
    const g = createSyncGuest(c, () => {}, { now: () => 0 })

    // Should not throw, should not affect playback.
    g.apply({ t: 'ready', position: 99 })
    expect(c.currentTime).toBe(3)
    expect(c.playing).toBe(false)
    g.stop()
  })

  it('compensates for latency when the host was playing', () => {
    const c = new FakeController()
    c.currentTime = 0.5 // guest clock slightly ahead
    const g = createSyncGuest(c, () => {}, { now: () => 500 })

    // Host was at position 0 at at=0ms. 500ms transit → host now ~0.5s.
    // Drift = 0.5 - 0.5 = 0 → no-op expected.
    g.apply({ t: 'state', playing: true, position: 0, at: 0 })
    expect(c.playbackRate).toBe(1)
    expect(c.currentTime).toBe(0.5)
    g.stop()
  })

  it('threshold exactly at DRIFT_SEEK_THRESHOLD triggers seek', () => {
    const c = new FakeController()
    c.currentTime = DRIFT_SEEK_THRESHOLD_S // exactly at threshold ahead
    const g = createSyncGuest(c, () => {}, { now: () => 0 })

    g.apply({ t: 'state', playing: false, position: 0, at: 0 })
    expect(c.currentTime).toBe(0)
    g.stop()
  })
})
