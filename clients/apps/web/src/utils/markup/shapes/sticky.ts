/**
 * Sticky note shape adapter.
 *
 * A sticky is a rect + baked-in text as a single element — you move
 * the note, the text moves with it, no boundTextId coupling. The
 * paint path draws the rounded rect background first, then the
 * text wrapped by centre-alignment inside the note's bounds.
 */

import type { FontFamily, StickyElement, TextAlign } from '../elements'
import { fontCssFor } from './text'

/** Background path — a soft-cornered rect. The same path is used for
 *  hit-testing so clicking anywhere inside the note selects it. */
export function pathFor(el: StickyElement): Path2D {
  const path = new Path2D()
  const { width, height } = el
  const r = Math.min(8, Math.min(width, height) / 2)

  path.moveTo(r, 0)
  path.lineTo(width - r, 0)
  path.quadraticCurveTo(width, 0, width, r)
  path.lineTo(width, height - r)
  path.quadraticCurveTo(width, height, width - r, height)
  path.lineTo(r, height)
  path.quadraticCurveTo(0, height, 0, height - r)
  path.lineTo(0, r)
  path.quadraticCurveTo(0, 0, r, 0)
  path.closePath()
  return path
}

export function paintSticky(
  ctx: CanvasRenderingContext2D,
  el: StickyElement,
  path: Path2D,
): void {
  ctx.save()
  ctx.globalAlpha = el.opacity / 100

  // Background.
  ctx.fillStyle = el.fillColor === 'transparent' ? '#fef3c7' : el.fillColor
  ctx.fill(path)
  // A thin border so the note reads as an object, not a colour blob.
  ctx.strokeStyle = el.strokeColor
  ctx.lineWidth = el.strokeWidth
  ctx.setLineDash([])
  ctx.stroke(path)

  // Text. The padding keeps glyphs off the rounded corners.
  const padding = 12
  ctx.fillStyle = el.strokeColor
  ctx.textBaseline = 'top'
  ctx.textAlign = (el.textAlign ?? 'left') as TextAlign
  const weight = el.fontWeight === 'bold' ? '700 ' : ''
  const style = el.fontStyle === 'italic' ? 'italic ' : ''
  ctx.font = `${style}${weight}${el.fontSize}px ${fontCssFor(el.fontFamily as FontFamily)}`
  ;(ctx as unknown as { letterSpacing?: string }).letterSpacing = `${
    (el.letterSpacing ?? 0) * el.fontSize
  }px`
  const maxWidth = el.width - padding * 2
  const lineHeight = el.fontSize * (el.lineHeight ?? 1.25)

  let anchorX = padding
  if (ctx.textAlign === 'center') anchorX = el.width / 2
  else if (ctx.textAlign === 'right') anchorX = el.width - padding

  const lines = wrapLines(ctx, el.text, maxWidth)
  for (let i = 0; i < lines.length; i++) {
    const y = padding + i * lineHeight
    if (y + lineHeight > el.height) break
    ctx.fillText(lines[i], anchorX, y)
  }
  ctx.restore()
}

/** Word-wrap ``text`` into lines that fit ``maxWidth`` pixels given
 *  the context's current ``font``. Split on ``\n`` first, then on
 *  whitespace when a line overflows. A token longer than
 *  ``maxWidth`` stays on its own line rather than being chopped
 *  mid-word — long unbreakable tokens stay readable rather than
 *  being chopped at an arbitrary character. */
function wrapLines(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
): string[] {
  const out: string[] = []
  const paragraphs = text.split('\n')
  for (const para of paragraphs) {
    if (para.length === 0) {
      out.push('')
      continue
    }
    const words = para.split(/(\s+)/)
    let line = ''
    for (const word of words) {
      const candidate = line + word
      if (ctx.measureText(candidate).width <= maxWidth || line === '') {
        line = candidate
      } else {
        out.push(line.trimEnd())
        line = word.trimStart()
      }
    }
    if (line.length > 0) out.push(line.trimEnd())
  }
  return out
}
