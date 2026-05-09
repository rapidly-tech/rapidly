'use client'

// ── Imports ──

import { useDownloader } from '@/hooks/file-sharing/useDownloader'
import { FILE_SHARING_API } from '@/utils/file-sharing/constants'
import {
  deriveReaderToken,
  importKey,
  importSalt,
} from '@/utils/file-sharing/encryption'
import { pluralize } from '@/utils/file-sharing/pluralize'
import { ALLOWED_STRIPE_ORIGINS, isSafeRedirect } from '@/utils/safe-redirect'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { motion } from 'framer-motion'
import React, { JSX, useCallback, useEffect, useState } from 'react'
import { ChecksumDisplay } from './ChecksumDisplay'
import DownloadButton from './DownloadButton'
import { ErrorMessage } from './ErrorMessage'
import { DownloadIcon, EncryptedBadge } from './Icons'
import Loading from './Loading'
import PasswordField from './PasswordField'
import ProgressBar from './ProgressBar'
import ReportViolationButton from './ReportViolationButton'
import ReturnHome from './ReturnHome'
import StopButton from './StopButton'
import TitleText from './TitleText'
import UnlockButton from './UnlockButton'
import UploadFileList, { formatFileSize } from './UploadFileList'
import { WarningBanner } from './WarningBanner'
import { WebViewWarning } from './WebViewWarning'

// ── Constants and Types ──

const fadeIn = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.4 } },
}

interface FileInfo {
  fileName: string
  size: number
  type: string
}

// ── Connecting State ──

export function ConnectingToUploader({
  showTroubleshootingAfter = 3000,
}: {
  showTroubleshootingAfter?: number
}): JSX.Element {
  const [showTroubleshooting, setShowTroubleshooting] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => {
      setShowTroubleshooting(true)
    }, showTroubleshootingAfter)
    return () => clearTimeout(timer)
  }, [showTroubleshootingAfter])

  return (
    <motion.div
      className="flex w-full max-w-2xl flex-col items-center gap-y-6 pt-12"
      variants={fadeIn}
      initial="hidden"
      animate="visible"
    >
      <Loading text="Connecting to sender..." />

      {showTroubleshooting && (
        <motion.div
          className="flex w-full flex-col items-center gap-y-6"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0, transition: { duration: 0.3 } }}
        >
          <div className="bg-surface w-full rounded-xl p-4 text-left">
            <h3 className="mb-4 text-lg font-medium text-slate-800 dark:text-slate-200">
              Having trouble connecting?
            </h3>

            <div className="space-y-3 text-sm text-slate-600 dark:text-slate-300">
              <p>
                This uses direct peer-to-peer connections, but sometimes the
                connection can get stuck:
              </p>

              <ul className="space-y-2">
                <li className="flex items-start gap-2">
                  <span>
                    The sender may have closed their browser or lost
                    connectivity
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span>
                    Your network might have strict firewalls or NAT settings
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span>
                    Some corporate or school networks block peer-to-peer
                    connections
                  </span>
                </li>
              </ul>
            </div>
          </div>
          <ReturnHome />
        </motion.div>
      )}
    </motion.div>
  )
}

// ── Download Complete ──

export function DownloadComplete({
  filesInfo,
  title,
  bytesDownloaded,
  totalSize,
  onDownloadAgain,
  remainingDownloads,
  isEncrypted,
  slug,
  encryptionKey,
  hkdfSalt,
}: {
  filesInfo: FileInfo[]
  title?: string | null
  bytesDownloaded: number
  totalSize: number
  onDownloadAgain?: () => void
  remainingDownloads: number | null
  isEncrypted?: boolean
  slug?: string
  encryptionKey?: CryptoKey | null
  hkdfSalt?: Uint8Array
}): JSX.Element {
  // After a successful download, the remaining count decrements by 1
  const downloadsLeft =
    remainingDownloads !== null ? Math.max(0, remainingDownloads - 1) : null
  const canDownloadAgain = downloadsLeft === null || downloadsLeft > 0

  return (
    <motion.div
      className="flex w-full max-w-2xl flex-col items-center gap-y-6"
      variants={fadeIn}
      initial="hidden"
      animate="visible"
    >
      <div className="text-center">
        <TitleText>{title || 'Download Complete'}</TitleText>
        <p className="text-base font-medium tracking-wide text-slate-400 dark:text-slate-500">
          Downloaded {pluralize(filesInfo.length, 'file', 'files')} successfully
        </p>
        {isEncrypted && (
          <div className="mt-2">
            <EncryptedBadge />
          </div>
        )}
      </div>
      <div className="flex w-full flex-col gap-4">
        {onDownloadAgain && canDownloadAgain && (
          <Button
            type="button"
            variant="secondary"
            size="lg"
            className="w-full"
            onClick={onDownloadAgain}
            aria-label="Download files again"
          >
            <DownloadIcon />
            Download Again
          </Button>
        )}
        <ProgressBar value={bytesDownloaded} max={totalSize} />
        <UploadFileList files={filesInfo} />
        {slug && encryptionKey && hkdfSalt && (
          <ChecksumDisplay
            slug={slug}
            encryptionKey={encryptionKey}
            hkdfSalt={hkdfSalt}
          />
        )}
        {downloadsLeft !== null && (
          <div className="text-center text-sm text-slate-500 dark:text-slate-400">
            {downloadsLeft > 0
              ? `${pluralize(downloadsLeft, 'download', 'downloads')} remaining`
              : 'No downloads remaining'}
          </div>
        )}
        <ReturnHome />
      </div>
    </motion.div>
  )
}

// ── Download In Progress ──

export function DownloadInProgress({
  filesInfo,
  title,
  bytesDownloaded,
  totalSize,
  filesCompleted,
  isPaused,
  onStop,
  onPause,
  onResume,
  isRelayMode,
}: {
  filesInfo: FileInfo[]
  title?: string | null
  bytesDownloaded: number
  totalSize: number
  filesCompleted: number
  isPaused: boolean
  onStop: () => void
  onPause: () => void
  onResume: () => void
  isRelayMode?: boolean
}): JSX.Element {
  const overallPercent =
    totalSize > 0 ? Math.round((bytesDownloaded / totalSize) * 100) : 0

  return (
    <motion.div
      className="flex w-full max-w-2xl flex-col items-center gap-y-6"
      variants={fadeIn}
      initial="hidden"
      animate="visible"
    >
      <div className="text-center">
        <TitleText>
          {isPaused
            ? 'Download Paused'
            : title ||
              `Downloading ${pluralize(filesInfo.length, 'file', 'files')}...`}
        </TitleText>
        <p className="text-base font-medium tracking-wide text-slate-400 dark:text-slate-500">
          {isPaused ? 'Tap resume to continue' : 'Transfer in progress'}
          {isRelayMode && (
            <span className="ml-2 inline-flex items-center rounded-md bg-teal-100 px-2 py-0.5 text-xs font-medium text-teal-700 dark:bg-teal-900/30 dark:text-teal-300">
              via relay
            </span>
          )}
        </p>
      </div>
      <div className="flex w-full flex-col gap-4">
        <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
          <span
            className={`shrink-0 rounded-md px-2 py-0.5 text-[10px] font-medium text-white ${
              isPaused ? 'bg-amber-500' : 'bg-slate-600'
            }`}
          >
            {isPaused ? 'paused' : 'downloading'}
          </span>
          <div className="text-right whitespace-nowrap">
            <div>
              {Math.min(filesCompleted, filesInfo.length)} / {filesInfo.length}{' '}
              files
            </div>
            <div>{overallPercent}%</div>
          </div>
        </div>
        <ProgressBar value={bytesDownloaded} max={totalSize} />
        <div className="flex justify-center gap-3">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={isPaused ? onResume : onPause}
            aria-label={isPaused ? 'Resume download' : 'Pause download'}
          >
            {isPaused ? 'Resume' : 'Pause'}
          </Button>
          <StopButton onClick={onStop} isDownloading />
        </div>
        <UploadFileList files={filesInfo} />
      </div>
    </motion.div>
  )
}

// ── Ready To Download ──

export function ReadyToDownload({
  filesInfo,
  title,
  onStart,
  slug,
  remainingDownloads,
  isEncrypted,
  readerToken,
}: {
  filesInfo: FileInfo[]
  title?: string | null
  onStart: () => void
  slug: string
  remainingDownloads: number | null
  isEncrypted?: boolean
  readerToken?: string
}): JSX.Element {
  return (
    <motion.div
      className="flex w-full max-w-2xl flex-col items-center gap-y-6"
      variants={fadeIn}
      initial="hidden"
      animate="visible"
    >
      <div className="text-center">
        <TitleText>
          {title ||
            `Ready to download ${pluralize(filesInfo.length, 'file', 'files')}`}
        </TitleText>
        <p className="text-base font-medium tracking-wide text-slate-400 dark:text-slate-500">
          {isEncrypted
            ? 'End-to-end encrypted transfer'
            : 'Files are ready for download'}
        </p>
      </div>
      <div className="flex w-full flex-col gap-4">
        {isEncrypted && <EncryptedBadge />}
        <DownloadButton onClick={onStart} />
        <UploadFileList files={filesInfo} />
        {remainingDownloads !== null && (
          <div className="text-center text-sm text-slate-500 dark:text-slate-400">
            {pluralize(remainingDownloads, 'download', 'downloads')} remaining
          </div>
        )}
        <div className="mt-2 border-t border-slate-200 pt-4 dark:border-slate-800">
          <ReportViolationButton slug={slug} readerToken={readerToken} />
        </div>
      </div>
    </motion.div>
  )
}

// ── Password Entry ──

export function PasswordEntry({
  onSubmit,
  errorMessage,
}: {
  onSubmit: (password: string) => void
  errorMessage: string | null
}): JSX.Element {
  const [password, setPassword] = useState('')
  const handleSubmit = useCallback(
    (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault()
      if (!password) return
      onSubmit(password)
    },
    [onSubmit, password],
  )

  return (
    <motion.div
      className="flex w-full max-w-2xl flex-col items-center gap-y-6"
      variants={fadeIn}
      initial="hidden"
      animate="visible"
    >
      <div className="text-center">
        <TitleText>Password Protected</TitleText>
        <p className="text-base font-medium tracking-wide text-slate-400 dark:text-slate-500">
          Enter the password to unlock this download
        </p>
      </div>
      <form onSubmit={handleSubmit} className="w-full">
        <div className="flex w-full flex-col gap-4">
          <PasswordField
            value={password}
            onChange={setPassword}
            isRequired
            isInvalid={Boolean(errorMessage)}
            autoFocus
          />
          {errorMessage && <ErrorMessage message={errorMessage} />}
          <UnlockButton />
        </div>
      </form>
    </motion.div>
  )
}

// ── Payment Required ──

interface ChannelInfo {
  paymentRequired: boolean
  title: string | null
  priceCents: number | null
  currency: string | null
  fileName: string | null
  fileSizeBytes: number | null
}

function formatPrice(cents: number, currency: string): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency.toUpperCase(),
  }).format(cents / 100)
}

function PaymentRequired({
  channelInfo,
  slug,
  readerToken,
  onCheckoutError,
}: {
  channelInfo: ChannelInfo
  slug: string
  readerToken?: string
  onCheckoutError: (msg: string) => void
}): JSX.Element {
  const [isRedirecting, setIsRedirecting] = useState(false)

  const handlePay = useCallback(async () => {
    setIsRedirecting(true)

    // Save current full URL (including hash fragment) to localStorage
    // so the return page can redirect back after payment (survives tab close)
    try {
      sessionStorage.setItem(
        `file-sharing:return:${slug}`,
        window.location.href,
      )
    } catch {
      onCheckoutError(
        'Could not save session data. Please enable localStorage and try again.',
      )
      setIsRedirecting(false)
      return
    }

    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      if (readerToken) {
        headers['Authorization'] = `Bearer ${readerToken}`
      }
      const resp = await fetch(
        `${FILE_SHARING_API}/channels/${slug}/checkout`,
        {
          method: 'POST',
          headers,
        },
      )
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(body.detail || 'Failed to create checkout session')
      }
      const data = await resp.json()
      if (
        data.checkout_url &&
        isSafeRedirect(data.checkout_url, ALLOWED_STRIPE_ORIGINS)
      ) {
        window.location.href = data.checkout_url
      } else if (data.checkout_url) {
        throw new Error('Invalid checkout URL')
      } else {
        throw new Error('No checkout URL returned')
      }
    } catch (err) {
      onCheckoutError(
        err instanceof Error ? err.message : 'Failed to start payment',
      )
      setIsRedirecting(false)
    }
  }, [slug, readerToken, onCheckoutError])

  const priceDisplay =
    channelInfo.priceCents && channelInfo.currency
      ? formatPrice(channelInfo.priceCents, channelInfo.currency)
      : null

  return (
    <motion.div
      className="flex w-full max-w-2xl flex-col items-center gap-y-6"
      variants={fadeIn}
      initial="hidden"
      animate="visible"
    >
      <div className="text-center">
        <TitleText>Payment Required</TitleText>
        <p className="text-base font-medium tracking-wide text-slate-400 dark:text-slate-500">
          The sender requires payment to download this file
        </p>
      </div>
      <div className="bg-surface flex w-full flex-col gap-4 rounded-xl p-6">
        {channelInfo.fileName && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-700 dark:text-slate-300">
              {channelInfo.fileName}
            </span>
            {channelInfo.fileSizeBytes && (
              <span className="text-sm text-slate-500 dark:text-slate-400">
                {formatFileSize(channelInfo.fileSizeBytes)}
              </span>
            )}
          </div>
        )}
        {priceDisplay && (
          <div className="rp-text-primary text-center text-2xl font-bold">
            {priceDisplay}{' '}
            <span className="text-sm font-normal text-slate-500 uppercase dark:text-slate-400">
              {channelInfo.currency}
            </span>
          </div>
        )}
        <Button
          type="button"
          size="lg"
          className="w-full"
          onClick={handlePay}
          disabled={isRedirecting}
        >
          {isRedirecting
            ? 'Redirecting to payment...'
            : priceDisplay
              ? `Pay ${priceDisplay}`
              : 'Pay'}
        </Button>
      </div>
      <ReturnHome />
    </motion.div>
  )
}

// ── Main Downloader Component ──

/** Orchestrates encrypted file downloads with payment gating, password protection, and WebRTC peer connection. */
export default function Downloader({
  slug,
  encryptionKey: encryptionKeyBase64,
  hkdfSalt: hkdfSaltBase64,
  password: embeddedPassword,
}: {
  slug: string
  encryptionKey?: string // Optional base64url encryption key from URL fragment
  hkdfSalt?: string // Optional base64url HKDF salt from URL fragment
  password?: string // Optional pre-hashed password from URL fragment
}): JSX.Element {
  const [cryptoKey, setCryptoKey] = useState<CryptoKey | null>(null)
  const [salt, setSalt] = useState<Uint8Array | undefined>(undefined)
  const [keyError, setKeyError] = useState<string | null>(null)

  // Import encryption key and salt from base64url strings on mount
  useEffect(() => {
    if (encryptionKeyBase64) {
      importKey(encryptionKeyBase64)
        .then(setCryptoKey)
        .catch(() => {
          setKeyError(
            'Invalid encryption key. The link may be corrupted or incomplete.',
          )
        })
    }
    if (hkdfSaltBase64) {
      try {
        setSalt(importSalt(hkdfSaltBase64))
      } catch {
        setKeyError(
          'Invalid encryption salt. The link may be corrupted or incomplete.',
        )
      }
    }
  }, [encryptionKeyBase64, hkdfSaltBase64])

  // Payment token is handled via httpOnly cookie set by the server
  // during checkout. No JavaScript access needed — the cookie is sent
  // automatically with HTTP and WebSocket requests.

  // Derive reader token for ReportViolationButton auth and payment
  const [readerToken, setReaderToken] = useState<string | undefined>(undefined)
  useEffect(() => {
    if (!cryptoKey || !salt) return
    deriveReaderToken(cryptoKey, salt)
      .then(setReaderToken)
      .catch(() => {
        setReaderToken(undefined)
      })
  }, [cryptoKey, salt])

  // Pre-check channel to detect if payment is required
  const [channelInfo, setChannelInfo] = useState<ChannelInfo | null>(null)
  const [channelCheckDone, setChannelCheckDone] = useState(false)
  const [channelUnavailable, setChannelUnavailable] = useState(false)
  const [checkoutError, setCheckoutError] = useState<string | null>(null)

  const keyReady = !encryptionKeyBase64 || cryptoKey !== null

  useEffect(() => {
    if (!keyReady || !slug) return
    let cancelled = false

    const checkChannel = async () => {
      try {
        const headers: Record<string, string> = {}
        if (readerToken) {
          headers['Authorization'] = `Bearer ${readerToken}`
        }
        // Payment token is in httpOnly cookie — sent automatically
        const resp = await fetch(`${FILE_SHARING_API}/channels/${slug}`, {
          headers,
        })
        if (!cancelled && resp.ok) {
          const data = await resp.json()
          setChannelInfo({
            paymentRequired: data.payment_required ?? false,
            title: data.title ?? null,
            priceCents: data.price_cents ?? null,
            currency: data.currency ?? null,
            fileName: data.file_name ?? null,
            fileSizeBytes: data.file_size_bytes ?? null,
          })
        } else if (!cancelled && (resp.status === 404 || resp.status === 410)) {
          // Channel not found or download limit reached — block download
          setChannelUnavailable(true)
        }
      } catch {
        // Channel check failed — proceed without payment info (free channel)
      }
      if (!cancelled) setChannelCheckDone(true)
    }

    checkChannel()
    return () => {
      cancelled = true
    }
  }, [slug, keyReady, readerToken])

  // Gate the downloader: only connect when payment is cleared.
  // Payment token is in httpOnly cookie — if present, the server returns
  // paymentRequired: false in the channel fetch response.
  const paymentCleared = channelCheckDone && !channelInfo?.paymentRequired
  const effectiveSlug = keyReady && paymentCleared ? slug : ''

  const {
    filesInfo,
    isConnected,
    isPasswordRequired,
    isDownloading,
    isDone,
    errorMessage,
    passwordError,
    submitPassword,
    startDownload,
    stopDownload,
    totalSize,
    bytesDownloaded,
    filesCompleted,
    remainingDownloads,
    isEncrypted,
    isResuming,
    isRelayMode,
    pauseDownload,
    resumeDownload,
    isPaused,
  } = useDownloader(effectiveSlug, cryptoKey, salt)

  const handleDownloadAgain = useCallback(() => {
    // Reload the page to restart the download process
    window.location.reload()
  }, [])

  // Auto-submit embedded password from URL hash (legacy URL format)
  // Must be above all early returns to satisfy React's rules of hooks.
  const [autoSubmitted, setAutoSubmitted] = useState(false)
  useEffect(() => {
    if (isPasswordRequired && embeddedPassword && !autoSubmitted) {
      setAutoSubmitted(true)
      // Embedded password from legacy URL fragment is already SHA-256 hashed
      submitPassword(embeddedPassword, { alreadyHashed: true })
    }
  }, [isPasswordRequired, embeddedPassword, autoSubmitted, submitPassword])

  // Show error if encryption key import failed
  if (keyError) {
    return (
      <motion.div
        className="flex w-full max-w-2xl flex-col items-center gap-y-6 text-center"
        variants={fadeIn}
        initial="hidden"
        animate="visible"
      >
        <TitleText>Invalid Encryption Key</TitleText>
        <p className="text-base font-medium tracking-wide text-slate-400 dark:text-slate-500">
          Ask the sender for a new link
        </p>
        <WarningBanner>{keyError}</WarningBanner>
        <ReturnHome />
      </motion.div>
    )
  }

  // Show checkout error
  if (checkoutError) {
    return (
      <motion.div
        className="flex w-full max-w-2xl flex-col items-center gap-y-6 text-center"
        variants={fadeIn}
        initial="hidden"
        animate="visible"
      >
        <TitleText>Payment Failed</TitleText>
        <p className="text-base font-medium tracking-wide text-slate-400 dark:text-slate-500">
          Something went wrong with the payment
        </p>
        <WarningBanner>{checkoutError}</WarningBanner>
        <ReturnHome />
      </motion.div>
    )
  }

  // Show payment barrier when payment is required but not yet made
  if (channelCheckDone && channelInfo?.paymentRequired) {
    return (
      <PaymentRequired
        channelInfo={channelInfo}
        slug={slug}
        readerToken={readerToken}
        onCheckoutError={setCheckoutError}
      />
    )
  }

  // Download limit reached or channel no longer available
  if (channelUnavailable) {
    return (
      <motion.div
        className="flex w-full max-w-2xl flex-col items-center gap-y-6 text-center"
        variants={fadeIn}
        initial="hidden"
        animate="visible"
      >
        <TitleText>Download Not Available</TitleText>
        <p className="text-base font-medium tracking-wide text-slate-400 dark:text-slate-500">
          The download limit has been reached or the sender stopped sharing
        </p>
        <ReturnHome />
      </motion.div>
    )
  }

  // Still checking channel info
  if (!channelCheckDone) {
    return <ConnectingToUploader />
  }

  if (isDone && filesInfo) {
    return (
      <DownloadComplete
        filesInfo={filesInfo}
        title={channelInfo?.title ?? null}
        bytesDownloaded={bytesDownloaded}
        totalSize={totalSize}
        onDownloadAgain={handleDownloadAgain}
        remainingDownloads={remainingDownloads}
        isEncrypted={isEncrypted}
        slug={slug}
        encryptionKey={cryptoKey}
        hkdfSalt={salt}
      />
    )
  }

  // isDone but no filesInfo means an unexpected state — treat as completed without metadata
  if (isDone) {
    return (
      <motion.div
        className="flex w-full max-w-2xl flex-col items-center gap-y-6 text-center"
        variants={fadeIn}
        initial="hidden"
        animate="visible"
      >
        <TitleText>Download Complete</TitleText>
        <p className="text-base font-medium tracking-wide text-slate-400 dark:text-slate-500">
          Your download has finished
        </p>
        <ReturnHome />
      </motion.div>
    )
  }

  if (errorMessage) {
    return (
      <motion.div
        className="flex w-full max-w-2xl flex-col items-center gap-y-6 text-center"
        variants={fadeIn}
        initial="hidden"
        animate="visible"
      >
        <TitleText>Download Not Available</TitleText>
        <p className="text-base font-medium tracking-wide text-slate-400 dark:text-slate-500">
          The sender may have stopped sharing or the download limit was reached
        </p>
        <WarningBanner>{errorMessage}</WarningBanner>
        <ReturnHome />
      </motion.div>
    )
  }

  if (isPasswordRequired && (!embeddedPassword || autoSubmitted)) {
    return (
      <PasswordEntry errorMessage={passwordError} onSubmit={submitPassword} />
    )
  }

  if (isDownloading && filesInfo) {
    return (
      <DownloadInProgress
        filesInfo={filesInfo}
        title={channelInfo?.title ?? null}
        bytesDownloaded={bytesDownloaded}
        totalSize={totalSize}
        filesCompleted={filesCompleted}
        isPaused={isPaused}
        onStop={stopDownload}
        onPause={pauseDownload}
        onResume={resumeDownload}
        isRelayMode={isRelayMode}
      />
    )
  }

  if (filesInfo) {
    return (
      <>
        {isResuming && (
          <div className="mb-2 w-full max-w-2xl text-center text-sm text-teal-600 dark:text-teal-400">
            Previous progress detected — download will resume from where it left
            off
          </div>
        )}
        <ReadyToDownload
          filesInfo={filesInfo}
          title={channelInfo?.title ?? null}
          onStart={startDownload}
          slug={slug}
          remainingDownloads={remainingDownloads}
          isEncrypted={isEncrypted}
          readerToken={readerToken}
        />
      </>
    )
  }

  if (!isConnected) {
    return (
      <>
        <WebViewWarning />
        <ConnectingToUploader />
      </>
    )
  }

  // Connected but waiting for file metadata from the sender
  return (
    <motion.div
      className="flex w-full max-w-2xl flex-col items-center gap-y-6 pt-12"
      variants={fadeIn}
      initial="hidden"
      animate="visible"
    >
      <Loading text="Waiting for file info from sender..." />
    </motion.div>
  )
}
