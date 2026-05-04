'use client'

import { fetchSecret, fetchSecretMetadata } from '@/hooks/file-sharing'
import { decryptMessage } from '@/utils/file-sharing'
import {
  type LocalSecretEnvelope,
  decodeLocalSecretEnvelope,
  fromBase64Url,
} from '@/utils/file-sharing/constants'
import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Input from '@rapidly-tech/ui/components/forms/Input'
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
  // Local-mode envelope state — parsed once on mount so title and
  // expiry are available before reveal. ``null`` means either we're
  // not in local mode or the fragment is a legacy raw-base64 link
  // (handled by the backward-compat branch in ``handleReveal``).
  const [envelope, setEnvelope] = useState<LocalSecretEnvelope | null>(null)
  const [expired, setExpired] = useState(false)
  // Password prompt state for encrypted local-mode envelopes.
  const [passwordInput, setPasswordInput] = useState('')
  const [passwordError, setPasswordError] = useState<string | null>(null)

  // Extract the URL fragment on mount. In server mode this is the
  // decryption key; in local mode it's the encoded envelope (or, for
  // legacy links, the raw base64 of the plaintext).
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const hash = window.location.hash.slice(1)
      if (hash) {
        setEncryptionKey(hash)
        if (isLocalMode) {
          const env = decodeLocalSecretEnvelope(hash)
          if (env) {
            setEnvelope(env)
            if (env.title) setSecretTitle(env.title)
            if (env.expires_at && Date.now() > env.expires_at) {
              setExpired(true)
            }
          }
        }
      }
    }
  }, [isLocalMode])

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

  const decryptLocalEnvelope = useCallback(
    async (env: LocalSecretEnvelope, password?: string): Promise<string> => {
      // Unencrypted: ``env.secret`` is base64url of the plaintext.
      if (!env.encrypted) return fromBase64Url(env.secret)
      // Encrypted: ``env.secret`` is base64url of the OpenPGP armored
      // ciphertext. Decrypt with the recipient-supplied password.
      if (!password) throw new Error('Password required')
      const armored = fromBase64Url(env.secret)
      const decrypted = await decryptMessage(armored, password)
      return decrypted.data as string
    },
    [],
  )

  const handleReveal = useCallback(async () => {
    if (!encryptionKey) {
      setError(
        isLocalMode
          ? 'The link is incomplete — no secret payload in the URL.'
          : 'Missing decryption key. The link may be incomplete.',
      )
      return
    }

    if (isLocalMode && expired) {
      setError(
        'This link has expired. Ask the sender for a fresh one — the secret is no longer available.',
      )
      setRevealed(true)
      return
    }

    // Encrypted local envelopes need the password before we can do
    // anything. The reveal button collects it; here we just gate.
    if (isLocalMode && envelope?.encrypted && !passwordInput) {
      setRevealed(true)
      return
    }

    setRevealed(true)
    setIsLoading(true)
    setError(null)
    setPasswordError(null)

    try {
      // ── No-server / local mode ──
      // Decode the secret from the URL fragment. The server never
      // saw it, so there's nothing to fetch and nothing to delete
      // after viewing — the URL itself is the delivery.
      if (isLocalMode) {
        try {
          if (envelope) {
            const plaintext = await decryptLocalEnvelope(
              envelope,
              passwordInput || undefined,
            )
            setDecryptedSecret(plaintext)
          } else {
            // Backward compat: legacy raw-base64 fragment from before
            // envelopes existed. ``fromBase64Url`` is the only path.
            setDecryptedSecret(fromBase64Url(encryptionKey))
          }
        } catch (err) {
          if (envelope?.encrypted) {
            setPasswordError(
              'Could not decrypt — check the password and try again.',
            )
            setRevealed(false)
          } else {
            setError(
              err instanceof Error
                ? err.message
                : 'The link is malformed — could not decode the secret.',
            )
          }
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
  }, [
    encryptionKey,
    secretKey,
    isLocalMode,
    envelope,
    expired,
    passwordInput,
    decryptLocalEnvelope,
  ])

  const handleCopy = useCallback(() => {
    if (decryptedSecret) {
      navigator.clipboard.writeText(decryptedSecret).catch(() => {})
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }, [decryptedSecret])

  // Pre-reveal — expired short-circuit, password prompt for encrypted
  // local envelopes, or the default reveal button.
  const isEncryptedLocal = isLocalMode && !!envelope?.encrypted
  const needsPasswordPrompt =
    isEncryptedLocal && revealed && !decryptedSecret && !isLoading && !error
  // Warning copy varies with mode: encrypted local links are *not*
  // readable from the URL alone, so the ""anyone with the link can
  // read it"" line would be wrong.
  const localPreRevealWarning = envelope?.encrypted
    ? 'The link by itself is useless — you also need the password the sender shared separately.'
    : 'The secret is in this URL. Anyone who has the link can read it — keep the URL out of public places.'

  if (!revealed) {
    if (isLocalMode && expired) {
      return (
        <div className="flex w-full max-w-md flex-col items-center gap-y-6 text-center">
          <h1 className="text-3xl font-semibold tracking-tight md:text-5xl">
            Link expired
          </h1>
          <p className="text-base font-medium tracking-wide text-slate-500 dark:text-slate-400">
            The sender set a deadline that has passed. Ask them for a fresh link
            — the secret is no longer available here.
          </p>
        </div>
      )
    }
    return (
      <div className="flex w-full max-w-md flex-col items-center gap-y-6 text-center">
        <h1 className="text-3xl font-semibold tracking-tight md:text-5xl">
          {secretTitle || (isLocalMode ? 'Shared Secret' : 'Encrypted Secret')}
        </h1>
        <p className="text-base font-medium tracking-wide text-slate-500 dark:text-slate-400">
          {isLocalMode
            ? envelope?.encrypted
              ? 'Someone shared an encrypted secret with you — enter the password to reveal it'
              : 'Someone shared a secret with you in the URL itself'
            : 'Someone shared an encrypted secret with you'}
        </p>

        <div className="flex w-full items-center gap-x-2 rounded-lg bg-amber-50 px-4 py-3 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400">
          <Icon icon="solar:danger-triangle-linear" className="h-4 w-4" />
          <span className="text-sm">
            {isLocalMode
              ? localPreRevealWarning
              : 'This is a one-time secret. It will be deleted after you view it.'}
          </span>
        </div>

        <Button onClick={handleReveal} size="lg" className="w-full">
          <Icon icon="solar:eye-linear" className="mr-2 h-4 w-4" />
          {envelope?.encrypted ? 'Enter password' : 'Reveal Secret'}
        </Button>
      </div>
    )
  }

  if (needsPasswordPrompt) {
    return (
      <div className="flex w-full max-w-md flex-col items-center gap-y-6 text-center">
        <h1 className="text-3xl font-semibold tracking-tight md:text-5xl">
          {secretTitle || 'Encrypted Secret'}
        </h1>
        <p className="text-base font-medium tracking-wide text-slate-500 dark:text-slate-400">
          Enter the password the sender shared with you to decrypt this secret.
        </p>
        <form
          className="flex w-full flex-col gap-y-3"
          onSubmit={(e) => {
            e.preventDefault()
            handleReveal()
          }}
        >
          <Input
            type="password"
            value={passwordInput}
            onChange={(e) => setPasswordInput(e.target.value)}
            placeholder="Password"
            autoFocus
          />
          {passwordError && (
            <p className="text-sm text-red-500">{passwordError}</p>
          )}
          <Button type="submit" size="lg" className="w-full">
            <Icon icon="solar:eye-linear" className="mr-2 h-4 w-4" />
            Decrypt
          </Button>
        </form>
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
