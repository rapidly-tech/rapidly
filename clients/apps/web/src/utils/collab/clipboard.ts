/**
 * In-app clipboard for the Collab v2 whiteboard.
 *
 * Copy / paste / cut / duplicate all run against a module-level buffer
 * — not the system clipboard — because the browser's clipboard API is
 * permission-gated, async, and text-only without opt-in. An in-app
 * buffer covers the 99% case (copy here, paste here) deterministically
 * and keeps this module test-friendly.
 *
 * System-clipboard PNG handling (paste an image → image element) lands
 * in a follow-up; it's a separate surface because it needs a different
 * contract (async, user-gesture-gated, MIME negotiation).
 *
 * Id rewriting on paste
 * ---------------------
 * Every pasted element gets a fresh nanoid so two pastes from the same
 * payload don't collide in the Yjs doc. Cross-element references are
 * rewritten through a single id map built once per paste:
 *
 *   - ``groupIds``   — any group id whose *origin* group had at least
 *                      one copied member is remapped to a fresh id, so
 *                      the pasted batch stays grouped together. Group
 *                      ids with no remapped counterpart are stripped.
 *   - ``startBinding`` / ``endBinding`` on arrows — if the bound
 *                      element is in the paste set, the binding is
 *                      rewritten to the new id; otherwise the binding
 *                      is dropped so the arrow endpoint goes free
 *                      (prevents ghost bindings to a distant target).
 *   - ``containerId``  on text and ``boundTextId`` on containers —
 *                      same rule: both-sides-in-set → rewrite, else
 *                      drop.
 */

import { nanoid } from 'nanoid'

import type { ElementStore } from './element-store'
import type { CollabElement } from './elements'

/** Magic string — used only when/if we extend this to system-clipboard
 *  JSON so we can detect our own payload on paste. Exported now so a
 *  later patch can depend on it without a version-bump. */
export const CLIPBOARD_MAGIC = 'rapidly-collab-v1' as const

export interface ClipboardPayload {
  /** Schema marker — bump when the payload shape changes. */
  magic: typeof CLIPBOARD_MAGIC
  /** Element snapshots in paint order (low-z first). The paste order
   *  follows this so the resulting z-stack matches the copy. */
  elements: CollabElement[]
}

/** Module-level in-app clipboard. Null until the user has copied
 *  something; replaced wholesale on each copy. */
let buffer: ClipboardPayload | null = null

/** Serialise the current selection into a ClipboardPayload. Elements
 *  are captured by value (plain JSON) so the buffer is immune to
 *  subsequent edits of the source elements. */
export function serialiseSelection(
  store: ElementStore,
  selected: ReadonlySet<string>,
): ClipboardPayload | null {
  if (selected.size === 0) return null
  const elements: CollabElement[] = []
  for (const el of store.list()) {
    if (selected.has(el.id)) elements.push(structuredClone(el))
  }
  if (elements.length === 0) return null
  return { magic: CLIPBOARD_MAGIC, elements }
}

/** Current clipboard contents, or ``null`` if nothing has been copied
 *  in this session. Exposed for callers that want to check whether
 *  paste would be a no-op. */
export function getClipboard(): ClipboardPayload | null {
  return buffer
}

/** Test-only reset. Keeps the module stateless between runs. */
export function _resetClipboard(): void {
  buffer = null
}

/** Copy — writes the selected elements into the in-app clipboard.
 *  Returns ``true`` when something was captured. */
export function copy(
  store: ElementStore,
  selected: ReadonlySet<string>,
): boolean {
  const payload = serialiseSelection(store, selected)
  if (!payload) return false
  buffer = payload
  return true
}

export interface PasteOptions {
  /** Shift applied to every pasted element's (x, y). Defaults to
   *  ``{ x: 16, y: 16 }`` so pasted copies don't sit exactly on top of
   *  the originals. */
  offset?: { x: number; y: number }
}

const DEFAULT_OFFSET = { x: 16, y: 16 }

/** Paste — writes fresh copies of ``payload`` into the store with new
 *  ids, remapped group ids, and remapped cross-element references.
 *  Returns the list of freshly-created ids (in paint order) so the
 *  caller can update the selection.
 *
 *  No-op when ``payload`` is null or contains zero elements. */
export function paste(
  store: ElementStore,
  payload: ClipboardPayload | null,
  options: PasteOptions = {},
): string[] {
  if (!payload || payload.elements.length === 0) return []
  const offset = options.offset ?? DEFAULT_OFFSET
  const { idMap, groupIdMap } = buildRewriteMaps(payload.elements)
  const newIds: string[] = []
  const patches: { id: string; element: Record<string, unknown> }[] = []

  const topZ = currentMaxZIndex(store)

  for (let i = 0; i < payload.elements.length; i++) {
    const src = payload.elements[i]
    const newId = idMap.get(src.id)!
    const rewritten = rewriteElement(
      src,
      idMap,
      groupIdMap,
      offset,
      topZ + 1 + i,
    )
    rewritten.id = newId
    patches.push({ id: newId, element: rewritten })
    newIds.push(newId)
  }

  // Commit in a single transaction so remote peers see an atomic frame.
  store.transact(() => {
    for (const { element } of patches) {
      // ``element`` already has the new id, so store.create will honour it.
      store.create(element as Parameters<typeof store.create>[0])
    }
  })

  return newIds
}

/** Duplicate — shortcut for copy + paste without touching the buffer.
 *  Matches Cmd+D in Figma / Excalidraw. Returns new ids. */
export function duplicate(
  store: ElementStore,
  selected: ReadonlySet<string>,
  options: PasteOptions = {},
): string[] {
  const payload = serialiseSelection(store, selected)
  if (!payload) return []
  return paste(store, payload, options)
}

/** Cut — copy then delete. Single transaction for the delete so remote
 *  peers don't observe a half-state. */
export function cut(
  store: ElementStore,
  selected: ReadonlySet<string>,
): boolean {
  const ok = copy(store, selected)
  if (!ok) return false
  store.deleteMany(Array.from(selected))
  return true
}

// ── Internals ────────────────────────────────────────────────────────

/** Build the id + groupId remaps in one pass. Each copied element
 *  gets a fresh element id; each distinct group id in the set gets a
 *  fresh group id so the pasted batch retains its grouping. */
function buildRewriteMaps(elements: readonly CollabElement[]): {
  idMap: Map<string, string>
  groupIdMap: Map<string, string>
} {
  const idMap = new Map<string, string>()
  const groupIdMap = new Map<string, string>()
  for (const el of elements) {
    idMap.set(el.id, nanoid(12))
    for (const gid of el.groupIds) {
      if (!groupIdMap.has(gid)) groupIdMap.set(gid, nanoid(12))
    }
  }
  return { idMap, groupIdMap }
}

/** Produce a fresh element object with all id-like fields rewritten.
 *  Does *not* set the new id — ``paste()`` writes that after the call
 *  so the map lookup and the assignment sit next to each other. */
function rewriteElement(
  src: CollabElement,
  idMap: Map<string, string>,
  groupIdMap: Map<string, string>,
  offset: { x: number; y: number },
  zIndex: number,
): Record<string, unknown> {
  const el: Record<string, unknown> = { ...src }
  el.x = src.x + offset.x
  el.y = src.y + offset.y
  el.zIndex = zIndex
  el.groupIds = src.groupIds
    .map((gid) => groupIdMap.get(gid))
    .filter((gid): gid is string => gid !== undefined)
  el.version = 1
  // Rewrite cross-element references when both ends are in the set.
  // Fields are type-specific; walk the union.
  if (src.type === 'arrow') {
    if (src.startBinding) {
      const mapped = idMap.get(src.startBinding.elementId)
      el.startBinding = mapped
        ? { ...src.startBinding, elementId: mapped }
        : undefined
    }
    if (src.endBinding) {
      const mapped = idMap.get(src.endBinding.elementId)
      el.endBinding = mapped
        ? { ...src.endBinding, elementId: mapped }
        : undefined
    }
  }
  if (src.type === 'text' && src.containerId) {
    const mapped = idMap.get(src.containerId)
    if (mapped) el.containerId = mapped
    else delete el.containerId
  }
  if (src.boundTextId) {
    const mapped = idMap.get(src.boundTextId)
    if (mapped) el.boundTextId = mapped
    else delete el.boundTextId
  }
  return el
}

function currentMaxZIndex(store: ElementStore): number {
  let max = -1
  for (const el of store.list()) {
    if (el.zIndex > max) max = el.zIndex
  }
  return max
}
