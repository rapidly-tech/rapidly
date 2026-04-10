// ── Imports ──

import { FILE_SHARING_API } from '@/utils/file-sharing/constants'
import { secureCompare } from '@/utils/file-sharing/crypto'
import {
  computeFileSHA256,
  computeKeyCommitment,
  deriveFileKey,
  encryptChunk,
  encryptMetadata,
} from '@/utils/file-sharing/encryption'
import { getFileName } from '@/utils/file-sharing/fs'
import { IdleTracker } from '@/utils/file-sharing/idle-tracker'
import { logger } from '@/utils/file-sharing/logger'
import {
  ChunkAckMessage,
  decodeMessage,
  Message,
  MessageType,
} from '@/utils/file-sharing/messages'
import { PeerDataConnection } from '@/utils/file-sharing/peer-connection'
import {
  SignalingClient,
  SignalingMessage,
} from '@/utils/file-sharing/signaling'
import { parseIceCandidate } from '@/utils/file-sharing/signaling-helpers'
import {
  UploadedFile,
  UploaderConnection,
  UploaderConnectionStatus,
} from '@/utils/file-sharing/types'
import { useEffect, useRef, useState } from 'react'
import { z } from 'zod'

// ── Constants ──

// SCTP maxMessageSize is 262,144 bytes (256 KB). After encryption (28 bytes:
// 12-byte IV + 16-byte GCM tag) and binary framing (~200 bytes: 4-byte length
// prefix + JSON header), the total frame must stay under that limit.
// 256 KB - 512 bytes overhead budget = 255.5 KB plaintext per chunk.
export const MAX_CHUNK_SIZE = 256 * 1024 - 512 // 261,632 bytes

/** Close connection if no activity for this long (ms). */
export const IDLE_TIMEOUT = 5 * 60_000
/** Close connection if peer doesn't send RequestInfo within this time (ms). */
const HANDSHAKE_TIMEOUT = 30_000

/**
 * Maximum number of password attempts before locking out the connection.
 * This prevents brute-force attacks on password-protected file shares.
 */
const MAX_PASSWORD_ATTEMPTS = 5

// ── Validation Helpers ──

export function isFinalChunk(offset: number, fileSize: number): boolean {
  return offset + MAX_CHUNK_SIZE >= fileSize
}

function validateOffset(
  files: UploadedFile[],
  fileName: string,
  offset: number,
): UploadedFile {
  // Defense-in-depth: validate offset is a non-negative integer (Zod also validates, but belt-and-suspenders)
  if (!Number.isInteger(offset) || offset < 0) {
    throw new Error('invalid file offset')
  }
  const validFile = files.find(
    (file) => getFileName(file) === fileName && offset <= file.size,
  )
  if (!validFile) {
    throw new Error('invalid file offset')
  }
  return validFile
}

// ── Server Communication ──

/**
 * Record a password attempt with the server for defense-in-depth rate limiting.
 * Returns whether the attempt is allowed and how many attempts remain.
 */
async function recordServerPasswordAttempt(
  slug: string,
  secret: string,
): Promise<{ allowed: boolean; remaining: number }> {
  try {
    const response = await fetch(
      `${FILE_SHARING_API}/channels/${slug}/password-attempt`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ secret }),
      },
    )
    if (!response.ok) {
      // Fail closed: deny attempt if server is unavailable
      logger.warn(
        '[UploaderConnections] server password attempt tracking failed:',
        response.status,
      )
      return { allowed: false, remaining: 0 }
    }
    const result = await response.json()
    // Validate expected shape to avoid silent false lockouts on API drift
    if (
      typeof result.allowed !== 'boolean' ||
      typeof result.remaining !== 'number'
    ) {
      logger.warn(
        '[UploaderConnections] unexpected password attempt response shape:',
        result,
      )
      return { allowed: false, remaining: 0 }
    }
    return result
  } catch {
    // Fail closed: deny attempt on network error to prevent brute-force bypass
    logger.warn(
      '[UploaderConnections] server password attempt tracking unavailable',
    )
    return { allowed: false, remaining: 0 }
  }
}

// ── Main Hook ──

export function useUploaderConnections(
  signaling: SignalingClient | null,
  iceServers: RTCIceServer[],
  files: UploadedFile[],
  password: string,
  maxDownloads: number = 0, // 0 = unlimited
  encryptionKey: CryptoKey | null = null,
  channelSlug: string = '',
  channelSecret: string = '',
  hkdfSalt?: Uint8Array,
): Array<UploaderConnection> {
  const [connections, setConnections] = useState<Array<UploaderConnection>>([])

  // Ref for connections so report handler avoids stale closures
  const connectionsRef = useRef<Array<UploaderConnection>>([])

  // Cache SHA-256 hashes per file to avoid recomputing for each peer connection.
  // Cleared when the file list changes to prevent unbounded growth.
  const sha256CacheRef = useRef<Map<string, string>>(new Map())
  const prevFilesRef = useRef(files)
  if (prevFilesRef.current !== files) {
    prevFilesRef.current = files
    sha256CacheRef.current.clear()
  }

  // Use ref to track completed downloads count (avoids stale closure issues)
  const completedCountRef = useRef(0)

  // Shared password attempts counter across all connections (prevents parallel brute-force)
  // Reset when password changes so changing the share password doesn't carry over old lockout
  const sharedPasswordAttemptsRef = useRef(0)
  const prevPasswordRef = useRef(password)
  if (prevPasswordRef.current !== password) {
    prevPasswordRef.current = password
    sharedPasswordAttemptsRef.current = 0
  }

  // Map of remote peer IDs to PeerDataConnections for routing signaling messages
  const peerMapRef = useRef<Map<string, PeerDataConnection>>(new Map())

  // Refs for values used inside the signaling effect's callbacks.
  // This prevents the effect from tearing down all peer connections when
  // array/object identity changes on re-render (iceServers, files, etc.).
  const iceServersRef = useRef(iceServers)
  iceServersRef.current = iceServers
  const filesRef = useRef(files)
  filesRef.current = files
  const passwordRef = useRef(password)
  passwordRef.current = password
  const encryptionKeyRef = useRef(encryptionKey)
  encryptionKeyRef.current = encryptionKey
  const channelSlugRef = useRef(channelSlug)
  channelSlugRef.current = channelSlug
  const channelSecretRef = useRef(channelSecret)
  channelSecretRef.current = channelSecret
  const hkdfSaltRef = useRef(hkdfSalt)
  hkdfSaltRef.current = hkdfSalt
  const maxDownloadsRef = useRef(maxDownloads)
  maxDownloadsRef.current = maxDownloads

  // Keep refs in sync with actual state (render-time to avoid one-render staleness)
  connectionsRef.current = connections
  completedCountRef.current = connections.filter(
    (c) => c.status === UploaderConnectionStatus.Done,
  ).length

  useEffect(() => {
    if (!signaling || !signaling.connected) return
    logger.log(
      '[UploaderConnections] initializing with',
      filesRef.current.length,
      'files',
    )
    const cleanupHandlers: Array<() => void> = []
    const peerMap = peerMapRef.current

    /** Maximum concurrent peer connections to prevent resource exhaustion. */
    const MAX_CONCURRENT_CONNECTIONS = 50

    // ── Peer Connection Setup ──

    const setupPeerConnection = (
      remotePeerId: string,
      metadata?: Record<string, unknown>,
    ) => {
      // Cap concurrent connections to prevent resource exhaustion from mass connection attempts
      if (peerMap.size >= MAX_CONCURRENT_CONNECTIONS) {
        logger.warn(
          '[UploaderConnections] rejecting connection - limit reached:',
          MAX_CONCURRENT_CONNECTIONS,
        )
        return
      }
      logger.log('[UploaderConnections] new connection from peer', remotePeerId)

      // Ignore report metadata from peers — report actions must go through
      // the server-side report API.  Trusting peer-supplied metadata would
      // let any downloader force-redirect the uploader (DoS).
      if (metadata?.type === 'report') {
        logger.warn(
          '[UploaderConnections] ignoring unverified report metadata from peer',
          remotePeerId,
        )
        return
      }

      const peerConn = new PeerDataConnection(
        signaling,
        iceServersRef.current,
        remotePeerId,
      )
      peerConn.metadata = metadata ?? {}
      peerMap.set(remotePeerId, peerConn)

      let sendingPaused = false
      let handshakeReceived = false
      // Track which file is actively being sent to this connection (prevents OOM from concurrent requests)
      let activeFileName: string | null = null
      // Cumulative bytes sent across all files for this connection
      let cumulativeBytesSent = 0
      // Synchronous status mirror — React 18 batches functional updaters so
      // we cannot read state back from inside them in the same tick.
      let connectionStatus: UploaderConnectionStatus =
        UploaderConnectionStatus.Pending

      // Handshake timeout: close if peer never sends RequestInfo
      const handshakeTimer = setTimeout(() => {
        if (!handshakeReceived && peerConn.open) {
          logger.log(
            '[UploaderConnections] closing connection - no handshake from',
            remotePeerId,
          )
          peerConn.close()
        }
      }, HANDSHAKE_TIMEOUT)

      // Idle timeout + keepalive pings
      const idleTracker = new IdleTracker(
        IDLE_TIMEOUT,
        () => {
          logger.log(
            '[UploaderConnections] closing idle connection to',
            remotePeerId,
          )
          peerConn.close()
        },
        () => {
          if (peerConn.open) {
            peerConn.send({ type: MessageType.Ping }).catch(() => {}) // Peer may have disconnected
          }
        },
      )

      const newConn: UploaderConnection = {
        status: UploaderConnectionStatus.Pending,
        dataConnection: peerConn,
        completedFiles: 0,
        totalFiles: filesRef.current.length,
        currentFileProgress: 0,
        acknowledgedBytes: 0,
        bytesSent: 0,
        totalBytes: filesRef.current.reduce((sum, f) => sum + f.size, 0),
      }

      setConnections((conns) => {
        return [newConn, ...conns]
      })

      const updateConnection = (
        fn: (c: UploaderConnection) => UploaderConnection,
      ) => {
        setConnections((conns) =>
          conns.map((c) =>
            c.dataConnection.peer === remotePeerId ? fn(c) : c,
          ),
        )
      }

      // Build file info immediately (no hashing) so the downloader sees
      // the file list without waiting. SHA-256 hashes are computed lazily
      // in the background and cached for integrity verification during transfer.
      const buildFileInfo = () =>
        filesRef.current.map((f, idx) => {
          const name = getFileName(f)
          const cacheKey = `${name}:${f.size}:${f.lastModified}:${idx}`
          const cachedHash = sha256CacheRef.current.get(cacheKey)
          return {
            fileName: name,
            size: f.size,
            type: f.type,
            sha256: cachedHash, // undefined until background hash completes
            commitment: undefined as string | undefined, // filled in sendInfoMessage
          }
        })

      // Kick off background SHA-256 hashing for all files (non-blocking).
      // Results are cached so subsequent peer connections get instant hashes.
      // Guard ensures only one hashing loop runs at a time across connections.
      let hashingStarted = false
      const startBackgroundHashing = () => {
        if (hashingStarted) return
        hashingStarted = true
        const files = filesRef.current
        // Process sequentially to avoid exhausting file handles on large folders
        ;(async () => {
          for (let idx = 0; idx < files.length; idx++) {
            if (!peerConn.open) break // stop if connection closed
            const f = files[idx]
            const name = getFileName(f)
            const cacheKey = `${name}:${f.size}:${f.lastModified}:${idx}`
            if (!sha256CacheRef.current.has(cacheKey)) {
              try {
                const hash = await computeFileSHA256(f)
                sha256CacheRef.current.set(cacheKey, hash)
              } catch (err) {
                logger.warn(
                  `[UploaderConnections] SHA-256 hash failed for ${name}:`,
                  err,
                )
              }
            }
          }
          // POST checksums to server after all hashes are computed
          const curSlug = channelSlugRef.current
          const curSecret = channelSecretRef.current
          if (curSlug && curSecret && sha256CacheRef.current.size > 0) {
            const checksums: Record<string, string> = {}
            for (let idx = 0; idx < files.length; idx++) {
              const name = getFileName(files[idx])
              const cacheKey = `${name}:${files[idx].size}:${files[idx].lastModified}:${idx}`
              const hash = sha256CacheRef.current.get(cacheKey)
              if (hash) checksums[name] = hash
            }
            try {
              await fetch(`${FILE_SHARING_API}/channels/${curSlug}/checksums`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  secret: curSecret,
                  checksums,
                }),
              })
            } catch {
              // Non-critical — checksums are a convenience feature
              logger.warn('[UploaderConnections] failed to upload checksums')
            }
          }
        })()
      }

      const sendInfoMessage = async () => {
        const fileInfo = buildFileInfo()
        // Defer SHA-256 hashing — don't start until first file transfer
        // completes. Hashing reads the entire file from disk, competing
        // with chunk sending for I/O and main thread time.
        logger.log('[UploaderConnections] sending file info:', fileInfo)
        const curMaxDownloads = maxDownloadsRef.current
        const remaining =
          curMaxDownloads > 0
            ? curMaxDownloads - completedCountRef.current
            : undefined
        const curEncryptionKey = encryptionKeyRef.current

        // Compute HMAC-SHA256 key commitments per file when encryption is active.
        // Yield to the event loop every 50 files to prevent the main thread
        // from freezing on large file sets (10000+ files).
        if (curEncryptionKey && hkdfSaltRef.current) {
          const salt = hkdfSaltRef.current
          for (let i = 0; i < fileInfo.length; i++) {
            const f = fileInfo[i]
            try {
              f.commitment = await computeKeyCommitment(
                curEncryptionKey,
                f.fileName,
                f.size,
                i,
                salt,
              )
            } catch (err) {
              logger.warn(
                `[UploaderConnections] failed to compute commitment for ${f.fileName}:`,
                err,
              )
            }
            // Yield every 50 iterations to keep the UI responsive
            if (i % 50 === 49) {
              await new Promise((r) => setTimeout(r, 0))
            }
          }
        }

        const infoPayload = {
          type: MessageType.Info,
          files: fileInfo,
          remainingDownloads: remaining,
          encrypted: curEncryptionKey !== null,
        }

        // Encrypt metadata when encryption key is available
        if (curEncryptionKey) {
          const encryptedPayload = await encryptMetadata(
            curEncryptionKey,
            infoPayload,
            hkdfSaltRef.current ?? new Uint8Array(0),
          )
          peerConn
            .send({
              type: MessageType.EncryptedInfo,
              payload: encryptedPayload,
            })
            .catch(() => {}) // Peer may have disconnected
        } else {
          peerConn.send(infoPayload as Message).catch(() => {}) // Peer may have disconnected
        }
      }

      // ── Message Handling ──

      const onData = async (data: unknown): Promise<void> => {
        try {
          const message = decodeMessage(data)
          idleTracker.resetActivity()
          logger.log('[UploaderConnections] received message:', message.type)

          // Respond to pings, ignore pongs (they just reset activity)
          if (message.type === MessageType.Ping) {
            peerConn.send({ type: MessageType.Pong }).catch(() => {}) // Peer may have disconnected
            return
          }
          if (message.type === MessageType.Pong) return

          switch (message.type) {
            case MessageType.RequestInfo: {
              handshakeReceived = true
              clearTimeout(handshakeTimer)
              logger.log('[UploaderConnections] client info:', {
                browser: `${message.browserName} ${message.browserVersion}`,
                os: `${message.osName} ${message.osVersion}`,
                mobile: message.mobileVendor
                  ? `${message.mobileVendor} ${message.mobileModel}`
                  : 'N/A',
              })
              const newConnectionState = {
                browserName: message.browserName,
                browserVersion: message.browserVersion,
                osName: message.osName,
                osVersion: message.osVersion,
                mobileVendor: message.mobileVendor,
                mobileModel: message.mobileModel,
              }

              if (passwordRef.current) {
                logger.log(
                  '[UploaderConnections] password required, requesting authentication',
                )
                const request: Message = {
                  type: MessageType.PasswordRequired,
                }
                peerConn.send(request).catch(() => {}) // Peer may have disconnected

                connectionStatus = UploaderConnectionStatus.Authenticating
                updateConnection((draft) => {
                  if (draft.status !== UploaderConnectionStatus.Pending) {
                    return draft
                  }

                  return {
                    ...draft,
                    ...newConnectionState,
                    status: UploaderConnectionStatus.Authenticating,
                  }
                })

                return
              }

              connectionStatus = UploaderConnectionStatus.Ready
              updateConnection((draft) => {
                if (draft.status !== UploaderConnectionStatus.Pending) {
                  return draft
                }

                return {
                  ...draft,
                  ...newConnectionState,
                  status: UploaderConnectionStatus.Ready,
                }
              })

              await sendInfoMessage()
              break
            }

            case MessageType.UsePassword: {
              logger.log('[UploaderConnections] password attempt received')
              const { password: submittedPassword } = message

              // Check if already locked out (shared counter)
              if (sharedPasswordAttemptsRef.current >= MAX_PASSWORD_ATTEMPTS) {
                logger.log(
                  '[UploaderConnections] locked out after',
                  MAX_PASSWORD_ATTEMPTS,
                  'failed attempts (shared counter)',
                )
                connectionStatus = UploaderConnectionStatus.LockedOut
                updateConnection((draft) => ({
                  ...draft,
                  status: UploaderConnectionStatus.LockedOut,
                }))

                const request: Message = {
                  type: MessageType.Error,
                  error:
                    'Too many failed password attempts. Please request a new share link.',
                }
                peerConn.send(request).catch(() => {}) // Peer may have disconnected
                peerConn.close()
                break
              }

              // Use constant-time comparison to prevent timing attacks
              if (secureCompare(submittedPassword, passwordRef.current)) {
                logger.log('[UploaderConnections] password correct')

                connectionStatus = UploaderConnectionStatus.Ready
                updateConnection((draft) => {
                  if (
                    draft.status !== UploaderConnectionStatus.Authenticating &&
                    draft.status !== UploaderConnectionStatus.InvalidPassword
                  ) {
                    return draft
                  }

                  return {
                    ...draft,
                    status: UploaderConnectionStatus.Ready,
                  }
                })

                await sendInfoMessage()
              } else {
                // Increment shared counter ONLY on failed attempts
                sharedPasswordAttemptsRef.current++
                const currentAttempts = sharedPasswordAttemptsRef.current

                // Server-side attempt tracking (defense-in-depth, blocking)
                if (channelSlugRef.current && channelSecretRef.current) {
                  const serverResult = await recordServerPasswordAttempt(
                    channelSlugRef.current,
                    channelSecretRef.current,
                  )
                  if (!serverResult.allowed) {
                    logger.log(
                      '[UploaderConnections] server rejected password attempt',
                    )
                    connectionStatus = UploaderConnectionStatus.LockedOut
                    updateConnection((draft) => ({
                      ...draft,
                      status: UploaderConnectionStatus.LockedOut,
                    }))
                    const request: Message = {
                      type: MessageType.Error,
                      error:
                        'Too many failed password attempts. Please request a new share link.',
                    }
                    peerConn.send(request).catch(() => {}) // Peer may have disconnected
                    peerConn.close()
                    break
                  }
                }

                logger.log(
                  '[UploaderConnections] password incorrect (attempt',
                  currentAttempts,
                  'of',
                  MAX_PASSWORD_ATTEMPTS,
                  ')',
                )
                connectionStatus = UploaderConnectionStatus.InvalidPassword
                updateConnection((draft) => {
                  if (
                    draft.status !== UploaderConnectionStatus.Authenticating &&
                    draft.status !== UploaderConnectionStatus.InvalidPassword
                  ) {
                    return draft
                  }

                  return {
                    ...draft,
                    status: UploaderConnectionStatus.InvalidPassword,
                  }
                })

                const remainingAttempts =
                  MAX_PASSWORD_ATTEMPTS - currentAttempts
                const request: Message = {
                  type: MessageType.PasswordRequired,
                  errorMessage: `Invalid password. ${remainingAttempts} attempt${remainingAttempts !== 1 ? 's' : ''} remaining.`,
                }
                peerConn.send(request).catch(() => {}) // Peer may have disconnected
              }
              break
            }

            case MessageType.Start: {
              // Enforce download limit on uploader side (defense-in-depth).
              // The server enforces via record_download_complete, but checking here
              // prevents wasting bandwidth on transfers that will be rejected.
              const maxDl = maxDownloadsRef.current
              if (maxDl > 0 && completedCountRef.current >= maxDl) {
                logger.warn(
                  '[UploaderConnections] rejecting Start — download limit reached:',
                  maxDl,
                )
                peerConn
                  .send({
                    type: MessageType.Error,
                    error: 'Download limit reached.',
                  } as Message)
                  .catch(() => {}) // Peer may have disconnected
                peerConn.close()
                break
              }

              const fileName = message.fileName
              let offset = message.offset

              // Prevent concurrent file transfers on the same connection (DoS protection)
              if (activeFileName && activeFileName !== fileName) {
                logger.warn(
                  '[UploaderConnections] rejecting concurrent Start for',
                  fileName,
                  'while',
                  activeFileName,
                  'is active',
                )
                peerConn
                  .send({
                    type: MessageType.Error,
                    error: 'Only one file transfer at a time.',
                  } as Message)
                  .catch(() => {}) // Peer may have disconnected
                break
              }
              activeFileName = fileName

              logger.log(
                '[UploaderConnections] starting transfer of',
                fileName,
                'from offset',
                offset,
              )
              const curFiles = filesRef.current
              const file = validateOffset(curFiles, fileName, offset)
              const fileIndex = curFiles.findIndex(
                (f) => getFileName(f) === fileName,
              )

              // Derive per-file encryption key if encryption is active
              let fileKeyPromise: Promise<CryptoKey> | null = null
              const curEncKey = encryptionKeyRef.current
              if (curEncKey) {
                fileKeyPromise = deriveFileKey(
                  curEncKey,
                  fileName,
                  fileIndex,
                  hkdfSaltRef.current ?? new Uint8Array(0),
                )
              }

              sendingPaused = false
              // Throttle progress UI updates to avoid flooding React's scheduler.
              // Transfer speed is not gated by UI — this only affects the progress bar.
              let lastProgressUpdate = 0
              const PROGRESS_INTERVAL = 100 // ms

              // Prefetch pipeline: read the next chunk from disk while the
              // current one is being encrypted and sent. This hides file I/O
              // latency behind encryption/transmission time, roughly doubling
              // throughput for large files.
              let prefetchedBuffer: ArrayBuffer | null = null
              let prefetchPromise: Promise<ArrayBuffer> | null = null
              let chunksSinceYield = 0

              const startPrefetch = (from: number) => {
                if (from >= file.size) {
                  prefetchPromise = null
                  return
                }
                const prefetchEnd = Math.min(file.size, from + MAX_CHUNK_SIZE)
                prefetchPromise = file.slice(from, prefetchEnd).arrayBuffer()
              }

              const sendNextChunkAsync = () => {
                // Use queueMicrotask for most chunks (near-zero delay) but
                // yield via setTimeout every 20 chunks so the browser can
                // paint and the UI stays responsive during large transfers.
                const schedule =
                  ++chunksSinceYield % 20 === 0
                    ? (fn: () => void) => setTimeout(fn, 0)
                    : queueMicrotask
                schedule(async () => {
                  try {
                    if (sendingPaused) return
                    const end = Math.min(file.size, offset + MAX_CHUNK_SIZE)
                    const final = isFinalChunk(offset, file.size)

                    // Use prefetched buffer if available, otherwise read now
                    let plaintext: ArrayBuffer
                    if (prefetchedBuffer) {
                      plaintext = prefetchedBuffer
                      prefetchedBuffer = null
                    } else {
                      plaintext = await file.slice(offset, end).arrayBuffer()
                    }

                    // Start prefetching the NEXT chunk while we encrypt/send this one
                    if (!final) {
                      startPrefetch(end)
                    }

                    let chunkBytes: ArrayBuffer
                    if (fileKeyPromise) {
                      const fileKey = await fileKeyPromise
                      if (!peerConn.open || sendingPaused) return
                      chunkBytes = await encryptChunk(fileKey, plaintext)
                    } else {
                      chunkBytes = plaintext
                    }

                    if (!peerConn.open || sendingPaused) return

                    // Await prefetch completion so the next iteration has data ready
                    if (prefetchPromise) {
                      prefetchedBuffer = await prefetchPromise
                      prefetchPromise = null
                    }

                    const request: Message = {
                      type: MessageType.Chunk,
                      fileName,
                      fileIndex,
                      offset,
                      bytes: chunkBytes,
                      final,
                    }
                    await peerConn.send(request)

                    // Update offset and state
                    const chunkSize = end - offset
                    offset = end
                    cumulativeBytesSent += chunkSize
                    if (final) {
                      activeFileName = null
                      connectionStatus = UploaderConnectionStatus.Ready
                      // Start background hashing after first file completes,
                      // so it doesn't compete with initial transfer I/O
                      startBackgroundHashing()
                      const sentSnapshot = cumulativeBytesSent
                      updateConnection((draft) => {
                        logger.log(
                          '[UploaderConnections] completed file',
                          fileName,
                          '- file',
                          draft.completedFiles + 1,
                          'of',
                          draft.totalFiles,
                        )
                        return {
                          ...draft,
                          status: UploaderConnectionStatus.Ready,
                          completedFiles: draft.completedFiles + 1,
                          currentFileProgress: 0,
                          bytesSent: sentSnapshot,
                        }
                      })
                    } else {
                      // Throttle progress updates to avoid excessive React re-renders
                      const now = performance.now()
                      if (now - lastProgressUpdate >= PROGRESS_INTERVAL) {
                        lastProgressUpdate = now
                        const sentSnapshot = cumulativeBytesSent
                        updateConnection((draft) => ({
                          ...draft,
                          uploadingOffset: end,
                          currentFileProgress: end / file.size,
                          bytesSent: sentSnapshot,
                        }))
                      }
                      sendNextChunkAsync()
                    }
                  } catch (err) {
                    logger.error(
                      '[UploaderConnections] chunk send failed:',
                      err,
                    )
                    peerConn
                      .send({
                        type: MessageType.Error,
                        error: 'Failed to send file data. Please try again.',
                      } as Message)
                      .catch(() => {}) // Peer may have disconnected
                    peerConn.close()
                  }
                })
              }

              // Guard: only start if connection is in valid state
              if (
                connectionStatus !== UploaderConnectionStatus.Ready &&
                connectionStatus !== UploaderConnectionStatus.Paused
              ) {
                logger.warn(
                  '[UploaderConnections] Start rejected — status:',
                  connectionStatus,
                )
                peerConn
                  .send({
                    type: MessageType.Error,
                    error: 'Uploader not ready. Try reloading.',
                  } as Message)
                  .catch(() => {}) // Peer may have disconnected
                break
              }

              connectionStatus = UploaderConnectionStatus.Uploading
              updateConnection((draft) => ({
                ...draft,
                status: UploaderConnectionStatus.Uploading,
                uploadingFileName: fileName,
                uploadingOffset: offset,
                acknowledgedBytes: 0,
                currentFileProgress: 0,
              }))
              sendNextChunkAsync()

              break
            }

            case MessageType.Pause: {
              logger.log('[UploaderConnections] transfer paused')
              connectionStatus = UploaderConnectionStatus.Paused
              // Set flag to cancel any in-flight async chunk sends
              sendingPaused = true
              updateConnection((draft) => {
                if (draft.status !== UploaderConnectionStatus.Uploading) {
                  return draft
                }

                return {
                  ...draft,
                  status: UploaderConnectionStatus.Paused,
                }
              })
              break
            }

            case MessageType.ChunkAck: {
              const ackMessage = message as z.infer<typeof ChunkAckMessage>
              logger.log(
                '[UploaderConnections] received chunk ack:',
                ackMessage.fileName,
                'offset',
                ackMessage.offset,
                'bytes',
                ackMessage.bytesReceived,
              )

              updateConnection((draft) => {
                const currentAcked = draft.acknowledgedBytes || 0
                const newAcked = currentAcked + ackMessage.bytesReceived

                const file = filesRef.current.find(
                  (f) => getFileName(f) === ackMessage.fileName,
                )
                if (file) {
                  const acknowledgedProgress = newAcked / file.size
                  return {
                    ...draft,
                    acknowledgedBytes: newAcked,
                    currentFileProgress: acknowledgedProgress,
                  }
                }

                return {
                  ...draft,
                  acknowledgedBytes: newAcked,
                }
              })
              break
            }

            case MessageType.Done: {
              logger.log(
                '[UploaderConnections] transfer completed successfully',
              )
              if (
                connectionStatus !== UploaderConnectionStatus.Ready &&
                connectionStatus !== UploaderConnectionStatus.Uploading
              ) {
                break
              }

              connectionStatus = UploaderConnectionStatus.Done
              updateConnection((draft) => ({
                ...draft,
                status: UploaderConnectionStatus.Done,
              }))
              peerConn.close()
              break
            }
            default:
              logger.warn(
                '[UploaderConnections] unhandled message type:',
                message.type,
              )
              break
          }
        } catch (err) {
          logger.error('[UploaderConnections] error handling message:', err)
          // Log full error locally but only send a generic message to the
          // remote peer to avoid leaking internal paths or state.
          peerConn
            .send({
              type: MessageType.Error,
              error: 'An error occurred on the sender side. Please try again.',
            } as Message)
            .catch(() => {}) // Peer may have disconnected
        }
      }

      // ── Connection Lifecycle ──

      const onClose = (): void => {
        logger.log('[UploaderConnections] connection closed')
        // Cancel any in-flight async chunk sends to prevent noisy error logs
        sendingPaused = true
        clearTimeout(handshakeTimer)
        idleTracker.destroy()
        peerMap.delete(remotePeerId)

        connectionStatus = UploaderConnectionStatus.Closed
        setConnections((conns) => {
          const updated = conns.map((c) => {
            if (c.dataConnection.peer !== remotePeerId) return c
            if (
              [
                UploaderConnectionStatus.InvalidPassword,
                UploaderConnectionStatus.Done,
              ].includes(c.status)
            ) {
              return c
            }
            return { ...c, status: UploaderConnectionStatus.Closed }
          })
          // Prune terminal connections beyond a cap to prevent unbounded growth
          const terminal = updated.filter((c) =>
            [
              UploaderConnectionStatus.Done,
              UploaderConnectionStatus.Closed,
              UploaderConnectionStatus.InvalidPassword,
              UploaderConnectionStatus.LockedOut,
            ].includes(c.status),
          )
          if (terminal.length > 50) {
            // Keep most recent 50 terminal connections
            const terminalSet = new Set(
              terminal.slice(50).map((c) => c.dataConnection.peer),
            )
            return updated.filter(
              (c) => !terminalSet.has(c.dataConnection.peer),
            )
          }
          return updated
        })
      }

      peerConn.onData = onData
      peerConn.onClose = onClose

      cleanupHandlers.push(() => {
        peerConn.onData = null
        // Don't null onClose before close() — PeerDataConnection.close() saves
        // and invokes it, which clears timers (idleCheck, etc.)
        peerConn.close()
        peerMap.delete(remotePeerId)
      })

      // Create offer and send to remote peer
      peerConn.createOffer().catch((err) => {
        logger.error('[UploaderConnections] createOffer failed:', err)
        peerConn.close()
      })
    }

    // ── Signaling Message Router ──

    const handleSignalingMessage = (msg: SignalingMessage) => {
      // Safely extract fromId — validate before use (prevents undefined cast)
      const fromId = typeof msg.fromId === 'string' ? msg.fromId : ''

      switch (msg.type) {
        case 'connect-request': {
          if (!fromId) {
            logger.warn(
              '[UploaderConnections] connect-request missing valid fromId',
            )
            break
          }
          const metadata = (msg.metadata as Record<string, unknown>) ?? {}
          setupPeerConnection(fromId, metadata)
          break
        }
        case 'answer': {
          if (!fromId) break
          const pc = peerMap.get(fromId)
          if (pc) {
            pc.handleAnswer(msg.sdp as string)
          }
          break
        }
        case 'ice-candidate': {
          if (!fromId) break
          const pc = peerMap.get(fromId)
          if (pc) {
            const candidate = parseIceCandidate(msg)
            if (candidate) pc.handleIceCandidate(candidate)
          }
          break
        }
        case 'peer-left': {
          const peerId = msg.peerId as string
          const pc = peerMap.get(peerId)
          if (pc) {
            pc.close()
            peerMap.delete(peerId)
          }
          break
        }
        case 'relay:start': {
          // Downloader wants to use relay fallback instead of WebRTC.
          // If the downloader already has a PeerDataConnection (from a failed
          // WebRTC attempt), the existing peer is already in peerMap with its
          // onData handler. Send relay:ack so the downloader knows relay is ready.
          if (!fromId) break
          logger.log('[UploaderConnections] relay requested by peer', fromId)
          signaling.send({
            type: 'relay:ack',
            targetId: fromId,
          })
          break
        }
        case 'relay:data': {
          // Text relay data from a downloader — route to existing peer's onData
          if (!fromId) break
          const pc = peerMap.get(fromId)
          if (pc && pc.onData) {
            try {
              const parsed = JSON.parse(msg.data as string)
              pc.onData(parsed)
            } catch {
              logger.error('[UploaderConnections] invalid relay data')
            }
          }
          break
        }
        case 'error': {
          logger.error('[UploaderConnections] signaling error:', msg.message)
          break
        }
      }
    }

    signaling.onMessage = handleSignalingMessage

    return () => {
      // Null onMessage FIRST to prevent new connections during teardown
      signaling.onMessage = null
      logger.log('[UploaderConnections] cleaning up connections')
      cleanupHandlers.forEach((fn) => fn())
    }
    // Only re-run this effect when the signaling client changes (new connection).
    // All other dependencies are accessed via refs to prevent tearing down
    // active peer connections when array/object identity changes on re-render.
  }, [signaling])

  return connections
}
