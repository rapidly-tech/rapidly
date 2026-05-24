/**
 * Style clipboard — copy the visual styling from one element and
 * paste it onto any other selection.
 *
 * Mirrors the Figma / Sketch behaviour: ``Cmd+Alt+C`` captures
 * stroke / fill / corner / typography fields from the focused
 * element; ``Cmd+Alt+V`` applies the captured patch to every
 * currently-selected element via the existing ``applyToSelection``
 * pipeline so remote peers see one atomic update per paste.
 *
 * Why a separate module from the regular clipboard
 * ------------------------------------------------
 * The element clipboard (``clipboard.ts``) carries position +
 * geometry + a fresh id; pasting *creates a copy* of the source.
 * Style paste leaves the target's id and geometry alone — only
 * the visual fields are overwritten. Two different operations,
 * two different buffers.
 *
 * The buffer lives in a module-local variable; it isn't replicated
 * via Yjs because it's a local-UI concern (each peer keeps their
 * own clipboard).
 */

import type { ElementStore } from './element-store'
import type { CollabElement } from './elements'
import { applyToSelection } from './properties'

/** Subset of element fields a "style" carries. Position / size /
 *  rotation / id / type / version / seed are deliberately excluded. */
export interface ElementStyle {
  strokeColor?: string
  fillColor?: string
  fillStyle?: string
  strokeWidth?: number
  strokeStyle?: string
  roughness?: 0 | 1 | 2
  opacity?: number
  roundness?: number
  fontFamily?: string
  fontSize?: number
  textAlign?: string
  fontWeight?: 'normal' | 'bold'
  fontStyle?: 'normal' | 'italic'
  lineHeight?: number
  letterSpacing?: number
}

/** Field names captured by ``copyStyle`` — exported so tests + the
 *  panel can reason about which fields the operation touches. */
export const STYLE_FIELDS = [
  'strokeColor',
  'fillColor',
  'fillStyle',
  'strokeWidth',
  'strokeStyle',
  'roughness',
  'opacity',
  'roundness',
  'fontFamily',
  'fontSize',
  'textAlign',
  'fontWeight',
  'fontStyle',
  'lineHeight',
  'letterSpacing',
] as const satisfies readonly (keyof ElementStyle)[]

let buffer: ElementStyle | null = null

/** Read every supported style field from ``element`` into a fresh
 *  object. Fields the element doesn't carry are simply absent — the
 *  paste step skips them, leaving the target's existing value
 *  untouched (so copying a rect's style and pasting onto a text
 *  doesn't blank the text's font). */
export function copyStyle(element: CollabElement): ElementStyle {
  const style: Record<string, unknown> = {}
  for (const field of STYLE_FIELDS) {
    const value = (element as unknown as Record<string, unknown>)[field]
    if (value !== undefined) style[field] = value
  }
  buffer = style as ElementStyle
  return style as ElementStyle
}

/** Apply the captured style to every element in ``targetIds``. Skips
 *  silently when nothing has been copied yet so the keybinding is a
 *  no-op rather than an error. */
export function pasteStyle(
  store: ElementStore,
  targetIds: ReadonlySet<string>,
  style: ElementStyle | null = buffer,
): boolean {
  if (!style) return false
  if (targetIds.size === 0) return false
  // The buffer-derived patch may carry fields not present on every
  // target — applying ``fontSize`` to a rect is harmless because the
  // store ignores unknown field updates per its update contract.
  applyToSelection(store, targetIds, style as Record<string, unknown>)
  return true
}

/** Inspector hook used by tests + future UI surfaces ("paste style"
 *  button greys out when the buffer is empty). */
export function hasStyle(): boolean {
  return buffer !== null
}

/** Test seam — clears the module-local buffer so suites stay
 *  isolated. Production code never calls this. */
export function clearStyleBuffer(): void {
  buffer = null
}
