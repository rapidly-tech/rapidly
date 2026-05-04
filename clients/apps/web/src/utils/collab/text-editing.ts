/**
 * Text-edit request broker.
 *
 * A cross-cutting concern: the text tool (and, later, double-click
 * in the select tool) needs to tell the renderer-hosting component
 * "please pop the inline editor on element id X." We keep the signal
 * here so tools stay framework-agnostic — they just call
 * ``requestEdit(id)`` and the component subscribes.
 *
 * Scope: one pending edit at a time (the canvas is single-focus
 * anyway). The subscriber is responsible for clearing the request
 * once the editor mounts; calling ``requestEdit`` again overrides.
 */

type Listener = (id: string | null) => void

let current: string | null = null
const listeners: Set<Listener> = new Set()

/** Ask the host component to open the inline editor on the given
 *  element id. Call with ``null`` to cancel a pending request that
 *  hasn't been picked up yet. */
export function requestEdit(id: string | null): void {
  current = id
  for (const fn of listeners) fn(id)
}

/** Subscribe to edit requests. Returns a disposer. */
export function onEditRequest(fn: Listener): () => void {
  listeners.add(fn)
  // Fire once with the current state so late subscribers don't miss
  // a pending request.
  if (current !== null) fn(current)
  return () => {
    listeners.delete(fn)
  }
}

/** Test helper — reset module state between tests. */
export function _resetEditBroker(): void {
  current = null
  listeners.clear()
}
