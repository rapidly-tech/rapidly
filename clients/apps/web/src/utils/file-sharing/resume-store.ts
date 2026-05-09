/**
 * IndexedDB-backed resume store for partial file transfers.
 *
 * Stores per-file progress so downloads can be resumed after connection drops.
 * Keyed by slug + saltHex to uniquely identify a transfer.
 *
 * NOT stored: partial file data (too large). On resume, start a new StreamSaver
 * stream and re-download from the saved offset.
 */

import { toHex } from './hex'
import { logger } from './logger'

// ── Types ──

export interface FileProgress {
  bytesReceived: number
  completed: boolean
  hasherState: HasherState | null
}

export interface HasherState {
  h: number[]
  buffer: number[]
  bufferOffset: number
  totalBytes: number
}

export interface TransferProgress {
  slug: string
  saltHex: string
  filesInfo: Array<{ fileName: string; size: number; type: string }>
  fileProgress: Record<string, FileProgress>
  savedAt: number
}

// ── Constants ──

const DB_NAME = 'rapidly-file-sharing'
const DB_VERSION = 1
const STORE_NAME = 'resume-progress'
const EXPIRY_MS = 24 * 60 * 60 * 1000 // 24 hours

// ── IndexedDB Helpers ──

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'id' })
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

function makeKey(slug: string, saltHex: string): string {
  return `${slug}:${saltHex}`
}

// ── Public API ──

/**
 * Save transfer progress to IndexedDB.
 */
export async function saveProgress(
  slug: string,
  salt: Uint8Array,
  filesInfo: Array<{ fileName: string; size: number; type: string }>,
  fileProgress: Record<string, FileProgress>,
): Promise<void> {
  let db: IDBDatabase | null = null
  try {
    db = await openDB()
    const saltHex = toHex(salt)
    const key = makeKey(slug, saltHex)
    const data: TransferProgress & { id: string } = {
      id: key,
      slug,
      saltHex,
      filesInfo,
      fileProgress,
      savedAt: Date.now(),
    }
    const tx = db.transaction(STORE_NAME, 'readwrite')
    tx.objectStore(STORE_NAME).put(data)
    await new Promise<void>((resolve, reject) => {
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
    })
  } catch (err) {
    logger.warn('[ResumeStore] failed to save progress:', err)
  } finally {
    db?.close()
  }
}

/**
 * Load transfer progress from IndexedDB.
 * Returns null if no progress found or if expired.
 */
export async function loadProgress(
  slug: string,
  salt: Uint8Array,
): Promise<TransferProgress | null> {
  let db: IDBDatabase | null = null
  try {
    db = await openDB()
    const saltHex = toHex(salt)
    const key = makeKey(slug, saltHex)
    const tx = db.transaction(STORE_NAME, 'readonly')
    const request = tx.objectStore(STORE_NAME).get(key)
    const result = await new Promise<TransferProgress | null>(
      (resolve, reject) => {
        request.onsuccess = () => resolve(request.result ?? null)
        request.onerror = () => reject(request.error)
      },
    )
    // Close before potential recursive call to deleteProgress
    db.close()
    db = null

    if (!result) return null
    // Check expiry
    if (Date.now() - result.savedAt > EXPIRY_MS) {
      await deleteProgress(slug, salt)
      return null
    }
    return result
  } catch (err) {
    // IndexedDB unavailable (e.g. private browsing) — graceful degradation
    logger.warn('[ResumeStore] failed to load progress:', err)
    return null
  } finally {
    db?.close()
  }
}

/**
 * Delete transfer progress from IndexedDB.
 */
export async function deleteProgress(
  slug: string,
  salt: Uint8Array,
): Promise<void> {
  let db: IDBDatabase | null = null
  try {
    db = await openDB()
    const saltHex = toHex(salt)
    const key = makeKey(slug, saltHex)
    const tx = db.transaction(STORE_NAME, 'readwrite')
    tx.objectStore(STORE_NAME).delete(key)
    await new Promise<void>((resolve, reject) => {
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
    })
  } catch (err) {
    logger.warn('[ResumeStore] failed to delete progress:', err)
  } finally {
    db?.close()
  }
}

/**
 * Clean up expired entries from IndexedDB.
 */
export async function cleanExpired(): Promise<void> {
  let db: IDBDatabase | null = null
  try {
    db = await openDB()
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const request = store.openCursor()
    const now = Date.now()

    await new Promise<void>((resolve, reject) => {
      request.onsuccess = () => {
        const cursor = request.result
        if (!cursor) {
          resolve()
          return
        }
        const entry = cursor.value as TransferProgress & { id: string }
        if (now - entry.savedAt > EXPIRY_MS) {
          cursor.delete()
        }
        cursor.continue()
      }
      request.onerror = () => reject(request.error)
    })
  } catch (err) {
    logger.warn('[ResumeStore] failed to clean expired entries:', err)
  } finally {
    db?.close()
  }
}
