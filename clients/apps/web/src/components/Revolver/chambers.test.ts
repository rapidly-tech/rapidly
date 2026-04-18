/**
 * Tests for the Revolver chamber registry.
 *
 * These are pure data assertions — no React rendering. Their purpose is
 * to fail loudly if someone reorders, deletes, or misconfigures a
 * chamber in a way that would break the hexagonal 60° layout or send a
 * visitor to a dead route.
 */

import { describe, expect, it } from 'vitest'

import { CHAMBERS } from './chambers'

describe('Revolver chamber registry', () => {
  it('has exactly 6 chambers (hexagonal layout)', () => {
    // 6 is a geometric invariant: the Revolver component places each
    // chamber at index * 60° around the ring. Adding or removing entries
    // silently breaks the layout, so pin the count at the test boundary.
    expect(CHAMBERS).toHaveLength(6)
  })

  it('uses unique ids', () => {
    const ids = CHAMBERS.map((c) => c.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('exposes the expected chamber set', () => {
    expect(CHAMBERS.map((c) => c.id).sort()).toEqual([
      'call',
      'collab',
      'files',
      'screen',
      'secret',
      'watch',
    ])
  })

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

  it('ships Files, Secret, Screen, and Watch as live', () => {
    const liveIds = CHAMBERS.filter((c) => c.status === 'live').map((c) => c.id)
    expect(liveIds.sort()).toEqual(['files', 'screen', 'secret', 'watch'])
  })

  it('ships Call and Collab as soon', () => {
    const soonIds = CHAMBERS.filter((c) => c.status === 'soon').map((c) => c.id)
    expect(soonIds.sort()).toEqual(['call', 'collab'])
  })
})
