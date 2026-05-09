/**
 * System-clipboard bridge for the Collab v2 whiteboard.
 *
 * The in-app ``clipboard.ts`` buffer is fast and deterministic for
 * within-tab copy/paste; this module extends that surface to the
 * browser's ``navigator.clipboard`` so:
 *
 *  - copying in tab A is pastable in tab B (or in a different browser
 *    window of the same machine);
 *  - copying our scene leaves a JSON payload that another Rapidly
 *    instance can detect via the ``CLIPBOARD_MAGIC`` marker;
 *  - paste from any text source is handled — non-Rapidly payloads
 *    fall through cleanly so callers can chain other handlers.
 *
 * Permissions
 * -----------
 * ``writeText`` / ``readText`` only work in a user gesture (Cmd+C /
 * Cmd+V keystroke or a button click). The whiteboard already calls
 * these from those code paths, so the gating doesn't bite. Failures
 * (insecure context, denied permission, missing API) are swallowed —
 * the in-app buffer remains the source of truth.
 *
 * Pure (text-level) helpers ``payloadToText`` and ``parseClipboardText``
 * are exported for tests so the JSON envelope can be exercised without
 * touching ``navigator``.
 */

import { CLIPBOARD_MAGIC, type ClipboardPayload } from './clipboard'

/** Serialise a ClipboardPayload to a string suitable for the system
 *  clipboard. Stable JSON ordering not required — paste reads the
 *  whole object. */
export function payloadToText(payload: ClipboardPayload): string {
  return JSON.stringify(payload)
}

/** Try to interpret a clipboard text blob as a Rapidly payload. Returns
 *  ``null`` on parse failure or wrong magic so callers can fall through
 *  to other paste handlers (image-on-clipboard, plain-text paste). */
export function parseClipboardText(text: string): ClipboardPayload | null {
  if (!text) return null
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    return null
  }
  if (!parsed || typeof parsed !== 'object') return null
  const obj = parsed as Record<string, unknown>
  if (obj.magic !== CLIPBOARD_MAGIC) return null
  if (!Array.isArray(obj.elements)) return null
  return {
    magic: CLIPBOARD_MAGIC,
    elements: obj.elements as ClipboardPayload['elements'],
  }
}

/** Write a payload to the system clipboard. Returns ``true`` on
 *  success, ``false`` on any failure (no permission, no API, SSR).
 *  Always swallows the underlying error — callers fall back to the
 *  in-app buffer. */
export async function writeSystemClipboard(
  payload: ClipboardPayload,
): Promise<boolean> {
  if (typeof navigator === 'undefined') return false
  const clipboard = navigator.clipboard
  if (!clipboard?.writeText) return false
  try {
    await clipboard.writeText(payloadToText(payload))
    return true
  } catch {
    return false
  }
}

/** Read the system clipboard and try to parse it as a Rapidly payload.
 *  Returns ``null`` for any failure mode (no permission, no API, not
 *  our payload) so callers can chain alternative handlers. */
export async function readSystemClipboardPayload(): Promise<ClipboardPayload | null> {
  if (typeof navigator === 'undefined') return null
  const clipboard = navigator.clipboard
  if (!clipboard?.readText) return null
  let text: string
  try {
    text = await clipboard.readText()
  } catch {
    return null
  }
  return parseClipboardText(text)
}
