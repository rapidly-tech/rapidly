import { sanitizeFileName } from './filename'
import { UploadedFile } from './types'

/**
 * Cache normalized filenames per File object. sanitizeFileName runs at most
 * once per file — subsequent calls are a WeakMap lookup.
 */
const nameCache = new WeakMap<UploadedFile, string>()

/** Maximum recursion depth when scanning dropped directories. */
const MAX_SCAN_DEPTH = 50
/** Maximum total files collected from a directory drop. */
const MAX_SCAN_FILES = 10_000

const getAsFile = (entry: FileSystemFileEntry): Promise<File> =>
  new Promise((resolve, reject) => {
    entry.file((file: File) => {
      ;(file as UploadedFile).entryFullPath = entry.fullPath
      resolve(file)
    }, reject)
  })

const readDirectoryEntries = (
  reader: FileSystemDirectoryReader,
): Promise<FileSystemEntry[]> =>
  new Promise((resolve, reject) => {
    reader.readEntries(resolve, reject)
  })

const scanDirectoryEntry = async (
  entry: FileSystemDirectoryEntry,
  depth = 0,
  fileCount = { value: 0 },
): Promise<File[]> => {
  if (depth > MAX_SCAN_DEPTH) return []
  const directoryReader = entry.createReader()
  const result: File[] = []

  while (true) {
    if (fileCount.value >= MAX_SCAN_FILES) return result
    const subentries = await readDirectoryEntries(directoryReader)
    if (!subentries.length) {
      return result
    }

    for (const se of subentries) {
      if (fileCount.value >= MAX_SCAN_FILES) return result
      if (se.isDirectory) {
        const ses = await scanDirectoryEntry(
          se as FileSystemDirectoryEntry,
          depth + 1,
          fileCount,
        )
        result.push(...ses)
      } else {
        const file = await getAsFile(se as FileSystemFileEntry)
        result.push(file)
        fileCount.value++
      }
    }
  }
}

export const extractFileList = async (
  e: React.DragEvent | DragEvent,
): Promise<File[]> => {
  if (!e.dataTransfer || !e.dataTransfer.items.length) {
    return []
  }

  const items = e.dataTransfer.items
  const scans: Promise<File[]>[] = []
  const files: Promise<File>[] = []
  // Share a single fileCount across all directory scans so the global
  // MAX_SCAN_FILES limit applies to the entire drop, not per-directory.
  const sharedFileCount = { value: 0 }

  for (let i = 0; i < items.length; i++) {
    const item = items[i]
    const entry = item.webkitGetAsEntry()
    if (entry) {
      if (entry.isDirectory) {
        scans.push(
          scanDirectoryEntry(
            entry as FileSystemDirectoryEntry,
            0,
            sharedFileCount,
          ),
        )
      } else {
        files.push(getAsFile(entry as FileSystemFileEntry))
      }
    }
  }

  const scanResults = await Promise.all(scans)
  const fileResults = await Promise.all(files)

  return scanResults.flat().concat(fileResults)
}

export const getFileName = (file: UploadedFile): string => {
  const cached = nameCache.get(file)
  if (cached !== undefined) return cached

  const path = file.entryFullPath ?? file.name ?? ''
  // Strip leading '/' from webkitGetAsEntry fullPath (e.g. '/folder/file.txt' → 'folder/file.txt')
  // to produce a valid relative path that passes safeFileName validation
  const raw = path.startsWith('/') ? path.slice(1) : path
  // Normalize through the same sanitization the downloader's Zod schema
  // applies, so uploader-side names match after parsing.
  const name = sanitizeFileName(raw)
  nameCache.set(file, name)
  return name
}
