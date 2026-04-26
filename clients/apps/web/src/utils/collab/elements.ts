/**
 * Element model for the Collab v2 whiteboard.
 *
 * The old ``strokes.ts`` model had a single ``Stroke`` type — fine for a
 * freehand-only demo, not enough for the full whiteboard we're building
 * in ``COLLAB_WHITEBOARD_PLAN.md``. This file owns the shared shape of
 * every element the whiteboard can hold: rect, ellipse, diamond, arrow,
 * line, freedraw, text, sticky, image, frame, embed.
 *
 * Design decisions captured in the plan:
 *   - Shared state lives in a Yjs ``Y.Map<id, Y.Map<field, value>>``
 *     keyed by element id (O(1) lookup; no index fights on concurrent
 *     reorder). The helpers in ``element-store.ts`` enforce that
 *     invariant at the API boundary.
 *   - Selection, active tool, viewport, and every other piece of local
 *     UI state live outside the Yjs doc. Only element content is
 *     replicated.
 *   - Coordinates are **world coordinates** — never pre-transformed.
 *     The renderer applies the viewport; cursors in Awareness also use
 *     world coords so remote peers can reproject to their own viewport.
 */

export type ElementType =
  | 'rect'
  | 'ellipse'
  | 'diamond'
  | 'arrow'
  | 'line'
  | 'freedraw'
  | 'text'
  | 'sticky'
  | 'image'
  | 'frame'
  | 'embed'

export type FillStyle = 'solid' | 'hatch' | 'cross-hatch' | 'dots' | 'none'
export type StrokeStyle = 'solid' | 'dashed' | 'dotted'
export type Roughness = 0 | 1 | 2
export type ArrowHead = 'triangle' | 'dot' | 'bar' | null
export type TextAlign = 'left' | 'center' | 'right'
export type FontFamily = 'handwritten' | 'sans' | 'mono'

/** Fields every element carries. Kept identical across the union so the
 *  generic bits of the renderer + tool system don't need discriminated-
 *  union narrowing for position/size/style. Per-type extensions hang
 *  off the discriminant below. */
export interface BaseElement {
  id: string
  type: ElementType
  /** World-space top-left corner, pre-rotation. */
  x: number
  y: number
  /** Pre-rotation dimensions. */
  width: number
  height: number
  /** Radians, rotation around the element's centre. */
  angle: number
  /** Higher = painted later = on top. Ties broken by ``id`` during render. */
  zIndex: number
  /** Innermost-first ancestor chain. Empty = not in any group. */
  groupIds: string[]
  strokeColor: string
  fillColor: string
  fillStyle: FillStyle
  strokeWidth: number
  strokeStyle: StrokeStyle
  roughness: Roughness
  /** 0..100 — avoids the 0..1 confusion vs CSS alpha. */
  opacity: number
  /** Stable seed for the rough-style renderer so the same element
   *  looks the same every paint. Assigned once at creation. */
  seed: number
  /** Bumps on every local edit. Used by the Path2D cache key. */
  version: number
  locked: boolean
  /** Optional URL; empty means no link. */
  link?: string
  /** Rect / diamond / ellipse can own a text child — this is its id. */
  boundTextId?: string
}

export interface RectElement extends BaseElement {
  type: 'rect'
  /** Corner radius in world pixels. 0 = square corners. */
  roundness: number
}

export interface EllipseElement extends BaseElement {
  type: 'ellipse'
}

export interface DiamondElement extends BaseElement {
  type: 'diamond'
  /** Corner rounding at the four points. */
  roundness: number
}

export interface ArrowBinding {
  elementId: string
  /** 0..1 parametric position along the target's perimeter. */
  focus: number
  /** Pixel offset away from the target's border. */
  gap: number
}

export interface ArrowElement extends BaseElement {
  type: 'arrow'
  /** Element-local polyline: [x0,y0,x1,y1,...]. */
  points: number[]
  startBinding?: ArrowBinding
  endBinding?: ArrowBinding
  startArrowhead?: ArrowHead
  endArrowhead?: ArrowHead
}

export interface LineElement extends BaseElement {
  type: 'line'
  points: number[]
}

export interface FreeDrawElement extends BaseElement {
  type: 'freedraw'
  /** Element-local: [x0,y0,pressure0, x1,y1,pressure1, ...].
   *  ``pressure`` is 0..1; if the device didn't report it, we
   *  simulate velocity-based pressure and store it here so the
   *  element paints identically for every peer. */
  points: number[]
  simulatePressure: boolean
}

export interface TextElement extends BaseElement {
  type: 'text'
  text: string
  fontFamily: FontFamily
  fontSize: number
  textAlign: TextAlign
  /** If this text is bound to a parent shape, the parent's id. */
  containerId?: string
}

export interface StickyElement extends BaseElement {
  type: 'sticky'
  text: string
  fontFamily: FontFamily
  fontSize: number
  textAlign: TextAlign
}

export interface ImageElement extends BaseElement {
  type: 'image'
  /** Base64 data URL of a compressed thumbnail (≤ ~30 KB) — must fit
   *  the 64 KB signaling envelope even after Yjs encoding. */
  thumbnailDataUrl: string
  /** Content hash of the full-resolution asset in the Collab asset
   *  service; undefined while an upload is in-flight. */
  assetHash?: string
  mimeType: string
  naturalWidth: number
  naturalHeight: number
}

export interface FrameElement extends BaseElement {
  type: 'frame'
  name: string
  /** Children are the authoritative ownership record. Elements outside
   *  this array but inside the frame's bounds are NOT considered children
   *  (makes drag-in/drag-out an explicit action, not a render-time test). */
  childIds: string[]
}

export interface EmbedElement extends BaseElement {
  type: 'embed'
  /** URL must pass the allowlist check at render time. */
  url: string
  /** Sandbox attributes for the <iframe> — never include
   *  ``allow-same-origin`` unless the host is on a trusted list. */
  sandbox: string
}

export type CollabElement =
  | RectElement
  | EllipseElement
  | DiamondElement
  | ArrowElement
  | LineElement
  | FreeDrawElement
  | TextElement
  | StickyElement
  | ImageElement
  | FrameElement
  | EmbedElement

/** The subset of fields that every element type exposes. Useful for the
 *  generic ``move / resize / setStyle`` operations that don't care about
 *  the discriminant. */
export type CommonElement = Pick<BaseElement, keyof BaseElement>

// ── Defaults ──────────────────────────────────────────────────────────

/** Visual defaults — chosen to match Excalidraw's muted light palette
 *  without copying any specific colour values. */
export const DEFAULT_STROKE_COLOR = '#1e1e1e'
export const DEFAULT_FILL_COLOR = 'transparent'
export const DEFAULT_STROKE_WIDTH = 2
export const DEFAULT_OPACITY = 100
export const DEFAULT_ROUGHNESS: Roughness = 1
export const DEFAULT_FILL_STYLE: FillStyle = 'none'
export const DEFAULT_STROKE_STYLE: StrokeStyle = 'solid'
export const DEFAULT_FONT_FAMILY: FontFamily = 'handwritten'
export const DEFAULT_FONT_SIZE = 20
export const DEFAULT_TEXT_ALIGN: TextAlign = 'left'

// ── Type guards ───────────────────────────────────────────────────────

/** Runtime narrowing — the Yjs Y.Map can hold arbitrary bytes from any
 *  peer, so every read from the shared doc goes through a guard before
 *  it hits the typed layer. */
export function isCollabElement(x: unknown): x is CollabElement {
  if (!x || typeof x !== 'object') return false
  const el = x as Record<string, unknown>
  if (typeof el.id !== 'string' || el.id.length === 0) return false
  if (typeof el.type !== 'string') return false
  const type = el.type as ElementType
  const validTypes: readonly ElementType[] = [
    'rect',
    'ellipse',
    'diamond',
    'arrow',
    'line',
    'freedraw',
    'text',
    'sticky',
    'image',
    'frame',
    'embed',
  ]
  if (!validTypes.includes(type)) return false
  // Numeric fields every element carries
  for (const k of [
    'x',
    'y',
    'width',
    'height',
    'angle',
    'zIndex',
    'strokeWidth',
    'opacity',
    'seed',
    'version',
  ] as const) {
    if (typeof el[k] !== 'number' || !Number.isFinite(el[k] as number)) {
      return false
    }
  }
  if (typeof el.locked !== 'boolean') return false
  if (!Array.isArray(el.groupIds)) return false
  if (!(el.groupIds as unknown[]).every((g) => typeof g === 'string')) {
    return false
  }
  return true
}

export function isRect(el: CollabElement): el is RectElement {
  return el.type === 'rect'
}
export function isEllipse(el: CollabElement): el is EllipseElement {
  return el.type === 'ellipse'
}
export function isDiamond(el: CollabElement): el is DiamondElement {
  return el.type === 'diamond'
}
export function isArrow(el: CollabElement): el is ArrowElement {
  return el.type === 'arrow'
}
export function isLine(el: CollabElement): el is LineElement {
  return el.type === 'line'
}
export function isFreeDraw(el: CollabElement): el is FreeDrawElement {
  return el.type === 'freedraw'
}
export function isText(el: CollabElement): el is TextElement {
  return el.type === 'text'
}
export function isSticky(el: CollabElement): el is StickyElement {
  return el.type === 'sticky'
}
export function isImage(el: CollabElement): el is ImageElement {
  return el.type === 'image'
}
export function isFrame(el: CollabElement): el is FrameElement {
  return el.type === 'frame'
}
export function isEmbed(el: CollabElement): el is EmbedElement {
  return el.type === 'embed'
}

// ── Sort order for painting ───────────────────────────────────────────

/** Sort comparator used by the renderer. zIndex first, then id for a
 *  stable tiebreak when two concurrent peers assign the same zIndex. */
export function paintOrder(a: CollabElement, b: CollabElement): number {
  if (a.zIndex !== b.zIndex) return a.zIndex - b.zIndex
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0
}
