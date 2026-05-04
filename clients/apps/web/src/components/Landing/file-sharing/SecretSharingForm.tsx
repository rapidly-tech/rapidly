'use client'

import { CopyableInput } from '@/components/FileSharing/CopyableInput'
import {
  FILE_SHARING_MAX_PRICE_CENTS,
  FILE_SHARING_MIN_PRICE_CENTS,
  PaymentConfigSection,
} from '@/components/FileSharing/PaymentConfigSection'
import {
  SocialShareGrid,
  useSocialShare,
} from '@/components/FileSharing/SocialShare'
import { WarningBanner } from '@/components/FileSharing/WarningBanner'
import { toast } from '@/components/Toast/use-toast'
import { postSecret } from '@/hooks/file-sharing'
import { encryptMessage, randomString } from '@/utils/file-sharing'
import {
  FILE_SHARING_API,
  buildLocalSecretURL,
  buildSecretURL,
  encodeLocalSecretEnvelope,
  toBase64Url,
} from '@/utils/file-sharing/constants'
import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Input from '@rapidly-tech/ui/components/forms/Input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@rapidly-tech/ui/components/forms/Select'
import { Checkbox } from '@rapidly-tech/ui/components/primitives/checkbox'
import { useCallback, useEffect, useId, useRef, useState } from 'react'
import QRCode from 'react-qr-code'

// ── Constants & Types ──

const SHARE_SUBJECT = 'Secure Secret Shared via Rapidly'
const MAX_SECRET_LENGTH = 50_000
const MIN_PASSWORD_LENGTH = 8

type Expiration = '3600' | '86400' | '604800'

const expirationLabels: Record<Expiration, string> = {
  '3600': '1 Hour',
  '86400': '1 Day',
  '604800': '1 Week',
}

interface Result {
  /** ``null`` for no-server mode (the secret is in the URL fragment). */
  password: string | null
  /** ``null`` for no-server mode — there's no server-side record. */
  uuid: string | null
  customPassword: boolean
  /** Pre-built share URL. For no-server mode this is the only thing
   *  the user needs to deliver; for server mode the URL is rebuilt
   *  on demand alongside the QR code. */
  shareUrl: string
  serverStored: boolean
}

export type SecretFormState = 'input' | 'result'

interface SecretSharingFormProps {
  onStateChange?: (state: SecretFormState) => void
  initialValue?: string
  workspaceId?: string
  showPricing?: boolean
}

// ── Main Component ──

/** Form for creating encrypted one-time secrets with expiration, optional custom password, and shareable link generation. */
export const SecretSharingForm = ({
  onStateChange,
  initialValue,
  workspaceId,
  showPricing,
}: SecretSharingFormProps) => {
  // ── State ──
  const [secret, setSecret] = useState('')
  const [expiration, setExpiration] = useState<Expiration>('3600')
  const [useCustomPassword, setUseCustomPassword] = useState(false)
  const [customPassword, setCustomPassword] = useState('')
  // ""Save on server"" defaults to OFF — by default the secret rides
  // in the URL fragment and the server never sees it (mirrors the
  // file-sharing model). Users opt in for offline delivery, expiry
  // tracking, custom password split-knowledge, and paid gating.
  const [saveOnServer, setSaveOnServer] = useState(false)
  const [result, setResult] = useState<Result | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const customPasswordId = useId()
  const saveOnServerId = useId()

  // ── Payment state ──
  const [usePayment, setUsePayment] = useState(false)
  const [priceCents, setPriceCents] = useState<number | null>(null)
  const [currency, setCurrency] = useState('usd')
  const [title, setTitle] = useState('')

  // Pre-fill textarea with initial character from keydown trigger
  useEffect(() => {
    if (initialValue) {
      setSecret(initialValue)
      // Focus textarea and place cursor after pre-filled char
      requestAnimationFrame(() => {
        const el = textareaRef.current
        if (el) {
          el.focus()
          el.setSelectionRange(initialValue.length, initialValue.length)
        }
      })
    }
  }, [initialValue])

  // ── Handlers ──
  const getPassword = useCallback(() => {
    return useCustomPassword && customPassword ? customPassword : randomString()
  }, [useCustomPassword, customPassword])

  const handlePaymentToggle = useCallback((checked: boolean) => {
    setUsePayment(checked)
    if (!checked) {
      setPriceCents(null)
    }
  }, [])

  const handleCreateSecret = useCallback(async () => {
    // Title is optional in every mode now. In server mode it's a
    // dashboard label (empty falls back to a generic "Untitled" on
    // listing); in no-server mode it rides in the envelope as a
    // recipient-facing hint and is omitted when empty.
    if (!secret.trim()) {
      toast({ title: 'Please enter a secret to share', variant: 'error' })
      return
    }

    if (useCustomPassword && customPassword.length < MIN_PASSWORD_LENGTH) {
      toast({
        title: `Password must be at least ${MIN_PASSWORD_LENGTH} characters`,
        variant: 'error',
      })
      return
    }

    if (
      usePayment &&
      (priceCents === null ||
        priceCents < FILE_SHARING_MIN_PRICE_CENTS ||
        priceCents > FILE_SHARING_MAX_PRICE_CENTS)
    ) {
      toast({ title: 'Please enter a valid price', variant: 'error' })
      return
    }

    setIsLoading(true)

    // Payment requires a server-side gate (URL fragments can't enforce
    // paywalls), so any paid secret implicitly uses server storage —
    // even if the ""Save on server"" toggle is off.
    const effectiveSaveOnServer = saveOnServer || usePayment

    try {
      // ── No-server (default) ──
      // Encode the secret into the URL fragment. The server never
      // sees it — fragments are not sent in HTTP requests. Same
      // delivery model as file-sharing: payload data stays on the
      // sender → recipient hop, the server only handles signaling /
      // metadata for opt-in features.
      if (!effectiveSaveOnServer) {
        // Optional password encryption: when on, the payload is
        // OpenPGP-armored under the user's password and the recipient
        // must enter the password to decrypt. Without it, the
        // payload rides as plaintext (URL-only privacy).
        const trimmedTitle = title.trim()
        const ttlSeconds = Number(expiration)
        const expiresAt =
          Number.isFinite(ttlSeconds) && ttlSeconds > 0
            ? Date.now() + ttlSeconds * 1000
            : undefined
        const passwordEncryption = useCustomPassword && !!customPassword
        const payloadString = passwordEncryption
          ? await encryptMessage(secret, customPassword)
          : secret
        const fragment = encodeLocalSecretEnvelope({
          v: 1,
          secret: toBase64Url(payloadString),
          ...(trimmedTitle && { title: trimmedTitle }),
          ...(expiresAt && { expires_at: expiresAt }),
          ...(passwordEncryption && { encrypted: true }),
        })
        const url = buildLocalSecretURL(fragment)
        setResult({
          password: null,
          uuid: null,
          customPassword: passwordEncryption,
          shareUrl: url,
          serverStored: false,
        })
        setSecret('')
        onStateChange?.('result')
        // Bump the share counter. The no-server payload itself never
        // reaches the server, but we ping a metadata-only endpoint
        // (workspace_id is the only data sent) so the public ""shares
        // so far"" tally — and the workspace tally for logged-in
        // users — include this share. Fire-and-forget with keepalive
        // so a subsequent navigation doesn't drop it; failures are
        // ignored because the share itself is already complete.
        fetch(`${FILE_SHARING_API}/no-server-secrets/ping`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          keepalive: true,
          body: JSON.stringify(
            workspaceId ? { workspace_id: workspaceId } : {},
          ),
        }).catch(() => {})
        window.dispatchEvent(new Event('rapidly:share-created'))
        return
      }

      // ── Server-stored (opt-in) ──
      const pw = getPassword()
      const encrypted = await encryptMessage(secret, pw)

      const { data, status } = await postSecret({
        message: encrypted,
        expiration: Number(expiration),
        title,
        ...(workspaceId && { workspace_id: workspaceId }),
        ...(usePayment && priceCents && { price_cents: priceCents, currency }),
      })

      if (status < 200 || status >= 300) {
        toast({
          title: data.message || 'Failed to create secret',
          variant: 'error',
        })
        return
      }

      const customPasswordActive = useCustomPassword && !!customPassword
      const serverShareUrl = buildSecretURL(
        data.message,
        customPasswordActive ? undefined : pw,
      )
      setResult({
        password: pw,
        uuid: data.message,
        customPassword: customPasswordActive,
        shareUrl: serverShareUrl,
        serverStored: true,
      })
      setSecret('')
      onStateChange?.('result')
      // Notify the share counter to refresh immediately
      window.dispatchEvent(new Event('rapidly:share-created'))
    } catch (err) {
      toast({
        title: err instanceof Error ? err.message : 'Failed to create secret',
        variant: 'error',
      })
    } finally {
      setIsLoading(false)
    }
  }, [
    secret,
    expiration,
    getPassword,
    useCustomPassword,
    customPassword,
    onStateChange,
    workspaceId,
    usePayment,
    priceCents,
    currency,
    title,
    saveOnServer,
  ])

  const handleReset = useCallback(() => {
    setResult(null)
    setSecret('')
    onStateChange?.('input')
  }, [onStateChange])

  // ── Share URL & Social Handlers ──
  // Unified — no-server mode embeds the secret in the fragment;
  // server mode embeds the password (or omits it for split-knowledge).
  // The form pre-builds the URL into the result so the rendering stays
  // a straight read.
  const shareLink = result?.shareUrl ?? ''

  const shareHandlers = useSocialShare({
    url: shareLink,
    emailSubject: SHARE_SUBJECT,
    emailBody: `I'm sharing a secret with you securely.\n\nView Secret: ${shareLink}\n\nThis link will self-destruct after one view.`,
    shareText: 'Secure secret',
  })

  // ── Render ──
  // Result view
  if (result) {
    return (
      <div className="flex w-full flex-col gap-y-6">
        {/* QR Code */}
        <div className="flex flex-col items-center">
          <div className="rounded-xl bg-white p-3 dark:bg-slate-800">
            <QRCode value={shareLink} size={120} />
          </div>
          <p className="mt-2 text-sm font-semibold text-slate-600 dark:text-slate-400">
            Scan to View Secret
          </p>
        </div>

        <WarningBanner
          icon={
            <Icon icon="solar:danger-triangle-linear" className="h-4 w-4" />
          }
        >
          {result.serverStored
            ? "This secret will be deleted after it's viewed once."
            : 'This secret rides in the URL itself — anyone with the link can read it. Send the link through a private channel.'}
        </WarningBanner>

        <div className="bg-surface rounded-xl p-4">
          <CopyableInput
            label={
              result.serverStored
                ? 'Share this link with a secret code'
                : 'Share this link — the secret is in the URL fragment, never sent to our server'
            }
            value={shareLink}
          />
          {result.customPassword && (
            <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
              Password protected — share your password separately
            </p>
          )}
        </div>

        <SocialShareGrid handlers={shareHandlers} />

        <Button
          onClick={handleReset}
          variant="secondary"
          size="lg"
          className="w-full"
        >
          Create Another Secret
        </Button>
      </div>
    )
  }

  // Input view
  return (
    <div className="flex w-full flex-col gap-4">
      {/* Title — optional in every mode. Server mode falls back to
          a generic label in the dashboard listing; no-server mode
          omits the hint from the envelope when empty. */}
      <div className="flex flex-col gap-2">
        <label htmlFor="secret-title" className="rp-text-secondary text-sm">
          Title
          <span className="rp-text-muted ml-1 text-xs">(optional)</span>
        </label>
        <input
          id="secret-title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. API Key, License Key"
          maxLength={255}
          className="bg-surface-inset rp-text-primary placeholder:rp-text-muted w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:ring-2 focus:ring-slate-400 focus:outline-none dark:border-slate-800 dark:focus:ring-slate-500"
        />
      </div>

      <textarea
        ref={textareaRef}
        value={secret}
        onChange={(e) => setSecret(e.target.value)}
        maxLength={MAX_SECRET_LENGTH}
        placeholder="Enter your secret here..."
        aria-label="Secret text to encrypt and share"
        className="rp-text-primary min-h-32 w-full rounded-xl border border-(--beige-border)/30 bg-white p-4 placeholder:text-(--text-muted) focus:border-(--beige-focus)/60 focus:ring-1 focus:ring-(--beige-border)/20 focus:outline-none dark:border-white/[0.06] dark:bg-white/[0.03]"
      />

      <div className="flex flex-col gap-4">
        {/* Save on server toggle — default OFF. The hint right under
            it tells the user what they re trading away when they flip
            it on, so the privacy-by-default story stays explicit.
            Locked ON when payment is enabled, since a paywall needs
            a server-side gate — keeps the toggle visually honest
            instead of off-but-actually-on. */}
        <div className="flex items-start gap-x-3">
          <Checkbox
            id={saveOnServerId}
            checked={saveOnServer || usePayment}
            disabled={usePayment}
            onCheckedChange={(checked) => setSaveOnServer(checked === true)}
          />
          <div className="flex flex-col gap-1">
            <label
              htmlFor={saveOnServerId}
              className="rp-text-secondary text-sm"
            >
              Save on our server
              <span className="rp-text-muted ml-1 text-xs">
                {usePayment ? '(required for payment)' : '(optional)'}
              </span>
            </label>
            <p className="rp-text-muted text-xs">
              {saveOnServer || usePayment
                ? 'The encrypted secret is stored on our server with an expiry. Enables offline delivery, custom-password split-knowledge, and paid gating.'
                : 'The secret stays in the URL fragment — never sent to our server. Same as how files are shared. Recipient must open the link before you forget the URL.'}
            </p>
          </div>
        </div>

        {/* Expires-in — server enforces in server mode; in no-server
            mode it's a soft client-checked deadline encoded in the
            envelope (the recipient's browser refuses to reveal past
            it). The helper line says so honestly. */}
        <div className="flex flex-col gap-y-2">
          <label className="rp-text-secondary text-sm">Expires in</label>
          <Select
            value={expiration}
            onValueChange={(v) => setExpiration(v as Expiration)}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(expirationLabels).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {!saveOnServer && (
            <p className="rp-text-muted text-xs">
              Checked by the recipient&apos;s browser, not enforced by a server.
              Use &ldquo;Save on our server&rdquo; if you need a hard deadline.
            </p>
          )}
        </div>

        <div className="flex items-center gap-x-3">
          <Checkbox
            id={customPasswordId}
            checked={useCustomPassword}
            onCheckedChange={(checked) =>
              setUseCustomPassword(checked === true)
            }
          />
          <label
            htmlFor={customPasswordId}
            className="rp-text-secondary text-sm"
          >
            Use custom password
          </label>
        </div>

        {useCustomPassword && (
          <div>
            <Input
              type="password"
              value={customPassword}
              onChange={(e) => setCustomPassword(e.target.value)}
              placeholder="Enter custom password"
              minLength={MIN_PASSWORD_LENGTH}
            />
            {customPassword.length > 0 &&
              customPassword.length < MIN_PASSWORD_LENGTH && (
                <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
                  Minimum {MIN_PASSWORD_LENGTH} characters
                </p>
              )}
            {!saveOnServer && (
              <p className="rp-text-muted mt-1 text-xs">
                The payload is encrypted with this password and sent through a
                separate channel. The link alone won&apos;t reveal the secret.
              </p>
            )}
          </div>
        )}

        {/* Payment — available in every mode for logged-in users.
            Anonymous users have no workspace_id, so the paid gate
            wouldn't have anywhere to attach. When payment is on but
            ""Save on server"" is off we transparently switch to
            server-storage at submit time, since a paywall needs a
            server-side gate that URL fragments can't provide. */}
        {workspaceId && (
          <PaymentConfigSection
            showPricing={showPricing}
            workspaceId={workspaceId}
            usePayment={usePayment}
            priceCents={priceCents}
            currency={currency}
            onPaymentToggle={handlePaymentToggle}
            onPriceCentsChange={setPriceCents}
            onCurrencyChange={setCurrency}
          />
        )}

        <Button
          onClick={handleCreateSecret}
          disabled={
            isLoading ||
            // Custom-password gate runs in both modes — no-server uses
            // the password to actually encrypt the payload, so a too-
            // short password is just as wrong there as on the server.
            (useCustomPassword &&
              customPassword.length < MIN_PASSWORD_LENGTH) ||
            // Price is required whenever payment is on, regardless of
            // storage mode (no-server with payment auto-switches to
            // server-stored at submit time).
            (usePayment &&
              (priceCents === null ||
                priceCents < FILE_SHARING_MIN_PRICE_CENTS ||
                priceCents > FILE_SHARING_MAX_PRICE_CENTS))
          }
          variant="secondary"
          className="w-full"
          size="lg"
        >
          {isLoading
            ? saveOnServer || (useCustomPassword && customPassword)
              ? 'Encrypting...'
              : 'Building link...'
            : saveOnServer
              ? 'Encrypt & Share'
              : useCustomPassword && customPassword
                ? 'Encrypt & Share'
                : 'Share'}
        </Button>
      </div>
    </div>
  )
}
