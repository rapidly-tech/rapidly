/**
 * Hyperlink helpers for the Collab v2 whiteboard.
 *
 * Every element already carries an optional ``link`` field on
 * ``BaseElement`` — this module owns the normalisation + validation
 * rules + the atomic read/write ops. Kept as a small pure surface so
 * tests don't need a DOM and the demo / ``useCollabRoom`` share one
 * code path.
 *
 * URL rules
 * ---------
 * We only accept ``http``, ``https``, and ``mailto:`` schemes. Other
 * schemes (``file:``, ``javascript:``, ``data:``) are rejected — a
 * shared whiteboard is a cross-user surface, so accepting arbitrary
 * schemes opens the door to script injection via the hover badge's
 * ``<a href>``. A bare ""example.com"" is normalised to
 * ``https://example.com``.
 */

import type { ElementStore } from './element-store'

const ALLOWED_PROTOCOLS = new Set(['http:', 'https:', 'mailto:'])

/** Add ``https://`` when the input has no scheme. Leaves already-
 *  schemed URLs untouched so ``mailto:x@y`` stays as-is. Whitespace
 *  is trimmed; an empty string returns empty (caller can then treat
 *  it as ""clear the link""). */
export function normalizeUrl(raw: string): string {
  const trimmed = raw.trim()
  if (trimmed === '') return ''
  // Already-schemed? Leave it alone.
  if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(trimmed)) return trimmed
  return `https://${trimmed}`
}

/** True when ``url`` parses as a valid URL with one of the allowed
 *  schemes. Pure — safe in tests. */
export function isValidUrl(url: string): boolean {
  if (typeof url !== 'string' || url.length === 0) return false
  try {
    const parsed = new URL(url)
    return ALLOWED_PROTOCOLS.has(parsed.protocol)
  } catch {
    return false
  }
}

/** Write ``link`` to every selected element in one Yjs transaction.
 *  The URL is normalised first; an empty string after normalisation
 *  clears the field instead (matches the Cmd+K ""unset"" flow). Returns
 *  ``true`` when something changed. */
export function setLink(
  store: ElementStore,
  selected: ReadonlySet<string>,
  rawUrl: string,
): boolean {
  if (selected.size === 0) return false
  const url = normalizeUrl(rawUrl)
  if (url === '') return clearLink(store, selected)
  if (!isValidUrl(url)) return false
  const patches: { id: string; patch: { link: string } }[] = []
  for (const id of selected) {
    if (store.has(id)) patches.push({ id, patch: { link: url } })
  }
  if (patches.length === 0) return false
  store.updateMany(patches)
  return true
}

/** Drop the ``link`` field from every selected element. Uses an empty
 *  string as the ""no link"" sentinel so the Yjs Y.Map doesn't retain
 *  a stale value; readers treat empty-string link the same as absent. */
export function clearLink(
  store: ElementStore,
  selected: ReadonlySet<string>,
): boolean {
  if (selected.size === 0) return false
  const patches: { id: string; patch: { link: string } }[] = []
  for (const id of selected) {
    const el = store.get(id)
    if (el && el.link && el.link !== '') {
      patches.push({ id, patch: { link: '' } })
    }
  }
  if (patches.length === 0) return false
  store.updateMany(patches)
  return true
}

/** True when an element has a usable link attached. Callers use this
 *  to decide whether to render the hover badge / accept Cmd+click
 *  navigation. */
export function hasLink(el: { link?: string }): boolean {
  return typeof el.link === 'string' && el.link.length > 0
}
