'use client'

import { usePortalAuthenticatedUser } from '@/hooks/api'
import { buildClientAPI } from '@/utils/client'
import { hasBillingPermission } from '@/utils/customerPortal'
import { Icon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import { EmptyState } from './EmptyState'

export interface CustomerPortalProps {
  workspace: schemas['CustomerWorkspace']
  customerSessionToken: string
}

/** Customer portal landing page showing file purchases or an empty state based on billing permissions. */
export const CustomerPortalOverview = ({
  workspace: _workspace,
  customerSessionToken,
}: CustomerPortalProps) => {
  const api = buildClientAPI(customerSessionToken)

  const { data: authenticatedUser } = usePortalAuthenticatedUser(api)
  const canManageBilling = hasBillingPermission(authenticatedUser)

  return (
    <div className="flex flex-col gap-y-12">
      <EmptyState
        icon={<Icon icon="solar:infinity-linear" className="h-5 w-5" />}
        title={canManageBilling ? 'No Files' : 'No Access'}
        description={
          canManageBilling
            ? "You don't have any file purchases at the moment."
            : "You don't have any access at the moment."
        }
      />
    </div>
  )
}
