/** Default debounce delay for auto-save and clipboard feedback (ms) */
export const DEBOUNCE_DELAY_MS = 1_000

/** Long-duration toast display time (ms) */
export const TOAST_LONG_DURATION_MS = 8_000

/** Auto-clear clipboard after this delay to limit exposure of sensitive URLs (ms) */
export const CLIPBOARD_CLEAR_DELAY_MS = 60_000

/** Initial retry delay for exponential backoff (ms) */
export const INITIAL_RETRY_DELAY_MS = 100

/** Maximum retry delay cap for exponential backoff (ms) */
export const MAX_RETRY_DELAY_MS = 1_000
