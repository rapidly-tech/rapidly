import { describe, expect, it, vi } from 'vitest'

import {
  createPointerPreference,
  HANDLE_SIZE_FOR_PRECISION,
} from './pointer-preference'

function fakeMatchMedia(initialCoarse: boolean) {
  let coarse = initialCoarse
  const listeners = new Set<() => void>()
  const mql = {
    get matches() {
      return coarse
    },
    addEventListener(_type: string, fn: () => void) {
      listeners.add(fn)
    },
    removeEventListener(_type: string, fn: () => void) {
      listeners.delete(fn)
    },
  }
  return {
    window: {
      matchMedia: (_q: string) => mql,
    } as unknown as Window,
    set(next: boolean) {
      coarse = next
      for (const fn of listeners) fn()
    },
    listenerCount(): number {
      return listeners.size
    },
  }
}

describe('createPointerPreference', () => {
  it('reports fine pointer on desktop-like defaults', () => {
    const { window } = fakeMatchMedia(false)
    const pref = createPointerPreference({ window })
    expect(pref.current()).toBe('fine')
    pref.dispose()
  })

  it('reports coarse pointer on touch-like defaults', () => {
    const { window } = fakeMatchMedia(true)
    const pref = createPointerPreference({ window })
    expect(pref.current()).toBe('coarse')
    pref.dispose()
  })

  it('subscribe fires on media-query change', () => {
    const { window, set } = fakeMatchMedia(false)
    const pref = createPointerPreference({ window })
    const listener = vi.fn()
    pref.subscribe(listener)
    set(true)
    expect(listener).toHaveBeenCalledWith('coarse')
    set(false)
    expect(listener).toHaveBeenLastCalledWith('fine')
    pref.dispose()
  })

  it('current() re-evaluates rather than reading a cached value', () => {
    const { window, set } = fakeMatchMedia(false)
    const pref = createPointerPreference({ window })
    expect(pref.current()).toBe('fine')
    set(true)
    expect(pref.current()).toBe('coarse')
    pref.dispose()
  })

  it('dispose removes the media-query listener', () => {
    const { window, listenerCount } = fakeMatchMedia(false)
    const pref = createPointerPreference({ window })
    pref.subscribe(() => {})
    expect(listenerCount()).toBe(1)
    pref.dispose()
    expect(listenerCount()).toBe(0)
  })

  it('unsubscribe stops further firing', () => {
    const { window, set } = fakeMatchMedia(false)
    const pref = createPointerPreference({ window })
    const listener = vi.fn()
    const off = pref.subscribe(listener)
    off()
    set(true)
    expect(listener).not.toHaveBeenCalled()
    pref.dispose()
  })

  it('SSR-safe: returns "fine" and never throws when window is absent', () => {
    const pref = createPointerPreference({
      window: undefined as unknown as Window,
    })
    expect(pref.current()).toBe('fine')
    pref.dispose()
  })

  it('falls back to the deprecated addListener API when addEventListener is missing', () => {
    const listeners = new Set<() => void>()
    const mql = {
      matches: false,
      addListener(fn: () => void) {
        listeners.add(fn)
      },
      removeListener(fn: () => void) {
        listeners.delete(fn)
      },
    }
    const win = {
      matchMedia: (_q: string) => mql,
    } as unknown as Window
    const pref = createPointerPreference({ window: win })
    // Listener was attached via the deprecated method.
    expect(listeners.size).toBe(1)
    pref.dispose()
    expect(listeners.size).toBe(0)
  })
})

describe('HANDLE_SIZE_FOR_PRECISION', () => {
  it('coarse is larger than fine', () => {
    expect(HANDLE_SIZE_FOR_PRECISION.coarse).toBeGreaterThan(
      HANDLE_SIZE_FOR_PRECISION.fine,
    )
  })

  it('coarse meets the accessible-touch-target floor (≥ 24 px)', () => {
    // Halved from Material's 48 dp recommendation — enough slack that
    // users' fingers don't cover neighbouring handles.
    expect(HANDLE_SIZE_FOR_PRECISION.coarse).toBeGreaterThanOrEqual(24)
  })
})
