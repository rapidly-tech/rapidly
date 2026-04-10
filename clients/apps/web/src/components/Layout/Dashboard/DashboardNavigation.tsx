'use client'

import { Icon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubItem,
  useSidebar,
} from '@rapidly-tech/ui/components/navigation/Sidebar'
import Link from 'next/link'
import { useMemo } from 'react'
import { twMerge } from 'tailwind-merge'
import {
  SubRouteWithActive,
  useAccountRoutes,
  useGeneralRoutes,
  useWorkspaceRoutes,
} from '../../Dashboard/navigation'

const LINK_BASE =
  'flex flex-row items-center rounded-lg border border-transparent px-2 transition-colors dark:border-transparent'

const ACTIVE_LINK =
  'dark:!bg-slate-950 dark:border-slate-900 border-slate-200 bg-white! rp-text-primary shadow-xs'

const INACTIVE_LINK =
  'text-slate-500 hover:text-foreground dark:hover:text-slate-400'

const ICON_BASE =
  'flex flex-col items-center justify-center overflow-visible rounded-full bg-transparent text-[15px]'

const SUB_LINK_BASE =
  'flex w-full flex-row items-center gap-x-2 rounded-lg border border-transparent px-2 py-1.5 pl-5 text-sm font-medium text-slate-500 transition-colors hover:text-foreground'

const SUB_LINK_ACTIVE =
  'rp-text-primary border-slate-200 bg-white! shadow-xs dark:border-slate-900 dark:!bg-slate-950'

const resolveLinkClasses = (isActive: boolean, isCollapsed: boolean): string =>
  twMerge(
    LINK_BASE,
    isActive ? ACTIVE_LINK : INACTIVE_LINK,
    isCollapsed && 'dark:text-slate-700!',
  )

const resolveIconClasses = (isActive: boolean): string =>
  twMerge(ICON_BASE, isActive ? 'rp-text-primary' : 'bg-transparent')

const RouteIcon = ({
  icon,
  isActive,
}: {
  icon: React.ReactNode
  isActive: boolean
}) => <span className={resolveIconClasses(isActive)}>{icon}</span>

const SubRouteLink = ({ sub }: { sub: SubRouteWithActive }) => (
  <SidebarMenuSubItem key={sub.link}>
    <Link
      href={sub.link}
      prefetch={true}
      className={twMerge(SUB_LINK_BASE, sub.isActive && SUB_LINK_ACTIVE)}
    >
      {sub.title}
      {sub.extra}
    </Link>
  </SidebarMenuSubItem>
)

const NavigationItem = ({
  route,
  isCollapsed,
}: {
  route: SubRouteWithActive & {
    subs?: SubRouteWithActive[]
    icon?: React.ReactNode
  }
  isCollapsed: boolean
}) => {
  const hasSubs = route.subs && route.subs.length > 0
  const showParentHighlight = route.isActive && !hasSubs
  const linkClasses = useMemo(
    () => resolveLinkClasses(showParentHighlight, isCollapsed),
    [showParentHighlight, isCollapsed],
  )
  const hasIcon = 'icon' in route && Boolean(route.icon)

  return (
    <SidebarMenuItem key={route.link}>
      <SidebarMenuButton
        tooltip={route.title}
        asChild
        isActive={showParentHighlight}
      >
        <Link
          key={route.link}
          prefetch={true}
          className={linkClasses}
          href={route.link}
        >
          {hasIcon ? (
            <RouteIcon icon={route.icon} isActive={route.isActive} />
          ) : undefined}
          <span className="ml-2 text-sm font-medium">{route.title}</span>
        </Link>
      </SidebarMenuButton>
      {route.isActive && route.subs && (
        <SidebarMenuSub className="my-2 ml-6 gap-y-1 border-l-0 px-0">
          {route.subs.map((sub: SubRouteWithActive) => (
            <SubRouteLink key={sub.link} sub={sub} />
          ))}
        </SidebarMenuSub>
      )}
    </SidebarMenuItem>
  )
}

export const WorkspaceNavigation = ({
  workspace,
}: {
  workspace: schemas['Workspace']
}) => {
  const generalRoutesList = useGeneralRoutes(workspace)
  const workspaceRoutes = useWorkspaceRoutes(workspace)
  const { state } = useSidebar()

  const isCollapsed = state === 'collapsed'

  const dashboardRoutes = useMemo(
    () => [...generalRoutesList, ...workspaceRoutes],
    [generalRoutesList, workspaceRoutes],
  )

  return (
    <SidebarMenu>
      {dashboardRoutes.map((route) => (
        <NavigationItem
          key={route.link}
          route={route}
          isCollapsed={isCollapsed}
        />
      ))}
    </SidebarMenu>
  )
}

const BACK_LINK_CLASSES =
  'flex flex-row items-center gap-4 border border-transparent rp-text-primary'

export const AccountNavigation = () => {
  const accountRoutes = useAccountRoutes()
  const { state } = useSidebar()
  const isCollapsed = state === 'collapsed'

  return (
    <SidebarMenu>
      <SidebarMenuItem className="mb-4 flex flex-row items-center gap-2">
        <SidebarMenuButton tooltip="Back to Dashboard" asChild>
          <Link href="/dashboard" className={BACK_LINK_CLASSES}>
            <span className="flex flex-col items-center justify-center overflow-visible rounded-full bg-transparent text-[15px]">
              <Icon icon="solar:arrow-left-linear" className="text-[1em]" />
            </span>
            <span>Account Settings</span>
          </Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
      {accountRoutes.map((route) => (
        <NavigationItem
          key={route.link}
          route={route}
          isCollapsed={isCollapsed}
        />
      ))}
    </SidebarMenu>
  )
}
