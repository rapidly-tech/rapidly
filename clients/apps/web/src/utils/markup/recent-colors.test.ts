import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  RECENT_COLORS_LIMIT,
  _resetRecentColorsForTests,
  addRecentColor,
  clearRecentColors,
  getRecentColors,
  subscribeRecentColors,
} from './recent-colors'

beforeEach(() => {
  if (typeof localStorage !== 'undefined') localStorage.clear()
  _resetRecentColorsForTests()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('addRecentColor', () => {
  it('starts empty', () => {
    expect(getRecentColors()).toEqual([])
  })

  it('pushes a colour to the front', () => {
    addRecentColor('#a5d8ff')
    expect(getRecentColors()).toEqual(['#a5d8ff'])
  })

  it('most-recent first when several are added', () => {
    addRecentColor('#a5d8ff')
    addRecentColor('#b2f2bb')
    addRecentColor('#ffec99')
    expect(getRecentColors()).toEqual(['#ffec99', '#b2f2bb', '#a5d8ff'])
  })

  it('dedupes — adding an existing colour moves it to the front', () => {
    addRecentColor('#a5d8ff')
    addRecentColor('#b2f2bb')
    addRecentColor('#a5d8ff')
    expect(getRecentColors()).toEqual(['#a5d8ff', '#b2f2bb'])
  })

  it('canonicalises hex input via normaliseHex', () => {
    addRecentColor('#ABC')
    expect(getRecentColors()).toEqual(['#aabbcc'])
  })

  it('skips transparent', () => {
    addRecentColor('transparent')
    expect(getRecentColors()).toEqual([])
  })

  it('skips an empty / falsy input', () => {
    addRecentColor('')
    expect(getRecentColors()).toEqual([])
  })

  it('caps the LRU at the documented limit', () => {
    for (let i = 0; i < RECENT_COLORS_LIMIT + 5; i++) {
      addRecentColor(`#${i.toString(16).padStart(6, '0')}`)
    }
    const list = getRecentColors()
    expect(list).toHaveLength(RECENT_COLORS_LIMIT)
  })

  it('no-ops when the colour is already at the front', () => {
    const fn = vi.fn()
    subscribeRecentColors(fn)
    addRecentColor('#a5d8ff')
    addRecentColor('#a5d8ff')
    // One state change, one listener call.
    expect(fn).toHaveBeenCalledTimes(1)
  })
})

describe('clearRecentColors', () => {
  it('empties the LRU', () => {
    addRecentColor('#a5d8ff')
    clearRecentColors()
    expect(getRecentColors()).toEqual([])
  })

  it('fires listeners with the empty array', () => {
    addRecentColor('#a5d8ff')
    const fn = vi.fn()
    subscribeRecentColors(fn)
    clearRecentColors()
    expect(fn).toHaveBeenCalledWith([])
  })
})

describe('subscribeRecentColors', () => {
  it('fires on every add', () => {
    const fn = vi.fn()
    subscribeRecentColors(fn)
    addRecentColor('#a5d8ff')
    addRecentColor('#b2f2bb')
    expect(fn).toHaveBeenCalledTimes(2)
    expect(fn).toHaveBeenLastCalledWith(['#b2f2bb', '#a5d8ff'])
  })

  it('returns an unsubscribe handle', () => {
    const fn = vi.fn()
    const unsub = subscribeRecentColors(fn)
    addRecentColor('#a5d8ff')
    unsub()
    addRecentColor('#b2f2bb')
    expect(fn).toHaveBeenCalledTimes(1)
  })
})

describe('persistence (localStorage)', () => {
  it('round-trips through localStorage', () => {
    if (typeof localStorage === 'undefined') return
    addRecentColor('#a5d8ff')
    addRecentColor('#b2f2bb')
    // Drop in-memory cache; next read re-hydrates from storage.
    _resetRecentColorsForTests()
    expect(getRecentColors()).toEqual(['#b2f2bb', '#a5d8ff'])
  })

  it('starts clean when localStorage holds garbage', () => {
    if (typeof localStorage === 'undefined') return
    localStorage.setItem('rapidly:collab:recent-colors:v1', 'not-json')
    _resetRecentColorsForTests()
    expect(getRecentColors()).toEqual([])
  })
})
