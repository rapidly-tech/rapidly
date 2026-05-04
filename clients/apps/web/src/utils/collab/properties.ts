/**
 * Property-panel helpers.
 *
 * A "shared" value is what the panel shows for a given field across
 * the current selection: if every selected element has the same
 * value, surface it; if any differ, surface ``'mixed'`` so the UI
 * can show an indeterminate state. Extracted as pure functions so
 * tests don't need a DOM.
 */

import type { ElementStore } from './element-store'
import type { BaseElement } from './elements'

/** Numeric or string value shared across the selection, or the
 *  special token ``'mixed'`` when any selected element differs. */
export type SharedValue<T> = T | 'mixed' | null

/** Read a field off every selected element in the store. Returns
 *  ``null`` when no selection, ``'mixed'`` when values differ, or
 *  the shared value. */
export function sharedField<K extends keyof BaseElement>(
  store: ElementStore,
  selected: ReadonlySet<string>,
  key: K,
): SharedValue<BaseElement[K]> {
  if (selected.size === 0) return null
  let out: BaseElement[K] | undefined
  let initialised = false
  for (const id of selected) {
    const el = store.get(id)
    if (!el) continue
    const v = el[key]
    if (!initialised) {
      out = v
      initialised = true
      continue
    }
    if (v !== out) return 'mixed'
  }
  return initialised ? (out as BaseElement[K]) : null
}

/** Apply a patch to every currently selected element in one
 *  transaction. The UI calls this on slider / picker change so remote
 *  peers see a single atomic update per interaction. */
export function applyToSelection(
  store: ElementStore,
  selected: ReadonlySet<string>,
  patch: Partial<BaseElement> & Record<string, unknown>,
): void {
  if (selected.size === 0) return
  const patches: { id: string; patch: typeof patch }[] = []
  for (const id of selected) {
    patches.push({ id, patch })
  }
  store.updateMany(patches)
}

/** Curated palettes shown in the panel swatches. Kept short so the
 *  panel stays compact; a future "more" sheet can expand. */
export const STROKE_PALETTE = [
  '#1e1e1e', // near-black
  '#e03131', // red
  '#2f9e44', // green
  '#1971c2', // blue
  '#f08c00', // amber
  '#9c36b5', // violet
] as const

export const FILL_PALETTE = [
  'transparent',
  '#ffc9c9', // pink
  '#b2f2bb', // mint
  '#a5d8ff', // sky
  '#ffec99', // butter
  '#e0a9f0', // lavender
] as const

export const STROKE_WIDTHS = [1, 2, 4] as const
export const ROUGHNESS_LEVELS = [0, 1, 2] as const

/** Stroke style options exposed in the panel — mirrors the
 *  ``StrokeStyle`` element field. Excalidraw parity. */
export const STROKE_STYLES = ['solid', 'dashed', 'dotted'] as const

/** Edge roundness presets in world units. ``0`` is a sharp corner;
 *  the larger values match Excalidraw's "round" preset for shapes
 *  that opt into corner rounding (rect, diamond). The picker is only
 *  meaningful for elements whose ``roundness`` field actually drives
 *  rendering — others ignore it. */
export const ROUNDNESS_PRESETS = [
  { id: 'sharp', label: 'Sharp', value: 0 },
  { id: 'round', label: 'Round', value: 16 },
] as const

/** Font family options for text + sticky elements. Mirrors the
 *  ``FontFamily`` element field; the labels match what we render so
 *  the picker is its own legend. */
export const FONT_FAMILIES = [
  { id: 'handwritten', label: 'Hand', sample: 'Aa' },
  { id: 'sans', label: 'Sans', sample: 'Aa' },
  { id: 'mono', label: 'Mono', sample: 'Aa' },
] as const

/** Discrete font-size presets. Excalidraw uses S/M/L/XL with concrete
 *  pixel values; we keep the same four steps so users coming from
 *  Excalidraw don't hit a continuous slider where they expect tiers. */
export const FONT_SIZES = [
  { id: 's', label: 'S', value: 16 },
  { id: 'm', label: 'M', value: 20 },
  { id: 'l', label: 'L', value: 28 },
  { id: 'xl', label: 'XL', value: 36 },
] as const

/** Horizontal text alignment options. */
export const TEXT_ALIGNMENTS = [
  { id: 'left', label: '⟸', aria: 'Align text left' },
  { id: 'center', label: '⇔', aria: 'Align text center' },
  { id: 'right', label: '⟹', aria: 'Align text right' },
] as const
