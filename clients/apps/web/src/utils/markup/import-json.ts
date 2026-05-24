/**
 * Import a previously exported Rapidly Collab scene.
 *
 * Pairs with ``export.ts``: the JSON envelope is the same shape, with
 * ``schema: 'rapidly-collab-v1'`` + a ``version`` discriminator. We
 * accept v1 only — future bumps land alongside a migration path here.
 *
 * Behaviour
 * ---------
 * - Fresh ids on every imported element so re-importing the same JSON
 *   doesn't collide with already-present elements (and a peer can do
 *   it without the new ids racing against the originator's).
 * - Optional ``offset`` translates every imported element so the user
 *   can drop the import at the viewport centre rather than world
 *   origin (the default behaviour stacks the import on top of the
 *   existing scene, which is rarely what you want).
 * - One Yjs transaction → one undo step. Remote peers see the import
 *   as a single frame.
 * - Returns the new ids so the caller can set the selection (the
 *   Mermaid import does the same — keeps both flows symmetric).
 *
 * Validation
 * ----------
 * The parser is intentionally permissive: it accepts any object whose
 * ``schema`` and ``version`` fields match and whose ``elements`` is an
 * array. Per-element validation happens implicitly when the element-
 * store materialises the new Y.Map — ``isCollabElement`` filters
 * malformed entries out of ``list()``. Anything that survives that
 * gauntlet renders correctly.
 */

import type { ElementStore } from './element-store'
import type { CollabElement } from './elements'
import { EXPORT_SCHEMA, type ExportedScene } from './export'

export interface ImportOptions {
  /** World-space translation applied to every imported element. The
   *  whiteboard wires this to the viewport centre minus the import
   *  bounds centre so the import drops where the camera is looking. */
  offset?: { x: number; y: number }
  /** Reuse the original ids when ``true`` (e.g. when round-tripping a
   *  full scene). Defaults to ``false`` so re-imports don't collide. */
  preserveIds?: boolean
}

export interface ImportError {
  reason:
    | 'invalid-json'
    | 'not-an-object'
    | 'wrong-schema'
    | 'wrong-version'
    | 'missing-elements'
}

/** Parse + validate a Rapidly export envelope. Accepts either a raw
 *  string (file contents / paste payload) or a pre-parsed object. */
export function parseExportedScene(
  input: string | unknown,
): ExportedScene | ImportError {
  let parsed: unknown
  if (typeof input === 'string') {
    try {
      parsed = JSON.parse(input)
    } catch {
      return { reason: 'invalid-json' }
    }
  } else {
    parsed = input
  }

  if (!parsed || typeof parsed !== 'object') {
    return { reason: 'not-an-object' }
  }
  const obj = parsed as Record<string, unknown>
  if (obj.schema !== EXPORT_SCHEMA) return { reason: 'wrong-schema' }
  if (obj.version !== 1) return { reason: 'wrong-version' }
  if (!Array.isArray(obj.elements)) return { reason: 'missing-elements' }

  return {
    schema: EXPORT_SCHEMA,
    version: 1,
    elements: obj.elements as CollabElement[],
  }
}

/** Whether the parser returned an error rather than a scene. Narrows
 *  the union for callers without re-checking ``schema`` themselves. */
export function isImportError(
  result: ExportedScene | ImportError,
): result is ImportError {
  return 'reason' in result
}

/** Import a scene into ``store``. Returns the new element ids so the
 *  caller can select them. Wrapped in a single transaction so undo
 *  rolls the whole import back as one step. */
export function importScene(
  store: ElementStore,
  scene: ExportedScene,
  options: ImportOptions = {},
): string[] {
  const offset = options.offset ?? { x: 0, y: 0 }
  const preserve = options.preserveIds ?? false
  const created: string[] = []
  store.transact(() => {
    for (const el of scene.elements) {
      // Spread first, then override id/x/y so the original element's
      // own id field doesn't sneak through when ``preserveIds`` is
      // false. The store will mint a fresh nanoid when ``id`` is
      // missing.
      const next: Record<string, unknown> = {
        ...el,
        x: el.x + offset.x,
        y: el.y + offset.y,
      }
      if (!preserve) delete next.id
      // CreateElementInput requires {type, x, y, width, height}; the
      // exporter emits all of those for every element. Cast through
      // the store's input shape — TypeScript can't narrow across the
      // structuredClone payload.
      created.push(store.create(next as Parameters<ElementStore['create']>[0]))
    }
  })
  return created
}
