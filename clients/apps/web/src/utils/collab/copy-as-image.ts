/**
 * Copy as image — render an element list to a PNG blob and write it
 * to the system clipboard via the ``ClipboardItem`` API. The output
 * pastes natively into Slack / Notion / email apps that already
 * accept image clipboard data.
 *
 * Why a separate module from ``export.ts``: ``exportToPNG`` returns
 * a blob; this module owns the *clipboard transport* (feature
 * detection, the ``ClipboardItem`` envelope, the user-gesture
 * requirement) so the export module stays renderer-only and
 * environment-agnostic.
 */

import type { CollabElement } from './elements'
import { type ExportPNGOptions, exportToPNG } from './export'

export interface CopyAsImageResult {
  /** ``true`` when the bytes were handed off to the clipboard. ``false``
   *  when the browser doesn't support image clipboards, the export
   *  produced no blob (empty selection / SSR), or the write was
   *  rejected (e.g. no user gesture). */
  ok: boolean
  /** Optional reason for failure — surfaced to the UI so we can show
   *  a hint instead of a silent no-op. */
  reason?: 'unsupported' | 'empty' | 'denied'
}

/** Whether the runtime exposes everything required to write an image
 *  to the system clipboard. Safari + Firefox lag on this so callers
 *  must feature-detect before showing the action in the UI. */
export function isCopyAsImageSupported(): boolean {
  if (typeof window === 'undefined') return false
  if (typeof ClipboardItem === 'undefined') return false
  return Boolean(navigator.clipboard?.write)
}

/** Inject point for tests + DI in non-browser environments. The
 *  default writes through ``navigator.clipboard.write``. */
export interface CopyAsImageDeps {
  /** Replaceable PNG factory — tests stub this without spinning up a
   *  real canvas. Defaults to ``exportToPNG`` from ``./export``. */
  exportPng?: (
    elements: readonly CollabElement[],
    options?: ExportPNGOptions,
  ) => Promise<Blob | null>
  /** Replaceable clipboard write — tests stub this so we can assert
   *  the ClipboardItem envelope without hitting the browser. */
  clipboardWrite?: (items: ClipboardItem[]) => Promise<void>
}

/** Copy the rendered PNG of ``elements`` to the system clipboard.
 *  Returns ``ok:true`` when the bytes were accepted. The caller
 *  should call this from a user-gesture handler — most browsers
 *  reject ``clipboard.write`` outside of one. */
export async function copyElementsAsPng(
  elements: readonly CollabElement[],
  options: ExportPNGOptions = {},
  deps: CopyAsImageDeps = {},
): Promise<CopyAsImageResult> {
  if (elements.length === 0) {
    return { ok: false, reason: 'empty' }
  }
  const exportPng = deps.exportPng ?? exportToPNG
  const blob = await exportPng(elements, options)
  if (!blob) return { ok: false, reason: 'empty' }

  const write =
    deps.clipboardWrite ??
    (typeof navigator !== 'undefined' && navigator.clipboard?.write
      ? navigator.clipboard.write.bind(navigator.clipboard)
      : null)
  if (!write || typeof ClipboardItem === 'undefined') {
    return { ok: false, reason: 'unsupported' }
  }

  try {
    const item = new ClipboardItem({ [blob.type]: blob })
    await write([item])
    return { ok: true }
  } catch {
    // The most common failure is a missing user-gesture or a permission
    // prompt the user dismissed. Either way the bytes weren't copied.
    return { ok: false, reason: 'denied' }
  }
}
