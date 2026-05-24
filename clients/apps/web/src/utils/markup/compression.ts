/**
 * Payload compression for the Collab provider.
 *
 * Every Yjs update flows through the E2EE envelope, which rides our
 * signaling relay with a hard 64 KB-per-message cap on the server side.
 * A mid-sized whiteboard ships tens of elements per sync-2 frame; a
 * full initial-sync to a fresh peer can easily blow that cap without
 * compression.
 *
 * We use the native ``CompressionStream`` API (gzip) — available in
 * every browser we target (Chrome 80+, Firefox 113+, Safari 16.4+) —
 * so no external dependency enters the repo. Yjs updates compress
 * 3–5× in the payload ranges we care about, which buys us roughly
 * 1000 elements per sync frame before we need chunking.
 *
 * **Order matters:** compress *then* encrypt. Ciphertext looks random
 * to any compressor, so the reverse order gives zero gain. The provider
 * calls ``compress`` right before ``encryptGcm`` and ``decompress``
 * right after ``decryptGcm``.
 *
 * Small payloads skip compression. Below the threshold, gzip's framing
 * overhead routinely exceeds the win.
 */

/** Below this size, compression round-trip costs more than it saves.
 *  1 KB is Yjs's typical single-update size — anything smaller is
 *  usually cursor / awareness traffic that doesn't benefit. */
export const COMPRESSION_THRESHOLD_BYTES = 1024

/** Whether the runtime has the CompressionStream API. Older browsers
 *  fall back to no-op compression; the ``z`` flag on the wire message
 *  is the source of truth for receivers. */
export function compressionAvailable(): boolean {
  return (
    typeof CompressionStream !== 'undefined' &&
    typeof DecompressionStream !== 'undefined'
  )
}

/** Feed ``bytes`` through a TransformStream and collect the output as
 *  a single contiguous Uint8Array. Works uniformly across browsers and
 *  the jsdom/Node test runtime — avoids Blob.stream() which isn't
 *  polyfilled everywhere.
 *
 *  Error handling: we drive the writer and the reader in parallel;
 *  if either side rejects, we cancel the other so no promise is left
 *  dangling as an unhandled rejection. Tests rely on ``decompress()``
 *  rejecting cleanly on malformed input. */
async function runStream(
  bytes: Uint8Array,
  // CompressionStream types its writable as
  // ``WritableStream<BufferSource>`` rather than matching the reader
  // side, so a parametrised ``TransformStream<U8, U8>`` can't be
  // handed either Compression or Decompression stream without a
  // structural mismatch. Typing the two ports independently — writer
  // as BufferSource, reader as Uint8Array — lets us pass both.
  ts: {
    readable: ReadableStream<Uint8Array>
    writable: WritableStream<BufferSource>
  },
): Promise<Uint8Array> {
  const writer = ts.writable.getWriter()
  const reader = ts.readable.getReader()

  const writeSide = (async () => {
    try {
      // Cast: strictSharedArrayBuffer in TS 5.7+ splits
      // Uint8Array<ArrayBufferLike> from the stricter
      // ArrayBufferView<ArrayBuffer> that write() expects. We know our
      // inputs are backed by a regular ArrayBuffer at runtime.
      await writer.write(bytes as unknown as BufferSource)
      await writer.close()
    } catch (err) {
      // Swallow here — the read side will surface the same failure
      // (or a more specific one) and we don't want an unhandled
      // rejection racing it.
      try {
        reader.cancel(err).catch(() => {})
      } catch {
        /* ignore */
      }
    }
  })()

  const chunks: Uint8Array[] = []
  let total = 0
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      chunks.push(value)
      total += value.byteLength
    }
  } finally {
    // Make sure the write-side promise settles before we resolve /
    // reject, otherwise an error it raised could still surface as
    // unhandled in the next microtask.
    await writeSide.catch(() => {})
  }

  const out = new Uint8Array(total)
  let off = 0
  for (const c of chunks) {
    out.set(c, off)
    off += c.byteLength
  }
  return out
}

/** Gzip-compress ``bytes``. Rejects if the runtime lacks the API;
 *  callers should guard with ``compressionAvailable()``. */
export async function compress(bytes: Uint8Array): Promise<Uint8Array> {
  return runStream(bytes, new CompressionStream('gzip'))
}

/** Gzip-decompress ``bytes``. Rejects on malformed input. */
export async function decompress(bytes: Uint8Array): Promise<Uint8Array> {
  return runStream(bytes, new DecompressionStream('gzip'))
}

/** Decide whether to compress a given plaintext. Keeps the policy in
 *  one place so provider + tests don't drift. */
export function shouldCompress(bytes: Uint8Array): boolean {
  return (
    compressionAvailable() && bytes.byteLength >= COMPRESSION_THRESHOLD_BYTES
  )
}
