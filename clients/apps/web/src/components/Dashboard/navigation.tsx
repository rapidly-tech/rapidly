import { RapidlyHog, usePostHog } from '@/hooks/posthog'
import { Icon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import { usePathname } from 'next/navigation'
import { useMemo } from 'react'

// ── Types ──

export type SubRoute = {
  readonly title: string
  readonly link: string
  readonly icon?: React.ReactNode
  readonly if?: boolean | (() => boolean)
  readonly extra?: React.ReactNode
}

export type Route = {
  readonly id: string
  readonly title: string
  readonly icon?: React.ReactElement
  readonly link: string
  readonly if: boolean | undefined
  readonly subs?: SubRoute[]
  readonly selectedExactMatchOnly?: boolean
  readonly selectedMatchFallback?: boolean
  readonly checkIsActive?: (currentPath: string) => boolean
}

export type SubRouteWithActive = SubRoute & { readonly isActive: boolean }

export type RouteWithActive = Route & {
  readonly isActive: boolean
  readonly subs?: SubRouteWithActive[]
}

// ── Active Route Helpers ──

const applySubRouteIsActive = (
  path: string,
  parentRoute?: Route,
): ((r: SubRoute) => SubRouteWithActive) => {
  return (r: SubRoute): SubRouteWithActive => {
    let isActive = r.link === path

    if (!isActive && path.startsWith(r.link)) {
      if (parentRoute?.subs) {
        const hasMoreSpecificMatch = parentRoute.subs.some(
          (sub) =>
            sub !== r && sub.link !== r.link && path.startsWith(sub.link),
        )
        isActive = !hasMoreSpecificMatch
      } else {
        isActive = true
      }
    }

    return {
      ...r,
      isActive,
    }
  }
}

const applyIsActive = (path: string): ((r: Route) => RouteWithActive) => {
  return (r: Route): RouteWithActive => {
    let isActive = false

    if (r.checkIsActive !== undefined) {
      isActive = r.checkIsActive(path)
    } else {
      // Fallback
      isActive = Boolean(path && path.startsWith(r.link))
    }

    const subs = r.subs ? r.subs.map(applySubRouteIsActive(path, r)) : undefined

    return {
      ...r,
      isActive,
      subs,
    }
  }
}

// ── Route Resolution Hook ──

const useResolveRoutes = (
  routesResolver: (
    workspace?: schemas['Workspace'],
    posthog?: RapidlyHog,
  ) => Route[],
  workspace?: schemas['Workspace'],
  allowAll?: boolean,
): RouteWithActive[] => {
  const path = usePathname()
  const posthog = usePostHog()

  return useMemo(() => {
    return (
      routesResolver(workspace, posthog)
        .filter((o) => allowAll || o.if)
        // Filter out child routes if they have an if-function and it evaluates to false
        .map((route) => {
          if (route.subs && Array.isArray(route.subs)) {
            return {
              ...route,
              subs: route.subs.filter(
                (child) =>
                  typeof child.if === 'undefined' ||
                  (typeof child.if === 'function' ? child.if() : child.if),
              ),
            }
          }
          return route
        })
        .map(applyIsActive(path))
    )
  }, [workspace, path, allowAll, routesResolver, posthog])
}

// ── Public Route Hooks ──

export const useDashboardRoutes = (
  workspace?: schemas['Workspace'],
  allowAll?: boolean,
): RouteWithActive[] => {
  return useResolveRoutes((ws) => dashboardRoutesList(ws), workspace, allowAll)
}

export const useGeneralRoutes = (
  workspace?: schemas['Workspace'],
  allowAll?: boolean,
): RouteWithActive[] => {
  return useResolveRoutes((ws) => generalRoutesList(ws), workspace, allowAll)
}

export const useWorkspaceRoutes = (
  workspace?: schemas['Workspace'],
  allowAll?: boolean,
): RouteWithActive[] => {
  return useResolveRoutes(workspaceRoutesList, workspace, allowAll)
}

export const useAccountRoutes = (): RouteWithActive[] => {
  const path = usePathname()
  return useMemo(
    () =>
      accountRoutesList()
        .filter((o) => o.if)
        .map(applyIsActive(path)),
    [path],
  )
}

// ── Route Definitions ──

const generalRoutesList = (workspace?: schemas['Workspace']): Route[] => [
  {
    id: 'home',
    title: 'Overview',
    icon: <Icon icon="solar:widget-2-linear" className="text-[1em]" />,
    link: `/dashboard/${workspace?.slug}`,
    checkIsActive: (currentRoute: string) =>
      currentRoute === `/dashboard/${workspace?.slug}`,
    if: true,
  },
  {
    id: 'send-files',
    title: 'Share Files',
    icon: <Icon icon="solar:share-linear" className="text-[1em]" />,
    link: `/dashboard/${workspace?.slug}/shares/send-files`,
    checkIsActive: (currentRoute: string): boolean =>
      currentRoute.startsWith(`/dashboard/${workspace?.slug}/shares`),
    if: true,
  },
  {
    id: 'my-files',
    title: 'My Files',
    icon: <Icon icon="solar:folder-linear" className="text-[1em]" />,
    link: `/dashboard/${workspace?.slug}/files`,
    checkIsActive: (currentRoute: string): boolean =>
      currentRoute.startsWith(`/dashboard/${workspace?.slug}/files`) ||
      currentRoute.startsWith(`/dashboard/${workspace?.slug}/customers`),
    if: true,
  },
  {
    id: 'analytics',
    title: 'Analytics',
    icon: <Icon icon="solar:chart-2-linear" className="text-[1em]" />,
    link: `/dashboard/${workspace?.slug}/analytics`,
    checkIsActive: (currentRoute: string): boolean =>
      currentRoute.startsWith(`/dashboard/${workspace?.slug}/analytics`),
    if: true,
  },
]

const dashboardRoutesList = (workspace?: schemas['Workspace']): Route[] => [
  ...accountRoutesList(),
  ...generalRoutesList(workspace),
  ...workspaceRoutesList(workspace),
]

const accountRoutesList = (): Route[] => [
  {
    id: 'preferences',
    title: 'Preferences',
    link: `/dashboard/account/preferences`,
    icon: <Icon icon="solar:tuning-2-linear" className="h-5 w-5 text-[1em]" />,
    if: true,
    subs: undefined,
  },
  {
    id: 'developer',
    title: 'Developer',
    link: `/dashboard/account/developer`,
    icon: <Icon icon="solar:code-linear" className="text-[1em]" />,
    if: true,
  },
]

const financeSubRoutesList = (workspace?: schemas['Workspace']): SubRoute[] => [
  {
    title: 'Overview',
    link: `/dashboard/${workspace?.slug}/finance/income`,
  },
  {
    title: 'Payouts',
    link: `/dashboard/${workspace?.slug}/finance/payouts`,
  },
  {
    title: 'Account',
    link: `/dashboard/${workspace?.slug}/finance/account`,
  },
]

const workspaceRoutesList = (workspace?: schemas['Workspace']): Route[] => [
  {
    id: 'finance',
    title: 'Finance',
    link: `/dashboard/${workspace?.slug}/finance/income`,
    icon: (
      <Icon icon="solar:dollar-minimalistic-linear" className="text-[1em]" />
    ),
    checkIsActive: (currentRoute: string): boolean =>
      currentRoute.startsWith(`/dashboard/${workspace?.slug}/finance`),
    if: true,
    subs: financeSubRoutesList(workspace),
  },
  {
    id: 'settings',
    title: 'Settings',
    link: `/dashboard/${workspace?.slug}/settings`,
    icon: <Icon icon="solar:tuning-2-linear" className="text-[1em]" />,
    checkIsActive: (currentRoute: string): boolean =>
      currentRoute.startsWith(`/dashboard/${workspace?.slug}/settings`),
    if: true,
    subs: [
      {
        title: 'General',
        link: `/dashboard/${workspace?.slug}/settings`,
      },
      {
        title: 'Account',
        link: `/dashboard/${workspace?.slug}/settings/account`,
      },
      {
        title: 'Developers',
        link: `/dashboard/${workspace?.slug}/settings/developers`,
      },
      {
        title: 'Members',
        link: `/dashboard/${workspace?.slug}/settings/members`,
      },
      {
        title: 'Webhooks',
        link: `/dashboard/${workspace?.slug}/settings/webhooks`,
      },
    ],
  },
]
