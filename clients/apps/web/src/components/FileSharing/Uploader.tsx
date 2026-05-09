'use client'

import { useUploaderChannel } from '@/hooks/file-sharing/useUploaderChannel'
import { useUploaderConnections } from '@/hooks/file-sharing/useUploaderConnections'
import {
  FILE_SHARING_API,
  FILE_SHARING_SIGNAL_PATH,
  buildFileShareURL,
} from '@/utils/file-sharing/constants'
import { hashPassword } from '@/utils/file-sharing/crypto'
import {
  deriveReaderToken,
  exportKey,
  exportSalt,
  generateMasterKey,
  generateSalt,
} from '@/utils/file-sharing/encryption'
import { logger } from '@/utils/file-sharing/logger'
import {
  UploadedFile,
  UploaderConnectionStatus,
} from '@/utils/file-sharing/types'
import { SignalingClient } from '@/utils/p2p/signaling'
import { JSX, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import QRCode from 'react-qr-code'
import { ConnectionListItem } from './ConnectionListItem'
import { CopyableInput } from './CopyableInput'
import { ErrorMessage } from './ErrorMessage'
import { DownloadIcon, EncryptedBadge } from './Icons'
import Loading from './Loading'
import { SocialShareGrid, useSocialShare } from './SocialShare'
import StopButton from './StopButton'
import { WarningBanner } from './WarningBanner'

// ── Constants ──

const QR_CODE_SIZE = 120

// ── Main Component ──

/** Manages encrypted peer-to-peer file sharing with QR code, download link, and real-time connection tracking. */
export default function Uploader({
  files,
  password,
  maxDownloads,
  onStop,
  title,
  priceCents,
  currency,
  workspaceId,
}: {
  files: UploadedFile[]
  password: string
  maxDownloads: number // 0 = unlimited
  onStop: () => void
  title?: string
  priceCents?: number | null
  currency?: string
  workspaceId?: string
}): JSX.Element {
  // ── Channel Setup ──
  const fileName = files.length === 1 ? files[0].name : `${files.length} files`
  const fileSizeBytes = files.reduce((sum, f) => sum + f.size, 0)
  const {
    isLoading,
    error,
    shortSlug,
    secret: channelSecret,
  } = useUploaderChannel(maxDownloads, undefined, {
    priceCents,
    currency,
    title,
    fileName,
    fileSizeBytes,
    workspaceId,
  })

  // ── Encryption Key & Salt ──
  // Generate encryption key and salt on mount
  const [encryptionKey, setEncryptionKey] = useState<CryptoKey | null>(null)
  const [exportedKey, setExportedKey] = useState<string | null>(null)
  const [hkdfSalt, setHkdfSalt] = useState<Uint8Array | null>(null)
  const [exportedSalt, setExportedSalt] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const salt = generateSalt()
    setHkdfSalt(salt)
    setExportedSalt(exportSalt(salt))
    generateMasterKey().then(async (key) => {
      if (cancelled) return
      setEncryptionKey(key)
      setExportedKey(await exportKey(key))
    })
    return () => {
      cancelled = true
    }
  }, [])

  // Derive and register reader token with server after key + channel are ready.
  // Retries up to 3 times with exponential backoff because a failed registration
  // leaves the pending-token marker in Redis, blocking downloaders for up to 120s.
  const [tokenRegError, setTokenRegError] = useState(false)
  useEffect(() => {
    if (!encryptionKey || !hkdfSalt || !shortSlug || !channelSecret) return
    let cancelled = false
    setTokenRegError(false)
    deriveReaderToken(encryptionKey, hkdfSalt).then(async (token) => {
      if (cancelled) return
      const tokenHash = await hashPassword(token) // SHA-256 hash
      if (cancelled) return
      const maxRetries = 3
      for (let attempt = 0; attempt < maxRetries; attempt++) {
        if (cancelled) return
        try {
          const resp = await fetch(
            `${FILE_SHARING_API}/channels/${shortSlug}/reader-token`,
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                secret: channelSecret,
                token_hash: tokenHash,
              }),
            },
          )
          if (resp.ok) return // Success
        } catch {
          // Network error — retry
        }
        // Exponential backoff: 1s, 2s, 4s
        if (attempt < maxRetries - 1) {
          await new Promise((r) => setTimeout(r, 1000 * 2 ** attempt))
        }
      }
      // All retries exhausted — downloaders will be blocked until pending-token expires
      if (!cancelled) setTokenRegError(true)
    })
    return () => {
      cancelled = true
    }
  }, [encryptionKey, hkdfSalt, shortSlug, channelSecret])

  // ── Signaling Connection ──
  // Create signaling connection after channel is ready
  const [signaling, setSignaling] = useState<SignalingClient | null>(null)
  const [iceServers, setIceServers] = useState<RTCIceServer[]>([])
  const [signalingError, setSignalingError] = useState(false)
  const signalingRef = useRef<SignalingClient | null>(null)

  useEffect(() => {
    if (!shortSlug || !channelSecret) return
    let cancelled = false
    setSignalingError(false)
    const client = new SignalingClient(FILE_SHARING_SIGNAL_PATH)
    signalingRef.current = client

    client
      .connect(shortSlug, 'uploader', channelSecret)
      .then((welcome) => {
        if (cancelled) {
          client.close()
          return
        }
        logger.log('[Uploader] signaling connected, peerId:', welcome.peerId)
        setIceServers(welcome.iceServers)
        setSignaling(client)
      })
      .catch((err) => {
        if (!cancelled) {
          logger.error('[Uploader] signaling connection failed:', err)
          setSignalingError(true)
        }
      })

    return () => {
      cancelled = true
      client.close()
      signalingRef.current = null
      setSignaling(null)
    }
  }, [shortSlug, channelSecret])

  // ── Connections & Download Tracking ──
  const connections = useUploaderConnections(
    signaling,
    iceServers,
    files,
    password,
    maxDownloads,
    encryptionKey,
    shortSlug ?? '',
    channelSecret ?? '',
    hkdfSalt ?? undefined,
  )

  // Count completed downloads
  const completedDownloads = connections.filter(
    (conn) => conn.status === UploaderConnectionStatus.Done,
  ).length

  // Check if download limit reached
  const isLimitReached = maxDownloads > 0 && completedDownloads >= maxDownloads
  const remainingDownloads =
    maxDownloads > 0 ? maxDownloads - completedDownloads : null

  // Auto-stop when limit reached
  useEffect(() => {
    if (isLimitReached) {
      // Give a short delay to show completion message
      const timer = setTimeout(() => {
        signalingRef.current?.close()
        onStop()
      }, 3000)
      return () => clearTimeout(timer)
    }
  }, [isLimitReached, onStop])

  // ── Share URL & Handlers ──
  // Generate combined URL with download slug, encryption key, and HKDF salt
  // Fragment is never sent to server, making this completely private (zero-knowledge)
  // Password is NOT in URL — receiver must enter it manually
  const combinedURL = useMemo(() => {
    if (!shortSlug || !exportedKey || !exportedSalt) return ''
    return buildFileShareURL(shortSlug, exportedKey, exportedSalt)
  }, [shortSlug, exportedKey, exportedSalt])

  const handleStop = useCallback(() => {
    signalingRef.current?.close()
    onStop()
  }, [onStop])

  const activeDownloaders = connections.filter(
    (conn) =>
      conn.status === UploaderConnectionStatus.Uploading ||
      // Count connections between files as active (status briefly flips to Ready
      // between individual file transfers within a bulk download)
      (conn.status === UploaderConnectionStatus.Ready &&
        conn.completedFiles > 0 &&
        conn.completedFiles < conn.totalFiles),
  ).length

  const shareHandlers = useSocialShare({
    url: combinedURL,
    emailSubject: 'Secure File Share',
    emailBody: `I'm sharing files with you securely.\n\nDownload Link: ${combinedURL}\n\nThis link will stop working when I close my browser.`,
    shareText: 'Secure file share',
  })

  // ── Render ──
  if (isLoading || !shortSlug || !exportedKey || !exportedSalt) {
    return <Loading text="Creating share link..." />
  }

  if (error) {
    return <ErrorMessage message={error.message} />
  }

  return (
    <div className="flex w-full flex-col gap-y-6">
      {signalingError && (
        <div className="flex items-center gap-x-2 rounded-lg bg-red-50 px-4 py-3 text-red-700 dark:bg-red-900/20 dark:text-red-400">
          <span className="text-sm">
            Could not connect to the signaling server. Downloaders will not be
            able to connect. Please try refreshing.
          </span>
        </div>
      )}
      {tokenRegError && (
        <WarningBanner>
          Downloaders may be temporarily unable to connect. Please try
          refreshing or creating a new share link.
        </WarningBanner>
      )}

      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <EncryptedBadge />
          {remainingDownloads !== null && (
            <p
              className={`mt-1 text-sm ${isLimitReached ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-500 dark:text-slate-400'}`}
            >
              {isLimitReached
                ? 'Download limit reached - stopping...'
                : `${remainingDownloads} download${remainingDownloads !== 1 ? 's' : ''} remaining`}
            </p>
          )}
        </div>
        <StopButton onClick={handleStop} />
      </div>

      {/* QR Code */}
      <div className="flex flex-col items-center">
        <div className="mb-3 rounded-xl bg-white p-3 dark:bg-slate-800">
          {combinedURL && <QRCode value={combinedURL} size={QR_CODE_SIZE} />}
        </div>
        <div className="flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-400">
          <DownloadIcon />
          <span className="font-semibold">Scan to Download</span>
        </div>
        <p className="mt-1 text-xs text-amber-600 dark:text-amber-500">
          {maxDownloads === 0
            ? 'Stops working when you close this page'
            : maxDownloads === 1
              ? 'One-time use - link expires after download'
              : `Limited to ${maxDownloads} downloads`}
        </p>
      </div>

      {/* Download Link */}
      {combinedURL && (
        <div className="bg-surface rounded-xl p-4">
          <CopyableInput label="Download Link" value={combinedURL} />
          {password && (
            <p className="mt-2 text-center text-xs text-amber-600 dark:text-amber-400">
              Password protected — share the password separately
            </p>
          )}
        </div>
      )}

      <SocialShareGrid handlers={shareHandlers} />

      {/* Connection Status */}
      <div className="bg-surface rounded-xl p-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
          {activeDownloaders > 0 ? (
            <span className="text-slate-600 dark:text-slate-300">
              {activeDownloaders} downloading
            </span>
          ) : (
            'Waiting for downloaders...'
          )}
          {connections.length > 0 && (
            <span className="ml-2 font-normal text-slate-400 dark:text-slate-500">
              ({connections.length} total)
            </span>
          )}
        </h3>
        <div className="max-h-[300px] overflow-y-auto">
          {connections.map((conn) => (
            <ConnectionListItem key={conn.dataConnection.peer} conn={conn} />
          ))}
          {connections.length === 0 && (
            <p className="py-4 text-center text-xs text-slate-500 dark:text-slate-400">
              Share the download link to start transferring files
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
