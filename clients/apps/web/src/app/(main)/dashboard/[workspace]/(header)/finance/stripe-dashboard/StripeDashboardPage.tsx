'use client'

import { DashboardBody } from '@/components/Layout/DashboardLayout'
import { useWorkspaceAccount } from '@/hooks/api'
import { api } from '@/utils/client'
import { ALLOWED_STRIPE_ORIGINS, isSafeRedirect } from '@/utils/safe-redirect'
import { Icon } from '@iconify/react'
import { resolveResponse, schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Link from 'next/link'
import { useCallback, useState } from 'react'

export default function StripeDashboardPage({
  workspace,
}: {
  workspace: schemas['Workspace']
}) {
  const { data: workspaceAccount } = useWorkspaceAccount(workspace.id)
  const [loading, setLoading] = useState(false)

  const isAccountSetUp =
    workspaceAccount?.stripe_id && workspaceAccount?.is_details_submitted

  const handleOpenDashboard = useCallback(async () => {
    if (!workspaceAccount) return
    setLoading(true)
    try {
      const link = await resolveResponse(
        api.POST('/api/accounts/{id}/dashboard_link', {
          params: {
            path: { id: workspaceAccount.id },
          },
        }),
      )
      if (isSafeRedirect(link.url, ALLOWED_STRIPE_ORIGINS)) {
        window.open(link.url, '_blank', 'noopener,noreferrer')
      }
    } catch {
      // fallback
    } finally {
      setLoading(false)
    }
  }, [workspaceAccount])

  return (
    <DashboardBody className="gap-y-8 pb-16 md:gap-y-12">
      <div className="flex flex-col gap-y-8">
        <div className="glass-elevated rounded-2xl bg-slate-50 p-8 shadow-xs lg:rounded-3xl dark:bg-slate-900">
          {isAccountSetUp ? (
            <div className="space-y-4 text-center">
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Manage your payments, view transaction history, and track
                payouts directly in your Stripe Dashboard.
              </p>
              <Button
                onClick={handleOpenDashboard}
                loading={loading}
                className="w-auto"
              >
                Open Stripe Dashboard
                <Icon
                  icon="solar:square-arrow-right-up-linear"
                  className="ml-2 h-4 w-4"
                />
              </Button>
            </div>
          ) : (
            <div className="space-y-4 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-amber-100 dark:bg-amber-900/30">
                <Icon
                  icon="solar:danger-circle-linear"
                  className="h-8 w-8 text-amber-600 dark:text-amber-400"
                />
              </div>
              <h3 className="text-lg font-medium">Stripe Account Required</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Set up your Stripe account first to access the dashboard.
              </p>
              <Link href={`/dashboard/${workspace.slug}/finance/account`}>
                <Button variant="outline" className="w-auto">
                  Set Up Account
                </Button>
              </Link>
            </div>
          )}
        </div>
      </div>
    </DashboardBody>
  )
}
