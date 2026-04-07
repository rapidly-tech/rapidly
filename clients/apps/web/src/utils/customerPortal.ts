import { Client, resolveResponse, schemas } from '@rapidly-tech/client'
import { notFound, redirect } from 'next/navigation'
import { cache } from 'react'

type PortalUser = schemas['PortalAuthenticatedUser'] | undefined

const BILLING_ROLES = new Set(['owner', 'billing_manager'])

const CACHE_TTL = 600

const ENDPOINT = '/api/customer-portal/workspaces/{slug}' as const

export const hasBillingPermission = (
  authenticatedUser: PortalUser,
): boolean => {
  if (!authenticatedUser) return false
  if (authenticatedUser.type === 'customer') return true
  return BILLING_ROLES.has(authenticatedUser.role as string)
}

const buildRedirectPath = (
  slug: string,
  searchParams?: Record<string, string>,
): string => {
  const qs = new URLSearchParams(searchParams).toString()
  return `/${slug}/portal/request?${qs}`
}

const statusHandlers = (
  slug: string,
  searchParams?: Record<string, string>,
) => ({
  404: notFound,
  429: () => redirect('/too-many-requests'),
  401: () => redirect(buildRedirectPath(slug, searchParams)),
})

const _getWorkspaceOrNotFound = async (
  api: Client,
  slug: string,
  searchParams?: Record<string, string>,
): Promise<schemas['CustomerWorkspaceData']> =>
  resolveResponse(
    api.GET(ENDPOINT, {
      params: { path: { slug } },
      next: {
        revalidate: CACHE_TTL,
        tags: [`workspaces:${slug}`],
      },
    }),
    statusHandlers(slug, searchParams),
  )

export const getWorkspaceOrNotFound = cache(_getWorkspaceOrNotFound)
