/**
 * View-mode predicates — pinned behaviour:
 *
 * - Read-only tools: hand + select. Everything else is editing.
 * - Read-only shortcuts (whitelist): h/v tool keys, Escape, '?',
 *   Cmd+Shift+P palette, Cmd+C copy. Everything else is denied.
 * - Read-only palette ids: view.*, export.*, help.*, tool.hand,
 *   tool.select.
 */

import { describe, expect, it } from 'vitest'

import {
  isReadOnlyPaletteCommand,
  isReadOnlyTool,
  isViewModeShortcutAllowed,
  isViewModeUrl,
  withViewModeUrl,
} from './view-mode'

describe('isReadOnlyTool', () => {
  it('allows hand and select', () => {
    expect(isReadOnlyTool('hand')).toBe(true)
    expect(isReadOnlyTool('select')).toBe(true)
  })

  it('denies every editing tool', () => {
    for (const id of [
      'rect',
      'ellipse',
      'diamond',
      'arrow',
      'line',
      'freedraw',
      'text',
      'sticky',
      'eraser',
    ] as const) {
      expect(isReadOnlyTool(id)).toBe(false)
    }
  })
})

describe('isViewModeShortcutAllowed', () => {
  it('allows h and v tool keys', () => {
    expect(isViewModeShortcutAllowed({ key: 'h' })).toBe(true)
    expect(isViewModeShortcutAllowed({ key: 'v' })).toBe(true)
  })

  it('allows Escape and ?', () => {
    expect(isViewModeShortcutAllowed({ key: 'Escape' })).toBe(true)
    expect(isViewModeShortcutAllowed({ key: '?' })).toBe(true)
  })

  it('allows Cmd+Shift+P', () => {
    expect(
      isViewModeShortcutAllowed({ key: 'p', metaKey: true, shiftKey: true }),
    ).toBe(true)
    expect(
      isViewModeShortcutAllowed({ key: 'P', ctrlKey: true, shiftKey: true }),
    ).toBe(true)
  })

  it('allows Cmd+C copy (read-only)', () => {
    expect(isViewModeShortcutAllowed({ key: 'c', metaKey: true })).toBe(true)
    expect(isViewModeShortcutAllowed({ key: 'c', ctrlKey: true })).toBe(true)
  })

  it('denies every editing shortcut', () => {
    for (const e of [
      { key: 'Delete' },
      { key: 'Backspace' },
      { key: 'v', metaKey: true }, // paste
      { key: 'x', metaKey: true }, // cut
      { key: 'd', metaKey: true }, // duplicate
      { key: 'g', metaKey: true }, // group
      { key: 'z', metaKey: true }, // undo
      { key: 'y', metaKey: true }, // redo
      { key: 'k', metaKey: true }, // hyperlink
      { key: 'l', metaKey: true, shiftKey: true }, // lock
      { key: ']', metaKey: true }, // forward
      { key: '[', metaKey: true }, // backward
      { key: 'r' }, // rect tool
      { key: 'o' }, // ellipse tool
      { key: 'd' }, // diamond tool
      { key: 'l' }, // line tool
    ]) {
      expect(isViewModeShortcutAllowed(e)).toBe(false)
    }
  })
})

describe('isReadOnlyPaletteCommand', () => {
  it('allows view.*, export.*, help.* commands', () => {
    expect(isReadOnlyPaletteCommand('view.zoomToFit')).toBe(true)
    expect(isReadOnlyPaletteCommand('view.toggleGrid')).toBe(true)
    expect(isReadOnlyPaletteCommand('export.png')).toBe(true)
    expect(isReadOnlyPaletteCommand('help.shortcuts')).toBe(true)
  })

  it('allows tool.hand and tool.select', () => {
    expect(isReadOnlyPaletteCommand('tool.hand')).toBe(true)
    expect(isReadOnlyPaletteCommand('tool.select')).toBe(true)
  })

  it('denies edit / align / import / mutating tool commands', () => {
    expect(isReadOnlyPaletteCommand('edit.undo')).toBe(false)
    expect(isReadOnlyPaletteCommand('edit.flipHorizontal')).toBe(false)
    expect(isReadOnlyPaletteCommand('edit.align.left')).toBe(false)
    expect(isReadOnlyPaletteCommand('import.json')).toBe(false)
    expect(isReadOnlyPaletteCommand('import.mermaid')).toBe(false)
    expect(isReadOnlyPaletteCommand('tool.rect')).toBe(false)
    expect(isReadOnlyPaletteCommand('tool.eraser')).toBe(false)
  })
})

describe('isViewModeUrl', () => {
  it('returns true for the canonical ?view=1 form', () => {
    expect(isViewModeUrl('?view=1')).toBe(true)
    expect(isViewModeUrl('?view=true')).toBe(true)
    expect(isViewModeUrl('?view=YES')).toBe(true)
    expect(isViewModeUrl('?view=on')).toBe(true)
  })

  it('parses a full URL', () => {
    expect(
      isViewModeUrl('https://rapidly.tech/collab/abc?view=1#key=...'),
    ).toBe(true)
  })

  it('returns false on missing or falsy values', () => {
    expect(isViewModeUrl('')).toBe(false)
    expect(isViewModeUrl('?other=1')).toBe(false)
    expect(isViewModeUrl('?view=0')).toBe(false)
    expect(isViewModeUrl('?view=false')).toBe(false)
  })

  it('handles a query string without the leading ?', () => {
    expect(isViewModeUrl('view=1')).toBe(true)
    expect(isViewModeUrl('view=0')).toBe(false)
  })
})

describe('withViewModeUrl', () => {
  it('adds ?view=1 to a clean URL', () => {
    expect(withViewModeUrl('https://rapidly.tech/collab/abc')).toBe(
      'https://rapidly.tech/collab/abc?view=1',
    )
  })

  it('preserves existing query params', () => {
    const out = withViewModeUrl('https://rapidly.tech/collab/abc?token=xyz')
    expect(out).toContain('token=xyz')
    expect(out).toContain('view=1')
  })

  it('replaces an existing view value', () => {
    expect(withViewModeUrl('https://rapidly.tech/collab/abc?view=0')).toContain(
      'view=1',
    )
  })

  it('preserves the URL fragment (E2EE invite keys)', () => {
    expect(withViewModeUrl('https://rapidly.tech/collab/abc#k=secret')).toBe(
      'https://rapidly.tech/collab/abc?view=1#k=secret',
    )
  })
})
