/**
 * Grouping — Cmd+G / Cmd+Shift+G semantics for the Collab v2 whiteboard.
 *
 * Group membership lives on ``BaseElement.groupIds`` as an innermost-
 * first ancestor chain:
 *
 *   ``groupIds = []``       → element is not in any group
 *   ``groupIds = [G1]``     → in group G1
 *   ``groupIds = [G1, G2]`` → in group G1 (innermost), nested inside G2
 *
 * Group records don't exist as first-class objects — a "group" is
 * implicit: the set of elements that share a given string id in their
 * ``groupIds``. That matches Excalidraw's approach and survives Yjs
 * concurrency trivially: two peers grouping overlapping selections
 * with different new-group-ids just end up with both ids present on
 * the shared elements, which renders as a single visual group anyway.
 *
 * The pure helpers at the top of this file take plain arrays so they
 * can be unit-tested without a Yjs doc; the thin store wrappers at the
 * bottom commit the resulting patches in a single transaction so
 * remote peers see one atomic frame per Cmd+G.
 */

import { nanoid } from 'nanoid'

import type { ElementStore } from './element-store'
import type { CollabElement } from './elements'

/** The innermost (tightest) group the element belongs to, or ``null``. */
export function innermostGroupId(el: CollabElement): string | null {
  return el.groupIds.length > 0 ? el.groupIds[0] : null
}

/** The outermost ancestor group, or ``null`` when ungrouped. This is
 *  what a single click expands to — you always select the whole
 *  top-level group, then drill in with double-click later. */
export function outermostGroupId(el: CollabElement): string | null {
  const n = el.groupIds.length
  return n > 0 ? el.groupIds[n - 1] : null
}

export interface GroupPatches {
  /** ``null`` when no grouping was produced — e.g. a selection of <2
   *  elements. The caller can use this to skip the store write. */
  groupId: string | null
  patches: { id: string; patch: { groupIds: string[] } }[]
}

/** Pure: wrap ``elements`` in a new outermost group. Needs at least
 *  two elements to be meaningful — a single-element group is
 *  indistinguishable from the element itself and would just clutter
 *  the doc. Exposed as a pure function so tests don't need a store.
 *
 *  The new id is appended (``[...existing, new]``) because each Cmd+G
 *  creates a fresh container around whatever the selection was already
 *  inside — the new group is strictly broader than the existing ones.
 *
 *  ``newGroupId`` is injectable so tests can assert exact output; in
 *  production callers let it default to a fresh nanoid. */
export function computeGroupPatches(
  elements: readonly CollabElement[],
  newGroupId: string = nanoid(12),
): GroupPatches {
  if (elements.length < 2) return { groupId: null, patches: [] }
  const patches = elements.map((el) => ({
    id: el.id,
    patch: { groupIds: [...el.groupIds, newGroupId] },
  }))
  return { groupId: newGroupId, patches }
}

/** Pure: remove the outermost group id from every element that has
 *  one. Elements not in any group are skipped entirely. Mirrors
 *  Cmd+Shift+G — unwrap one layer at a time, most-recently-grouped
 *  first. */
export function computeUngroupPatches(
  elements: readonly CollabElement[],
): { id: string; patch: { groupIds: string[] } }[] {
  const out: { id: string; patch: { groupIds: string[] } }[] = []
  for (const el of elements) {
    if (el.groupIds.length === 0) continue
    out.push({ id: el.id, patch: { groupIds: el.groupIds.slice(0, -1) } })
  }
  return out
}

/** Atomic group op: writes the new innermost group to every element in
 *  ``selected`` in a single Yjs transaction. Returns the new group id,
 *  or ``null`` when the selection was too small (<2 resolvable elts)
 *  to form a group. */
export function group(
  store: ElementStore,
  selected: ReadonlySet<string>,
): string | null {
  if (selected.size < 2) return null
  const elements: CollabElement[] = []
  for (const id of selected) {
    const el = store.get(id)
    if (el) elements.push(el)
  }
  const { groupId, patches } = computeGroupPatches(elements)
  if (patches.length === 0) return null
  store.updateMany(patches)
  return groupId
}

/** Atomic ungroup op: strips the innermost group from each selected
 *  element in one transaction. No-op when nothing selected is in a
 *  group. */
export function ungroup(
  store: ElementStore,
  selected: ReadonlySet<string>,
): void {
  if (selected.size === 0) return
  const elements: CollabElement[] = []
  for (const id of selected) {
    const el = store.get(id)
    if (el) elements.push(el)
  }
  const patches = computeUngroupPatches(elements)
  if (patches.length === 0) return
  store.updateMany(patches)
}

/** Expand a set of seed ids to include every element sharing the
 *  **outermost** group of any seed. Ungrouped seeds stay singletons.
 *  Idempotent — running twice returns the same set.
 *
 *  The select tool calls this on click / marquee so a click on any
 *  member of a group selects the whole group. Use via
 *  ``sel.set(expandToGroups(store, new Set([hitId])))``. */
export function expandToGroups(
  store: ElementStore,
  seeds: ReadonlySet<string>,
): Set<string> {
  const out = new Set<string>(seeds)
  if (seeds.size === 0) return out
  const groupIds = new Set<string>()
  for (const id of seeds) {
    const el = store.get(id)
    if (!el) continue
    const gid = outermostGroupId(el)
    if (gid) groupIds.add(gid)
  }
  if (groupIds.size === 0) return out
  for (const el of store.list()) {
    const gid = outermostGroupId(el)
    if (gid && groupIds.has(gid)) out.add(el.id)
  }
  return out
}
