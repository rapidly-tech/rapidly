/**
 * Tests for the chamber registry.
 *
 * These are pure data assertions — no React rendering. Their purpose is
 * to fail loudly if someone reorders, deletes, or misconfigures a
 * chamber in a way that breaks the chamber-strip nav, sitemap coverage,
 * or sends a visitor to a dead route.
 */

import { describe, expect, it } from 'vitest'

import { CHAMBERS } from './chambers'

describe('chamber registry', () => {
  it('has exactly 2 chambers', () => {
    // Pinned at the test boundary so adds / drops surface in review.
    // After the engineering-suite pivot, only Secret + Markup remain as
    // public product chambers. Files / Screen / Watch / Call were
    // removed in M1.0 + M1.1, and Collab was renamed to Markup in M1.4
    // (see RAPIDLY_ENGINEERING_SUITE_PLAN.md §2).
    expect(CHAMBERS).toHaveLength(2)
  })

  it('uses unique ids', () => {
    const ids = CHAMBERS.map((c) => c.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('exposes the expected chamber set', () => {
    expect(CHAMBERS.map((c) => c.id).sort()).toEqual(['markup', 'secret'])
  })

  it.each(['files', 'screen', 'watch', 'call', 'collab'])(
    'does not include the removed chamber "%s"',
    (id) => {
      // file_sharing stays in code as transport but is not a product
      // chamber; the media chambers (screen/watch/call) were removed
      // entirely. Re-adding any here would surface them in the chamber-
      // strip nav, which contradicts the engineering-suite framing.
      expect(CHAMBERS.map((c) => c.id)).not.toContain(id)
    },
  )

  it.each(CHAMBERS)(
    'chamber "$id" has a non-empty label, icon, href, tagline',
    (chamber) => {
      expect(chamber.label.length).toBeGreaterThan(0)
      expect(chamber.icon.length).toBeGreaterThan(0)
      expect(chamber.href.length).toBeGreaterThan(0)
      expect(chamber.tagline.length).toBeGreaterThan(0)
    },
  )

  it.each(CHAMBERS)(
    'chamber "$id" uses a namespaced Iconify icon',
    (chamber) => {
      // Iconify names are ``<collection>:<name>``. An unnamespaced string
      // would render as a blank square at runtime — guard at the data
      // layer so a typo in chambers.ts does not silently ship.
      expect(chamber.icon).toMatch(/^[a-z0-9-]+:[a-z0-9-]+$/)
    },
  )

  it.each(CHAMBERS)('chamber "$id" has a valid status', (chamber) => {
    expect(['live', 'soon']).toContain(chamber.status)
  })

  it.each(CHAMBERS.filter((c) => c.status === 'live'))(
    'live chamber "$id" uses an absolute internal href',
    (chamber) => {
      // Live chambers render as <Link href="..."> and must point at a
      // routable internal path. External URLs would bypass Next.js
      // client navigation without explicit opt-in, which is not what
      // this surface is for.
      expect(chamber.href.startsWith('/')).toBe(true)
    },
  )

  it('ships both remaining chambers as live', () => {
    // Both chambers are live with no remaining ``soon`` tiles. If a
    // future chamber is added in preview, explicitly update this
    // assertion instead of silently letting it drift.
    const liveIds = CHAMBERS.filter((c) => c.status === 'live').map((c) => c.id)
    expect(liveIds.sort()).toEqual(['markup', 'secret'])
  })

  it('has no soon chambers', () => {
    const soonIds = CHAMBERS.filter((c) => c.status === 'soon').map((c) => c.id)
    expect(soonIds).toEqual([])
  })
})
