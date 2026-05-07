/**
 * Select-same — expand the current selection to every element that
 * shares a given trait with the seed. Mirrors the Figma / Sketch
 * "Select Same…" submenu so users can bulk-restyle by colour, type,
 * or other shared properties without lassoing one shape at a time.
 *
 * Each helper returns the new selection as an array of ids — the
 * caller is responsible for handing it to ``SelectionState.set``
 * so the view + remote-selection broadcast stay coherent. Empty
 * input returns an empty result; when nothing matches the seed,
 * the returned array contains only the seed itself (callers can
 * collapse a no-op result into the original selection if they
 * want, but the conservative default is "you asked, here's what
 * we found").
 */

import type { ElementStore } from './element-store'
import type { CollabElement } from './elements'

/** Pick the first id in ``seedIds`` that resolves to an element in
 *  the store. Used as the "this is what you mean" anchor for every
 *  ``selectSame*`` helper — calling them with a multi-id selection
 *  is fine; the first valid entry wins. */
function seedElement(
  store: ElementStore,
  seedIds: ReadonlySet<string>,
): CollabElement | null {
  for (const id of seedIds) {
    const el = store.get(id)
    if (el) return el
  }
  return null
}

/** Every element that shares ``type`` with the seed. A rect seed
 *  yields every rect on the scene. */
export function selectSameType(
  store: ElementStore,
  seedIds: ReadonlySet<string>,
): string[] {
  const seed = seedElement(store, seedIds)
  if (!seed) return []
  const type = seed.type
  return store
    .list()
    .filter((el) => el.type === type)
    .map((el) => el.id)
}

/** Every element with the same ``strokeColor`` as the seed. */
export function selectSameStrokeColor(
  store: ElementStore,
  seedIds: ReadonlySet<string>,
): string[] {
  const seed = seedElement(store, seedIds)
  if (!seed) return []
  const stroke = seed.strokeColor
  return store
    .list()
    .filter((el) => el.strokeColor === stroke)
    .map((el) => el.id)
}

/** Every element with the same ``fillColor`` as the seed. */
export function selectSameFillColor(
  store: ElementStore,
  seedIds: ReadonlySet<string>,
): string[] {
  const seed = seedElement(store, seedIds)
  if (!seed) return []
  const fill = seed.fillColor
  return store
    .list()
    .filter((el) => el.fillColor === fill)
    .map((el) => el.id)
}

/** Every text / sticky element with the same ``fontFamily`` as the
 *  seed. Returns an empty array when the seed has no font (rect /
 *  ellipse / arrow / …) so the caller can show "no matches" rather
 *  than collapsing the selection to nothing useful. */
export function selectSameFontFamily(
  store: ElementStore,
  seedIds: ReadonlySet<string>,
): string[] {
  const seed = seedElement(store, seedIds)
  if (!seed) return []
  const font = (seed as { fontFamily?: string }).fontFamily
  if (!font) return []
  return store
    .list()
    .filter((el) => (el as { fontFamily?: string }).fontFamily === font)
    .map((el) => el.id)
}
