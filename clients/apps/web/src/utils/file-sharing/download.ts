import { ZIP64_THRESHOLD } from './constants'
import { createZipStream } from './zip-stream'

// ── StreamSaver Loader ──

// Lazy-loaded browser-only dependencies.
// Using dynamic import() instead of require() to avoid module-scope side effects
// during SSR, which causes Next.js hydration mismatch warnings.
type StreamSaver = typeof import('streamsaver')
let streamSaverModule: StreamSaver | null = null

async function getStreamSaver(): Promise<StreamSaver> {
  if (streamSaverModule) return streamSaverModule
  if (typeof window === 'undefined')
    throw new Error('StreamSaver requires a browser environment')
  await import('web-streams-polyfill/polyfill')
  const mod = await import('streamsaver')
  // Turbopack (Next.js 16+) creates frozen ES module namespace objects from CJS
  // modules, so named exports are read-only getters. Use `default` to get the
  // actual mutable object, falling back to mod for older bundlers.
  const ss = (mod.default ?? mod) as StreamSaver
  ss.mitm = `${window.location.protocol}//${window.location.host}/stream.html`
  streamSaverModule = ss
  return ss
}

// ── Types ──

type DownloadFileStream = {
  name: string
  size: number
  stream: () => ReadableStream<Uint8Array>
}

// ── Single File Download ──

export async function streamDownloadSingleFile(
  file: DownloadFileStream,
  filename: string,
  signal?: AbortSignal,
): Promise<void> {
  const streamSaver = await getStreamSaver()
  const fileStream = streamSaver.createWriteStream(filename, {
    size: file.size,
  })

  const writer = fileStream.getWriter()
  const reader = file.stream().getReader()

  async function cleanup(reason: string): Promise<void> {
    try {
      await reader.cancel()
    } catch {
      /* already released */
    }
    try {
      await writer.abort(reason)
    } catch {
      /* already closed */
    }
  }

  try {
    while (true) {
      if (signal?.aborted) {
        await cleanup('download aborted')
        return
      }
      const res = await reader.read()
      if (res.done) {
        await writer.close()
        return
      }
      if (signal?.aborted) {
        await cleanup('download aborted')
        return
      }
      await writer.write(res.value)
    }
  } catch (err) {
    await cleanup(err instanceof Error ? err.message : 'download failed')
    throw err
  }
}

// ── Multi-File Zip Download ──

export async function streamDownloadMultipleFiles(
  files: Array<DownloadFileStream>,
  filename: string,
  signal?: AbortSignal,
): Promise<void> {
  const streamSaver = await getStreamSaver()
  // Estimate ZIP overhead per file:
  // ZIP32: 30 (local header) + 16 (data descriptor) + 46 (central directory) = 92 + name*2
  // ZIP64 extra: +20 (local) + 8 (data descriptor: 24 vs 16) + 28 (central) = 56/file
  // ZIP64 EOCD: 56 + 20 (locator) = 76
  // Use generous estimate that accounts for potential ZIP64
  const hasLargeFiles = files.some((f) => f.size >= ZIP64_THRESHOLD)
  const perFileExtra = hasLargeFiles ? 56 : 0
  const eocdExtra = hasLargeFiles ? 76 : 0
  const zipOverhead = files.reduce(
    (acc, file) => acc + file.name.length * 2 + 92 + perFileExtra,
    22 + eocdExtra,
  )
  const totalSize =
    files.reduce((acc, file) => acc + file.size, 0) + zipOverhead
  const fileStream = streamSaver.createWriteStream(filename, {
    size: totalSize,
  })

  const readableZipStream = createZipStream({
    start(ctrl) {
      for (const file of files) {
        ctrl.enqueue(file)
      }
      ctrl.close()
    },
    async pull(_ctrl) {
      // Gets executed everytime zip-stream asks for more data
    },
  })

  try {
    await readableZipStream.pipeTo(fileStream, { signal })
  } catch (err) {
    // pipeTo should abort the writable stream automatically, but
    // StreamSaver's service worker may not clean up properly.
    // Attempt explicit abort to dismiss the download prompt.
    try {
      await fileStream.abort(
        err instanceof Error ? err.message : 'download failed',
      )
    } catch {
      /* writable may already be closed by pipeTo */
    }
    throw err
  }
}
