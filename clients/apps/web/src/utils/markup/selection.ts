/**
 * Local selection state for the Collab v2 whiteboard.
 *
 * Selection is NOT part of the Yjs doc — it's per-user, per-session.
 * A peer's selection is broadcast via Awareness (Phase 13) so remote
 * cursors can render coloured outlines, but the authoritative selection
 * set for *this* client stays in-memory.
 *
 * SelectionState wraps a ``Set<string>`` with a tiny pub/sub API so
 * React state and the selection overlay can both re-render on change
 * without prop-drilling.
 */

export type SelectionListener = (ids: ReadonlySet<string>) => void

export class SelectionState {
  private ids: Set<string> = new Set()
  private listeners: Set<SelectionListener> = new Set()

  /** Number of selected ids. */
  get size(): number {
    return this.ids.size
  }

  /** Readonly view of the selected ids. */
  get snapshot(): ReadonlySet<string> {
    return this.ids
  }

  has(id: string): boolean {
    return this.ids.has(id)
  }

  /** Replace the full selection. */
  set(ids: Iterable<string>): void {
    this.ids = new Set(ids)
    this.emit()
  }

  /** Add one id; no-op if already selected. */
  add(id: string): void {
    if (this.ids.has(id)) return
    this.ids.add(id)
    this.emit()
  }

  /** Toggle membership — the standard shift-click behaviour. */
  toggle(id: string): void {
    if (this.ids.has(id)) this.ids.delete(id)
    else this.ids.add(id)
    this.emit()
  }

  /** Remove one id; no-op if not selected. */
  remove(id: string): void {
    if (!this.ids.has(id)) return
    this.ids.delete(id)
    this.emit()
  }

  clear(): void {
    if (this.ids.size === 0) return
    this.ids.clear()
    this.emit()
  }

  /** Drop ids that no longer exist (e.g. remote peer deleted them).
   *  Returns true if anything changed. */
  reconcile(existingIds: ReadonlySet<string>): boolean {
    let changed = false
    for (const id of this.ids) {
      if (!existingIds.has(id)) {
        this.ids.delete(id)
        changed = true
      }
    }
    if (changed) this.emit()
    return changed
  }

  subscribe(fn: SelectionListener): () => void {
    this.listeners.add(fn)
    return () => {
      this.listeners.delete(fn)
    }
  }

  private emit(): void {
    for (const fn of this.listeners) fn(this.ids)
  }
}
