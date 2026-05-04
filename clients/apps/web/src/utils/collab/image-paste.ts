/**
 * System-clipboard image → image element.
 *
 * Complements the in-app clipboard from Phase 12. When the user
 * Cmd+V's while an image sits on the OS clipboard (screenshot,
 * drag-copy from Finder, Copy-Image from a browser), this module
 * extracts the blob, encodes it as a data URL, measures its natural
 * dimensions, and hands a ``PastedImage`` back to the caller. The
 * demo page wraps this in a ``paste`` event listener and forwards
 * the result to ``createImageElement`` below.
 *
 * Scope: decode + resize. Upload to a shared asset store lives
 * behind ``ImageElement.assetHash`` and is deliberately out of scope
 * here — Phase 12b carries the inline thumbnail only.
 */

import type { ElementStore } from './element-store'

/** The three bits of information we need to mint an ``ImageElement``
 *  from whatever was on the OS clipboard. */
export interface PastedImage {
  dataUrl: string
  mimeType: string
  width: number
  height: number
}

export interface ExtractOptions {
  /** Override the HTMLImageElement-based dimension probe. Injected by
   *  tests so they can resolve synchronously without a DOM. Production
   *  callers let this default. */
  loadImage?: (dataUrl: string) => Promise<{ width: number; height: number }>
  /** Override the FileReader step. Same story as ``loadImage``. */
  readDataUrl?: (file: Blob) => Promise<string>
}

/** Inspect a ``DataTransfer`` (the ``clipboardData`` on a ``paste``
 *  event) for an image item and return a fully-loaded ``PastedImage``
 *  when one is found. Returns ``null`` when no image present — the
 *  caller should then fall back to in-app clipboard paste. */
export async function extractPastedImage(
  clipboardData: DataTransfer | null,
  options: ExtractOptions = {},
): Promise<PastedImage | null> {
  if (!clipboardData) return null
  const readDataUrl = options.readDataUrl ?? defaultReadDataUrl
  const loadImage = options.loadImage ?? defaultLoadImage

  for (let i = 0; i < clipboardData.items.length; i++) {
    const item = clipboardData.items[i]
    if (item.kind !== 'file') continue
    if (!item.type.startsWith('image/')) continue
    const file = item.getAsFile()
    if (!file) continue
    const dataUrl = await readDataUrl(file)
    const { width, height } = await loadImage(dataUrl)
    return { dataUrl, mimeType: file.type, width, height }
  }
  return null
}

export interface CreateImageOptions {
  /** Where the new element's centre should land (world coords). The
   *  demo uses the current viewport centre; ``useCollabRoom`` would
   *  use the last pointer position. */
  center: { x: number; y: number }
  /** Cap the image's on-canvas size. Larger images are scaled down
   *  proportionally so a 4K screenshot doesn't instantly dwarf the
   *  scene. Defaults to 480 world units — roughly the width of a
   *  single column in the demo layout. */
  maxSize?: number
}

const DEFAULT_MAX_SIZE = 480

/** Mint a new image element from an extracted ``PastedImage``. Scales
 *  down to ``maxSize`` preserving aspect ratio; the original pixel
 *  dimensions stay on ``naturalWidth`` / ``naturalHeight`` so a later
 *  ""reset size"" action can restore them. */
export function createImageElement(
  store: ElementStore,
  image: PastedImage,
  options: CreateImageOptions,
): string {
  const maxSize = options.maxSize ?? DEFAULT_MAX_SIZE
  let w = image.width
  let h = image.height
  if (w > maxSize || h > maxSize) {
    const scale = Math.min(maxSize / w, maxSize / h)
    w = Math.max(1, Math.round(w * scale))
    h = Math.max(1, Math.round(h * scale))
  }
  return store.create({
    type: 'image',
    x: options.center.x - w / 2,
    y: options.center.y - h / 2,
    width: w,
    height: h,
    thumbnailDataUrl: image.dataUrl,
    mimeType: image.mimeType,
    naturalWidth: image.width,
    naturalHeight: image.height,
  })
}

// ── Default async implementations ────────────────────────────────────

function defaultReadDataUrl(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(reader.error ?? new Error('read failed'))
    reader.readAsDataURL(file)
  })
}

function defaultLoadImage(
  dataUrl: string,
): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () =>
      resolve({ width: img.naturalWidth, height: img.naturalHeight })
    img.onerror = () => reject(new Error('image decode failed'))
    img.src = dataUrl
  })
}
