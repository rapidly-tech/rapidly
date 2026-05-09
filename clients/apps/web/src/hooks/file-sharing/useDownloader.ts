// ── Imports ──

import {
  FILE_SHARING_API,
  FILE_SHARING_SIGNAL_PATH,
  ZIP64_THRESHOLD,
} from '@/utils/file-sharing/constants'
import { hashPassword } from '@/utils/file-sharing/crypto'
import {
  streamDownloadMultipleFiles,
  streamDownloadSingleFile,
} from '@/utils/file-sharing/download'
import {
  decryptChunk,
  decryptMetadata,
  deriveFileKey,
  deriveReaderToken,
  GCM_TAG_LENGTH,
  IV_LENGTH,
  verifyKeyCommitment,
} from '@/utils/file-sharing/encryption'
import { IdleTracker } from '@/utils/file-sharing/idle-tracker'
import { logger } from '@/utils/file-sharing/logger'
import {
  ChunkMessage,
  decodeMessage,
  InfoMessage,
  Message,
  MessageType,
} from '@/utils/file-sharing/messages'
import {
  cleanExpired,
  deleteProgress,
  FileProgress,
  loadProgress,
  saveProgress,
} from '@/utils/file-sharing/resume-store'
import { parseIceCandidate } from '@/utils/file-sharing/signaling-helpers'
import { StreamingSHA256 } from '@/utils/file-sharing/streaming-hash'
import { PeerDataConnection } from '@/utils/p2p/peer-connection'
import { SignalingClient, SignalingMessage } from '@/utils/p2p/signaling'
import { WebSocketRelay } from '@/utils/p2p/ws-relay'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  browserName,
  browserVersion,
  mobileModel,
  mobileVendor,
  osName,
  osVersion,
} from 'react-device-detect'
import { z } from 'zod'
import { IDLE_TIMEOUT, MAX_CHUNK_SIZE } from './useUploaderConnections'

// ── Constants ──

// Uploader sends MAX_CHUNK_SIZE plaintext chunks; encrypted chunks add IV + GCM tag
// Reject individual chunks larger than this to prevent memory exhaustion
const ENCRYPTION_OVERHEAD_PER_CHUNK = IV_LENGTH + GCM_TAG_LENGTH
const MAX_INCOMING_CHUNK_SIZE =
  MAX_CHUNK_SIZE + ENCRYPTION_OVERHEAD_PER_CHUNK + 1024 // + 1KB margin

const getZipFilename = (): string => `file-sharing-download-${Date.now()}.zip`

// ── Main Hook ──

export function useDownloader(
  slug: string,
  encryptionKey: CryptoKey | null = null,
  hkdfSalt?: Uint8Array,
  paymentToken?: string | null,
): {
  filesInfo: Array<{
    fileName: string
    size: number
    type: string
    sha256?: string
  }> | null
  isConnected: boolean
  isPasswordRequired: boolean
  isDownloading: boolean
  isDone: boolean
  isEncrypted: boolean
  isResuming: boolean
  isRelayMode: boolean
  errorMessage: string | null
  passwordError: string | null
  submitPassword: (
    password: string,
    options?: { alreadyHashed?: boolean },
  ) => Promise<void>
  startDownload: () => void
  stopDownload: () => void
  pauseDownload: () => void
  resumeDownload: () => void
  isPaused: boolean
  totalSize: number
  bytesDownloaded: number
  filesCompleted: number
  remainingDownloads: number | null // null = unlimited
} {
  // ── State ──

  const [filesInfo, setFilesInfo] = useState<Array<{
    fileName: string
    size: number
    type: string
    sha256?: string
  }> | null>(null)
  const processChunk = useRef<
    ((message: z.infer<typeof ChunkMessage>) => Promise<void>) | null
  >(null)
  const [isConnected, setIsConnected] = useState(false)
  const [isPasswordRequired, setIsPasswordRequired] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)
  const [isDone, setDone] = useState(false)
  const [bytesDownloaded, setBytesDownloaded] = useState(0)
  const [filesCompleted, setFilesCompleted] = useState(0)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [remainingDownloads, setRemainingDownloads] = useState<number | null>(
    null,
  )
  const [isEncrypted, setIsEncrypted] = useState(false)
  const [isResuming, setIsResuming] = useState(false)
  // Store resume progress data for use in startDownload
  const resumeProgressRef = useRef<Record<string, FileProgress> | null>(null)
  const isEncryptedRef = useRef(false)
  isEncryptedRef.current = isEncrypted
  const encryptionKeyRef = useRef(encryptionKey)
  encryptionKeyRef.current = encryptionKey
  const hkdfSaltRef = useRef(hkdfSalt)
  hkdfSaltRef.current = hkdfSalt
  // Track completion so post-teardown errors (DataChannel close) don't flash error UI
  const doneRef = useRef(false)
  // Track open file streams so stopDownload can close them (prevent resource leaks)
  const activeStreamsRef = useRef<Array<{ close: () => void }>>([])
  // Keep signaling client ref for cleanup
  const signalingRef = useRef<SignalingClient | null>(null)
  // Keep peer connection ref for cleanup (prevents orphaned RTCPeerConnection/TURN allocations)
  const peerConnRef = useRef<PeerDataConnection | null>(null)
  // Keep idle tracker ref for cleanup on unmount
  const idleTrackerRef = useRef<IdleTracker | null>(null)
  // Relay state for HTTP fallback
  const [isPaused, setIsPaused] = useState(false)
  const isPausedRef = useRef(false)
  // Holds a resume callback set inside startDownload closure (has access to local state)
  const resumeFnRef = useRef<(() => void) | null>(null)
  const [isRelayMode, setIsRelayMode] = useState(false)
  const relayRef = useRef<WebSocketRelay | null>(null)
  const iceTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Guard flag set by stopDownload — prevents pc.onOpen from flashing isConnected=true
  // during the 100ms teardown delay between peerConnRef=null and pc.close()
  const stoppedRef = useRef(false)
  // Ref to avoid stale slug closure in startDownload callback
  const slugRef = useRef(slug)
  slugRef.current = slug
  const paymentTokenRef = useRef(paymentToken)
  paymentTokenRef.current = paymentToken

  // ── Signaling and Peer Connection ──

  useEffect(() => {
    // Wait for both slug and encryptionKey to be available before connecting.
    // The reader token (derived from encryptionKey + hkdfSalt) is required for
    // authentication — connecting without it would either fail or bypass auth.
    if (!slug || !encryptionKey) return

    stoppedRef.current = false
    let cancelled = false
    const signaling = new SignalingClient(FILE_SHARING_SIGNAL_PATH)
    signalingRef.current = signaling

    // Clean up expired resume entries on mount (non-blocking)
    cleanExpired()

    const connect = async () => {
      try {
        // Derive reader token for authentication
        let token = ''
        const currentKey = encryptionKeyRef.current
        const currentSalt = hkdfSaltRef.current
        if (currentKey && currentSalt) {
          token = await deriveReaderToken(currentKey, currentSalt)
        }

        if (cancelled || stoppedRef.current) return

        const connectOptions = paymentTokenRef.current
          ? { paymentToken: paymentTokenRef.current }
          : undefined
        await signaling.connect(slug, 'downloader', token, connectOptions)
        if (cancelled || stoppedRef.current) {
          signaling.close()
          return
        }

        const iceServers = signaling.iceServers

        // Send connect-request to uploader (routed via signaling server)
        signaling.send({ type: 'connect-request' })

        // Wait for offer from uploader
        signaling.onMessage = async (msg: SignalingMessage) => {
          if (cancelled || stoppedRef.current) return

          switch (msg.type) {
            case 'offer': {
              const fromId = msg.fromId
              if (typeof fromId !== 'string' || !fromId) {
                logger.error('[Downloader] offer missing valid fromId')
                break
              }
              // Clean up any existing connection before creating a new one
              // (prevents resource leak if server sends duplicate offers)
              if (idleTrackerRef.current) {
                idleTrackerRef.current.destroy()
                idleTrackerRef.current = null
              }
              if (peerConnRef.current) {
                peerConnRef.current.close()
                peerConnRef.current = null
              }
              const pc = new PeerDataConnection(signaling, iceServers, fromId)
              peerConnRef.current = pc

              // Idle timeout tracking
              const idleTracker = new IdleTracker(IDLE_TIMEOUT, () => {
                logger.log('[Downloader] closing idle connection')
                pc.close()
              })
              idleTrackerRef.current = idleTracker

              pc.onOpen = () => {
                if (cancelled || stoppedRef.current) return
                logger.log('[Downloader] data channel opened')
                // Cancel ICE timeout — WebRTC succeeded
                if (iceTimeoutRef.current) {
                  clearTimeout(iceTimeoutRef.current)
                  iceTimeoutRef.current = null
                }
                setIsConnected(true)
                pc.send({
                  type: MessageType.RequestInfo,
                  browserName,
                  browserVersion,
                  osName,
                  osVersion,
                  mobileVendor,
                  mobileModel,
                } as z.infer<typeof Message>).catch(() => {}) // Connection may have closed
              }

              // Promise chain to serialize async processChunk calls
              let chunkChain = Promise.resolve()

              pc.onData = async (data: unknown) => {
                if (cancelled || stoppedRef.current) return
                try {
                  const message = decodeMessage(data)
                  idleTracker.resetActivity()
                  logger.log('[Downloader] received message', message.type)

                  // Respond to pings, ignore pongs (they just reset activity)
                  if (message.type === MessageType.Ping) {
                    pc.send({ type: MessageType.Pong }).catch(() => {}) // Connection may have closed
                    return
                  }
                  if (message.type === MessageType.Pong) return

                  switch (message.type) {
                    case MessageType.PasswordRequired:
                      setIsPasswordRequired(true)
                      setErrorMessage(null)
                      if (message.errorMessage)
                        setPasswordError(message.errorMessage)
                      break
                    case MessageType.Info: {
                      // Validate no duplicate file names (would corrupt stream routing)
                      const names = new Set(
                        message.files.map(
                          (f: { fileName: string }) => f.fileName,
                        ),
                      )
                      if (names.size !== message.files.length) {
                        logger.error(
                          '[Downloader] duplicate file names in Info message',
                        )
                        setErrorMessage(
                          'The sender has files with duplicate names. Ask them to rename and try again.',
                        )
                        pc.close()
                        break
                      }

                      // Verify key commitments if present (HMAC-SHA256)
                      const curKey = encryptionKeyRef.current
                      const curSalt = hkdfSaltRef.current
                      if (curKey && curSalt) {
                        for (let i = 0; i < message.files.length; i++) {
                          const f = message.files[i]
                          if (f.commitment) {
                            try {
                              const valid = await verifyKeyCommitment(
                                curKey,
                                f.fileName,
                                f.size,
                                i,
                                curSalt,
                                f.commitment,
                              )
                              if (!valid) {
                                logger.error(
                                  `[Downloader] key commitment mismatch for ${f.fileName}`,
                                )
                                setErrorMessage(
                                  `Key commitment verification failed for "${f.fileName}". The encryption key may have been substituted.`,
                                )
                                pc.close()
                                return
                              }
                            } catch (err) {
                              logger.error(
                                '[Downloader] commitment verification error:',
                                err,
                              )
                              setErrorMessage(
                                'Failed to verify key commitment. The link may be corrupted.',
                              )
                              pc.close()
                              return
                            }
                          }
                        }
                      }

                      setFilesInfo(message.files)
                      setIsPasswordRequired(false)
                      setPasswordError(null)
                      setRemainingDownloads(message.remainingDownloads ?? null)
                      setIsEncrypted(message.encrypted ?? false)

                      // Check IndexedDB for prior progress (resume support)
                      if (hkdfSaltRef.current) {
                        try {
                          const prior = await loadProgress(
                            slugRef.current,
                            hkdfSaltRef.current,
                          )
                          if (prior) {
                            // Compare filesInfo to detect if files changed
                            const filesMatch =
                              prior.filesInfo.length === message.files.length &&
                              prior.filesInfo.every(
                                (pf, i) =>
                                  pf.fileName === message.files[i].fileName &&
                                  pf.size === message.files[i].size,
                              )
                            if (filesMatch) {
                              const hasProgress = Object.values(
                                prior.fileProgress,
                              ).some(
                                (fp) => fp.bytesReceived > 0 || fp.completed,
                              )
                              if (hasProgress) {
                                resumeProgressRef.current = prior.fileProgress
                                setIsResuming(true)
                              }
                            } else {
                              // Files changed — discard progress
                              await deleteProgress(
                                slugRef.current,
                                hkdfSaltRef.current,
                              )
                            }
                          }
                        } catch {
                          // IndexedDB unavailable — no resume
                        }
                      }
                      break
                    }
                    case MessageType.EncryptedInfo: {
                      const key = encryptionKeyRef.current
                      if (!key) {
                        logger.error(
                          '[Downloader] received encrypted metadata but no key available',
                        )
                        setErrorMessage(
                          'This transfer has encrypted metadata but the link is missing the encryption key. Ask the sender for a new link.',
                        )
                        pc.close()
                        break
                      }
                      try {
                        const decrypted = await decryptMetadata(
                          key,
                          message.payload as ArrayBuffer,
                          hkdfSaltRef.current ?? new Uint8Array(0),
                        )
                        const info = InfoMessage.parse(decrypted)
                        const encNames = new Set(
                          info.files.map(
                            (f: { fileName: string }) => f.fileName,
                          ),
                        )
                        if (encNames.size !== info.files.length) {
                          logger.error(
                            '[Downloader] duplicate file names in EncryptedInfo',
                          )
                          setErrorMessage(
                            'The sender has files with duplicate names. Ask them to rename and try again.',
                          )
                          pc.close()
                          break
                        }
                        // Verify key commitments if present (HMAC-SHA256)
                        const encInfoKey = encryptionKeyRef.current
                        const encInfoSalt = hkdfSaltRef.current
                        if (encInfoKey && encInfoSalt) {
                          for (let i = 0; i < info.files.length; i++) {
                            const f = info.files[i]
                            if (f.commitment) {
                              const valid = await verifyKeyCommitment(
                                encInfoKey,
                                f.fileName,
                                f.size,
                                i,
                                encInfoSalt,
                                f.commitment,
                              )
                              if (!valid) {
                                logger.error(
                                  `[Downloader] key commitment mismatch for ${f.fileName}`,
                                )
                                setErrorMessage(
                                  `Key commitment verification failed for "${f.fileName}". The encryption key may have been substituted.`,
                                )
                                pc.close()
                                return
                              }
                            }
                          }
                        }

                        setFilesInfo(info.files)
                        setIsPasswordRequired(false)
                        setPasswordError(null)
                        setRemainingDownloads(info.remainingDownloads ?? null)
                        setIsEncrypted(info.encrypted ?? false)
                      } catch (err) {
                        logger.error(
                          '[Downloader] failed to decrypt metadata:',
                          err,
                        )
                        setErrorMessage(
                          'Failed to decrypt file metadata. The encryption key may be invalid.',
                        )
                        pc.close()
                      }
                      break
                    }
                    case MessageType.Chunk:
                      // Serialize chunk processing via promise chain to prevent
                      // concurrent async execution (fire-and-forget from sync onData)
                      chunkChain = chunkChain
                        .then(() => processChunk.current?.(message))
                        .catch((err: unknown) => {
                          logger.error('[Downloader] processChunk error:', err)
                        })
                      break
                    case MessageType.Error:
                      logger.error(
                        '[Downloader] received error message:',
                        message.error,
                      )
                      setErrorMessage(message.error)
                      pc.close()
                      break
                    case MessageType.Report:
                      // Ignore peer-supplied report messages — report actions must
                      // go through the server-side report API. Trusting peer messages
                      // would let a malicious uploader force-redirect the downloader.
                      logger.warn(
                        '[Downloader] ignoring unverified report message from uploader',
                      )
                      break
                  }
                } catch (err) {
                  logger.error('[Downloader] error handling message:', err)
                }
              }

              pc.onClose = () => {
                logger.log('[Downloader] connection closed')
                idleTracker.destroy()
                // Close any active download streams so the download promise
                // can settle (e.g. if connection drops mid-transfer)
                for (const s of activeStreamsRef.current) {
                  try {
                    s.close()
                  } catch {
                    /* stream may already be closed */
                  }
                }
                activeStreamsRef.current = []
                if (cancelled) return
                peerConnRef.current = null
                setIsConnected(false)
                if (!doneRef.current) {
                  setIsDownloading(false)
                }
              }

              pc.onError = (err: Error) => {
                if (cancelled) return
                // Ignore DataChannel errors after download is complete (benign teardown)
                if (doneRef.current) {
                  logger.log(
                    '[Downloader] ignoring post-completion error:',
                    err.message,
                  )
                  return
                }
                logger.error('[Downloader] connection error:', err)
                setErrorMessage(err.message)
                pc.close()
              }

              // Handle the offer
              await pc.handleOffer(msg.sdp as string)

              // ICE timeout: if DataChannel doesn't open in 15s, fall back to relay
              if (iceTimeoutRef.current) clearTimeout(iceTimeoutRef.current)
              iceTimeoutRef.current = setTimeout(() => {
                if (!pc.open && !stoppedRef.current && !cancelled) {
                  logger.log(
                    '[Downloader] ICE timeout — falling back to WS relay',
                  )
                  const relay = new WebSocketRelay(signaling, fromId)
                  relayRef.current = relay
                  setIsRelayMode(true)

                  relay.onData = (data: unknown) => {
                    if (cancelled || stoppedRef.current) return
                    try {
                      const message = decodeMessage(data)
                      idleTracker.resetActivity()
                      if (message.type === MessageType.Ping) {
                        relay.send({ type: MessageType.Pong }).catch(() => {}) // Connection may have closed
                        return
                      }
                      if (message.type === MessageType.Pong) return
                      if (message.type === MessageType.Chunk) {
                        chunkChain = chunkChain
                          .then(() => processChunk.current?.(message))
                          .catch((err: unknown) => {
                            logger.error(
                              '[Downloader] relay processChunk error:',
                              err,
                            )
                          })
                      }
                    } catch (err) {
                      logger.error('[Downloader] relay message error:', err)
                    }
                  }

                  relay.onClose = () => {
                    if (!doneRef.current) setIsConnected(false)
                  }

                  relay.start()
                  setIsConnected(true)
                  // Send RequestInfo via relay
                  relay
                    .send({
                      type: MessageType.RequestInfo,
                      browserName,
                      browserVersion,
                      osName,
                      osVersion,
                      mobileVendor,
                      mobileModel,
                    })
                    .catch(() => {}) // Connection may have closed
                }
              }, 15_000)

              // No handler replacement — the main handler below routes
              // ice-candidate/peer-left/error via peerConnRef, and can
              // handle new offers for reconnection scenarios.
              break
            }
            case 'ice-candidate': {
              const currentPc = peerConnRef.current
              if (currentPc) {
                const msgFromId = msg.fromId
                if (
                  typeof msgFromId === 'string' &&
                  msgFromId === currentPc.peer
                ) {
                  const candidate = parseIceCandidate(msg)
                  if (candidate) currentPc.handleIceCandidate(candidate)
                }
              }
              break
            }
            case 'peer-left': {
              const currentPc = peerConnRef.current
              if (currentPc && (msg.peerId as string) === currentPc.peer) {
                logger.log('[Downloader] uploader disconnected')
                if (!doneRef.current) {
                  setErrorMessage(
                    'The sender closed their browser or lost connectivity.',
                  )
                }
                currentPc.close()
              } else if (!currentPc) {
                logger.log('[Downloader] uploader disconnected before offer')
                setErrorMessage(
                  'The sender closed their browser or lost connectivity.',
                )
              }
              break
            }
            case 'relay:start':
            case 'relay:ack':
            case 'relay:done':
            case 'relay:data': {
              // Forward relay messages to the WebSocketRelay handler
              const relay = relayRef.current
              if (relay) {
                if (msg.type === 'relay:data' && typeof msg.data === 'string') {
                  try {
                    relay.handleRelayData(msg.data as string)
                  } catch {
                    logger.error('[Downloader] relay data error')
                  }
                } else if (msg.type === 'relay:done') {
                  relay.close()
                }
              }
              break
            }
            case 'relay:binary': {
              // Binary relay data from signaling server
              const relay2 = relayRef.current
              if (relay2 && msg.data instanceof ArrayBuffer) {
                relay2.handleRelayData(msg.data as ArrayBuffer)
              }
              break
            }
            case 'error':
              logger.error('[Downloader] signaling error:', msg.message)
              if (!peerConnRef.current) {
                setErrorMessage(
                  'Connection failed. The link may be invalid or expired.',
                )
              }
              break
          }
        }

        signaling.onClose = () => {
          if (!cancelled) {
            logger.log('[Downloader] signaling closed')
          }
        }
      } catch (err) {
        if (!cancelled) {
          logger.error('[Downloader] signaling connection failed:', err)
          setErrorMessage(
            err instanceof Error
              ? err.message
              : 'Could not connect to the uploader. They may have closed their browser or the download limit was reached.',
          )
        }
      }
    }

    connect()

    return () => {
      cancelled = true
      logger.log('[Downloader] cleaning up')
      // Reset download state so a new slug/key triggers a fresh download
      downloadStartedRef.current = false
      doneRef.current = false
      processChunk.current = null
      // Reset UI state to prevent stale values when effect re-runs
      setFilesInfo(null)
      setIsConnected(false)
      setIsPasswordRequired(false)
      setIsDownloading(false)
      setDone(false)
      setBytesDownloaded(0)
      setFilesCompleted(0)
      setErrorMessage(null)
      setPasswordError(null)
      setRemainingDownloads(null)
      setIsEncrypted(false)
      // Cancel ICE timeout
      if (iceTimeoutRef.current) {
        clearTimeout(iceTimeoutRef.current)
        iceTimeoutRef.current = null
      }
      // Close relay
      if (relayRef.current) {
        relayRef.current.close()
        relayRef.current = null
      }
      setIsRelayMode(false)
      // Destroy idle tracker to prevent leak
      if (idleTrackerRef.current) {
        idleTrackerRef.current.destroy()
        idleTrackerRef.current = null
      }
      if (peerConnRef.current) {
        peerConnRef.current.close()
        peerConnRef.current = null
      }
      signaling.close()
      signalingRef.current = null
    }
  }, [slug, encryptionKey, paymentToken])

  // ── Password Submission ──

  const submitPassword = useCallback(
    async (pass: string, { alreadyHashed = false } = {}) => {
      const pc = peerConnRef.current
      if (!pc) return
      logger.log('[Downloader] submitting password')
      setPasswordError(null)
      // Hash the password to match the uploader's stored hash.
      // Skip hashing if the password is already a SHA-256 hex digest (e.g. from legacy URL fragment).
      const hashedPass = alreadyHashed ? pass : await hashPassword(pass)
      pc.send({
        type: MessageType.UsePassword,
        password: hashedPass,
      } as z.infer<typeof Message>).catch(() => {}) // Connection may have closed
    },
    [],
  )

  // Keep filesInfo ref in sync for use in startDownload (avoids stale closure)
  const filesInfoRef = useRef(filesInfo)
  filesInfoRef.current = filesInfo
  // Guard against double-invocation of startDownload (e.g. rapid double-click)
  const downloadStartedRef = useRef(false)

  // ── Download Logic ──

  const startDownload = useCallback(() => {
    const pc = peerConnRef.current
    const currentFilesInfo = filesInfoRef.current
    if (!currentFilesInfo || currentFilesInfo.length === 0 || !pc) return
    if (downloadStartedRef.current) return
    downloadStartedRef.current = true

    // Check if transfer is encrypted but we have no key
    const currentKey = encryptionKeyRef.current
    if (isEncryptedRef.current && !currentKey) {
      setErrorMessage(
        'This transfer is encrypted but the link is missing the encryption key. Ask the sender for a new link.',
      )
      pc.close()
      return
    }

    logger.log('[Downloader] starting download')
    setIsDownloading(true)

    // Cache per-file decryption keys to avoid re-deriving for each chunk
    const fileKeyCache: Record<string, Promise<CryptoKey>> = {}

    const getFileKey = (
      fileName: string,
      fileIndex: number,
    ): Promise<CryptoKey> | null => {
      if (!currentKey || !isEncryptedRef.current) return null
      const cacheKey = `${fileName}:${fileIndex}`
      if (!fileKeyCache[cacheKey]) {
        fileKeyCache[cacheKey] = deriveFileKey(
          currentKey,
          fileName,
          fileIndex,
          hkdfSaltRef.current ?? new Uint8Array(0),
        )
      }
      return fileKeyCache[cacheKey]
    }

    const fileStreamByPath: Record<
      string,
      {
        stream: ReadableStream<Uint8Array>
        enqueue: (chunk: Uint8Array) => void
        close: () => void
      }
    > = {}
    const fileStreams = currentFilesInfo.map((info) => {
      let enqueue: ((chunk: Uint8Array) => void) | null = null
      let close: (() => void) | null = null
      const stream = new ReadableStream<Uint8Array>({
        start(ctrl) {
          enqueue = (chunk: Uint8Array) => ctrl.enqueue(chunk)
          close = () => ctrl.close()
        },
      })
      if (!enqueue || !close)
        throw new Error('Failed to initialize stream controllers')
      fileStreamByPath[info.fileName] = { stream, enqueue, close }
      activeStreamsRef.current.push({ close })
      return stream
    })

    // Resume progress — restore state from IndexedDB if available
    const resumeData = resumeProgressRef.current
    resumeProgressRef.current = null
    setIsResuming(false)

    let nextFileIndex = 0
    // Track which files have been requested so far to reject unsolicited chunks
    const requestedFiles = new Set<string>()
    const startNextFileOrFinish = () => {
      // Skip completed files from prior session
      while (
        nextFileIndex < currentFilesInfo.length &&
        resumeData?.[currentFilesInfo[nextFileIndex].fileName]?.completed
      ) {
        const skippedName = currentFilesInfo[nextFileIndex].fileName
        completedFiles.add(skippedName)
        requestedFiles.add(skippedName)
        // Close the stream for the already-completed file
        const skipStream = fileStreamByPath[skippedName]
        if (skipStream) skipStream.close()
        logger.log('[Downloader] skipping completed file:', skippedName)
        nextFileIndex++
      }
      if (nextFileIndex >= currentFilesInfo.length) {
        activeFileName = null
        return
      }
      const fileName = currentFilesInfo[nextFileIndex].fileName
      activeFileName = fileName
      requestedFiles.add(fileName)
      // Use offset from resume data if available
      const resumeOffset = resumeData?.[fileName]?.bytesReceived ?? 0
      logger.log(
        '[Downloader] starting next file:',
        fileName,
        'offset:',
        resumeOffset,
      )
      pc.send({
        type: MessageType.Start,
        fileName,
        offset: resumeOffset,
      } as z.infer<typeof Message>).catch(() => {}) // Connection may have closed
      nextFileIndex++
    }

    // O(1) lookup for file info by name (avoids O(n) .find() per chunk)
    const fileInfoMap = new Map(currentFilesInfo.map((f) => [f.fileName, f]))

    const chunkCountByFile: Record<string, number> = {}
    const completedFiles = new Set<string>()

    // Track expected next offset per file to detect out-of-order/replay chunks
    const expectedOffset: Record<string, number> = {}
    // Track total bytes received per file to detect overflow beyond declared size
    const totalBytesReceived: Record<string, number> = {}

    // Incremental SHA-256 hashers per file for integrity verification
    const integrityHashers: Record<string, StreamingSHA256> = {}
    const expectedHashes: Record<string, string> = {}
    for (const info of currentFilesInfo) {
      if (info.sha256) {
        expectedHashes[info.fileName] = info.sha256
        // Restore hasher from resume data if available
        const rp = resumeData?.[info.fileName]
        if (rp?.hasherState && !rp.completed) {
          try {
            integrityHashers[info.fileName] = StreamingSHA256.deserialize(
              rp.hasherState,
            )
          } catch {
            // Deserialization failed — restart hash for this file
            integrityHashers[info.fileName] = new StreamingSHA256()
          }
        } else if (!rp?.completed) {
          integrityHashers[info.fileName] = new StreamingSHA256()
        }
      }
    }

    // Restore expected offsets and bytes received from resume data
    if (resumeData) {
      for (const info of currentFilesInfo) {
        const rp = resumeData[info.fileName]
        if (rp && !rp.completed) {
          expectedOffset[info.fileName] = rp.bytesReceived
          totalBytesReceived[info.fileName] = rp.bytesReceived
        }
      }
    }

    // Track the file currently being received (for in-session pause/resume)
    let activeFileName: string | null = null

    // Set up resume function — captures closure locals (expectedOffset, nextFileIndex, etc.)
    resumeFnRef.current = () => {
      if (!activeFileName) return
      const offset = expectedOffset[activeFileName] ?? 0
      logger.log(
        '[Downloader] resuming file:',
        activeFileName,
        'from offset:',
        offset,
      )
      pc.send({
        type: MessageType.Start,
        fileName: activeFileName,
        offset,
      } as z.infer<typeof Message>).catch(() => {}) // Connection may have closed
    }

    // Periodic progress save for resume (every 5 seconds)
    let lastSaveTime = 0
    const SAVE_INTERVAL = 5_000
    const saveResumeProgress = () => {
      const curSalt = hkdfSaltRef.current
      if (!curSalt) return
      const now = performance.now()
      if (now - lastSaveTime < SAVE_INTERVAL) return
      lastSaveTime = now
      const fileProgress: Record<string, FileProgress> = {}
      for (const info of currentFilesInfo) {
        fileProgress[info.fileName] = {
          bytesReceived: expectedOffset[info.fileName] ?? 0,
          completed: completedFiles.has(info.fileName),
          hasherState: integrityHashers[info.fileName]
            ? integrityHashers[info.fileName].serialize()
            : null,
        }
      }
      saveProgress(slugRef.current, curSalt, currentFilesInfo, fileProgress)
    }

    // Throttle progress state updates to avoid flooding React with re-renders
    let lastProgressUpdate = 0
    let pendingBytes = 0
    const PROGRESS_INTERVAL = 100 // ms

    processChunk.current = async (message: z.infer<typeof ChunkMessage>) => {
      // Drop chunks that arrive after pause (uploader may have queued them before receiving Pause)
      if (isPausedRef.current) return

      // Reject chunks for files we haven't requested yet (prevents unsolicited data injection)
      if (!requestedFiles.has(message.fileName)) {
        logger.warn(
          `[Downloader] ignoring chunk for unrequested file: ${message.fileName}`,
        )
        return
      }

      // Skip chunks for files that are already complete
      if (completedFiles.has(message.fileName)) {
        logger.log(
          `[Downloader] ignoring duplicate chunk for completed file: ${message.fileName}`,
        )
        return
      }

      const fileStream = fileStreamByPath[message.fileName]
      if (!fileStream) {
        logger.error('[Downloader] no stream found for', message.fileName)
        return
      }

      if (!chunkCountByFile[message.fileName]) {
        chunkCountByFile[message.fileName] = 0
      }
      chunkCountByFile[message.fileName]++

      let chunkData = message.bytes as ArrayBuffer

      // Capture raw (pre-decryption) size for consistent overflow tracking
      const rawChunkSize = chunkData.byteLength

      // Use ref to avoid stale closure over peerConn state
      const activePc = peerConnRef.current

      // Validate chunk size to prevent memory exhaustion from malicious uploaders
      if (rawChunkSize > MAX_INCOMING_CHUNK_SIZE) {
        logger.error(
          `[Downloader] chunk too large: ${rawChunkSize} bytes (max ${MAX_INCOMING_CHUNK_SIZE})`,
        )
        setErrorMessage(
          'Received an oversized chunk. The transfer may be corrupted or malicious.',
        )
        activePc?.close()
        return
      }

      // Validate chunk offset matches expected position (prevents replay/reorder attacks)
      const expected = expectedOffset[message.fileName] ?? 0
      if (message.offset !== expected) {
        logger.error(
          `[Downloader] unexpected offset for ${message.fileName}: got ${message.offset}, expected ${expected}`,
        )
        setErrorMessage(
          'Received out-of-order data. The transfer may be corrupted.',
        )
        activePc?.close()
        return
      }

      // Check declared file size isn't exceeded
      const fileInfo = fileInfoMap.get(message.fileName)
      const received =
        (totalBytesReceived[message.fileName] ?? 0) + rawChunkSize
      if (fileInfo) {
        const numChunks = Math.ceil(fileInfo.size / MAX_CHUNK_SIZE) + 1
        const maxOverhead = numChunks * ENCRYPTION_OVERHEAD_PER_CHUNK + 1024
        if (received > fileInfo.size + maxOverhead) {
          logger.error(
            `[Downloader] file ${message.fileName} exceeded declared size: ${received} > ${fileInfo.size} (max overhead ${maxOverhead})`,
          )
          setErrorMessage(
            'Received more data than expected. The transfer may be corrupted.',
          )
          activePc?.close()
          return
        }
      }
      totalBytesReceived[message.fileName] = received

      // Decrypt chunk if encryption is active
      const fileIndex = message.fileIndex ?? 0
      const fileKeyPromise = getFileKey(message.fileName, fileIndex)
      if (fileKeyPromise) {
        try {
          const fileKey = await fileKeyPromise
          // Guard: component may have unmounted or paused during async key derivation
          if (!processChunk.current || isPausedRef.current) return
          chunkData = await decryptChunk(fileKey, chunkData)
          // Guard: component may have unmounted or paused during async decryption
          if (!processChunk.current || isPausedRef.current) return
        } catch (err) {
          logger.error('[Downloader] decryption failed for chunk:', err)
          setErrorMessage(
            'Decryption failed. The encryption key may be invalid or the data was tampered with.',
          )
          activePc?.close()
          return
        }
      }

      // Use decrypted size for progress display and offset tracking
      const decryptedChunkSize = chunkData.byteLength

      // Update offset tracking with plaintext size.
      // IMPORTANT: Offsets are always in plaintext byte positions. The uploader sends
      // message.offset based on raw file position (before encryption), so we advance
      // by decryptedChunkSize here to stay in sync. Do not change to ciphertext size.
      expectedOffset[message.fileName] = message.offset + decryptedChunkSize
      fileStream.enqueue(new Uint8Array(chunkData))

      // Feed decrypted chunk into incremental hasher for integrity verification
      if (integrityHashers[message.fileName]) {
        integrityHashers[message.fileName].update(chunkData)
      }

      // Throttle progress state updates to avoid excessive React re-renders.
      // Accumulate bytes and flush at intervals (or on final chunk).
      pendingBytes += decryptedChunkSize
      const now = performance.now()
      if (now - lastProgressUpdate >= PROGRESS_INTERVAL || message.final) {
        const bytes = pendingBytes
        pendingBytes = 0
        lastProgressUpdate = now
        setBytesDownloaded((bd) => bd + bytes)
      }

      // Periodic save for resume support
      saveResumeProgress()

      const ackMessage: Message = {
        type: MessageType.ChunkAck,
        fileName: message.fileName,
        offset: message.offset,
        bytesReceived: decryptedChunkSize,
      }
      activePc?.send(ackMessage)?.catch(() => {}) // Connection may have closed

      if (message.final) {
        logger.log(
          `[Downloader] finished receiving ${message.fileName} after ${chunkCountByFile[message.fileName]} chunks`,
        )

        // Verify SHA-256 integrity if hash was provided
        if (
          expectedHashes[message.fileName] &&
          integrityHashers[message.fileName]
        ) {
          let actualHash: string
          try {
            actualHash = integrityHashers[message.fileName].finalize()
          } catch (hashErr) {
            logger.error(
              `[Downloader] hash finalization failed for ${message.fileName}:`,
              hashErr,
            )
            setErrorMessage(
              `Integrity verification failed for "${message.fileName}".`,
            )
            fileStream.close()
            activePc?.close()
            return
          } finally {
            delete integrityHashers[message.fileName]
          }
          if (actualHash !== expectedHashes[message.fileName]) {
            logger.error(
              `[Downloader] SHA-256 mismatch for ${message.fileName}: expected ${expectedHashes[message.fileName]}, got ${actualHash}`,
            )
            setErrorMessage(
              `File integrity check failed for "${message.fileName}". The file may have been tampered with.`,
            )
            // Close the file stream to unblock the download promise (prevents hang)
            fileStream.close()
            activePc?.close()
            return
          }
          logger.log(`[Downloader] SHA-256 verified for ${message.fileName}`)
        }

        completedFiles.add(message.fileName)
        setFilesCompleted(completedFiles.size)
        fileStream.close()
        startNextFileOrFinish()
      }
    }

    const downloads = currentFilesInfo.map((info, i) => ({
      name: info.fileName.replace(/^\//, ''),
      size: info.size,
      stream: () => fileStreams[i],
    }))

    // ZIP64 handles files >4 GB in multi-file ZIP downloads.
    // Log a notice for large files but don't block the download.
    if (
      downloads.length > 1 &&
      currentFilesInfo.some((f) => f.size >= ZIP64_THRESHOLD)
    ) {
      logger.log(
        '[Downloader] large file detected in multi-file download — using ZIP64 format',
      )
    }

    const downloadPromise =
      downloads.length > 1
        ? streamDownloadMultipleFiles(downloads, getZipFilename())
        : streamDownloadSingleFile(downloads[0], downloads[0].name)

    downloadPromise
      .then(async () => {
        logger.log('[Downloader] all files downloaded')
        doneRef.current = true
        peerConnRef.current
          ?.send({ type: MessageType.Done } as z.infer<typeof Message>)
          ?.catch(() => {}) // Connection may have closed

        // Clear file key cache and stream refs
        for (const k of Object.keys(fileKeyCache)) delete fileKeyCache[k]
        activeStreamsRef.current = []

        // Delete resume progress on successful completion
        if (hkdfSaltRef.current) {
          deleteProgress(slugRef.current, hkdfSaltRef.current)
        }

        // Report download completion to server for limit enforcement
        if (slugRef.current && currentKey && hkdfSaltRef.current) {
          try {
            const token = await deriveReaderToken(
              currentKey,
              hkdfSaltRef.current,
            )
            await fetch(
              `${FILE_SHARING_API}/channels/${slugRef.current}/download-complete`,
              {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token }),
              },
            )
          } catch {
            // Non-critical — download already succeeded locally
          }
        }

        setIsDownloading(false)
        setDone(true)
      })
      .catch((err) => {
        logger.error('[Downloader] download error:', err)
        if (!doneRef.current) {
          setErrorMessage('Download failed. Please try again.')
          setIsDownloading(false)
        }
      })

    startNextFileOrFinish()
  }, [])

  const totalSize = useMemo(
    () => filesInfo?.reduce((acc, info) => acc + info.size, 0) ?? 0,
    [filesInfo],
  )

  // ── Pause / Resume ──

  const pauseDownload = useCallback(() => {
    const pc = peerConnRef.current
    if (pc) {
      logger.log('[Downloader] pausing download')
      isPausedRef.current = true
      setIsPaused(true)
      pc.send({ type: MessageType.Pause }).catch(() => {}) // Connection may have closed
    }
  }, [])

  const resumeDownload = useCallback(() => {
    const pc = peerConnRef.current
    if (pc && resumeFnRef.current) {
      logger.log('[Downloader] resuming download')
      isPausedRef.current = false
      setIsPaused(false)
      resumeFnRef.current()
    }
  }, [])

  // ── Stop and Cleanup ──

  const stopDownload = useCallback(() => {
    stoppedRef.current = true
    const pc = peerConnRef.current
    if (pc) {
      logger.log('[Downloader] stopping download')
      // Null the ref immediately to prevent stale usage during the 100ms delay
      peerConnRef.current = null
      pc.send({ type: MessageType.Pause }).catch(() => {}) // Connection may have closed
      // Brief delay before closing so the Pause message can be flushed
      setTimeout(() => pc.close(), 100)
    }
    // Close signaling WebSocket to free resources
    if (signalingRef.current) {
      signalingRef.current.close()
      signalingRef.current = null
    }
    // Null processChunk immediately to prevent incoming data from being processed
    // during teardown (peerConn may still deliver messages until pc.close() fires)
    processChunk.current = null
    resumeFnRef.current = null
    isPausedRef.current = false
    // Close any open file streams to prevent resource leaks
    for (const s of activeStreamsRef.current) {
      try {
        s.close()
      } catch {
        /* stream may already be closed */
      }
    }
    activeStreamsRef.current = []
    doneRef.current = false
    downloadStartedRef.current = false
    setIsConnected(false)
    setIsDownloading(false)
    setIsPaused(false)
    setDone(false)
    setBytesDownloaded(0)
    setFilesCompleted(0)
    setErrorMessage(null)
    setPasswordError(null)
  }, [])

  return {
    filesInfo,
    isConnected,
    isPasswordRequired,
    isDownloading,
    isDone,
    isEncrypted,
    isResuming,
    isRelayMode,
    errorMessage,
    passwordError,
    submitPassword,
    startDownload,
    stopDownload,
    pauseDownload,
    resumeDownload,
    isPaused,
    totalSize,
    bytesDownloaded,
    filesCompleted,
    remainingDownloads,
  }
}
