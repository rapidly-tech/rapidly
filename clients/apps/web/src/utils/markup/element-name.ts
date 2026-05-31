/**
 * Element naming — let users give any element a friendly name so the
 * outline panel and scene search can find it by what the user calls
 * it (``"Login screen"``) rather than what the canvas calls it
 * (``"Rectangle"``).
 *
 * This module is the single point that reads / writes ``name`` on a
 * generic element. Frames already carry a required ``name`` for
 * their label; for frames we treat that field as the same value (no
 * separate "name" stored in BaseElement.name when the frame's own
 * label already exists).
 *
 * Pure helpers — no DOM. The keyboard shortcut + command-palette
 * entries that drive renaming live in ``CollabWhiteboard.tsx``.
 */

import type { ElementStore } from './element-store'
import type { CollabElement } from './elements'
import { applyToSelection } from './properties'

/** Apply a name to every element in ``ids``. Empty / whitespace-only
 *  ``name`` clears the field on each target. Frames intentionally
 *  share their ``name`` slot (their built-in frame label) so renaming
 *  a frame from the outline behaves like renaming any other element. */
export function setName(
  store: ElementStore,
  ids: ReadonlySet<string>,
  name: string,
): void {
  if (ids.size === 0) return
  const trimmed = name.trim()
  // Build the patch lazily per type so a frame retains its label
  // semantics (``name: string``) while other elements use the
  // optional ``name?: string`` we added to ``BaseElement``.
  const patches: { id: string; patch: Record<string, unknown> }[] = []
  for (const id of ids) {
    const el = store.get(id)
    if (!el) continue
    if (el.type === 'frame') {
      // Frames keep an empty string when cleared (the field is
      // required) — the outline + search treat empty as "no name".
      patches.push({ id, patch: { name: trimmed } })
    } else {
      patches.push({
        id,
        patch: { name: trimmed.length > 0 ? trimmed : undefined },
      })
    }
  }
  if (patches.length === 0) return
  // Apply via the store's bulk-update so remote peers see one
  // transaction. ``applyToSelection`` emits a uniform patch, but
  // here each element gets its own (frame vs non-frame), so go
  // through ``updateMany`` directly.
  store.updateMany(patches)
}

/** Read the user-facing name for an element. Returns the explicit
 *  ``name`` when set, otherwise falls back to a humanised type
 *  label so callers always have something printable. */
export function displayName(el: CollabElement): string {
  // Frames carry a required ``name`` field; other types carry the
  // optional one we added to BaseElement.
  const explicit =
    el.type === 'frame'
      ? (el as { name: string }).name
      : ((el as { name?: string }).name ?? '')
  if (explicit && explicit.trim().length > 0) return explicit.trim()
  return typeFallback(el)
}

function typeFallback(el: CollabElement): string {
  switch (el.type) {
    case 'rect':
      return 'Rectangle'
    case 'ellipse':
      return 'Ellipse'
    case 'diamond':
      return 'Diamond'
    case 'arrow':
      return 'Arrow'
    case 'line':
      return 'Line'
    case 'freedraw':
      return 'Drawing'
    case 'text':
      return 'Text'
    case 'sticky':
      return 'Sticky note'
    case 'image':
      return 'Image'
    case 'frame':
      return 'Frame'
    case 'embed':
      return 'Embed'
    case 'pdf-underlay':
      return 'PDF underlay'
    case 'image-underlay':
      return 'Image underlay'
  }
}

// Keep ``applyToSelection`` import resolved — even though setName
// goes through ``updateMany`` directly, we re-export it so callers
// can pair other patches with a name change in a single round trip
// if they need to.
export { applyToSelection }
