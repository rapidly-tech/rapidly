import { describe, expect, it } from 'vitest'

import { TOOL_KEY_MAP, toolIdForKey } from './tool-keys'

describe('TOOL_KEY_MAP', () => {
  it('covers every tool the demo exposes', () => {
    const expected = [
      'hand',
      'select',
      'rect',
      'ellipse',
      'diamond',
      'line',
      'arrow',
      'freedraw',
      'text',
      'sticky',
    ]
    const bound = Object.values(TOOL_KEY_MAP)
    for (const id of expected) expect(bound).toContain(id)
  })

  it('maps canonical Excalidraw-style letters', () => {
    expect(TOOL_KEY_MAP.h).toBe('hand')
    expect(TOOL_KEY_MAP.v).toBe('select')
    expect(TOOL_KEY_MAP.r).toBe('rect')
    expect(TOOL_KEY_MAP.o).toBe('ellipse')
    expect(TOOL_KEY_MAP.d).toBe('diamond')
    expect(TOOL_KEY_MAP.l).toBe('line')
    expect(TOOL_KEY_MAP.a).toBe('arrow')
    expect(TOOL_KEY_MAP.p).toBe('freedraw')
    expect(TOOL_KEY_MAP.t).toBe('text')
    expect(TOOL_KEY_MAP.s).toBe('sticky')
  })
})

describe('toolIdForKey', () => {
  it('maps a plain letter to its tool', () => {
    expect(toolIdForKey({ key: 'r' })).toBe('rect')
    expect(toolIdForKey({ key: 'V' })).toBe('select')
  })

  it('returns null when any modifier is pressed', () => {
    expect(toolIdForKey({ key: 'd', metaKey: true })).toBeNull()
    expect(toolIdForKey({ key: 'd', ctrlKey: true })).toBeNull()
    expect(toolIdForKey({ key: 'd', altKey: true })).toBeNull()
  })

  it('returns null for unbound letters', () => {
    expect(toolIdForKey({ key: 'z' })).toBeNull()
    expect(toolIdForKey({ key: 'w' })).toBeNull()
  })

  it('returns null for non-letter keys', () => {
    expect(toolIdForKey({ key: 'Enter' })).toBeNull()
    expect(toolIdForKey({ key: ' ' })).toBeNull()
  })

  it('maps Excalidraw-style number aliases', () => {
    expect(toolIdForKey({ key: '1' })).toBe('select')
    expect(toolIdForKey({ key: '2' })).toBe('rect')
    expect(toolIdForKey({ key: '3' })).toBe('diamond')
    expect(toolIdForKey({ key: '4' })).toBe('ellipse')
    expect(toolIdForKey({ key: '5' })).toBe('arrow')
    expect(toolIdForKey({ key: '6' })).toBe('line')
    expect(toolIdForKey({ key: '7' })).toBe('freedraw')
    expect(toolIdForKey({ key: '8' })).toBe('text')
    expect(toolIdForKey({ key: '0' })).toBe('eraser')
  })

  it('lets Shift+1/2/3 fall through so zoom shortcuts can claim them', () => {
    expect(toolIdForKey({ key: '1', shiftKey: true })).toBeNull()
    expect(toolIdForKey({ key: '2', shiftKey: true })).toBeNull()
    expect(toolIdForKey({ key: '3', shiftKey: true })).toBeNull()
  })

  it('returns null when the event target is a form input', () => {
    const target = { tagName: 'INPUT' } as unknown as HTMLElement
    expect(toolIdForKey({ key: 'r', target })).toBeNull()
  })

  it('returns null when focus is in a textarea or contenteditable', () => {
    const ta = { tagName: 'TEXTAREA' } as unknown as HTMLElement
    expect(toolIdForKey({ key: 'r', target: ta })).toBeNull()
    const ce = {
      tagName: 'DIV',
      isContentEditable: true,
    } as unknown as HTMLElement
    expect(toolIdForKey({ key: 'r', target: ce })).toBeNull()
  })
})
