/**
 * Local-first persistence for the Collab v2 whiteboard.
 *
 * Saves the Yjs state (encoded via ``Y.encodeStateAsUpdate``) into
 * IndexedDB on each document update, debounced so a flurry of edits
 * produces one write. Re-hydrates the same state on the next mount
 * so a user who reloads the tab rejoins their session without
 * waiting for a remote peer.
 *
 * Why this module is a thin wrapper
 * ---------------------------------
 * A ``PersistenceStorage`` interface hides the backend (IndexedDB in
 * production, an in-memory ``Map`` in tests). That keeps the
 * controller pure enough to unit-test without ``fake-indexeddb`` as
 * a dev dep and leaves the door open for a filesystem-backed store
 * in a future Electron / native shell.
 *
 * Scope
 * -----
 * Plaintext storage only. The user's own IndexedDB is already inside
 * their device's security boundary (disk encryption / OS keychain
 * cover rest-at-rest). An encrypted snapshot layer can land on top
 * of this interface without any consumers changing.
 *
 * What this does NOT do (yet)
 * ---------------------------
 *  - No cross-tab coordination (two tabs on the same room would race).
 *  - No snapshot compaction — we append-then-overwrite the full
 *    state blob each save. Fine for whiteboards up to a few MB.
 *  - No tombstone GC — deleted elements ride along in the Yjs doc
 *    state as they always have.
 */

import * as Y from 'yjs'

/** Backing store abstraction. Keys are strings (typically the room
 *  id). Values are raw Yjs update bytes. All three methods are async
 *  so IndexedDB works naturally; in-memory impls resolve immediately. */
export interface PersistenceStorage {
  get(key: string): Promise<Uint8Array | null>
  put(key: string, value: Uint8Array): Promise<void>
  delete(key: string): Promise<void>
}

export interface PersistenceOptions {
  doc: Y.Doc
  /** Stable identifier — typically the Collab room slug. Persistence
   *  entries for different rooms never collide. */
  roomId: string
  /** Storage backend. Defaults to ``indexedDbStorage()``. Tests
   *  inject an in-memory stub. */
  storage?: PersistenceStorage
  /** How long to wait after an edit before writing. Keeps noisy
   *  drags from hammering IndexedDB. Defaults to 250ms. */
  debounceMs?: number
}

export interface PersistenceController {
  /** Hydrate the doc from storage if an entry exists. Resolves with
   *  ``true`` when state was loaded, ``false`` otherwise. Safe to
   *  call even if nothing's there. */
  load(): Promise<boolean>
  /** Force an immediate write, cancelling any pending debounce. Use
   *  before ``dispose`` if you want a guaranteed flush. */
  save(): Promise<void>
  /** Stop listening to doc updates and cancel the pending write. */
  dispose(): void
}

const DEFAULT_DEBOUNCE_MS = 250

/** Wire a doc to a backing store. Returns a controller so the caller
 *  can load before rendering and dispose on unmount. */
export function createPersistence(
  opts: PersistenceOptions,
): PersistenceController {
  const storage = opts.storage ?? indexedDbStorage()
  const debounceMs = opts.debounceMs ?? DEFAULT_DEBOUNCE_MS
  let timer: ReturnType<typeof setTimeout> | null = null
  let disposed = false

  const flush = async (): Promise<void> => {
    if (disposed) return
    timer = null
    const update = Y.encodeStateAsUpdate(opts.doc)
    await storage.put(opts.roomId, update)
  }

  const scheduleSave = (): void => {
    if (disposed) return
    if (timer !== null) clearTimeout(timer)
    timer = setTimeout(() => {
      void flush()
    }, debounceMs)
  }

  const onUpdate = (): void => scheduleSave()
  opts.doc.on('update', onUpdate)

  return {
    async load() {
      const existing = await storage.get(opts.roomId)
      if (!existing || existing.byteLength === 0) return false
      Y.applyUpdate(opts.doc, existing, PERSISTENCE_ORIGIN)
      return true
    },
    async save() {
      if (timer !== null) {
        clearTimeout(timer)
        timer = null
      }
      await flush()
    },
    dispose() {
      disposed = true
      if (timer !== null) {
        clearTimeout(timer)
        timer = null
      }
      opts.doc.off('update', onUpdate)
    },
  }
}

/** Origin tag used when we apply a persisted update. Consumers can
 *  filter on this to skip, e.g., echoing the hydration back over a
 *  provider. Exported so callers + tests can compare against it. */
export const PERSISTENCE_ORIGIN = Symbol('collab.v2.persistence')

// ── In-memory storage (tests + SSR fallback) ─────────────────────────

/** ``Map``-backed store. Ideal for unit tests and for SSR where no
 *  IndexedDB exists — production callers use ``indexedDbStorage``. */
export function inMemoryStorage(): PersistenceStorage {
  const store = new Map<string, Uint8Array>()
  return {
    async get(key) {
      return store.get(key) ?? null
    },
    async put(key, value) {
      store.set(key, value)
    },
    async delete(key) {
      store.delete(key)
    },
  }
}

// ── IndexedDB storage ────────────────────────────────────────────────

const DEFAULT_DB_NAME = 'rapidly-collab-v2'
const STORE_NAME = 'snapshots'

/** Production default: writes into a single ``snapshots`` object store
 *  keyed by room id. Lazily opens the database on first op so we don't
 *  touch IDB until the user's actually loading a room.
 *
 *  In SSR (``typeof indexedDB === 'undefined'``) this falls back to an
 *  in-memory ``Map`` so code paths that accidentally pre-render with
 *  persistence wired still type-check and no-op cleanly. */
export function indexedDbStorage(
  dbName: string = DEFAULT_DB_NAME,
): PersistenceStorage {
  if (typeof indexedDB === 'undefined') return inMemoryStorage()

  let dbPromise: Promise<IDBDatabase> | null = null
  const openDb = (): Promise<IDBDatabase> => {
    if (!dbPromise) {
      dbPromise = new Promise<IDBDatabase>((resolve, reject) => {
        const req = indexedDB.open(dbName, 1)
        req.onupgradeneeded = () => {
          const db = req.result
          if (!db.objectStoreNames.contains(STORE_NAME)) {
            db.createObjectStore(STORE_NAME)
          }
        }
        req.onsuccess = () => resolve(req.result)
        req.onerror = () =>
          reject(req.error ?? new Error('indexedDB open failed'))
      })
    }
    return dbPromise
  }

  const run = async <T>(
    mode: IDBTransactionMode,
    fn: (store: IDBObjectStore) => IDBRequest<T>,
  ): Promise<T> => {
    const db = await openDb()
    return new Promise<T>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, mode)
      const store = tx.objectStore(STORE_NAME)
      const req = fn(store)
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error ?? new Error('idb op failed'))
    })
  }

  return {
    async get(key) {
      const value = await run<Uint8Array | undefined>('readonly', (s) =>
        s.get(key),
      )
      return value ?? null
    },
    async put(key, value) {
      await run('readwrite', (s) => s.put(value, key))
    },
    async delete(key) {
      await run('readwrite', (s) => s.delete(key))
    },
  }
}
