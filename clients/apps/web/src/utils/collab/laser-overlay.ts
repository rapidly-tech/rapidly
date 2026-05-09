/**
 * Paints remote peers' laser trails on the interactive canvas.
 *
 * The trail itself lives on ``PresenceSource`` entries with sampled
 * timestamps. This painter walks each peer's trail newest-to-oldest,
 * drawing short line segments whose alpha falls off with age via
 * ``ageToAlpha``. A small solid dot at the head gives the pointer
 * itself; the line segments trailing behind are the ""laser"".
 *
 * Normalisation
 * -------------
 * Sample timestamps are ``performance.now()`` on the emitting client.
 * We don't attempt cross-clock sync — instead we compute age **relative
 * to the freshest point** in the trail, which is both the simplest
 * interpretation and also roughly correct because packets arrive close
 * in wall time. Older samples in the same trail fade relative to the
 * newest one.
 */

import { ageToAlpha } from './laser'
import type { PresenceSource, RemotePresence } from './presence'
import type { Viewport } from './viewport'

export interface LaserOverlayOptions {
  source: PresenceSource
  getViewport: () => Viewport
}

const HEAD_RADIUS_PX = 6
const LINE_WIDTH_PX = 4

/** Build an interactive paint fn that draws every peer's laser trail.
 *  Composes cheaply — returns immediately when no peer has a live
 *  trail. */
export function makeLaserOverlay(
  opts: LaserOverlayOptions,
): (ctx: CanvasRenderingContext2D) => void {
  return (ctx) => {
    const remotes = opts.source.getRemotes()
    if (remotes.length === 0) return
    const vp = opts.getViewport()
    ctx.save()
    for (const remote of remotes) paintOne(ctx, remote, vp)
    ctx.restore()
  }
}

function paintOne(
  ctx: CanvasRenderingContext2D,
  remote: RemotePresence,
  vp: Viewport,
): void {
  const trail = remote.laser
  if (!trail || trail.points.length === 0) return

  const s = 1 / vp.scale
  const headR = HEAD_RADIUS_PX * s
  const lineW = LINE_WIDTH_PX * s

  // Newest timestamp is the reference for ""now"" — accommodates
  // cross-device clock drift without a real sync.
  let newestT = -Infinity
  for (const p of trail.points) if (p.t > newestT) newestT = p.t

  ctx.save()
  ctx.strokeStyle = remote.user.color
  ctx.lineWidth = lineW
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'

  // Connected segments — each segment takes the alpha of its older
  // endpoint so the fade reads evenly across the trail.
  for (let i = 1; i < trail.points.length; i++) {
    const a = trail.points[i - 1]
    const b = trail.points[i]
    const age = newestT - a.t
    ctx.globalAlpha = ageToAlpha(age)
    ctx.beginPath()
    ctx.moveTo(a.x, a.y)
    ctx.lineTo(b.x, b.y)
    ctx.stroke()
  }

  // Head dot — filled circle in the peer's colour, fully opaque.
  const head = trail.points[trail.points.length - 1]
  ctx.globalAlpha = 1
  ctx.fillStyle = remote.user.color
  ctx.beginPath()
  ctx.arc(head.x, head.y, headR, 0, Math.PI * 2)
  ctx.fill()

  ctx.restore()
}
