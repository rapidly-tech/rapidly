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
import { buildSecretURL } from '@/utils/file-sharing/constants'
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
  password: string
  uuid: string
  customPassword: boolean
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
  const [result, setResult] = useState<Result | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const customPasswordId = useId()

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
    if (!title.trim()) {
      toast({ title: 'Please enter a title', variant: 'error' })
      return
    }

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

    try {
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

      setResult({
        password: pw,
        uuid: data.message,
        customPassword: useCustomPassword && !!customPassword,
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
  ])

  const handleReset = useCallback(() => {
    setResult(null)
    setSecret('')
    onStateChange?.('input')
  }, [onStateChange])

  // ── Share URL & Social Handlers ──
  // When custom password is used, share the link WITHOUT the password embedded
  // so the user can send the password through a separate channel (split-knowledge)
  const shareLink = result
    ? buildSecretURL(
        result.uuid,
        result.customPassword ? undefined : result.password,
      )
    : ''

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
          This secret will be deleted after it&apos;s viewed once.
        </WarningBanner>

        <div className="bg-surface rounded-xl p-4">
          <CopyableInput
            label="Share this link with a secret code"
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
      {/* Title — on top, always visible and required */}
      <div className="flex flex-col gap-2">
        <label htmlFor="secret-title" className="rp-text-secondary text-sm">
          Title <span className="text-red-500">*</span>
        </label>
        <input
          id="secret-title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. API Key, License Key"
          maxLength={255}
          required
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
          </div>
        )}

        {/* Require payment — only shown in dashboard */}
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

        <Button
          onClick={handleCreateSecret}
          disabled={
            isLoading ||
            (useCustomPassword &&
              customPassword.length < MIN_PASSWORD_LENGTH) ||
            (usePayment &&
              (priceCents === null ||
                priceCents < FILE_SHARING_MIN_PRICE_CENTS ||
                priceCents > FILE_SHARING_MAX_PRICE_CENTS))
          }
          variant="secondary"
          className="w-full"
          size="lg"
        >
          {isLoading ? 'Encrypting...' : 'Encrypt & Share'}
        </Button>
      </div>
    </div>
  )
}
