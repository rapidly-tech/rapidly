/**
 * Defence-in-depth test for the landing sitemap.
 *
 * The sitemap is hand-maintained — adding a new chamber means
 * touching two places (chambers.ts + sitemap.ts). Pinning the full
 * expected URL set here means "forgot the sitemap entry" fails at
 * ``pnpm test`` rather than silently making a new feature
 * un-indexable.
 */

import { describe, expect, it } from 'vitest'

import sitemap from './sitemap'

describe('landing sitemap', () => {
  const entries = sitemap()
  const urls = entries.map((e) => e.url)

  // Each live chamber's feature page must appear. If this list ever
  // lags behind ``components/Revolver/chambers.ts``, a chamber ships
  // without SEO coverage — that's why we pin every expected suffix.
  it.each([
    '/features/shares',
    '/features/secret-messages',
    '/features/screen-share',
    '/features/watch-together',
    '/features/call',
    '/features/collab',
  ])('includes %s', (suffix) => {
    const matches = urls.filter((u) => u.endsWith(suffix))
    expect(matches).toHaveLength(1)
  })

  it('includes /revolver (the canonical six-chamber landing)', () => {
    expect(urls.some((u) => u.endsWith('/revolver'))).toBe(true)
  })

  it('every entry has an absolute URL', () => {
    for (const entry of entries) {
      expect(entry.url).toMatch(/^https?:\/\//)
    }
  })

  it('every entry has a lastModified, changeFrequency, and priority', () => {
    for (const entry of entries) {
      expect(entry.lastModified).toBeDefined()
      expect(entry.changeFrequency).toBeDefined()
      expect(typeof entry.priority).toBe('number')
    }
  })
})
