/**
 * Watch chamber — playback synchronisation protocol (PR 10).
 *
 * The host is the authoritative clock. It broadcasts its playback state
 * (``playing``, ``position``, ``at``) to every connected guest on change
 * and on a periodic heartbeat. Guests reconcile against their local
 * playback clock within a tolerance window.
 *
 * The protocol is three small JSON messages sent on the existing
 * ``PeerDataConnection``. No new wire format, no server involvement —
 * everything is host → guest or guest → host, peer-to-peer.
 *
 *   - ``state``  host → guest, playing + position + host-timestamp
 *   - ``ready``  guest → host, guest has buffered up to ``position``
 *   - ``seek``   host → guest, immediate seek command
 *
 * DOM dependencies are abstracted behind ``SyncMediaController`` so
 * this module is unit-testable without jsdom or a real <video>.
 */

// ── Tunables ──

/** Heartbeat interval (ms) — the host resends ``state`` even when nothing
 *  visibly changed so a late-joining guest converges quickly and slow
 *  drift stays bounded. */
export const HEARTBEAT_MS = 2000

/** Max drift (seconds) tolerated before the guest issues a visible seek. */
export const DRIFT_SEEK_THRESHOLD_S = 0.5

/** Target drift (seconds) the guest aims at via small rate nudges before
 *  falling back to a seek. Nothing visibly jumps for drifts below this. */
export const DRIFT_RATE_THRESHOLD_S = 0.05

/** Playback rate used while nudging. 1 ±0.05 = perceptible but not jarring. */
export const RATE_NUDGE_DELTA = 0.05

// ── Message types ──

export interface StateMessage {
  t: 'state'
  /** Whether the host is currently in a playing state. */
  playing: boolean
  /** Host-clock position in the media, in seconds. */
  position: number
  /** Host ``performance.now()`` at send time, in ms. Guests use it to
   *  compensate for transit latency before comparing to their own clock. */
  at: number
}

export interface ReadyMessage {
  t: 'ready'
  /** Guest is buffered up to this position (seconds). */
  position: number
}

export interface SeekMessage {
  t: 'seek'
  /** Target position in seconds. */
  position: number
}

export type SyncMessage = StateMessage | ReadyMessage | SeekMessage

/** Runtime narrower — a raw ``unknown`` from the DC is a SyncMessage when
 *  it has one of the three literal ``t`` values and the expected shape. */
export function isSyncMessage(x: unknown): x is SyncMessage {
  if (!x || typeof x !== 'object') return false
  const obj = x as Record<string, unknown>
  if (obj.t === 'state') {
    return (
      typeof obj.playing === 'boolean' &&
      typeof obj.position === 'number' &&
      typeof obj.at === 'number'
    )
  }
  if (obj.t === 'ready' || obj.t === 'seek') {
    return typeof obj.position === 'number'
  }
  return false
}

// ── Media controller abstraction ──

/** Minimal interface the sync engines call into. Hooking a real <video>
 *  element is a separate concern (PR 11); tests pass a hand-rolled fake. */
export interface SyncMediaController {
  /** Whether the media is currently playing. */
  readonly playing: boolean
  /** Current playback position in seconds. */
  readonly currentTime: number
  /** Start playback. May reject if the browser blocks autoplay. */
  play(): Promise<void>
  /** Pause playback. */
  pause(): void
  /** Jump to ``time`` seconds. */
  seek(time: number): void
  /** Set the playback rate (1 = normal). Used only for small drift
   *  corrections; guest falls back to ``seek`` for large drifts. */
  setPlaybackRate(rate: number): void
  /** Subscribe to play/pause transitions. Returns an unsubscribe fn. */
  onPlayOrPause(cb: (playing: boolean) => void): () => void
  /** Subscribe to explicit seeks issued by the local user (not by us). */
  onSeek(cb: (time: number) => void): () => void
  /** Subscribe to ``canplay`` — media is buffered enough to resume. */
  onCanPlay(cb: () => void): () => void
}

// ── Send abstraction ──

/** Host and guest both get a generic ``send`` of a typed message. Paired
 *  with the DataChannel in production; paired with a collector array in
 *  tests. Using the narrow signature means neither half of this module
 *  has a direct import of PeerDataConnection. */
export type Send = (msg: SyncMessage) => void

// ── Host ──

export interface SyncHost {
  /** Stop the heartbeat and unsubscribe from controller events. */
  stop(): void
  /** Force-broadcast the current state immediately (e.g. on new guest). */
  broadcastState(): void
}

/** Create the host-side orchestrator. The host broadcasts ``state``
 *  messages whenever play/pause/seek happens and every ``HEARTBEAT_MS``
 *  ms otherwise. */
export function createSyncHost(
  controller: SyncMediaController,
  send: Send,
  now: () => number = () => performance.now(),
): SyncHost {
  function broadcastState(): void {
    send({
      t: 'state',
      playing: controller.playing,
      position: controller.currentTime,
      at: now(),
    })
  }

  const unsubs: Array<() => void> = []
  unsubs.push(controller.onPlayOrPause(() => broadcastState()))
  unsubs.push(
    controller.onSeek((position) => {
      // Distinct ``seek`` message lets the guest short-circuit drift
      // correction and jump immediately rather than treating it as a
      // (playing=X, position=Y) state change that might be within the
      // drift tolerance window.
      send({ t: 'seek', position })
      broadcastState()
    }),
  )

  const timer = setInterval(broadcastState, HEARTBEAT_MS)

  return {
    stop(): void {
      clearInterval(timer)
      for (const u of unsubs) u()
    },
    broadcastState,
  }
}

// ── Guest ──

export interface SyncGuest {
  /** Apply an incoming message from the host. */
  apply(msg: SyncMessage): void
  /** Stop the ready-on-canplay listener and clear any pending rate nudge. */
  stop(): void
}

export interface CreateSyncGuestOptions {
  now?: () => number
  /** Injected for test determinism — replaces global setTimeout. */
  setTimer?: (fn: () => void, ms: number) => unknown
  /** Injected for test determinism — replaces global clearTimeout. */
  clearTimer?: (handle: unknown) => void
}

export function createSyncGuest(
  controller: SyncMediaController,
  send: Send,
  opts: CreateSyncGuestOptions = {},
): SyncGuest {
  const now = opts.now ?? (() => performance.now())
  const setTimer = opts.setTimer ?? ((fn, ms) => setTimeout(fn, ms))
  const clearTimer = opts.clearTimer ?? ((h) => clearTimeout(h as number))

  let rateResetHandle: unknown = null

  function scheduleRateReset(): void {
    if (rateResetHandle !== null) clearTimer(rateResetHandle)
    rateResetHandle = setTimer(() => {
      controller.setPlaybackRate(1)
      rateResetHandle = null
    }, 500)
  }

  const unsub = controller.onCanPlay(() => {
    send({ t: 'ready', position: controller.currentTime })
  })

  function apply(msg: SyncMessage): void {
    if (msg.t === 'seek') {
      controller.seek(msg.position)
      return
    }
    if (msg.t === 'ready') {
      // ``ready`` is a guest → host message; if another implementation
      // echoes it to us, ignore.
      return
    }

    // state message — reconcile play/pause and position.
    if (msg.playing && !controller.playing) {
      void controller.play()
    } else if (!msg.playing && controller.playing) {
      controller.pause()
    }

    // Latency compensation: estimate what the host's position would be
    // "now" from our perspective. If the host was playing, the position
    // advanced by (now - msg.at)/1000 seconds in transit. Paused states
    // are compared as-is.
    const elapsedSincePacket = msg.playing ? (now() - msg.at) / 1000 : 0
    const hostPositionNow = msg.position + elapsedSincePacket
    const drift = controller.currentTime - hostPositionNow

    if (Math.abs(drift) >= DRIFT_SEEK_THRESHOLD_S) {
      // Large drift — visible seek. Cheaper than waiting seconds of
      // subtle rate correction.
      controller.seek(hostPositionNow)
    } else if (Math.abs(drift) >= DRIFT_RATE_THRESHOLD_S) {
      // Subtle drift — nudge rate and reset after a beat.
      const rate = drift > 0 ? 1 - RATE_NUDGE_DELTA : 1 + RATE_NUDGE_DELTA
      controller.setPlaybackRate(rate)
      scheduleRateReset()
    }
    // else: within target; do nothing.
  }

  return {
    apply,
    stop(): void {
      unsub()
      if (rateResetHandle !== null) clearTimer(rateResetHandle)
      rateResetHandle = null
    },
  }
}
