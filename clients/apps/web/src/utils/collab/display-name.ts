/**
 * Pure helpers for the chamber's ""display name"" — the human-readable
 * label peers see next to each other's cursors and in the presence
 * strip.
 *
 * Persists in ``localStorage`` under a stable key so a returning user
 * doesn't have to retype their name each session. Sanitisation caps
 * length and strips control characters so a malicious or accidentally
 * oversized name can't inflate the awareness payload or hijack the UI.
 *
 * No React — the hook lives in ``components/Collab/useDisplayName.ts``
 * (below) and composes these pure bits. Tests here only touch the
 * pure logic.
 */

export const DISPLAY_NAME_STORAGE_KEY = 'rapidly.collab.displayName'
export const DISPLAY_NAME_MAX_LENGTH = 32

/** Strip control chars + trim + cap length. Returns the empty string
 *  when the input is null / undefined / blank so callers can branch
 *  on ``!name``. */
export function sanitiseDisplayName(raw: string | null | undefined): string {
  if (typeof raw !== 'string') return ''
  // eslint-disable-next-line no-control-regex
  const cleaned = raw.replace(/[\u0000-\u001F\u007F]/g, '').trim()
  return cleaned.slice(0, DISPLAY_NAME_MAX_LENGTH)
}

/** Read the stored display name from the supplied storage (defaults
 *  to ``window.localStorage``). Sanitises on read so a stale / tampered
 *  entry can't ship a pathological value. SSR-safe. */
export function readStoredDisplayName(
  storage: Pick<Storage, 'getItem'> | null | undefined = resolveStorage(),
): string {
  if (!storage) return ''
  try {
    return sanitiseDisplayName(storage.getItem(DISPLAY_NAME_STORAGE_KEY))
  } catch {
    return ''
  }
}

/** Persist the display name. Writes only the sanitised form so a
 *  re-read yields an identical value. Accepts an empty string to
 *  clear the entry. SSR-safe + tolerant of quota errors. */
export function writeStoredDisplayName(
  name: string,
  storage:
    | Pick<Storage, 'setItem' | 'removeItem'>
    | null
    | undefined = resolveStorage(),
): void {
  if (!storage) return
  const sanitised = sanitiseDisplayName(name)
  try {
    if (sanitised === '') storage.removeItem(DISPLAY_NAME_STORAGE_KEY)
    else storage.setItem(DISPLAY_NAME_STORAGE_KEY, sanitised)
  } catch {
    /* quota / private-mode — silent */
  }
}

/** Default display name derived from a Yjs clientID when the user
 *  hasn't typed one. Picks the last four hex-ish digits so ""Peer a3f2""
 *  reads naturally in the presence strip. */
export function defaultDisplayName(clientID: number): string {
  return `Peer ${clientID.toString().slice(-4)}`
}

/** Build the display name to broadcast — user's typed value when set,
 *  otherwise the clientID-derived default. Keeps the choice in one
 *  place so the chamber client + any future consumer stay aligned. */
export function effectiveDisplayName(
  typed: string,
  clientID: number | null,
): string {
  const sanitised = sanitiseDisplayName(typed)
  if (sanitised !== '') return sanitised
  if (clientID === null) return 'Peer'
  return defaultDisplayName(clientID)
}

function resolveStorage(): Pick<
  Storage,
  'getItem' | 'setItem' | 'removeItem'
> | null {
  if (typeof window === 'undefined') return null
  try {
    return window.localStorage
  } catch {
    return null
  }
}
