'use client'

import { fetchSecret, fetchSecretMetadata } from '@/hooks/file-sharing'
import { decryptMessage } from '@/utils/file-sharing'
import { fromBase64Url } from '@/utils/file-sharing/constants'
import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { useCallback, useEffect, useState } from 'react'

interface SecretClientProps {
  secretKey: string
}

/** ``secretKey === 'local'`` is the sentinel set by ``buildLocalSecretURL``
 *  for no-server delivery. The full secret is in the URL fragment;
 *  there's nothing to fetch and nothing for the server to delete. */
const LOCAL_SENTINEL = 'local'

export default function SecretClient({ secretKey }: SecretClientProps) {
  const isLocalMode = secretKey === LOCAL_SENTINEL
  const [encryptionKey, setEncryptionKey] = useState<string | null>(null)
  const [decryptedSecret, setDecryptedSecret] = useState<string | null>(null)
  const [secretTitle, setSecretTitle] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [revealed, setRevealed] = useState(false)
  const [copied, setCopied] = useState(false)

  // Extract the URL fragment on mount. In server mode this is the
  // decryption key; in local mode it's the base64url-encoded secret.
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const hash = window.location.hash.slice(1)
      if (hash) {
        setEncryptionKey(hash)
      }
    }
  }, [])

  // Pre-fetch metadata (title) without consuming the secret. Skipped
  // in local mode — there's no server-side record to query.
  useEffect(() => {
    if (isLocalMode) return
    fetchSecretMetadata(secretKey).then(({ data }) => {
      if (data?.title) {
        setSecretTitle(data.title)
      }
    })
  }, [secretKey, isLocalMode])

  const handleReveal = useCallback(async () => {
    if (!encryptionKey) {
      setError(
        isLocalMode
          ? 'The link is incomplete — no secret payload in the URL.'
          : 'Missing decryption key. The link may be incomplete.',
      )
      return
    }

    setRevealed(true)
    setIsLoading(true)
    setError(null)

    try {
      // ── No-server / local mode ──
      // Decode the secret straight from the URL fragment. The server
      // never saw it, so there's nothing to fetch and nothing to
      // delete after viewing — the URL itself is the delivery.
      if (isLocalMode) {
        try {
          setDecryptedSecret(fromBase64Url(encryptionKey))
        } catch {
          setError('The link is malformed — could not decode the secret.')
        }
        return
      }

      const { data, status } = await fetchSecret(secretKey)
      if (status < 200 || status >= 300) {
        setError(data.message || 'Secret not found or already viewed')
        return
      }

      if (data.title) {
        setSecretTitle(data.title)
      }
      const decrypted = await decryptMessage(data.message, encryptionKey)
      setDecryptedSecret(decrypted.data as string)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to decrypt. The link may be invalid.',
      )
    } finally {
      setIsLoading(false)
    }
  }, [encryptionKey, secretKey, isLocalMode])

  const handleCopy = useCallback(() => {
    if (decryptedSecret) {
      navigator.clipboard.writeText(decryptedSecret).catch(() => {})
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }, [decryptedSecret])

  // Before reveal
  if (!revealed) {
    return (
      <div className="flex w-full max-w-md flex-col items-center gap-y-6 text-center">
        <h1 className="text-3xl font-semibold tracking-tight md:text-5xl">
          {secretTitle || (isLocalMode ? 'Shared Secret' : 'Encrypted Secret')}
        </h1>
        <p className="text-base font-medium tracking-wide text-slate-500 dark:text-slate-400">
          {isLocalMode
            ? 'Someone shared a secret with you in the URL itself'
            : 'Someone shared an encrypted secret with you'}
        </p>

        <div className="flex w-full items-center gap-x-2 rounded-lg bg-amber-50 px-4 py-3 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400">
          <Icon icon="solar:danger-triangle-linear" className="h-4 w-4" />
          <span className="text-sm">
            {isLocalMode
              ? 'The secret is in this URL. Anyone who has the link can read it — keep the URL out of public places.'
              : 'This is a one-time secret. It will be deleted after you view it.'}
          </span>
        </div>

        <Button onClick={handleReveal} size="lg" className="w-full">
          <Icon icon="solar:eye-linear" className="mr-2 h-4 w-4" />
          Reveal Secret
        </Button>
      </div>
    )
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex w-full max-w-md flex-col items-center gap-y-6 text-center">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-slate-300 border-t-slate-600 dark:border-slate-700 dark:border-t-slate-400" />
        <p className="text-slate-500 dark:text-slate-400">
          Fetching and decrypting...
        </p>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="flex w-full max-w-md flex-col items-center gap-y-6 text-center">
        <h1 className="text-3xl font-semibold tracking-tight md:text-5xl">
          Secret Not Available
        </h1>
        <p className="text-base font-medium tracking-wide text-slate-500 dark:text-slate-400">
          {error}
        </p>
        {!isLocalMode && (
          <div className="flex w-full items-center gap-x-2 rounded-lg bg-amber-50 px-4 py-3 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400">
            <Icon icon="solar:danger-triangle-linear" className="h-4 w-4" />
            <span className="text-sm">
              One-time secrets are deleted after being viewed once.
            </span>
          </div>
        )}
      </div>
    )
  }

  // Decrypted secret
  if (decryptedSecret) {
    return (
      <div className="flex w-full max-w-lg flex-col items-center gap-y-6">
        <h1 className="text-3xl font-semibold tracking-tight md:text-5xl">
          {secretTitle || 'Secret Revealed'}
        </h1>
        <p className="text-base font-medium tracking-wide text-slate-500 dark:text-slate-400">
          {isLocalMode
            ? 'Decoded from the URL — our server never saw this secret'
            : 'This secret has been deleted from the server'}
        </p>

        <div className="bg-surface w-full rounded-xl p-4">
          <pre className="max-h-96 overflow-auto text-sm wrap-break-word whitespace-pre-wrap text-slate-900 dark:text-slate-300">
            {decryptedSecret}
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
              Copy to Clipboard
            </>
          )}
        </Button>
      </div>
    )
  }

  // Fallback - shouldn't reach here
  return null
}
