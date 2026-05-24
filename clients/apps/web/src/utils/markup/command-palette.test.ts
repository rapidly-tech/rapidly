import { describe, expect, it, vi } from 'vitest'

import { dedupeCommands, matchCommands, type Command } from './command-palette'

function cmd(id: string, label: string, extra: Partial<Command> = {}): Command {
  return { id, label, run: vi.fn(), ...extra }
}

describe('matchCommands', () => {
  const commands: Command[] = [
    cmd('tool.rect', 'Rectangle'),
    cmd('tool.ellipse', 'Ellipse'),
    cmd('edit.copy', 'Copy selection'),
    cmd('edit.paste', 'Paste from clipboard', { keywords: ['image'] }),
    cmd('export.png', 'Export PNG'),
    cmd('lock.toggle', 'Toggle lock'),
  ]

  it('returns the full list untouched on an empty query', () => {
    expect(matchCommands('', commands)).toEqual(commands)
    expect(matchCommands('   ', commands)).toEqual(commands)
  })

  it('ranks prefix matches above word-start matches above contains', () => {
    const out = matchCommands('p', commands)
    // Paste starts with "p" → 100.
    // Export PNG: word "PNG" starts with "p" → 70.
    // Any other "contains p" (Ellipse, Copy selection) rank below the
    // word-start matches.
    expect(out[0].id).toBe('edit.paste')
    expect(out[1].id).toBe('export.png')
    expect(out.slice(2).map((c) => c.id)).toContain('edit.copy')
  })

  it('word-start match beats mere contains', () => {
    const out = matchCommands('se', commands)
    // "Copy selection" — "selection" starts with "se" → 70
    expect(out[0].id).toBe('edit.copy')
  })

  it('keyword match falls below label matches', () => {
    // "image" as a keyword on Paste. Query "image" has no label match
    // anywhere, so Paste should surface via its keyword.
    const out = matchCommands('image', commands)
    expect(out).toHaveLength(1)
    expect(out[0].id).toBe('edit.paste')
  })

  it('drops non-matching commands entirely', () => {
    const out = matchCommands('xyzzy', commands)
    expect(out).toEqual([])
  })

  it('is case-insensitive', () => {
    expect(matchCommands('RECT', commands).map((c) => c.id)).toEqual([
      'tool.rect',
    ])
  })

  it('tiebreaks on original order', () => {
    const list: Command[] = [cmd('a', 'Alpha beta'), cmd('b', 'Alpha gamma')]
    // Both start with "alpha" → both score 100; original order wins.
    const out = matchCommands('alpha', list)
    expect(out.map((c) => c.id)).toEqual(['a', 'b'])
  })
})

describe('dedupeCommands', () => {
  it('keeps the first occurrence of each id', () => {
    const a = cmd('x', 'First')
    const b = cmd('x', 'Second')
    const c = cmd('y', 'Y')
    const out = dedupeCommands([a, b, c])
    expect(out).toHaveLength(2)
    expect(out[0]).toBe(a)
    expect(out[1]).toBe(c)
  })

  it('preserves order for non-duplicates', () => {
    const a = cmd('a', 'A')
    const b = cmd('b', 'B')
    expect(dedupeCommands([a, b])).toEqual([a, b])
  })
})
