'use client'

import { Downloader } from '@/components/FileSharing'
import { FileSharingErrorBoundary } from '@/components/FileSharing/ErrorBoundary'
import { formatFileSize } from '@/components/FileSharing/UploadFileList'
import { WarningBanner } from '@/components/FileSharing/WarningBanner'
import {
  createSecretCheckout,
  fetchFile,
  fetchSecret,
  fetchSecretMetadata,
  type FetchSecretResponse,
} from '@/hooks/file-sharing'
import { decryptFile, decryptMessage } from '@/utils/file-sharing'
import {
  parseHash,
  type FileSharingSecretHash,
  type ParsedHash,
} from '@/utils/file-sharing/url-parser'
import { ALLOWED_STRIPE_ORIGINS, isSafeRedirect } from '@/utils/safe-redirect'
import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { useCallback, useEffect, useRef, useState } from 'react'

// ── PasswordViewer Sub-component ──
function PasswordViewer({ password }: { password: string }) {
  const [copied, setCopied] = useState(false)
  const copyTimerRef = useRef<ReturnType<typeof setTimeout>>(null)

  useEffect(() => {
    return () => {
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
    }
  }, [])

  const handleCopy = useCallback(() => {
    navigator.clipboard
      .writeText(password)
      .then(() => {
        setCopied(true)
        if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
        copyTimerRef.current = setTimeout(() => setCopied(false), 2000)
      })
      .catch(() => {
        // Clipboard API may fail in non-secure contexts or when denied
      })
  }, [password])

  const handleGoBack = useCallback(() => {
    window.location.hash = ''
  }, [])

  return (
    <div className="rp-page-bg fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-full items-center justify-center px-4 py-8">
        <div className="flex w-full max-w-md flex-col items-center gap-y-6 text-center">
          <h1 className="text-3xl font-semibold tracking-tight md:text-5xl">
            File Password
          </h1>
          <p className="rp-text-secondary text-base font-medium tracking-wide">
            Use this password to decrypt the downloaded file
          </p>

          <div className="bg-surface w-full rounded-xl p-4">
            <pre className="rp-text-primary text-lg break-all whitespace-pre-wrap">
              {password}
            </pre>
          </div>

          <Button onClick={handleCopy} variant="secondary" className="w-full">
            {copied ? (
              <>
                <Icon icon="solar:check-read-linear" className="mr-2 h-4 w-4" />
                Copied!
              </>
            ) : (
              <>
                <Icon icon="solar:copy-linear" className="mr-2 h-4 w-4" />
                Copy Password
              </>
            )}
          </Button>

          <div className="flex w-full items-center gap-x-2 rounded-lg bg-slate-100 px-4 py-3 text-slate-700 dark:bg-slate-800/40 dark:text-slate-400">
            <Icon icon="solar:check-read-linear" className="h-4 w-4" />
            <span className="text-sm">
              Zero-knowledge: This password never touched any server.
            </span>
          </div>

          <Button onClick={handleGoBack} variant="ghost" className="w-full">
            Done
          </Button>
        </div>
      </div>
    </div>
  )
}

// ── FileSharingDownloadViewer Sub-component ──
function FileSharingDownloadViewer({
  slug,
  password,
  encryptionKey,
  hkdfSalt,
}: {
  slug: string
  password?: string
  encryptionKey?: string
  hkdfSalt?: string
}) {
  // Skip the pre-check loading state — the Downloader component handles
  // its own connection state (ConnectingToUploader, errors, etc.).
  // This avoids a double-loading-spinner: one here, then another in Downloader.
  return (
    <div className="rp-page-bg fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-full items-center justify-center px-4 py-8">
        <FileSharingErrorBoundary>
          <Downloader
            slug={slug}
            encryptionKey={encryptionKey}
            hkdfSalt={hkdfSalt}
            password={password}
          />
        </FileSharingErrorBoundary>
      </div>
    </div>
  )
}

// ── FileSharingSecretViewer Sub-component ──
function FileSharingSecretViewer({
  parsed,
}: {
  parsed: FileSharingSecretHash
}) {
  const [isLoading, setIsLoading] = useState(false)
  const [revealed, setRevealed] = useState(false)
  const [decryptedContent, setDecryptedContent] = useState<string | null>(null)
  const [fileName, setFileName] = useState<string | null>(null)
  const [fileData, setFileData] = useState<Uint8Array | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [manualPassword, setManualPassword] = useState('')
  const [paymentInfo, setPaymentInfo] = useState<FetchSecretResponse | null>(
    null,
  )
  const [isCheckingOut, setIsCheckingOut] = useState(false)
  const [secretTitle, setSecretTitle] = useState<string | null>(null)
  const [metadataLoaded, setMetadataLoaded] = useState(false)
  const copyTimerRef = useRef<ReturnType<typeof setTimeout>>(null)

  const needsPassword = !parsed.password

  useEffect(() => {
    return () => {
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
    }
  }, [])

  // Pre-fetch metadata (title) without consuming the secret
  useEffect(() => {
    let cancelled = false
    fetchSecretMetadata(parsed.uuid)
      .then(({ data }) => {
        if (!cancelled && data?.title) {
          setSecretTitle(data.title)
        }
      })
      .finally(() => {
        if (!cancelled) setMetadataLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [parsed.uuid])

  // ── Payment handler ──
  const handlePay = useCallback(async () => {
    setIsCheckingOut(true)
    try {
      const { data, status } = await createSecretCheckout(parsed.uuid)
      if (status >= 200 && status < 300 && data.checkout_url) {
        if (!isSafeRedirect(data.checkout_url, ALLOWED_STRIPE_ORIGINS)) {
          setError('Checkout URL is not a trusted origin')
          return
        }
        // Save the current URL so we can return after payment
        sessionStorage.setItem('rapidly_secret_return', window.location.href)
        window.location.href = data.checkout_url
      } else {
        setError('Failed to create checkout session')
      }
    } catch {
      setError('Failed to initiate payment')
    } finally {
      setIsCheckingOut(false)
    }
  }, [parsed.uuid])

  // ── Handlers ──
  const handleReveal = useCallback(async () => {
    const password = parsed.password ?? manualPassword
    if (!password) return

    setIsLoading(true)
    setError(null)
    setRevealed(true)

    try {
      if (parsed.type === 's') {
        const { data, status } = await fetchSecret(parsed.uuid)
        if (status < 200 || status >= 300) {
          setError(data.message || 'Secret not found or already viewed')
          return
        }

        // Check if payment is required
        if (data.payment_required) {
          setPaymentInfo(data)
          setRevealed(false)
          return
        }

        const decrypted = await decryptMessage(data.message, password)
        setDecryptedContent(decrypted.data as string)
      } else {
        const { data, status } = await fetchFile(parsed.uuid)
        if (status < 200 || status >= 300) {
          setError(data.message || 'File not found or already viewed')
          return
        }

        if (data.payment_required) {
          setPaymentInfo(data)
          setRevealed(false)
          return
        }

        const decrypted = await decryptFile(data.message, password)
        const binary = decrypted.data as Uint8Array
        const name = decrypted.filename || 'download'
        setFileData(binary)
        setFileName(name)
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to decrypt. The link may be invalid or corrupted.',
      )
    } finally {
      setIsLoading(false)
    }
  }, [parsed, manualPassword])

  const handleCopy = useCallback(() => {
    if (decryptedContent) {
      navigator.clipboard
        .writeText(decryptedContent)
        .then(() => {
          setCopied(true)
          if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
          copyTimerRef.current = setTimeout(() => setCopied(false), 2000)
        })
        .catch(() => {
          // Clipboard API may fail in non-secure contexts or when denied
        })
    }
  }, [decryptedContent])

  const handleDownload = useCallback(() => {
    if (fileData && fileName) {
      const blob = new Blob([
        (fileData.buffer as ArrayBuffer).slice(
          fileData.byteOffset,
          fileData.byteOffset + fileData.byteLength,
        ),
      ])
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = fileName
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      // Defer revoking to give the browser time to start reading the blob URL
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    }
  }, [fileData, fileName])

  // Clear sensitive state when page is hidden (bfcache, tab switch, navigation)
  // and on component unmount (SPA navigation via React router)
  useEffect(() => {
    const handlePageHide = () => {
      setDecryptedContent(null)
      setFileData(null)
      setFileName(null)
    }
    window.addEventListener('pagehide', handlePageHide)
    return () => {
      window.removeEventListener('pagehide', handlePageHide)
    }
  }, [])

  const handleGoBack = useCallback(() => {
    window.location.hash = ''
  }, [])

  // ── Render ──
  // Error state
  if (error) {
    return (
      <div className="rp-page-bg fixed inset-0 z-50 overflow-y-auto">
        <div className="flex min-h-full items-center justify-center px-4 py-8">
          <div className="flex w-full max-w-md flex-col items-center gap-y-6 text-center">
            <h1 className="text-3xl font-semibold tracking-tight md:text-5xl">
              Secret Not Available
            </h1>
            <p className="rp-text-secondary text-base font-medium tracking-wide">
              {error}
            </p>
            <WarningBanner
              icon={
                <Icon icon="solar:danger-triangle-linear" className="h-4 w-4" />
              }
            >
              One-time secrets are deleted after being viewed once.
            </WarningBanner>
            <Button
              onClick={handleGoBack}
              variant="secondary"
              className="w-full"
            >
              Go Back
            </Button>
          </div>
        </div>
      </div>
    )
  }

  // Payment required
  if (paymentInfo?.payment_required) {
    const priceDisplay =
      paymentInfo.price_cents != null
        ? `$${(paymentInfo.price_cents / 100).toFixed(2)} ${(paymentInfo.currency ?? 'usd').toUpperCase()}`
        : ''

    return (
      <div className="rp-page-bg fixed inset-0 z-50 overflow-y-auto">
        <div className="flex min-h-full items-center justify-center px-4 py-8">
          <div className="flex w-full max-w-md flex-col items-center gap-y-6 text-center">
            <Icon
              icon="solar:lock-linear"
              className="rp-text-muted h-12 w-12"
            />
            <h1 className="text-3xl font-semibold tracking-tight md:text-5xl">
              {paymentInfo.title || 'Paid Secret'}
            </h1>
            <p className="rp-text-secondary text-base font-medium tracking-wide">
              This secret requires payment to view
            </p>

            {priceDisplay && (
              <div className="bg-surface w-full rounded-xl p-6">
                <p className="rp-text-primary text-3xl font-semibold">
                  {priceDisplay}
                </p>
                <p className="rp-text-secondary mt-1 text-sm">
                  One-time payment
                </p>
              </div>
            )}

            <Button
              onClick={handlePay}
              size="lg"
              className="w-full"
              disabled={isCheckingOut}
            >
              {isCheckingOut
                ? 'Redirecting to Stripe...'
                : `Pay ${priceDisplay}`}
            </Button>

            <Button onClick={handleGoBack} variant="ghost" className="w-full">
              Cancel
            </Button>
          </div>
        </div>
      </div>
    )
  }

  // Before reveal — wait for metadata so the title doesn't flash
  if (!revealed) {
    const displayTitle = metadataLoaded
      ? secretTitle ||
        (parsed.type === 's' ? 'Encrypted Secret' : 'Encrypted File')
      : null

    return (
      <div className="rp-page-bg fixed inset-0 z-50 overflow-y-auto">
        <div className="flex min-h-full items-center justify-center px-4 py-8">
          <div className="flex w-full max-w-md flex-col items-center gap-y-6 text-center">
            <h1 className="text-3xl font-semibold tracking-tight md:text-5xl">
              {displayTitle ?? '\u00A0'}
            </h1>
            <p className="rp-text-secondary text-base font-medium tracking-wide">
              Someone shared an encrypted{' '}
              {parsed.type === 's' ? 'secret' : 'file'} with you
            </p>

            <WarningBanner
              icon={
                <Icon icon="solar:danger-triangle-linear" className="h-4 w-4" />
              }
            >
              This is a one-time {parsed.type === 's' ? 'secret' : 'file'}. It
              will be deleted after you view it.
            </WarningBanner>

            {needsPassword && (
              <input
                type="password"
                value={manualPassword}
                onChange={(e) => setManualPassword(e.target.value)}
                placeholder="Enter decryption key"
                aria-label="Decryption key"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && manualPassword) handleReveal()
                }}
                className="rp-text-primary placeholder:rp-text-muted w-full rounded-xl border border-slate-200 bg-white px-4 py-3 focus:ring-1 focus:ring-slate-300/20 focus:outline-none dark:border-slate-800 dark:bg-white/3"
              />
            )}

            <Button
              onClick={handleReveal}
              size="lg"
              className="w-full"
              disabled={needsPassword && !manualPassword}
            >
              <Icon icon="solar:eye-linear" className="mr-2 h-4 w-4" />
              Reveal {parsed.type === 's' ? 'Secret' : 'File'}
            </Button>

            <Button onClick={handleGoBack} variant="ghost" className="w-full">
              Cancel
            </Button>
          </div>
        </div>
      </div>
    )
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="rp-page-bg fixed inset-0 z-50 overflow-y-auto">
        <div className="flex min-h-full items-center justify-center px-4 py-8">
          <div className="flex w-full max-w-md flex-col items-center gap-y-6 text-center">
            <div className="h-12 w-12 animate-spin rounded-full border-4 border-slate-300 border-t-slate-600 dark:border-slate-600 dark:border-t-slate-400" />
            <p className="rp-text-secondary">Fetching and decrypting...</p>
          </div>
        </div>
      </div>
    )
  }

  // Decrypted text secret
  if (decryptedContent) {
    return (
      <div className="rp-page-bg fixed inset-0 z-50 overflow-y-auto">
        <div className="flex min-h-full items-center justify-center px-4 py-8">
          <div className="flex w-full max-w-lg flex-col items-center gap-y-6">
            <h1 className="text-3xl font-semibold tracking-tight md:text-5xl">
              {secretTitle || 'Secret Revealed'}
            </h1>
            <p className="rp-text-secondary text-base font-medium tracking-wide">
              This secret has been deleted from the server
            </p>

            <div className="bg-surface w-full rounded-xl p-4">
              <pre className="rp-text-primary max-h-96 overflow-auto text-sm break-words whitespace-pre-wrap">
                {decryptedContent}
              </pre>
            </div>

            <Button onClick={handleCopy} variant="secondary" className="w-full">
              {copied ? (
                <>
                  <Icon
                    icon="solar:check-read-linear"
                    className="mr-2 h-4 w-4"
                  />
                  Copied!
                </>
              ) : (
                <>
                  <Icon icon="solar:copy-linear" className="mr-2 h-4 w-4" />
                  Copy to Clipboard
                </>
              )}
            </Button>

            <Button onClick={handleGoBack} variant="ghost" className="w-full">
              Go Back
            </Button>
          </div>
        </div>
      </div>
    )
  }

  // Decrypted file
  if (fileData && fileName) {
    return (
      <div className="rp-page-bg fixed inset-0 z-50 overflow-y-auto">
        <div className="flex min-h-full items-center justify-center px-4 py-8">
          <div className="flex w-full max-w-lg flex-col items-center gap-y-6">
            <h1 className="text-3xl font-semibold tracking-tight md:text-5xl">
              File Ready
            </h1>
            <p className="rp-text-secondary text-base font-medium tracking-wide">
              This file has been deleted from the server
            </p>

            <div className="bg-surface flex w-full flex-col items-center gap-y-2 rounded-xl p-6">
              <Icon
                icon="solar:download-linear"
                className="rp-text-muted h-9 w-9"
              />
              <p className="rp-text-primary font-medium">{fileName}</p>
              <p className="rp-text-secondary text-sm">
                {formatFileSize(fileData.length)}
              </p>
            </div>

            <Button onClick={handleDownload} className="w-full" size="lg">
              <Icon icon="solar:download-linear" className="mr-2 h-4 w-4" />
              Download File
            </Button>

            <Button onClick={handleGoBack} variant="ghost" className="w-full">
              Go Back
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return null
}

// ── Main Component ──
/** Hash-based router that parses URL fragments to display file downloads, encrypted secrets, or password viewers. */
export const SecretViewer = () => {
  const [parsed, setParsed] = useState<ParsedHash | null>(null)
  const [initialized, setInitialized] = useState(false)
  // Pre-check: if there's a hash on mount, show overlay immediately to prevent
  // the landing page from flashing before the parsed route takes over.
  const [hasHash, setHasHash] = useState(false)

  // Parse hash on mount and hash change
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash
      const result = parseHash(hash)
      setParsed(result)
      setHasHash(hash.length > 1)
    }

    // Check for hash presence immediately (before parse completes)
    setHasHash(window.location.hash.length > 1)
    handleHashChange()
    setInitialized(true)
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  // Show a blank overlay while initializing when a hash is present,
  // preventing the landing page from flashing underneath.
  if (!initialized && hasHash) {
    return <div className="rp-page-bg fixed inset-0 z-50" />
  }

  // Don't render until we've checked the hash
  if (!initialized) return null

  // If no valid hash, don't render anything (show normal landing page)
  if (!parsed) return null

  // Route to appropriate viewer
  if (parsed.mode === 'file-sharing') {
    return (
      <FileSharingDownloadViewer
        slug={parsed.slug}
        password={parsed.password}
        encryptionKey={parsed.encryptionKey}
        hkdfSalt={parsed.hkdfSalt}
      />
    )
  }

  if (parsed.mode === 'password') {
    return <PasswordViewer password={parsed.password} />
  }

  return <FileSharingSecretViewer parsed={parsed} />
}
