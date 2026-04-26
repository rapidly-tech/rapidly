/**
 * Defence-in-depth test for the robots policy.
 *
 * Every P2P chamber has a ``/<name>/<slug>`` guest route that must be
 * crawler-disallowed — the slugs are per-session ephemera and
 * indexing them pollutes the search index and leaks session handles
 * into crawler logs. Pinning the full set means "added a chamber,
 * forgot to disallow its guest tree" fails at test time.
 */

import { describe, expect, it } from 'vitest'

import { DISALLOWED_PATHS } from './robots'

describe('robots DISALLOWED_PATHS', () => {
  it.each(['/file-sharing/', '/screen/', '/watch/', '/call/', '/collab/'])(
    'disallows %s (per-session slug trees)',
    (path) => {
      expect(DISALLOWED_PATHS).toContain(path)
    },
  )

  it.each(['/dashboard/', '/login/', '/verify-email/'])(
    'disallows %s (private surface)',
    (path) => {
      expect(DISALLOWED_PATHS).toContain(path)
    },
  )

  it('does not disallow the public chamber host pages', () => {
    // The no-slash variants (``/screen``, ``/watch`` etc.) remain
    // allowed so the "Start a session" landings get indexed.
    for (const path of ['/screen', '/watch', '/call', '/collab']) {
      expect(DISALLOWED_PATHS).not.toContain(path)
    }
  })

  it('every entry is trailing-slash terminated', () => {
    // robots.txt semantics: ``/foo/`` disallows ``/foo/bar`` but not
    // ``/foo`` itself. Trailing-slash discipline keeps the host
    // pages indexable by accident.
    for (const p of DISALLOWED_PATHS) {
      expect(p.endsWith('/')).toBe(true)
    }
  })
})
