/**
 * Swap stroke ↔ fill — flip the two colour fields on every selected
 * element in one transaction. Common Figma / Sketch shortcut for
 * inverting an outlined shape into a filled one (and back).
 *
 * Edge cases
 * ----------
 *   - When ``fillStyle`` is ``'none'`` (the canonical "no fill"
 *     state on rect / ellipse / diamond), swapping puts the element
 *     into a "stroke-becomes-fill, no stroke" state. We promote
 *     ``fillStyle`` to ``'solid'`` so the new fill actually paints.
 *   - When the swap leaves ``fillColor`` as ``'transparent'``, we
 *     clamp ``fillStyle`` to ``'none'`` so the renderer doesn't try
 *     to fill with transparent (cosmetically identical but keeps
 *     the data model consistent with the rest of the codebase).
 *   - Elements that don't carry one of the colour fields (rare —
 *     every base element has both) are skipped.
 */

import type { ElementStore } from './element-store'

export function swapStrokeAndFill(
  store: ElementStore,
  ids: ReadonlySet<string>,
): void {
  if (ids.size === 0) return
  const patches: { id: string; patch: Record<string, unknown> }[] = []
  for (const id of ids) {
    const el = store.get(id)
    if (!el) continue
    const stroke = el.strokeColor
    const fill = el.fillColor
    if (stroke === undefined || fill === undefined) continue
    const newStroke = fill
    const newFill = stroke
    // Promote / demote fillStyle so the colour we just moved into
    // it actually paints. Without this swap, an outlined-only shape
    // (fillStyle: 'none') would still look outlined-only after the
    // swap because the painter wouldn't draw the fill.
    let nextFillStyle: string | undefined
    if (newFill === 'transparent') {
      nextFillStyle = 'none'
    } else if (el.fillStyle === 'none') {
      nextFillStyle = 'solid'
    }
    const patch: Record<string, unknown> = {
      strokeColor: newStroke,
      fillColor: newFill,
    }
    if (nextFillStyle !== undefined) patch.fillStyle = nextFillStyle
    patches.push({ id, patch })
  }
  if (patches.length === 0) return
  store.updateMany(patches)
}
