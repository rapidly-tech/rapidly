/**
 * Scene search — find elements on the whiteboard by their text content.
 *
 * Cmd+F (or ``/``) opens a search overlay. The user types; this module
 * returns ranked matches across every text-bearing element kind:
 *
 *   - ``text`` elements (free-floating labels)
 *   - ``sticky`` notes
 *   - bound-text labels owned by ``rect`` / ``ellipse`` / ``diamond``
 *     (resolved via the parent's ``boundTextId`` so a hit jumps to the
 *     parent shape, not the floating text child)
 *   - ``frame`` names (so "Onboarding" jumps to the frame named that)
 *   - ``embed`` URLs (so a YouTube/Loom URL search works)
 *
 * Ranking favours:
 *   - exact case-insensitive match  (score 100)
 *   - whole-word match              (score  80)
 *   - prefix match                  (score  60)
 *   - any substring                 (score  40)
 *
 * Ties broken by the element's reading order (top-down, left-right of
 * its centre) so results read predictably as the user steps through.
 */

import type { CollabElement } from './elements'

export interface SearchHit {
  /** The element to focus / select when the user picks this hit. */
  elementId: string
  /** Human-readable kind label for the result row (``"text"``,
   *  ``"sticky"``, ``"rect label"``, ``"frame"``, ``"embed"``). */
  kind: string
  /** Snippet shown in the result row — the matched string with
   *  surrounding context, never longer than ~80 chars. */
  snippet: string
  /** World-space centre to pan the viewport to. */
  centerX: number
  centerY: number
  /** Higher = better match. Used for ordering. */
  score: number
}

const SCORE_EXACT = 100
const SCORE_WHOLE_WORD = 80
const SCORE_PREFIX = 60
const SCORE_SUBSTRING = 40
const SNIPPET_RADIUS = 32

/** Search every text-bearing element for matches against ``query``.
 *  Returns up to ``limit`` hits sorted by score (desc), then by
 *  reading order. An empty query returns ``[]``. */
export function searchScene(
  elements: CollabElement[],
  query: string,
  limit = 25,
): SearchHit[] {
  const trimmed = query.trim()
  if (trimmed.length === 0) return []
  const needle = trimmed.toLowerCase()

  // Index elements by id so bound-text lookups are O(1) instead of
  // re-scanning the array per parent.
  const byId = new Map(elements.map((e) => [e.id, e]))
  // Track which text-element ids are bound to a parent shape so we
  // can attribute hits to the parent and skip the orphan text row.
  const childToParent = new Map<string, CollabElement>()
  for (const el of elements) {
    if (el.boundTextId && byId.has(el.boundTextId)) {
      childToParent.set(el.boundTextId, el)
    }
  }

  const hits: SearchHit[] = []
  for (const el of elements) {
    const haystacks = haystacksFor(el)
    for (const { text, kindLabel } of haystacks) {
      const score = scoreMatch(text, needle)
      if (score === 0) continue
      // Prefer attributing a hit to the parent shape when the matched
      // element is a bound text child — clicking the result then
      // selects the surrounding box, which is what the user sees.
      const target = childToParent.get(el.id) ?? el
      hits.push({
        elementId: target.id,
        kind: childToParent.has(el.id) ? `${target.type} label` : kindLabel,
        snippet: makeSnippet(text, needle),
        centerX: target.x + target.width / 2,
        centerY: target.y + target.height / 2,
        score,
      })
    }
  }

  // Stable ordering: score desc, then top-down, then left-right.
  hits.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score
    if (a.centerY !== b.centerY) return a.centerY - b.centerY
    return a.centerX - b.centerX
  })
  // Dedupe — a parent shape could match its own bound text plus
  // (hypothetically) its own field; only keep the highest-scoring
  // hit per element id.
  const seen = new Set<string>()
  const out: SearchHit[] = []
  for (const h of hits) {
    if (seen.has(h.elementId)) continue
    seen.add(h.elementId)
    out.push(h)
    if (out.length >= limit) break
  }
  return out
}

interface Haystack {
  text: string
  kindLabel: string
}

function haystacksFor(el: CollabElement): Haystack[] {
  switch (el.type) {
    case 'text':
      return el.text ? [{ text: el.text, kindLabel: 'text' }] : []
    case 'sticky':
      return el.text ? [{ text: el.text, kindLabel: 'sticky' }] : []
    case 'frame':
      return el.name ? [{ text: el.name, kindLabel: 'frame' }] : []
    case 'embed':
      return el.url ? [{ text: el.url, kindLabel: 'embed' }] : []
    default:
      return []
  }
}

function scoreMatch(haystack: string, needle: string): number {
  const lower = haystack.toLowerCase()
  if (lower === needle) return SCORE_EXACT
  // Whole-word: surrounded by start/end or non-word characters.
  const wordRe = new RegExp(`(^|\\W)${escapeRegExp(needle)}(\\W|$)`)
  if (wordRe.test(lower)) return SCORE_WHOLE_WORD
  if (lower.startsWith(needle)) return SCORE_PREFIX
  if (lower.includes(needle)) return SCORE_SUBSTRING
  return 0
}

function makeSnippet(haystack: string, needle: string): string {
  const lower = haystack.toLowerCase()
  const idx = lower.indexOf(needle)
  if (idx < 0) return haystack.slice(0, SNIPPET_RADIUS * 2)
  const start = Math.max(0, idx - SNIPPET_RADIUS)
  const end = Math.min(haystack.length, idx + needle.length + SNIPPET_RADIUS)
  const prefix = start > 0 ? '…' : ''
  const suffix = end < haystack.length ? '…' : ''
  return prefix + haystack.slice(start, end) + suffix
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
