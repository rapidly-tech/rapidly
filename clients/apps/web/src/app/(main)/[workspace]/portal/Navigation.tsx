'use client'

import {
  useAuthenticatedCustomer,
  useCustomerPortalSession,
  usePortalAuthenticatedUser,
} from '@/hooks/api'
import { buildClientAPI } from '@/utils/client'
import { hasBillingPermission } from '@/utils/customerPortal'
import { Icon } from '@iconify/react'
import { Client, schemas } from '@rapidly-tech/client'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@rapidly-tech/ui/components/forms/Select'
import Link from 'next/link'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { twMerge } from 'tailwind-merge'

const links = (
  workspace: schemas['CustomerWorkspace'],
  authenticatedUser: schemas['PortalAuthenticatedUser'] | undefined,
  _customer: schemas['CustomerPortalCustomer'] | undefined,
) => {
  const canAccessBilling = hasBillingPermission(authenticatedUser)

  return [
    {
      href: `/${workspace.slug}/portal/overview`,
      label: 'Overview',
      isActive: (path: string) => path.includes('/overview'),
    },
    ...(canAccessBilling
      ? [
          {
            href: `/${workspace.slug}/portal/settings`,
            label: 'Billing',
            isActive: (path: string) => path.includes('/settings'),
          },
        ]
      : []),
  ]
}

// Inner component that uses hooks - only rendered when token is available
const NavigationContent = ({
  workspace,
  api,
  currentPath,
  searchParams,
}: {
  workspace: schemas['CustomerWorkspace']
  api: Client
  currentPath: string
  searchParams: URLSearchParams
}) => {
  const router = useRouter()
  const { data: customerPortalSession } = useCustomerPortalSession(api)
  const { data: authenticatedUser } = usePortalAuthenticatedUser(api)
  const { data: customer } = useAuthenticatedCustomer(api)

  const buildPath = (path: string) => {
    return `${path}?${searchParams.toString()}`
  }

  const filteredLinks = links(workspace, authenticatedUser, customer)

  return (
    <>
      <nav className="sticky top-0 hidden h-fit w-40 flex-none flex-col gap-y-6 py-12 md:flex lg:w-64">
        {customerPortalSession?.return_url &&
          /^https:\/\//.test(customerPortalSession.return_url) && (
            <Link
              href={customerPortalSession.return_url}
              className="flex flex-row items-center gap-x-4 py-2 text-slate-500 dark:text-slate-400"
            >
              <Icon icon="solar:arrow-left-linear" className="text-[1em]" />
              <span>Back to {workspace.name}</span>
            </Link>
          )}
        <div className="flex flex-col">
          <h3>{authenticatedUser?.name ?? '—'}</h3>
          <span className="text-slate-500 dark:text-slate-400">
            {authenticatedUser?.email ?? '—'}
          </span>
        </div>
        <div className="flex flex-col gap-y-1">
          {filteredLinks.map((link) => (
            <Link
              key={link.href}
              href={buildPath(link.href)}
              className={twMerge(
                'rounded-lg border border-transparent px-3 py-1.5 text-sm font-medium text-slate-500 transition-colors duration-75 hover:bg-slate-100 dark:hover:bg-slate-900',
                link.isActive(currentPath) &&
                  'rp-text-primary bg-slate-100 dark:border-slate-800 dark:bg-slate-900',
              )}
              prefetch
            >
              {link.label}
            </Link>
          ))}
        </div>
      </nav>
      <Select
        value={filteredLinks.find(({ href }) => href === currentPath)?.label}
        onValueChange={(value: string) => {
          router.push(
            buildPath(
              filteredLinks.find(({ label }) => label === value)?.href ?? '',
            ),
          )
        }}
      >
        <SelectTrigger className="md:hidden">
          <SelectValue placeholder="Select page" />
        </SelectTrigger>
        <SelectContent>
          {filteredLinks.map((link) => (
            <SelectItem key={link.href} value={link.label}>
              {link.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </>
  )
}

export const Navigation = ({
  workspace,
}: {
  workspace: schemas['CustomerWorkspace']
}) => {
  const currentPath = usePathname()
  const searchParams = useSearchParams()

  // Hide navigation on routes where portal access is being requested or authenticated
  if (
    currentPath.endsWith('/portal/request') ||
    currentPath.endsWith('/portal/authenticate')
  ) {
    return null
  }

  const token =
    searchParams.get('customer_session_token') ??
    searchParams.get('member_session_token')

  // Don't render until token is available (handles SSR/hydration)
  if (!token) {
    return null
  }

  const api = buildClientAPI(token)

  return (
    <NavigationContent
      workspace={workspace}
      api={api}
      currentPath={currentPath}
      searchParams={searchParams}
    />
  )
}
