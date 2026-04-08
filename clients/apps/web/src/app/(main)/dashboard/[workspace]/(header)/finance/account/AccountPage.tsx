'use client'

import AccountCreateModal from '@/components/Accounts/AccountCreateModal'
import AccountsList from '@/components/Accounts/AccountsList'
import { DashboardBody } from '@/components/Layout/DashboardLayout'
import { Modal } from '@/components/Modal'
import { useModal } from '@/components/Modal/useModal'
import { useListAccounts, useWorkspaceAccount } from '@/hooks/api'
import { api } from '@/utils/client'
import { ALLOWED_STRIPE_ORIGINS, isSafeRedirect } from '@/utils/safe-redirect'
import { Icon } from '@iconify/react'
import { resolveResponse, schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { useRouter, useSearchParams } from 'next/navigation'
import { useCallback, useEffect } from 'react'

export default function ClientPage({
  workspace,
}: {
  workspace: schemas['Workspace']
}) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const returnTo = searchParams.get('return_to')
  const { data: accounts } = useListAccounts()
  const {
    isShown: isShownSetupModal,
    show: showSetupModal,
    hide: hideSetupModal,
  } = useModal()

  const { data: workspaceAccount, error: accountError } = useWorkspaceAccount(
    workspace.id,
  )

  const isNotAdmin =
    accountError &&
    'response' in accountError &&
    (accountError as { response: { status: number } }).response?.status === 403

  const isAccountSetUp =
    workspaceAccount?.stripe_id && workspaceAccount?.is_details_submitted

  // Redirect back to the referring page after account setup completes
  useEffect(() => {
    if (isAccountSetUp && returnTo) {
      // Sanitize: strip leading slashes/dots to prevent path traversal
      const sanitized = returnTo.replace(/^[./\\]+/, '')
      router.replace(`/dashboard/${workspace.slug}/${sanitized}`)
    }
  }, [isAccountSetUp, returnTo, router, workspace.slug])

  const handleStartAccountSetup = useCallback(async () => {
    if (!workspaceAccount || !workspaceAccount.stripe_id) {
      showSetupModal()
    } else {
      try {
        const link = await resolveResponse(
          api.POST('/api/accounts/{id}/onboarding_link', {
            params: {
              path: {
                id: workspaceAccount.id,
              },
              query: {
                return_path: `/dashboard/${workspace.slug}/finance/account`,
              },
            },
          }),
        )
        if (isSafeRedirect(link.url, ALLOWED_STRIPE_ORIGINS)) {
          window.location.href = link.url
        } else {
          window.location.reload()
        }
      } catch {
        window.location.reload()
      }
    }
  }, [workspace.slug, workspaceAccount, showSetupModal])

  return (
    <DashboardBody className="gap-y-8 pb-16 md:gap-y-12">
      <div className="flex flex-col gap-y-8">
        {/* Status Card */}
        <div className="glass-elevated flex flex-col items-center gap-y-4 rounded-2xl bg-slate-50 p-8 text-center shadow-xs lg:rounded-3xl dark:bg-slate-900">
          {isAccountSetUp ? (
            <>
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/60 dark:bg-slate-800">
                <Icon
                  icon="solar:check-read-linear"
                  className="h-6 w-6 text-slate-600 dark:text-slate-400"
                />
              </div>
              <h3 className="text-lg font-medium">Stripe Account Connected</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Your Stripe account is set up and ready to accept payments.
              </p>
              <Button onClick={showSetupModal} className="w-auto">
                Add a new account
                <Icon icon="solar:add-circle-linear" className="ml-2 h-4 w-4" />
              </Button>
            </>
          ) : isNotAdmin ? (
            <>
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/60 dark:bg-slate-800">
                <Icon
                  icon="solar:user-check-rounded-linear"
                  className="h-6 w-6 text-slate-600 dark:text-slate-400"
                />
              </div>
              <h3 className="text-lg font-medium">Admin Access Required</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Only the workspace admin can set up the payout account.
              </p>
            </>
          ) : (
            <>
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/60 dark:bg-slate-800">
                <Icon
                  icon="solar:user-check-rounded-linear"
                  className="h-6 w-6 text-slate-600 dark:text-slate-400"
                />
              </div>
              <h3 className="text-lg font-medium">Set Up Payout Account</h3>
              <p className="max-w-md text-sm text-slate-500 dark:text-slate-400">
                Connect or create a Stripe account to receive payments from your
                customers.
              </p>
              <Button onClick={handleStartAccountSetup} className="w-auto">
                Continue with Account Setup
                <Icon
                  icon="solar:arrow-right-linear"
                  className="ml-2 h-4 w-4"
                />
              </Button>
            </>
          )}
        </div>

        {/* Accounts List */}
        {accounts?.data && accounts.data.length > 0 && (
          <div className="glass-elevated rounded-2xl bg-slate-50 p-6 shadow-xs lg:rounded-3xl dark:bg-slate-900">
            <div className="flex flex-col gap-y-1">
              <h2 className="text-lg font-medium">All payout accounts</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Payout accounts you manage
              </p>
            </div>
            <div className="mt-6 border-t border-slate-200/50 pt-6 dark:border-slate-800">
              <AccountsList
                accounts={accounts.data}
                currentWorkspace={workspace}
                activeAccountId={workspaceAccount?.id}
              />
            </div>
          </div>
        )}
      </div>

      <Modal
        title="Create Payout Account"
        isShown={isShownSetupModal}
        className="min-w-[400px]"
        hide={hideSetupModal}
        modalContent={
          <AccountCreateModal
            forWorkspaceId={workspace.id}
            returnPath={`/dashboard/${workspace.slug}/finance/account`}
            forceNew={!!isAccountSetUp}
          />
        }
      />
    </DashboardBody>
  )
}
