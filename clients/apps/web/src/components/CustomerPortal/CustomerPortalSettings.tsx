'use client'

import revalidate from '@/app/actions'
import { schemas } from '@rapidly-tech/client'
import { useCustomerPortalCustomer } from '@rapidly-tech/customer-portal/react'
import { Separator } from '@rapidly-tech/ui/components/primitives/separator'
import { useRouter } from 'next/navigation'
import { Well, WellContent, WellHeader } from '../Shared/Well'
import EditBillingDetails from './EditBillingDetails'

interface CustomerPortalSettingsProps {
  workspace: schemas['CustomerWorkspace']
  customerSessionToken?: string
}

/** Renders the customer portal settings page with billing details editing. */
export const CustomerPortalSettings = ({
  workspace: _workspace,
}: CustomerPortalSettingsProps) => {
  const router = useRouter()
  const { data: customer } = useCustomerPortalCustomer()

  if (!customer) {
    return null
  }

  return (
    <div className="flex flex-col gap-y-8">
      <h3 className="text-2xl">Settings</h3>
      <Well className="glass-surface flex flex-col gap-y-6">
        <WellHeader className="flex-row items-center justify-between">
          <div className="flex flex-col gap-y-2">
            <h3 className="text-xl">Billing Details</h3>
            <p className="text-slate-500 dark:text-slate-400">
              Update your billing details
            </p>
          </div>
        </WellHeader>
        <Separator className="dark:bg-slate-800" />
        <WellContent>
          <EditBillingDetails
            onSuccess={() => {
              revalidate(`customer_portal`)
              router.refresh()
            }}
          />
        </WellContent>
      </Well>
    </div>
  )
}
