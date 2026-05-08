/**
 * Bulk find-and-replace across every text-bearing element on the
 * scene — case-insensitive substring match with a literal
 * replacement (no regex special-character interpretation).
 *
 * Touches the same fields the scene-search haystacks read so the
 * mental model is "rename anything search finds":
 *   - ``text`` element ``text`` field
 *   - ``sticky`` element ``text`` field
 *   - ``frame`` element ``name`` field
 *   - ``embed`` element ``url`` field
 *   - any element's optional ``BaseElement.name`` field (added in
 *     #571 for friendly element names)
 *
 * Pure / synchronous. The wiring in ``CollabWhiteboard.tsx`` runs
 * ``previewReplacements`` first to count + describe the changes,
 * then calls ``applyReplacements`` after the user confirms.
 */

import type { ElementStore } from './element-store'
import type { CollabElement } from './elements'

export interface ReplacementPreview {
  elementId: string
  /** Field on the element that the substitution will touch. */
  field: 'text' | 'name' | 'url'
  before: string
  after: string
}

/** Walk every element on the scene, return every field whose value
 *  changes after a case-insensitive replace. ``query`` is treated
 *  literally (no regex). Empty / whitespace-only ``query`` returns
 *  an empty list — the host shouldn't be calling this without a
 *  search term, but we'd rather no-op than throw. */
export function previewReplacements(
  elements: readonly CollabElement[],
  query: string,
  replacement: string,
): ReplacementPreview[] {
  const trimmed = query.trim()
  if (trimmed.length === 0) return []
  const re = new RegExp(escapeRegExp(trimmed), 'gi')
  const out: ReplacementPreview[] = []
  for (const el of elements) {
    for (const { field, value } of fieldsOf(el)) {
      if (!value) continue
      if (!matches(value, re)) continue
      const after = value.replace(re, replacement)
      if (after === value) continue
      out.push({ elementId: el.id, field, before: value, after })
    }
  }
  return out
}

/** Apply the replacements computed by ``previewReplacements`` to
 *  the store in one transaction. Returns the count of touched
 *  fields so the caller can show a summary toast. */
export function applyReplacements(
  store: ElementStore,
  elements: readonly CollabElement[],
  query: string,
  replacement: string,
): number {
  const previews = previewReplacements(elements, query, replacement)
  if (previews.length === 0) return 0
  // Group by element id so each element gets one patch (multiple
  // fields on the same element collapse into a single update).
  const byId = new Map<string, Record<string, string>>()
  for (const p of previews) {
    const patch = byId.get(p.elementId) ?? {}
    patch[p.field] = p.after
    byId.set(p.elementId, patch)
  }
  const updates: { id: string; patch: Record<string, unknown> }[] = []
  for (const [id, patch] of byId) {
    updates.push({ id, patch })
  }
  store.updateMany(updates)
  return previews.length
}

interface FieldRead {
  field: 'text' | 'name' | 'url'
  value: string
}

function fieldsOf(el: CollabElement): FieldRead[] {
  const out: FieldRead[] = []
  // Generic ``BaseElement.name`` (added in #571) — check first
  // so explicit names rename ahead of content.
  const generic = (el as { name?: string }).name
  if (typeof generic === 'string' && el.type !== 'frame') {
    out.push({ field: 'name', value: generic })
  }
  switch (el.type) {
    case 'text':
      out.push({ field: 'text', value: el.text ?? '' })
      break
    case 'sticky':
      out.push({ field: 'text', value: el.text ?? '' })
      break
    case 'frame':
      out.push({ field: 'name', value: el.name ?? '' })
      break
    case 'embed':
      out.push({ field: 'url', value: el.url ?? '' })
      break
    default:
      break
  }
  return out
}

function matches(value: string, re: RegExp): boolean {
  re.lastIndex = 0
  return re.test(value)
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
