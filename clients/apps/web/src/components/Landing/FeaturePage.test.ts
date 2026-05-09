/**
 * Defense against a silent-regression class: a feature-page icon
 * string that isn't in ``iconMap``. When that happens, ``iconMap[name]``
 * is ``undefined``, the guard ``{iconName && ...}`` skips rendering,
 * and the page ships without the glyph — no error, no warning.
 *
 * This test enumerates every icon name currently referenced on a live
 * ``/features/*`` page and asserts each is mapped. Adding a new name
 * requires a matching entry in the registry, same pattern as
 * chambers.test.ts.
 */

import { describe, expect, it } from 'vitest'

import { iconMap } from './FeaturePage'

// Every icon name referenced in src/app/.../features/*/page.tsx
// as of this PR. If you add a feature card with a new icon, add it
// here AND to ``iconMap`` — the test catches a half-done update.
const USED_ICON_NAMES = [
  'ArrowLeftRight',
  'Banknote',
  'BarChart3',
  'Clock',
  'Cloud',
  'CreditCard',
  'Eye',
  'FileText',
  'Globe',
  'Infinity',
  'Link',
  'Lock',
  'Mic',
  'Monitor',
  'Phone',
  'Play',
  'ShieldCheck',
  'Trash2',
  'TrendingUp',
  'Users',
  'Wifi',
  'Zap',
]

describe('FeaturePage iconMap', () => {
  it.each(USED_ICON_NAMES)('maps %s to a namespaced Iconify icon', (name) => {
    const icon = iconMap[name]
    expect(icon).toBeDefined()
    // Iconify names are ``collection:name`` — unmapped or typoed
    // entries (e.g. plain ``solar-lock``) would render nothing.
    expect(icon).toMatch(/^[a-z0-9-]+:[a-z0-9-]+$/)
  })

  it('every map entry uses a namespaced Iconify icon', () => {
    for (const [key, value] of Object.entries(iconMap)) {
      expect(value, `${key} icon malformed`).toMatch(/^[a-z0-9-]+:[a-z0-9-]+$/)
    }
  })
})
