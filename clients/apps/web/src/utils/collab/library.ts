/**
 * Local-only template library for the Collab whiteboard.
 *
 * The user can save the current selection as a named template and
 * later insert it back into any whiteboard. Storage is plain
 * ``localStorage`` per-browser per-origin — there is no server, no
 * sync, no public hosting. Each template is a frozen snapshot of
 * the elements as they were at save time, normalised so the top-
 * left of the selection's bounding box is at (0, 0). Inserts replay
 * the snapshot at a target position with fresh ids.
 *
 * Why local-only: keeps the feature simple and respects the
 * clean-room policy — no third-party storage hooks, no public
 * library service. Users who want cross-device sync can export
 * their templates as JSON and re-import elsewhere using the
 * existing scene import.
 *
 * Schema: a ``LibraryDocument`` is the array of templates; the
 * envelope carries a ``schema`` marker so a future migration can
 * recognise stale data and refuse to consume it.
 */

import type { ElementStore } from './element-store'
import { importScene } from './import-json'

export const LIBRARY_STORAGE_KEY = 'rapidly:collab:library'
const SCHEMA = 'rapidly-collab-library-v1'

export interface LibraryTemplate {
  id: string
  name: string
  /** Wall-clock save time (ms since epoch). Used for sort + display. */
  createdAt: number
  /** Bounding-box dimensions of the saved snapshot, useful for the
   *  picker thumbnail layout. */
  width: number
  height: number
  /** Fully-serialised elements in template-local coordinates: the
   *  selection's top-left has been normalised to (0, 0) so insert
   *  can offset by any target position cleanly. Each element keeps
   *  its full property bag (style, roughness, seed, etc.). */
  elements: Array<Record<string, unknown>>
}

interface LibraryDocument {
  schema: typeof SCHEMA
  templates: LibraryTemplate[]
}

/** Read the current library from local storage. Returns an empty
 *  list when no library exists, when the data is corrupt, or when
 *  the schema marker doesn't match — the safer default than throwing
 *  is "behave as though the library was empty" so a wedged template
 *  list never blocks the editor from loading. */
export function listTemplates(
  storage: Storage = defaultStorage(),
): LibraryTemplate[] {
  const raw = safeRead(storage)
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw) as LibraryDocument
    if (
      typeof parsed !== 'object' ||
      parsed === null ||
      parsed.schema !== SCHEMA ||
      !Array.isArray(parsed.templates)
    ) {
      return []
    }
    return parsed.templates
  } catch {
    return []
  }
}

/** Persist a new template made from the given elements. Caller passes
 *  the *resolved* elements (already pulled from the store) so this
 *  module stays decoupled from store internals. Normalises positions
 *  so the snapshot's top-left lives at (0, 0). Returns the saved
 *  template (with assigned id + timestamp). */
export function saveTemplate(
  name: string,
  elements: ReadonlyArray<{
    x: number
    y: number
    width: number
    height: number
    [k: string]: unknown
  }>,
  storage: Storage = defaultStorage(),
): LibraryTemplate | null {
  const trimmed = name.trim()
  if (!trimmed || elements.length === 0) return null

  // Normalise so the saved coords are template-local. Compute the
  // selection's union AABB and translate every element by (-minX,
  // -minY) so the top-left lands at (0, 0). The width/height of the
  // template is the full AABB extent so the inserter knows what to
  // expect.
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const el of elements) {
    if (el.x < minX) minX = el.x
    if (el.y < minY) minY = el.y
    if (el.x + el.width > maxX) maxX = el.x + el.width
    if (el.y + el.height > maxY) maxY = el.y + el.height
  }
  if (!Number.isFinite(minX)) return null
  const width = maxX - minX
  const height = maxY - minY

  // Strip ids — inserts always mint fresh ones — but keep everything
  // else (style, seed, roughness, points, …). The seed in particular
  // is what makes a hand-drawn shape paint the same way on every
  // re-insert; preserving it is intentional.
  const localElements = elements.map((el) => {
    const next: Record<string, unknown> = { ...el }
    delete next.id
    next.x = el.x - minX
    next.y = el.y - minY
    return next
  })

  const template: LibraryTemplate = {
    id: makeId(),
    name: trimmed,
    createdAt: Date.now(),
    width,
    height,
    elements: localElements,
  }

  const existing = listTemplates(storage)
  const next: LibraryDocument = {
    schema: SCHEMA,
    templates: [template, ...existing],
  }
  safeWrite(storage, JSON.stringify(next))
  return template
}

/** Insert a stored template into the live document at ``target``
 *  (world coords). Wraps the existing ``importScene`` so the insert
 *  is one undo-able transaction and returns the new element ids for
 *  selection. */
export function insertTemplate(
  store: ElementStore,
  template: LibraryTemplate,
  target: { x: number; y: number },
): string[] {
  // Centre the template on ``target`` so the user's click lands in
  // the middle of the inserted block instead of its top-left corner.
  const offset = {
    x: target.x - template.width / 2,
    y: target.y - template.height / 2,
  }
  return importScene(
    store,
    {
      schema: 'rapidly-collab-v1',
      version: 1,
      // ``importScene`` already adds the offset to each element, so
      // we pass the template-local (origin-anchored) elements
      // unchanged.
      elements: template.elements as unknown as Parameters<
        typeof importScene
      >[1]['elements'],
    },
    { offset },
  )
}

/** Delete a template from the library. No-op when the id isn't found
 *  so the caller doesn't need to check first. */
export function deleteTemplate(
  id: string,
  storage: Storage = defaultStorage(),
): void {
  const existing = listTemplates(storage)
  const next: LibraryDocument = {
    schema: SCHEMA,
    templates: existing.filter((t) => t.id !== id),
  }
  safeWrite(storage, JSON.stringify(next))
}

// ── Internals ────────────────────────────────────────────────────────

function defaultStorage(): Storage {
  // Guard against SSR / Node where ``window`` and ``localStorage``
  // don't exist. Returns a no-op stub so calls don't throw — the
  // library just appears empty.
  if (typeof window === 'undefined' || !window.localStorage) {
    return {
      getItem: () => null,
      setItem: () => undefined,
      removeItem: () => undefined,
      clear: () => undefined,
      key: () => null,
      length: 0,
    } as Storage
  }
  return window.localStorage
}

function safeRead(storage: Storage): string | null {
  try {
    return storage.getItem(LIBRARY_STORAGE_KEY)
  } catch {
    // Some browsers throw on ``localStorage`` access in private mode
    // or with strict cookie rules. Treat as "no library" rather than
    // surfacing the exception.
    return null
  }
}

function safeWrite(storage: Storage, value: string): void {
  try {
    storage.setItem(LIBRARY_STORAGE_KEY, value)
  } catch {
    // Quota exceeded / disabled storage. We swallow so the editor
    // doesn't crash; the user just won't see the template appear in
    // the next session.
  }
}

function makeId(): string {
  // Short readable id — not security-sensitive, only needs to be
  // unique within a single browser's library.
  return 'tpl-' + Math.random().toString(36).slice(2, 10)
}
