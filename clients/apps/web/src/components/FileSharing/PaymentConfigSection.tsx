'use client'

import { useWorkspacePaymentStatus } from '@/hooks/api'
import { CURRENCY_OPTIONS } from '@/utils/constants/currencies'
import {
  FILE_SHARING_MAX_PRICE_CENTS,
  FILE_SHARING_MIN_PRICE_CENTS,
} from '@/utils/constants/validation'
import { Checkbox } from '@rapidly-tech/ui/components/primitives/checkbox'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useCallback, useState } from 'react'

export interface PaymentConfigProps {
  showPricing?: boolean
  workspaceId?: string
  usePayment: boolean
  priceCents: number | null
  currency: string
  onPaymentToggle: (checked: boolean) => void
  onPriceCentsChange: (cents: number | null) => void
  onCurrencyChange: (currency: string) => void
}

export function PaymentConfigSection({
  showPricing,
  workspaceId,
  usePayment,
  priceCents,
  currency,
  onPaymentToggle,
  onPriceCentsChange,
  onCurrencyChange,
}: PaymentConfigProps) {
  const pathname = usePathname()
  const { data: paymentStatus } = useWorkspacePaymentStatus(
    workspaceId ?? '',
    showPricing === true && Boolean(workspaceId),
    true,
  )
  const isStripeReady = paymentStatus?.payment_ready
  const financeAccountPath =
    pathname.replace(
      /\/(file-sharing|shares\/send-files)$/,
      '/finance/account',
    ) + '?return_to=shares/send-files'

  const [priceInput, setPriceInput] = useState(
    priceCents !== null ? (priceCents / 100).toFixed(2) : '',
  )

  const handlePriceChange = useCallback(
    (value: string) => {
      setPriceInput(value)
      const parsed = parseFloat(value)
      if (!isNaN(parsed) && parsed > 0) {
        onPriceCentsChange(Math.round(parsed * 100))
      } else {
        onPriceCentsChange(null)
      }
    },
    [onPriceCentsChange],
  )

  if (!showPricing) return null

  return (
    <div className="flex flex-col gap-2">
      <label className="flex cursor-pointer items-center gap-2">
        <Checkbox
          checked={usePayment}
          onCheckedChange={(checked) => onPaymentToggle(checked === true)}
        />
        <span className="text-sm text-slate-500 dark:text-slate-400">
          Require payment
        </span>
      </label>
      {usePayment && !isStripeReady && (
        <div className="flex flex-col gap-2 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:bg-amber-900/20 dark:text-amber-400">
          <p className="font-medium">Stripe account required</p>
          <p className="text-xs">
            To accept payments, you need to set up a Stripe payout account
            first.
          </p>
          <Link
            href={financeAccountPath}
            className="inline-flex items-center gap-1 text-xs font-medium text-amber-800 underline hover:text-amber-900 dark:text-amber-300 dark:hover:text-amber-200"
          >
            Set up Stripe account
          </Link>
        </div>
      )}
      {usePayment && isStripeReady && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-500 dark:text-slate-400">
              {CURRENCY_OPTIONS.find((c) => c.code === currency)?.symbol ?? '$'}
            </span>
            <input
              type="number"
              value={priceInput}
              onChange={(e) => handlePriceChange(e.target.value)}
              placeholder="0.00"
              min={(FILE_SHARING_MIN_PRICE_CENTS / 100).toFixed(2)}
              max={(FILE_SHARING_MAX_PRICE_CENTS / 100).toFixed(2)}
              step="0.01"
              className="bg-surface-inset rp-text-primary placeholder:rp-text-muted w-32 rounded-xl border border-slate-200 px-3 py-2 text-sm focus:ring-2 focus:ring-slate-400 focus:outline-none dark:border-slate-800 dark:focus:ring-slate-500"
              autoFocus
            />
          </div>
          <div
            className="flex flex-wrap gap-2"
            role="radiogroup"
            aria-label="Currency"
          >
            {CURRENCY_OPTIONS.map((c) => (
              <button
                key={c.code}
                type="button"
                role="radio"
                aria-checked={currency === c.code}
                onClick={() => onCurrencyChange(c.code)}
                className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
                  currency === c.code
                    ? 'border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900'
                    : 'bg-surface-inset border-slate-200 text-slate-600 hover:border-slate-400 dark:border-slate-800 dark:text-slate-400 dark:hover:border-slate-500'
                }`}
              >
                {c.symbol} {c.label}
              </button>
            ))}
          </div>
          {priceCents !== null && priceCents > FILE_SHARING_MAX_PRICE_CENTS && (
            <p className="text-xs text-red-500 dark:text-red-400">
              Maximum price is{' '}
              {CURRENCY_OPTIONS.find((c) => c.code === currency)?.symbol ?? '$'}
              {(FILE_SHARING_MAX_PRICE_CENTS / 100).toLocaleString()}
            </p>
          )}
          {priceCents !== null &&
            priceCents > 0 &&
            priceCents < FILE_SHARING_MIN_PRICE_CENTS && (
              <p className="text-xs text-red-500 dark:text-red-400">
                Minimum price is{' '}
                {CURRENCY_OPTIONS.find((c) => c.code === currency)?.symbol ??
                  '$'}
                {(FILE_SHARING_MIN_PRICE_CENTS / 100).toFixed(2)}
              </p>
            )}
          <p className="text-xs text-slate-400 dark:text-slate-500">
            Buyers will pay via Stripe before accessing the content.
          </p>
        </div>
      )}
    </div>
  )
}

export { FILE_SHARING_MAX_PRICE_CENTS, FILE_SHARING_MIN_PRICE_CENTS }
