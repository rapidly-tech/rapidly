/**
 * PWA install prompt controller.
 *
 * Chromium-based browsers fire ``beforeinstallprompt`` on pages that
 * meet the install criteria (HTTPS, manifest present, icons resolved,
 * engagement heuristics). The event ships a deferred prompt which the
 * page can ``prompt()`` at a user-triggered moment — exactly what we
 * want for a ""Install as app"" button in the Collab demo toolbar.
 *
 * Firefox + Safari don't fire the event; ``canInstall`` just returns
 * ``false`` and the UI hides the button.
 *
 * Why a controller (not raw event)
 * --------------------------------
 * The event fires exactly once and *keeps* the deferred prompt alive
 * until a page refresh. A thin controller lets React components mount
 * late without missing the event, and normalises the ""installed now""
 * transition (``appinstalled`` clears the button).
 */

/** Narrowed shape of the event the browser fires. Not in lib.dom.d.ts
 *  for every TS target, so we describe exactly the API we touch. */
export interface InstallPromptEvent extends Event {
  prompt(): Promise<void>
  readonly userChoice: Promise<{
    outcome: 'accepted' | 'dismissed'
    platform: string
  }>
}

export interface InstallPromptController {
  /** True once the browser has offered an install prompt and the user
   *  hasn't accepted / dismissed it yet. */
  canInstall(): boolean
  /** Fire the deferred browser prompt. Resolves with ``'accepted'``
   *  or ``'dismissed'``. Returns ``null`` when no prompt is
   *  available (Safari / Firefox / already installed). */
  install(): Promise<'accepted' | 'dismissed' | null>
  /** Subscribe to availability changes. Fires on prompt arrival,
   *  consumption, and ``appinstalled``. */
  subscribe(fn: () => void): () => void
  /** Tear down listeners — call from useEffect cleanup. */
  dispose(): void
}

export interface InstallPromptOptions {
  /** Attach target — defaults to ``window``. Injected by tests. */
  target?: {
    addEventListener: (type: string, listener: (e: Event) => void) => void
    removeEventListener: (type: string, listener: (e: Event) => void) => void
  }
}

/** Start watching for the install prompt. Safe in SSR (resolves a
 *  noop controller). */
export function createInstallPromptController(
  options: InstallPromptOptions = {},
): InstallPromptController {
  const target =
    options.target ?? (typeof window === 'undefined' ? null : window)
  if (!target) {
    return noopController()
  }

  let deferred: InstallPromptEvent | null = null
  const listeners = new Set<() => void>()
  const emit = (): void => {
    for (const fn of listeners) fn()
  }

  const onBeforeInstallPrompt = (e: Event): void => {
    // The spec says the page must call preventDefault to retain the
    // deferred prompt for later firing. Skipping it would let the
    // browser show its own install UI immediately.
    e.preventDefault()
    deferred = e as InstallPromptEvent
    emit()
  }

  const onAppInstalled = (): void => {
    // Once the user installs, the deferred prompt is consumed. Some
    // browsers fire ``appinstalled`` here; others just leave the
    // prompt silent. Clear state either way.
    deferred = null
    emit()
  }

  target.addEventListener('beforeinstallprompt', onBeforeInstallPrompt)
  target.addEventListener('appinstalled', onAppInstalled)

  return {
    canInstall() {
      return deferred !== null
    },
    async install() {
      if (!deferred) return null
      const prompt = deferred
      // Clear before awaiting so rapid double-clicks can't double-
      // fire the prompt — once consumed, the event is single-use.
      deferred = null
      emit()
      await prompt.prompt()
      const choice = await prompt.userChoice
      return choice.outcome
    },
    subscribe(fn) {
      listeners.add(fn)
      return () => {
        listeners.delete(fn)
      }
    },
    dispose() {
      target.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt)
      target.removeEventListener('appinstalled', onAppInstalled)
      listeners.clear()
      deferred = null
    },
  }
}

function noopController(): InstallPromptController {
  return {
    canInstall: () => false,
    install: async () => null,
    subscribe: () => () => {},
    dispose: () => {},
  }
}
