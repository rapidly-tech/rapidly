import { describe, expect, it, vi } from 'vitest'

import {
  createInstallPromptController,
  type InstallPromptEvent,
} from './install-prompt'

function fakeTarget() {
  const listeners = new Map<string, Set<(e: Event) => void>>()
  return {
    target: {
      addEventListener(type: string, l: (e: Event) => void) {
        if (!listeners.has(type)) listeners.set(type, new Set())
        listeners.get(type)!.add(l)
      },
      removeEventListener(type: string, l: (e: Event) => void) {
        listeners.get(type)?.delete(l)
      },
    },
    dispatch(type: string, event: Event) {
      const batch = listeners.get(type)
      if (!batch) return
      for (const l of batch) l(event)
    },
    has(type: string): boolean {
      return (listeners.get(type)?.size ?? 0) > 0
    },
  }
}

function fakePromptEvent(outcome: 'accepted' | 'dismissed' = 'accepted'): {
  event: InstallPromptEvent
  prompt: ReturnType<typeof vi.fn>
} {
  const prompt = vi.fn().mockResolvedValue(undefined)
  const event = {
    preventDefault: vi.fn(),
    prompt,
    userChoice: Promise.resolve({ outcome, platform: 'web' }),
  } as unknown as InstallPromptEvent
  return { event, prompt }
}

describe('createInstallPromptController', () => {
  it('returns a no-op controller in SSR (no window)', async () => {
    const ctrl = createInstallPromptController({
      target: undefined as unknown as Window,
    })
    expect(ctrl.canInstall()).toBe(false)
    expect(await ctrl.install()).toBeNull()
    ctrl.dispose()
  })

  it('starts with canInstall = false', () => {
    const { target } = fakeTarget()
    const ctrl = createInstallPromptController({ target })
    expect(ctrl.canInstall()).toBe(false)
    ctrl.dispose()
  })

  it('captures the deferred prompt and flips canInstall', () => {
    const { target, dispatch } = fakeTarget()
    const ctrl = createInstallPromptController({ target })
    const { event } = fakePromptEvent()
    dispatch('beforeinstallprompt', event)
    expect(ctrl.canInstall()).toBe(true)
    ctrl.dispose()
  })

  it('preventDefault is called so the browser does not show its own prompt', () => {
    const { target, dispatch } = fakeTarget()
    const ctrl = createInstallPromptController({ target })
    const { event } = fakePromptEvent()
    dispatch('beforeinstallprompt', event)
    expect(
      (event as unknown as { preventDefault: ReturnType<typeof vi.fn> })
        .preventDefault,
    ).toHaveBeenCalled()
    ctrl.dispose()
  })

  it('install() returns null when no prompt is available', async () => {
    const { target } = fakeTarget()
    const ctrl = createInstallPromptController({ target })
    expect(await ctrl.install()).toBeNull()
    ctrl.dispose()
  })

  it('install() fires the browser prompt and returns the user outcome', async () => {
    const { target, dispatch } = fakeTarget()
    const ctrl = createInstallPromptController({ target })
    const { event, prompt } = fakePromptEvent('accepted')
    dispatch('beforeinstallprompt', event)
    const outcome = await ctrl.install()
    expect(prompt).toHaveBeenCalled()
    expect(outcome).toBe('accepted')
  })

  it('install() consumes the prompt — second call returns null', async () => {
    const { target, dispatch } = fakeTarget()
    const ctrl = createInstallPromptController({ target })
    const { event } = fakePromptEvent()
    dispatch('beforeinstallprompt', event)
    await ctrl.install()
    expect(ctrl.canInstall()).toBe(false)
    expect(await ctrl.install()).toBeNull()
    ctrl.dispose()
  })

  it('appinstalled event clears canInstall even without install() being called', () => {
    const { target, dispatch } = fakeTarget()
    const ctrl = createInstallPromptController({ target })
    dispatch('beforeinstallprompt', fakePromptEvent().event)
    expect(ctrl.canInstall()).toBe(true)
    dispatch('appinstalled', new Event('appinstalled'))
    expect(ctrl.canInstall()).toBe(false)
    ctrl.dispose()
  })

  it('subscribe fires on prompt arrival, install, and appinstalled', async () => {
    const { target, dispatch } = fakeTarget()
    const ctrl = createInstallPromptController({ target })
    const fn = vi.fn()
    ctrl.subscribe(fn)
    dispatch('beforeinstallprompt', fakePromptEvent().event)
    expect(fn).toHaveBeenCalledTimes(1)
    await ctrl.install()
    expect(fn.mock.calls.length).toBeGreaterThanOrEqual(2)
    ctrl.dispose()
  })

  it('dispose removes listeners so the target stops firing', () => {
    const { target, dispatch, has } = fakeTarget()
    const ctrl = createInstallPromptController({ target })
    expect(has('beforeinstallprompt')).toBe(true)
    ctrl.dispose()
    expect(has('beforeinstallprompt')).toBe(false)
    // Subsequent dispatches don't flip state.
    dispatch('beforeinstallprompt', fakePromptEvent().event)
    expect(ctrl.canInstall()).toBe(false)
  })
})
