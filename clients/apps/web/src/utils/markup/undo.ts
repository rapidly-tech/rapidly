/**
 * Per-client undo / redo for the Collab v2 whiteboard.
 *
 * Wraps Yjs's built-in ``UndoManager`` with two invariants the rest
 * of the app depends on:
 *
 *  1. **Scoped to local edits.** The manager's ``trackedOrigins`` is
 *     the single ``ORIGIN_LOCAL`` symbol used by ``ElementStore``.
 *     Remote peers' mutations ride in with a different origin and
 *     are deliberately ignored — an undo here cannot rewind another
 *     user's work.
 *  2. **Deep tracking.** ``captureTimeout`` stays at 0 so every
 *     ``updateMany`` / ``create`` / ``delete`` transaction produces a
 *     single, crisp undo step regardless of how many elements it
 *     touched.
 *
 * Why a thin wrapper instead of handing ``Y.UndoManager`` to callers
 * directly?
 *   - Consumers don't depend on Yjs internals — swapping the
 *     implementation later (e.g. a purpose-built journal for the
 *     history sidebar) only needs this module to change.
 *   - The subscribe hook exposes exactly one ""state changed"" event
 *     so React UI doesn't have to know about ``stack-item-added`` vs
 *     ``stack-item-popped`` vs ``stack-cleared``.
 */

import * as Y from 'yjs'

import { ORIGIN_LOCAL, type ElementStore } from './element-store'

export interface UndoController {
  /** Roll back the most recent local transaction. Returns ``true``
   *  when something was undone, ``false`` when the stack was empty. */
  undo(): boolean
  /** Re-apply the most recently undone transaction. */
  redo(): boolean
  canUndo(): boolean
  canRedo(): boolean
  /** Fire on every stack change (pushed, popped, cleared). Use it to
   *  re-render toolbar buttons or trigger React updates. */
  subscribe(fn: () => void): () => void
  /** Tear down the underlying manager + drop listeners. Call on
   *  component unmount. */
  dispose(): void
}

export function createUndoManager(store: ElementStore): UndoController {
  const manager = new Y.UndoManager(store.getRoot(), {
    trackedOrigins: new Set([ORIGIN_LOCAL]),
    // 0 = ""every local transaction is its own step"". The group-
    // operations in ElementStore (updateMany etc.) are already the
    // natural batching unit so we don't want time-based re-batching
    // on top.
    captureTimeout: 0,
  })

  const listeners = new Set<() => void>()
  const emit = (): void => {
    for (const fn of listeners) fn()
  }

  // Three event names cover every stack transition — add listeners
  // individually so listener-order across events is deterministic.
  manager.on('stack-item-added', emit)
  manager.on('stack-item-popped', emit)
  manager.on('stack-cleared', emit)

  return {
    undo() {
      const popped = manager.undo()
      return popped !== null
    },
    redo() {
      const popped = manager.redo()
      return popped !== null
    },
    canUndo() {
      return manager.undoStack.length > 0
    },
    canRedo() {
      return manager.redoStack.length > 0
    },
    subscribe(fn) {
      listeners.add(fn)
      return () => {
        listeners.delete(fn)
      }
    },
    dispose() {
      manager.off('stack-item-added', emit)
      manager.off('stack-item-popped', emit)
      manager.off('stack-cleared', emit)
      manager.destroy()
      listeners.clear()
    },
  }
}
