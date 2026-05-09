/**
 * Embed shape adapter — paints a placeholder for ``EmbedElement``.
 *
 * The actual sandboxed iframe lives in a DOM overlay layer (Phase 19
 * follow-up); the canvas just shows a placeholder rectangle with the
 * URL preview so the element is selectable, movable, and visible at
 * any zoom — the iframe overlay can mount on top of this without
 * interfering with the canvas hit-test.
 *
 * Visual: rounded outline + a small "embed" badge in the top-left
 * + the URL hostname centred — enough to read as a placeholder for
 * the iframe that the DOM overlay paints over the top.
 */

import type { EmbedElement } from '../elements'

export function pathFor(el: EmbedElement): Path2D {
  const path = new Path2D()
  const r = Math.min(8, Math.min(el.width, el.height) / 2)
  // Rounded-rect path so the placeholder reads as a contained block.
  path.moveTo(r, 0)
  path.lineTo(el.width - r, 0)
  path.quadraticCurveTo(el.width, 0, el.width, r)
  path.lineTo(el.width, el.height - r)
  path.quadraticCurveTo(el.width, el.height, el.width - r, el.height)
  path.lineTo(r, el.height)
  path.quadraticCurveTo(0, el.height, 0, el.height - r)
  path.lineTo(0, r)
  path.quadraticCurveTo(0, 0, r, 0)
  path.closePath()
  return path
}

const BADGE_HEIGHT = 18
const BADGE_PADDING = 6
const BADGE_FONT = '11px Cascadia, Menlo, monospace'

export function paintEmbed(
  ctx: CanvasRenderingContext2D,
  el: EmbedElement,
  path: Path2D,
): void {
  ctx.save()
  ctx.globalAlpha = el.opacity / 100

  // Background fill so the placeholder reads as a block, not as
  // ""nothing"". Soft slate tint that survives any underlying canvas
  // colour.
  ctx.fillStyle = el.fillColor === 'transparent' ? '#e2e8f0' : el.fillColor
  ctx.fill(path)

  ctx.strokeStyle = el.strokeColor
  ctx.lineWidth = el.strokeWidth
  ctx.setLineDash([])
  ctx.stroke(path)

  // ""embed"" badge.
  ctx.font = BADGE_FONT
  const label = 'embed'
  const labelW = ctx.measureText(label).width + BADGE_PADDING * 2
  ctx.globalAlpha = (el.opacity / 100) * 0.85
  ctx.fillStyle = el.strokeColor
  ctx.fillRect(0, 0, labelW, BADGE_HEIGHT)
  ctx.globalAlpha = el.opacity / 100
  ctx.fillStyle = '#ffffff'
  ctx.textBaseline = 'middle'
  ctx.textAlign = 'left'
  ctx.fillText(label, BADGE_PADDING, BADGE_HEIGHT / 2)

  // URL hostname centred, truncated when too long.
  let hostname = el.url
  try {
    hostname = new URL(el.url).hostname
  } catch {
    /* keep raw — defensive only */
  }
  ctx.fillStyle = el.strokeColor
  ctx.textBaseline = 'middle'
  ctx.textAlign = 'center'
  ctx.font = `13px Cascadia, Menlo, monospace`
  ctx.fillText(hostname, el.width / 2, el.height / 2, el.width - 24)

  ctx.restore()
}
