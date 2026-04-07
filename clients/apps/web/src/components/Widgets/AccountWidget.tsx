import { useStripeBalance, useStripePayouts } from '@/hooks/api/stripeConnect'
import { WorkspaceContext } from '@/providers/workspaceContext'
import { formatCurrency } from '@rapidly-tech/currency'
import { Status } from '@rapidly-tech/ui/components/feedback/Status'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Link from 'next/link'
import { useContext } from 'react'
import { twMerge } from 'tailwind-merge'
export interface AccountWidgetProps {
  className?: string
}

export const AccountWidget = ({ className }: AccountWidgetProps) => {
  const { workspace } = useContext(WorkspaceContext)

  const { data: balance } = useStripeBalance(workspace.id)
  const { data: payouts } = useStripePayouts(workspace.id, { limit: 1 })

  const lastPayout = payouts?.items?.[0]

  const availableBalance = balance?.available?.[0]
  const canWithdraw =
    workspace.status === 'active' &&
    availableBalance?.amount &&
    availableBalance.amount > 0

  return (
    <div
      className={twMerge(
        'flex h-80 flex-col justify-between rounded-4xl bg-slate-50 dark:bg-slate-900',
        className,
      )}
    >
      <div className="flex flex-col gap-y-4 p-6 pb-2">
        <div className="flex flex-row items-center justify-between">
          <span className="text-lg">Account Balance</span>
          <Link href={`/dashboard/${workspace.slug}/finance`}>
            <Button
              variant={canWithdraw ? 'default' : 'secondary'}
              size="sm"
              className="rounded-full border-none"
            >
              {canWithdraw ? 'Withdraw' : 'Transactions'}
            </Button>
          </Link>
        </div>
        <h2 className="text-5xl font-light">
          {availableBalance &&
            formatCurrency(
              availableBalance.amount,
              availableBalance.currency,
              0,
              undefined,
              'narrowSymbol',
            )}
        </h2>
      </div>
      <div className="m-2 flex flex-col gap-y-4 rounded-3xl bg-white p-4 dark:bg-slate-800">
        {lastPayout ? (
          <div className="flex flex-col">
            <div className="flex flex-row items-center justify-between gap-x-2">
              <h3 className="text-lg">
                {formatCurrency(lastPayout.amount, lastPayout.currency, 0)}
              </h3>
              <Status
                status={lastPayout.status.split('_').join(' ')}
                className={twMerge(
                  'px-2 py-1 text-sm capitalize',
                  lastPayout.status === 'paid'
                    ? 'bg-emerald-50 text-emerald-500 dark:bg-emerald-950'
                    : 'bg-amber-50 text-amber-500 dark:bg-amber-950',
                )}
              />
            </div>
            <p className="text-sm text-slate-500">
              {new Date(lastPayout.created).toLocaleDateString('en-US', {
                month: 'long',
                day: 'numeric',
                year: 'numeric',
              })}
            </p>
          </div>
        ) : (
          <div className="flex flex-col">
            <h3>No payouts yet</h3>
            <p className="text-sm text-slate-500">
              You may only withdraw funds above $10.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
