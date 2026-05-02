'use client'

import LogoIcon from '@/components/Brand/LogoIcon'
import Footer from '@/components/Workspace/Footer'
import { useAuth } from '@/hooks/auth'
import { WorkspaceContext } from '@/providers/workspaceContext'
import { setLastVisitedOrg } from '@/utils/cookies'
import { schemas } from '@rapidly-tech/client'
import {
  SidebarTrigger,
  useSidebar,
} from '@rapidly-tech/ui/components/navigation/Sidebar'
import {
  Tabs,
  TabsList,
  TabsTrigger,
} from '@rapidly-tech/ui/components/navigation/Tabs'
import { motion } from 'framer-motion'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  PropsWithChildren,
  useContext,
  useEffect,
  useState,
  type JSX,
} from 'react'
import { twMerge } from 'tailwind-merge'
import { SubRouteWithActive } from '../Dashboard/navigation'
import { useRoute } from '../Navigation/useRoute'
import { DashboardSidebar } from './Dashboard/DashboardSidebar'
import TopbarRight from './Public/TopbarRight'

// ── Main Layout ──

/** Top-level dashboard shell with responsive sidebar, mobile navigation, and content area with optional context panel. */
const DashboardLayout = (
  props: PropsWithChildren<{
    type?: 'workspace' | 'account'
    className?: string
    isImpersonating?: boolean
  }>,
) => {
  const { workspace, workspaces } = useContext(WorkspaceContext)

  useEffect(() => {
    if (workspace) {
      setLastVisitedOrg(workspace.slug)
    }
  }, [workspace])

  return (
    <div className="relative flex h-full w-full flex-col md:flex-row md:pt-2 md:pb-2 md:pl-2">
      <MobileNav
        workspace={workspace}
        workspaces={workspaces ?? []}
        type={props.type}
        isImpersonating={props.isImpersonating}
      />
      <div className="hidden md:flex">
        <DashboardSidebar
          workspace={workspace}
          workspaces={workspaces ?? []}
          type={props.type}
          isImpersonating={props.isImpersonating}
        />
      </div>
      <div
        className={twMerge(
          'relative flex h-full w-full flex-col',
          props.className,
        )}
      >
        {/* On large devices, scroll here. On small devices the _document_ is the only element that should scroll. */}
        <main className="relative flex min-h-0 min-w-0 grow flex-col md:overflow-y-auto md:[scrollbar-gutter:stable]">
          {props.children}
          <Footer />
        </main>
      </div>
    </div>
  )
}

export default DashboardLayout

// ── MobileNav Sub-component ──

const MobileNav = ({
  type = 'workspace',
  workspace,
  workspaces,
  isImpersonating,
}: {
  type?: 'workspace' | 'account'
  workspace?: schemas['Workspace']
  workspaces: schemas['Workspace'][]
  isImpersonating?: boolean
}) => {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const pathname = usePathname()
  const { currentUser } = useAuth()

  useEffect(() => {
    setMobileNavOpen(false)
  }, [pathname])

  const header = (
    <div className="sticky top-0 right-0 left-0 flex w-full flex-row items-center justify-between border-b border-white/[0.08] bg-white/[0.06] p-4 backdrop-blur-2xl backdrop-saturate-150 dark:border-white/[0.06] dark:bg-white/[0.04]">
      <Link
        href="/"
        className="rp-text-primary shrink-0 items-center font-semibold"
      >
        <LogoIcon className="h-10 w-10" />
      </Link>

      <div className="flex flex-row items-center gap-x-6">
        <TopbarRight authenticatedUser={currentUser} />
        <SidebarTrigger />
      </div>
    </div>
  )

  return (
    <div className="relative z-20 flex w-screen flex-col items-center justify-between bg-white/[0.06] backdrop-blur-2xl backdrop-saturate-150 md:hidden dark:bg-white/[0.04]">
      {mobileNavOpen ? (
        <div className="relative flex h-full w-full flex-col">
          {header}
          <div className="flex h-full flex-col px-4">
            <DashboardSidebar
              workspace={workspace}
              workspaces={workspaces}
              type={type}
              isImpersonating={isImpersonating}
            />
          </div>
        </div>
      ) : (
        header
      )}
    </div>
  )
}

// ── SubNav Sub-component ──

const SubNav = (props: { items: SubRouteWithActive[] }) => {
  const current = props.items.find((i) => i.isActive)

  return (
    <Tabs value={current?.title ?? props.items[0]?.title ?? ''}>
      <TabsList className="flex flex-row bg-transparent ring-0 dark:bg-transparent dark:ring-0">
        {props.items.map((item) => {
          return (
            <Link key={item.title} href={item.link} prefetch={true}>
              <TabsTrigger
                className="flex flex-row items-center gap-x-2 px-4"
                value={item.title}
              >
                <h3>{item.title}</h3>
              </TabsTrigger>
            </Link>
          )
        })}
      </TabsList>
    </Tabs>
  )
}

// ── DashboardBody Component ──

export interface DashboardBodyProps {
  children?: React.ReactNode
  className?: string
  wrapperClassName?: string
  title?: JSX.Element | string | null
  contextView?: React.ReactNode
  contextViewClassName?: string
  contextViewPlacement?: 'left' | 'right'
  header?: JSX.Element
  wide?: boolean
}

export const DashboardBody = ({
  children,
  className,
  wrapperClassName,
  title,
  contextView,
  contextViewClassName,
  contextViewPlacement = 'right',
  header,
  wide = false,
}: DashboardBodyProps) => {
  const { currentRoute, currentSubRoute } = useRoute()

  const { state } = useSidebar()

  const isCollapsed = state === 'collapsed'

  const current = currentSubRoute ?? currentRoute

  const parsedTitle = title ?? current?.title

  return (
    <motion.div
      className={twMerge(
        'flex h-full w-full flex-row gap-x-2',
        contextViewPlacement === 'left' ? 'flex-row-reverse' : '',
      )}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      <div className="relative flex min-w-0 flex-2 flex-col items-center px-4 md:px-8">
        <div
          className={twMerge(
            'flex h-full w-full flex-col gap-8 pt-8',
            wrapperClassName,
            wide ? '' : 'max-w-(--breakpoint-xl)',
          )}
        >
          {(title !== null || !!header) && (
            <div className="flex flex-col gap-y-4 md:flex-row md:items-center md:justify-between md:gap-x-4">
              {title !== null &&
                (!title || typeof parsedTitle === 'string' ? (
                  currentRoute?.link ? (
                    <Link href={currentRoute.link}>
                      <h4 className="rp-text-primary text-2xl font-medium whitespace-nowrap transition-opacity hover:opacity-70">
                        {title ?? current?.title}
                      </h4>
                    </Link>
                  ) : (
                    <h4 className="rp-text-primary text-2xl font-medium whitespace-nowrap">
                      {title ?? current?.title}
                    </h4>
                  )
                ) : (
                  parsedTitle
                ))}

              {isCollapsed && currentRoute && 'subs' in currentRoute ? (
                <SubNav items={currentRoute.subs ?? []} />
              ) : null}
              {header ?? null}
            </div>
          )}

          <motion.div
            className={twMerge('flex w-full flex-col pb-8', className)}
            variants={{
              initial: { opacity: 0 },
              animate: { opacity: 1, transition: { duration: 0.3 } },
              exit: { opacity: 0, transition: { duration: 0.3 } },
            }}
          >
            {children}
          </motion.div>
        </div>
      </div>
      {contextView ? (
        <motion.div
          variants={{
            initial: { opacity: 0 },
            animate: { opacity: 1, transition: { duration: 0.3 } },
            exit: { opacity: 0, transition: { duration: 0.3 } },
          }}
          className={twMerge(
            'w-full flex-1 overflow-y-auto md:max-w-[320px] xl:max-w-[440px]',
            contextViewClassName,
          )}
        >
          {contextView}
        </motion.div>
      ) : null}
    </motion.div>
  )
}
