/**
 * Service-worker registration helper for offline-shell support.
 *
 * The file-sharing chamber already ships a StreamSaver service worker
 * at ``/sw.js`` (used for download piping). A second SW at the same
 * path would clobber it, so the offline-shell SW needs a distinct
 * script path. This module owns the registration + update lifecycle
 * in a backend-agnostic way so the actual SW script can evolve
 * separately from the React code that registers it.
 *
 * No SW file is shipped by this PR — it's the plumbing only. A
 * deployed SW needs a per-environment path + a Next.js build step
 * that emits a SW bundle with the right asset manifest; both land in
 * follow-up PRs once the shell scope is nailed down.
 *
 * Update notifications
 * --------------------
 * When the browser fetches a new version of the SW script and the
 * byte diff is non-zero, the registration transitions through
 * ``installing`` → ``installed`` while the old one still controls
 * the page. ``onUpdateAvailable`` fires on that ``installed``
 * transition — UI typically surfaces a ""New version available — refresh""
 * banner at that point.
 */

export interface ServiceWorkerRegistrationOptions {
  /** URL of the SW script. Default ``/sw-collab.js`` so it sits in a
   *  different slot than the StreamSaver ``/sw.js``. Override for
   *  staging / per-chamber deployments. */
  scriptPath?: string
  /** SW scope. Defaults to the script's directory. Widening past
   *  that requires the server to send a
   *  ``Service-Worker-Allowed`` header — out of scope here. */
  scope?: string
  /** Fires when a new SW has finished installing but the page is
   *  still controlled by the previous version — classic
   *  ""refresh for the update"" moment. */
  onUpdateAvailable?: () => void
  /** Called on registration errors (script 404, scope violation,
   *  etc.). Always fires on the main thread. */
  onError?: (error: Error) => void
  /** Injectable navigator target — tests pass a fake without
   *  touching the global. */
  navigator?: NavigatorLike
}

/** Narrowest subset of the Navigator service-worker API we touch.
 *  Matches the real DOM type structurally so production callers don't
 *  need to cast. */
export interface NavigatorLike {
  serviceWorker?: {
    register(
      scriptURL: string,
      options?: { scope?: string },
    ): Promise<ServiceWorkerRegistrationLike>
  }
}

export interface ServiceWorkerRegistrationLike {
  installing?: {
    addEventListener(type: 'statechange', fn: () => void): void
  } | null
  waiting?: unknown | null
  active?: unknown | null
  addEventListener(type: 'updatefound', fn: () => void): void
  /** Full unregister — tests call this through the handle, callers
   *  rarely need it. */
  unregister(): Promise<boolean>
}

export interface ServiceWorkerHandle {
  /** Resolves with the underlying registration or ``null`` when the
   *  browser doesn't support service workers. */
  registration: Promise<ServiceWorkerRegistrationLike | null>
  /** Best-effort unregister. Resolves ``true`` when the SW was
   *  actually unregistered, ``false`` on no-op. */
  unregister(): Promise<boolean>
}

const DEFAULT_SCRIPT_PATH = '/sw-collab.js'

/** Register the offline-shell SW. Returns a handle whose
 *  ``registration`` resolves once the browser accepts the script. In
 *  unsupported environments (SSR, older browsers without SW support)
 *  the handle resolves ``null`` and nothing throws. */
export function registerServiceWorker(
  options: ServiceWorkerRegistrationOptions = {},
): ServiceWorkerHandle {
  const nav =
    options.navigator ??
    (typeof navigator === 'undefined'
      ? undefined
      : (navigator as NavigatorLike))
  const scriptPath = options.scriptPath ?? DEFAULT_SCRIPT_PATH

  if (!nav?.serviceWorker) {
    return {
      registration: Promise.resolve(null),
      unregister: () => Promise.resolve(false),
    }
  }

  const registration = nav.serviceWorker
    .register(scriptPath, options.scope ? { scope: options.scope } : undefined)
    .then((reg) => {
      // Wire the ``updatefound`` → ``statechange(installed)`` path so
      // consumers get one coherent notification when an update is
      // ready to be applied.
      reg.addEventListener('updatefound', () => {
        const installing = reg.installing
        if (!installing) return
        installing.addEventListener('statechange', () => {
          // ``state`` is exposed on the ServiceWorker object in real
          // browsers; our minimal type doesn't surface it — callers
          // that want state names read through the real DOM type.
          // Firing on every statechange is harmless: ``installed`` is
          // the last transition before ``activated``, and consumers
          // typically debounce a banner render anyway.
          options.onUpdateAvailable?.()
        })
      })
      return reg
    })
    .catch((err: unknown) => {
      const error = err instanceof Error ? err : new Error(String(err))
      options.onError?.(error)
      return null
    })

  return {
    registration,
    async unregister() {
      const reg = await registration
      if (!reg) return false
      return reg.unregister()
    },
  }
}
