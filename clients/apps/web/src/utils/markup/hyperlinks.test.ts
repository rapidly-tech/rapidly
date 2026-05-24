import { describe, expect, it } from 'vitest'
import * as Y from 'yjs'

import { createElementStore, type ElementStore } from './element-store'
import {
  clearLink,
  hasLink,
  isValidUrl,
  normalizeUrl,
  setLink,
} from './hyperlinks'

function rect(store: ElementStore): string {
  return store.create({
    type: 'rect',
    x: 0,
    y: 0,
    width: 10,
    height: 10,
    roundness: 0,
  })
}

describe('normalizeUrl', () => {
  it('adds https:// to a bare host', () => {
    expect(normalizeUrl('example.com')).toBe('https://example.com')
  })

  it('keeps the existing scheme', () => {
    expect(normalizeUrl('http://example.com')).toBe('http://example.com')
    expect(normalizeUrl('mailto:x@y.com')).toBe('mailto:x@y.com')
  })

  it('trims whitespace', () => {
    expect(normalizeUrl('  example.com  ')).toBe('https://example.com')
  })

  it('returns empty on empty input', () => {
    expect(normalizeUrl('')).toBe('')
    expect(normalizeUrl('   ')).toBe('')
  })
})

describe('isValidUrl', () => {
  it('accepts http, https, mailto', () => {
    expect(isValidUrl('http://a.com')).toBe(true)
    expect(isValidUrl('https://a.com')).toBe(true)
    expect(isValidUrl('mailto:x@y.com')).toBe(true)
  })

  it('rejects dangerous schemes', () => {
    expect(isValidUrl('javascript:alert(1)')).toBe(false)
    expect(isValidUrl('data:text/html,abc')).toBe(false)
    expect(isValidUrl('file:///etc/passwd')).toBe(false)
  })

  it('rejects malformed / empty input', () => {
    expect(isValidUrl('')).toBe(false)
    expect(isValidUrl('not a url')).toBe(false)
  })
})

describe('setLink', () => {
  it('writes the normalised URL to each selected element', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    const ok = setLink(store, new Set([a, b]), 'example.com')
    expect(ok).toBe(true)
    expect(store.get(a)!.link).toBe('https://example.com')
    expect(store.get(b)!.link).toBe('https://example.com')
  })

  it('rejects invalid URLs without writing', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    let updates = 0
    doc.on('update', () => {
      updates++
    })
    expect(setLink(store, new Set([a]), 'javascript:evil')).toBe(false)
    expect(updates).toBe(0)
    expect(store.get(a)!.link).toBeUndefined()
  })

  it('empty input clears existing links', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    setLink(store, new Set([a]), 'example.com')
    expect(setLink(store, new Set([a]), '')).toBe(true)
    expect(store.get(a)!.link).toBe('')
  })

  it('no-op on empty selection', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    expect(setLink(store, new Set(), 'example.com')).toBe(false)
  })

  it('emits a single Yjs update per call', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    const c = rect(store)
    let updates = 0
    doc.on('update', () => {
      updates++
    })
    setLink(store, new Set([a, b, c]), 'example.com')
    expect(updates).toBe(1)
  })
})

describe('clearLink', () => {
  it('clears links from every selected element that has one', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    const b = rect(store)
    setLink(store, new Set([a, b]), 'https://example.com')
    expect(clearLink(store, new Set([a, b]))).toBe(true)
    expect(store.get(a)!.link).toBe('')
    expect(store.get(b)!.link).toBe('')
  })

  it('skips elements without a link — no write, returns false', () => {
    const doc = new Y.Doc()
    const store = createElementStore(doc)
    const a = rect(store)
    let updates = 0
    doc.on('update', () => {
      updates++
    })
    expect(clearLink(store, new Set([a]))).toBe(false)
    expect(updates).toBe(0)
  })
})

describe('hasLink', () => {
  it('true only when link is a non-empty string', () => {
    expect(hasLink({ link: 'https://example.com' })).toBe(true)
    expect(hasLink({ link: '' })).toBe(false)
    expect(hasLink({})).toBe(false)
  })
})
