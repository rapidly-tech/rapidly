/**
 * Web Worker for SHA-256 file hashing.
 *
 * Runs the streaming SHA-256 computation entirely off the main thread,
 * keeping the UI responsive during large file transfers.
 *
 * Protocol:
 *   Main → Worker: { file: Blob }
 *   Worker → Main: { hash: string } | { error: string }
 */

import { StreamingSHA256, computeFileSHA256Streaming } from './streaming-hash'

// Re-export to ensure the class is bundled into the worker
void StreamingSHA256

self.onmessage = async (event: MessageEvent<{ file: Blob }>) => {
  try {
    const hash = await computeFileSHA256Streaming(event.data.file)
    self.postMessage({ hash })
  } catch (err) {
    self.postMessage({
      error: err instanceof Error ? err.message : 'Hash computation failed',
    })
  }
}
