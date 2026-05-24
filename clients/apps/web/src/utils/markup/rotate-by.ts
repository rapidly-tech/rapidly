/**
 * Bulk rotation by an angle delta — quick-action helpers for the
 * "Rotate 90° CW / CCW" command-palette entries.
 *
 * The rotation is per-element around each element's own centre
 * (matches the Figma behaviour for ``Selection › Rotate 90°``):
 * each element keeps its position; only its ``angle`` changes.
 * The renderer applies ``angle`` as a centre rotation at paint
 * time so the geometry update stays a one-field write — no
 * point-mirroring needed for lines / arrows / freedraw.
 *
 * Locked elements are skipped so a stray rotate doesn't disturb
 * pinned layout shapes.
 */

import type { ElementStore } from './element-store'

const TWO_PI = Math.PI * 2

/** Add ``deltaRad`` to ``angle`` on every unlocked element in
 *  ``ids``. The result is wrapped into ``[0, 2π)`` so the field
 *  doesn't drift to absurd values after many rotations. Empty
 *  selection / locked-only selection / ghost ids → no-op. */
export function rotateBy(
  store: ElementStore,
  ids: ReadonlySet<string>,
  deltaRad: number,
): void {
  if (ids.size === 0) return
  if (!Number.isFinite(deltaRad)) return
  const patches: { id: string; patch: Record<string, unknown> }[] = []
  for (const id of ids) {
    const el = store.get(id)
    if (!el) continue
    if (el.locked) continue
    let next = (el.angle ?? 0) + deltaRad
    // Wrap into [0, 2π). The renderer doesn't care, but the
    // properties-panel rotation input + collab snapshots stay
    // tidy this way.
    next = ((next % TWO_PI) + TWO_PI) % TWO_PI
    patches.push({ id, patch: { angle: next } })
  }
  if (patches.length === 0) return
  store.updateMany(patches)
}

/** Quarter-turn clockwise. */
export function rotate90Clockwise(
  store: ElementStore,
  ids: ReadonlySet<string>,
): void {
  rotateBy(store, ids, Math.PI / 2)
}

/** Quarter-turn counter-clockwise. */
export function rotate90CounterClockwise(
  store: ElementStore,
  ids: ReadonlySet<string>,
): void {
  rotateBy(store, ids, -Math.PI / 2)
}
