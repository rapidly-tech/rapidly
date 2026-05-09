import { ACCOUNT_TYPE_DISPLAY_NAMES } from '@/utils/account'
import { api } from '@/utils/client'
import { ALLOWED_STRIPE_ORIGINS, isSafeRedirect } from '@/utils/safe-redirect'
import { resolveResponse, schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { twMerge } from 'tailwind-merge'

interface AccountsListProps {
  accounts: schemas['Account'][]
  currentWorkspace?: schemas['Workspace']
  activeAccountId?: string
}

const AccountsList = ({
  accounts,
  currentWorkspace,
  activeAccountId,
}: AccountsListProps) => {
  const accountRows = useMemo(
    () =>
      accounts
        .filter((account) => account.stripe_id)
        .map((account) => ({
          account,
          workspace: account.workspaces[0] ?? null,
        }))
        .sort((a, b) => {
          // Put the active/default account first
          const aActive = a.account.id === activeAccountId ? 1 : 0
          const bActive = b.account.id === activeAccountId ? 1 : 0
          return bActive - aActive
        }),
    [accounts, activeAccountId],
  )

  return (
    <table className="-mx-4 w-full text-left">
      <thead className="text-slate-500 dark:text-slate-400">
        <tr className="text-sm">
          <th
            scope="col"
            className="relative isolate px-4 py-3.5 pr-2 text-left font-normal whitespace-nowrap"
          >
            Type
          </th>
          <th
            scope="col"
            className="relative isolate px-4 py-3.5 pr-2 text-left font-normal whitespace-nowrap"
          >
            Status
          </th>
          <th
            scope="col"
            className="relative isolate px-4 py-3.5 pr-2 text-left font-normal whitespace-nowrap"
          >
            Used by
          </th>
          <th
            scope="col"
            className="relative isolate px-4 py-3.5 pr-2 font-normal whitespace-nowrap"
          >
            Actions
          </th>
        </tr>
      </thead>
      <tbody>
        {accountRows.map(({ account, workspace }) => (
          <AccountListItem
            key={account.id}
            account={account}
            workspace={workspace}
            currentWorkspace={currentWorkspace}
            isActive={account.id === activeAccountId}
          />
        ))}
      </tbody>
    </table>
  )
}

export default AccountsList

interface AccountListItemProps {
  account: schemas['Account']
  workspace: schemas['Workspace'] | null
  currentWorkspace?: schemas['Workspace']
  isActive?: boolean
}

const AccountListItem = ({
  account,
  workspace,
  currentWorkspace,
  isActive = false,
}: AccountListItemProps) => {
  const queryClient = useQueryClient()
  const childClass = twMerge(
    'dark:group-hover:bg-slate-800 px-4 py-2 transition-colors group-hover:bg-slate-100 group-hover:text-foreground text-slate-700 dark:text-slate-400',
  )

  const [loading, setLoading] = useState(false)

  const isFullyOnboarded =
    account?.stripe_id !== null && account.is_details_submitted
  const isPendingOnboarding =
    account?.stripe_id !== null && !account.is_details_submitted

  const goToOnboarding = async () => {
    setLoading(true)
    try {
      const link = await resolveResponse(
        api.POST('/api/accounts/{id}/onboarding_link', {
          params: {
            path: { id: account.id },
            query: {
              return_path: `/dashboard/${workspace?.slug ?? currentWorkspace?.slug ?? ''}/finance/account`,
            },
          },
        }),
      )
      if (isSafeRedirect(link.url, ALLOWED_STRIPE_ORIGINS)) {
        window.location.href = link.url
      }
    } catch {
      setLoading(false)
    }
  }

  const switchToThis = async () => {
    if (!currentWorkspace) return
    setLoading(true)
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/api/workspaces/${currentWorkspace.id}/switch-account`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ account_id: account.id }),
        },
      )
      if (response.ok) {
        // Invalidate cached data so the UI refreshes
        await queryClient.invalidateQueries({ queryKey: ['user', 'accounts'] })
        await queryClient.invalidateQueries({
          queryKey: ['workspaces', 'account', currentWorkspace.id],
        })
        await queryClient.invalidateQueries({ queryKey: ['workspaces'] })
      }
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  return (
    <tr className="group text-sm">
      <td className={twMerge(childClass, 'rounded-l-xl')}>
        <div>
          {ACCOUNT_TYPE_DISPLAY_NAMES[account.account_type]}
          {account.stripe_id && (
            <div className="text-xs text-slate-400">
              {account.stripe_id.slice(-8)}
            </div>
          )}
        </div>
      </td>
      <td className={childClass}>
        {isActive
          ? 'Default'
          : isFullyOnboarded
            ? 'Active'
            : isPendingOnboarding
              ? 'Pending'
              : '—'}
      </td>
      <td className={childClass}>
        {workspace ? (
          workspace.slug
        ) : (
          <span className="text-slate-400">Available</span>
        )}
      </td>
      <td className={twMerge(childClass, 'rounded-r-xl')}>
        <div className="flex gap-2">
          {isPendingOnboarding && (
            <Button
              size="sm"
              variant="secondary"
              onClick={goToOnboarding}
              loading={loading}
            >
              Continue setup
            </Button>
          )}
          {isFullyOnboarded && !isActive && currentWorkspace && (
            <Button
              size="sm"
              variant="secondary"
              onClick={switchToThis}
              loading={loading}
            >
              Switch to this
            </Button>
          )}
        </div>
      </td>
    </tr>
  )
}
