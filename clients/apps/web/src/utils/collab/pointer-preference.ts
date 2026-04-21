/**
 * Pointer-precision detection.
 *
 * The ``(pointer: coarse)`` / ``(pointer: fine)`` CSS media queries
 * describe the **primary** input device: fine = mouse / stylus,
 * coarse = finger. Chrome + Safari + Firefox all support it; it's
 * more reliable than sniffing ``ontouchstart`` because modern laptops
 * with touchscreens report ``any-pointer: coarse`` but ``pointer:
 * fine`` — meaning the user is primarily driving with a trackpad.
 *
 * This module owns that query behind a tiny controller so the
 * renderer overlay + tool system can branch on the result *and* on
 * later changes (user picks up a second display with a different
 * primary pointer, OS-level setting toggles, etc.).
 */

export type PointerPrecision = 'coarse' | 'fine'

export interface PointerPreference {
  /** Current reading — re-evaluates the media query on every call so
   *  a stale closure never ships a wrong answer. */
  current(): PointerPrecision
  /** Subscribe to changes. Fires whenever the media query flips. */
  subscribe(fn: (precision: PointerPrecision) => void): () => void
  /** Remove all listeners. Idempotent. */
  dispose(): void
}

export interface PointerPreferenceOptions {
  /** Override the lookup target. Defaults to ``window``. Injected by
   *  tests so they can drive the query without the real DOM. */
  window?: Pick<Window, 'matchMedia'>
}

/** Build a pointer-preference observer. Safe in SSR (``window``
 *  absent) — the controller returns ``fine`` and never fires. */
export function createPointerPreference(
  options: PointerPreferenceOptions = {},
): PointerPreference {
  const win = options.window ?? (typeof window === 'undefined' ? null : window)
  if (!win || typeof win.matchMedia !== 'function') return noopPreference()

  // One MQL per precision — we only subscribe to the ``coarse`` one
  // because the two are complements, and MQL lists browsers provide
  // explicit ``matches`` readings on both without needing a second
  // listener.
  const coarse = win.matchMedia('(pointer: coarse)')
  const listeners = new Set<(p: PointerPrecision) => void>()

  const read = (): PointerPrecision => (coarse.matches ? 'coarse' : 'fine')

  const onChange = (): void => {
    const current = read()
    for (const fn of listeners) fn(current)
  }

  // Older Safari + some Android browsers still only expose
  // ``addListener`` (the deprecated name). Prefer the modern API but
  // fall back so we don't silently skip events there.
  if (typeof coarse.addEventListener === 'function') {
    coarse.addEventListener('change', onChange)
  } else if (
    typeof (coarse as unknown as { addListener?: (fn: () => void) => void })
      .addListener === 'function'
  ) {
    ;(
      coarse as unknown as { addListener: (fn: () => void) => void }
    ).addListener(onChange)
  }

  return {
    current: read,
    subscribe(fn) {
      listeners.add(fn)
      return () => {
        listeners.delete(fn)
      }
    },
    dispose() {
      if (typeof coarse.removeEventListener === 'function') {
        coarse.removeEventListener('change', onChange)
      } else if (
        typeof (
          coarse as unknown as { removeListener?: (fn: () => void) => void }
        ).removeListener === 'function'
      ) {
        ;(
          coarse as unknown as { removeListener: (fn: () => void) => void }
        ).removeListener(onChange)
      }
      listeners.clear()
    },
  }
}

function noopPreference(): PointerPreference {
  return {
    current: () => 'fine',
    subscribe: () => () => {},
    dispose: () => {},
  }
}

/** Screen-pixel handle size for the two primary precisions. Coarse
 *  (finger) bumps up to 24 per Apple HIG / Material's 48dp target
 *  halved; fine stays at the default 8 we ship on desktop. */
export const HANDLE_SIZE_FOR_PRECISION: Record<PointerPrecision, number> = {
  coarse: 24,
  fine: 8,
}
