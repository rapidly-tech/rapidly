/**
 * Text shape adapter.
 *
 * Canvas-rendered text for the Collab v2 whiteboard. Phase 7a paints
 * the committed ``text`` field using ``ctx.fillText``; Phase 7b
 * swaps in a DOM contenteditable overlay for inline editing.
 *
 * The Path2D we return is the element's axis-aligned bounding rect,
 * kept as a single cheap rectangle for hit-testing + resize handles.
 * This does mean clicking in the "whitespace" of a multi-line text
 * element still selects it — a deliberate trade-off so users don't
 * have to land their click on a specific glyph.
 */

import type { FontFamily, TextElement } from '../elements'

/** ``font-family`` string passed to the canvas context. Handwritten
 *  maps to ``cursive`` until we ship Caveat via ``public/fonts``;
 *  sans/mono fall back to the system default. */
export function fontCssFor(family: FontFamily): string {
  switch (family) {
    case 'handwritten':
      return '"Caveat", "Comic Sans MS", cursive'
    case 'mono':
      return '"Cascadia Code", "Menlo", "Monaco", monospace'
    default:
      return 'system-ui, -apple-system, "Segoe UI", sans-serif'
  }
}

export function pathFor(el: TextElement): Path2D {
  const path = new Path2D()
  // Text hit-target = element AABB. Simple and matches how users
  // expect selecting text by clicking near it to work.
  path.rect(0, 0, Math.max(1, el.width), Math.max(1, el.height))
  return path
}

export function paintText(
  ctx: CanvasRenderingContext2D,
  el: TextElement,
  _path: Path2D,
): void {
  void _path
  ctx.save()
  ctx.globalAlpha = el.opacity / 100
  ctx.fillStyle = el.strokeColor
  ctx.textBaseline = 'top'
  ctx.textAlign = el.textAlign
  // Optional weight + style toggle on the per-element font field.
  // We don't carry per-character runs — that's a far larger
  // subsystem — so the whole element renders bold or italic.
  const weight = el.fontWeight === 'bold' ? '700 ' : ''
  const style = el.fontStyle === 'italic' ? 'italic ' : ''
  ctx.font = `${style}${weight}${el.fontSize}px ${fontCssFor(el.fontFamily)}`
  // Letter spacing is honoured when the browser supports it (Chromium
  // 99+, Firefox 117+). Older browsers silently ignore the property
  // — text just paints with default tracking.
  ;(ctx as unknown as { letterSpacing?: string }).letterSpacing = `${
    (el.letterSpacing ?? 0) * el.fontSize
  }px`

  const lines = el.text.split('\n')
  const lineHeight = el.fontSize * (el.lineHeight ?? 1.2)
  // textAlign is applied at draw-call time; we pick the anchor X
  // based on it so left-aligned text hugs the element's left edge,
  // right-aligned hugs the right, centre splits the middle.
  let anchorX = 0
  if (el.textAlign === 'center') anchorX = el.width / 2
  else if (el.textAlign === 'right') anchorX = el.width

  for (let i = 0; i < lines.length; i++) {
    ctx.fillText(lines[i], anchorX, i * lineHeight)
  }
  ctx.restore()
}

/** Measure the text + return the AABB needed to contain it at the
 *  given font size. Used by the text tool to size new elements and
 *  by the editor overlay (Phase 7b) to resize on Enter. The caller
 *  must supply a 2D context since text metrics depend on the browser's
 *  font renderer. */
export function measureText(
  ctx: CanvasRenderingContext2D,
  text: string,
  fontFamily: FontFamily,
  fontSize: number,
): { width: number; height: number } {
  ctx.save()
  ctx.font = `${fontSize}px ${fontCssFor(fontFamily)}`
  const lines = text.split('\n')
  let maxWidth = 0
  for (const line of lines) {
    // measureText returns subpixel width; round up so the AABB
    // contains the rendered glyphs comfortably.
    const w = Math.ceil(ctx.measureText(line).width)
    if (w > maxWidth) maxWidth = w
  }
  ctx.restore()
  const lineHeight = fontSize * 1.2
  return {
    width: Math.max(1, maxWidth),
    height: Math.max(1, lines.length * lineHeight),
  }
}
