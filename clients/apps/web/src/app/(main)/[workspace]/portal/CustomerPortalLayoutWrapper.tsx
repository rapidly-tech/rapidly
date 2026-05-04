'use client'

import { schemas } from '@rapidly-tech/client'
import { CustomerPortalProvider } from '@rapidly-tech/customer-portal/react'
import { useRouter, useSearchParams } from 'next/navigation'

interface CustomerPortalLayoutWrapperProps {
  workspace: schemas['CustomerWorkspace']
  children: React.ReactNode
}

export function CustomerPortalLayoutWrapper({
  workspace,
  children,
}: CustomerPortalLayoutWrapperProps) {
  const searchParams = useSearchParams()
  const router = useRouter()
  const token =
    searchParams.get('customer_session_token') ??
    searchParams.get('member_session_token') ??
    ''

  return (
    <CustomerPortalProvider
      token={token}
      workspaceId={workspace.id}
      workspaceSlug={workspace.slug}
      baseUrl={process.env.NEXT_PUBLIC_API_URL}
      onUnauthorized={() => {
        router.push(`/${workspace.slug}/portal/request`)
      }}
    >
      {children}
    </CustomerPortalProvider>
  )
}
