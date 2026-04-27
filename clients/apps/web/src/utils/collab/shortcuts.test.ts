import { describe, expect, it } from 'vitest'

import { allShortcuts, formatKeys, SHORTCUT_CATEGORIES } from './shortcuts'

describe('SHORTCUT_CATEGORIES', () => {
  it('has at least one entry per category', () => {
    for (const cat of SHORTCUT_CATEGORIES) {
      expect(cat.entries.length).toBeGreaterThan(0)
    }
  })

  it('every entry has a non-empty keys list and description', () => {
    for (const cat of SHORTCUT_CATEGORIES) {
      for (const e of cat.entries) {
        expect(e.keys.length).toBeGreaterThan(0)
        expect(e.description.length).toBeGreaterThan(0)
      }
    }
  })

  it('describes each canonical action exactly once', () => {
    // Prevent drift where two rows list the same shortcut with
    // different wording — easy to introduce when adding a feature.
    const descriptions = new Set<string>()
    for (const cat of SHORTCUT_CATEGORIES) {
      for (const e of cat.entries) {
        expect(descriptions.has(e.description)).toBe(false)
        descriptions.add(e.description)
      }
    }
  })

  it('lists shortcuts the keydown handler actually wires', () => {
    // Drift guard: each item below has a real handler in
    // CollabWhiteboard.tsx. If a row goes stale, the dialog lies to
    // the user. Match by description fragment so wording can evolve
    // without breaking the test.
    const flat = allShortcuts()
      .map((s) => s.description.toLowerCase())
      .join(' | ')
    for (const fragment of [
      'eraser',
      'select all',
      'clear selection',
      'nudge selection by 1',
      'nudge selection by 10',
      'command palette',
      'zoom in',
      'zoom out',
      'reset zoom',
      'duplicate selection while dragging',
    ]) {
      expect(flat).toContain(fragment)
    }
  })
})

describe('formatKeys', () => {
  it('maps Mod to ⌘ on macOS', () => {
    expect(formatKeys(['Mod', 'K'], 'mac')).toEqual(['⌘', 'K'])
  })

  it('maps Mod to Ctrl on other platforms', () => {
    expect(formatKeys(['Mod', 'K'], 'other')).toEqual(['Ctrl', 'K'])
  })

  it('substitutes Shift symbol on macOS only', () => {
    expect(formatKeys(['Mod', 'Shift', 'L'], 'mac')).toEqual(['⌘', '⇧', 'L'])
    expect(formatKeys(['Mod', 'Shift', 'L'], 'other')).toEqual([
      'Ctrl',
      'Shift',
      'L',
    ])
  })

  it('replaces Backspace with the ⌫ glyph', () => {
    expect(formatKeys(['Backspace'], 'other')).toEqual(['⌫'])
  })

  it('leaves plain letters untouched', () => {
    expect(formatKeys(['R'], 'mac')).toEqual(['R'])
  })
})

describe('allShortcuts', () => {
  it('returns a flat list covering every category entry', () => {
    const flat = allShortcuts()
    let total = 0
    for (const cat of SHORTCUT_CATEGORIES) total += cat.entries.length
    expect(flat.length).toBe(total)
  })
})
