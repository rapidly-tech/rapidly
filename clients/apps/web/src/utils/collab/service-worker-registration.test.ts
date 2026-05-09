import { describe, expect, it, vi } from 'vitest'

import {
  registerServiceWorker,
  type NavigatorLike,
  type ServiceWorkerRegistrationLike,
} from './service-worker-registration'

function fakeRegistration(): {
  reg: ServiceWorkerRegistrationLike
  fireUpdate: () => void
  fireInstalled: () => void
  setInstallingState: (state: string) => void
} {
  const updateListeners = new Set<() => void>()
  const installingListeners = new Set<() => void>()
  const installing: NonNullable<ServiceWorkerRegistrationLike['installing']> = {
    addEventListener(type: 'statechange', fn: () => void) {
      if (type === 'statechange') installingListeners.add(fn)
    },
    state: 'installing',
  }
  const reg: ServiceWorkerRegistrationLike = {
    installing,
    waiting: null,
    active: null,
    addEventListener(type: 'updatefound', fn: () => void) {
      if (type === 'updatefound') updateListeners.add(fn)
    },
    unregister: vi.fn(async () => true),
  }
  return {
    reg,
    fireUpdate: () => {
      for (const fn of updateListeners) fn()
    },
    fireInstalled: () => {
      installing.state = 'installed'
      for (const fn of installingListeners) fn()
    },
    setInstallingState: (state) => {
      installing.state = state
    },
  }
}

function fakeNavigator(
  outcome: 'ok' | 'error',
  reg?: ServiceWorkerRegistrationLike,
  opts: { hasController?: boolean } = { hasController: true },
): { navigator: NavigatorLike; register: ReturnType<typeof vi.fn> } {
  const register = vi.fn(async () => {
    if (outcome === 'error') throw new Error('script 404')
    return reg!
  })
  return {
    navigator: {
      serviceWorker: {
        register,
        controller: opts.hasController ? {} : null,
      },
    },
    register,
  }
}

describe('registerServiceWorker', () => {
  it('returns a null registration when the browser has no serviceWorker API', async () => {
    const handle = registerServiceWorker({
      navigator: {} as NavigatorLike,
    })
    expect(await handle.registration).toBeNull()
    expect(await handle.unregister()).toBe(false)
  })

  it('calls navigator.serviceWorker.register with the script path', async () => {
    const { reg } = fakeRegistration()
    const { navigator, register } = fakeNavigator('ok', reg)
    const handle = registerServiceWorker({
      navigator,
      scriptPath: '/sw-custom.js',
    })
    await handle.registration
    expect(register).toHaveBeenCalledWith('/sw-custom.js', undefined)
  })

  it('passes scope when provided', async () => {
    const { reg } = fakeRegistration()
    const { navigator, register } = fakeNavigator('ok', reg)
    registerServiceWorker({ navigator, scope: '/collab/' })
    // Need to await the microtask queue so the register call resolves.
    await Promise.resolve()
    expect(register).toHaveBeenCalledWith('/sw-collab.js', {
      scope: '/collab/',
    })
  })

  it('defaults to /sw-collab.js (not /sw.js which StreamSaver owns)', async () => {
    const { reg } = fakeRegistration()
    const { navigator, register } = fakeNavigator('ok', reg)
    registerServiceWorker({ navigator })
    await Promise.resolve()
    const arg = register.mock.calls[0][0]
    expect(arg).toBe('/sw-collab.js')
    expect(arg).not.toBe('/sw.js')
  })

  it('forwards registration errors to onError + resolves null', async () => {
    const { navigator } = fakeNavigator('error')
    const onError = vi.fn()
    const handle = registerServiceWorker({ navigator, onError })
    expect(await handle.registration).toBeNull()
    expect(onError).toHaveBeenCalled()
    expect(onError.mock.calls[0][0]).toBeInstanceOf(Error)
    expect(onError.mock.calls[0][0].message).toContain('script 404')
  })

  it('fires onUpdateAvailable once the installing worker reaches installed', async () => {
    const { reg, fireUpdate, fireInstalled } = fakeRegistration()
    const { navigator } = fakeNavigator('ok', reg)
    const onUpdateAvailable = vi.fn()
    const handle = registerServiceWorker({ navigator, onUpdateAvailable })
    await handle.registration
    fireUpdate()
    fireInstalled()
    expect(onUpdateAvailable).toHaveBeenCalledTimes(1)
  })

  it('does not fire on the first install (no existing controller)', async () => {
    const { reg, fireUpdate, fireInstalled } = fakeRegistration()
    const { navigator } = fakeNavigator('ok', reg, { hasController: false })
    const onUpdateAvailable = vi.fn()
    const handle = registerServiceWorker({ navigator, onUpdateAvailable })
    await handle.registration
    fireUpdate()
    fireInstalled()
    expect(onUpdateAvailable).not.toHaveBeenCalled()
  })

  it('does not fire on intermediate statechanges before installed', async () => {
    const { reg, fireUpdate, setInstallingState } = fakeRegistration()
    const installingListeners: Array<() => void> = []
    // Re-wire to capture statechange listeners and fire them with a
    // pre-installed state so we can assert the gate ignores them.
    reg.installing!.addEventListener = (
      type: 'statechange',
      fn: () => void,
    ) => {
      if (type === 'statechange') installingListeners.push(fn)
    }
    const { navigator } = fakeNavigator('ok', reg)
    const onUpdateAvailable = vi.fn()
    const handle = registerServiceWorker({ navigator, onUpdateAvailable })
    await handle.registration
    fireUpdate()
    setInstallingState('installing')
    for (const fn of installingListeners) fn()
    expect(onUpdateAvailable).not.toHaveBeenCalled()
  })

  it('no onUpdateAvailable fires before updatefound', async () => {
    const { reg, fireInstalled } = fakeRegistration()
    const { navigator } = fakeNavigator('ok', reg)
    const onUpdateAvailable = vi.fn()
    const handle = registerServiceWorker({ navigator, onUpdateAvailable })
    await handle.registration
    // Force a spurious statechange without an updatefound first.
    fireInstalled()
    expect(onUpdateAvailable).not.toHaveBeenCalled()
  })

  it('unregister proxies through to the registration', async () => {
    const { reg } = fakeRegistration()
    const { navigator } = fakeNavigator('ok', reg)
    const handle = registerServiceWorker({ navigator })
    await handle.registration
    expect(await handle.unregister()).toBe(true)
    expect(reg.unregister).toHaveBeenCalled()
  })

  it('unregister returns false when registration never resolved to a handle', async () => {
    const { navigator } = fakeNavigator('error')
    const handle = registerServiceWorker({ navigator, onError: () => {} })
    expect(await handle.unregister()).toBe(false)
  })
})
