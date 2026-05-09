// ── Imports ──

import { NotificationsPopover } from '@/components/Notifications/NotificationsPopover'
import { OmniSearch } from '@/components/Search/OmniSearch'
import { toast } from '@/components/Toast/use-toast'
import { useCreateWorkspace } from '@/hooks/api'
import { CONFIG } from '@/utils/config'
import { ROUTES } from '@/utils/routes'
import { Icon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import Avatar from '@rapidly-tech/ui/components/data/Avatar'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Input from '@rapidly-tech/ui/components/forms/Input'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
  useSidebar,
} from '@rapidly-tech/ui/components/navigation/Sidebar'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@rapidly-tech/ui/components/primitives/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@rapidly-tech/ui/components/primitives/dropdown-menu'
import { Separator } from '@rapidly-tech/ui/components/primitives/separator'
import { useTheme } from 'next-themes'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useCallback, useEffect, useState } from 'react'
import { twMerge } from 'tailwind-merge'
import { RapidlyLogotype } from '../Public/RapidlyLogotype'
import { AccountNavigation, WorkspaceNavigation } from './DashboardNavigation'

// ── Main Component ──

/** Collapsible dashboard sidebar with navigation, workspace switcher, search trigger, and quick org creation. */
export const DashboardSidebar = ({
  type = 'workspace',
  workspace,
  workspaces,
  isImpersonating = false,
}: {
  type?: 'workspace' | 'account'
  workspace?: schemas['Workspace']
  workspaces: schemas['Workspace'][]
  isImpersonating?: boolean
}) => {
  const router = useRouter()
  const { state } = useSidebar()
  const { theme, setTheme, resolvedTheme } = useTheme()

  const toggleTheme = useCallback(() => {
    // Cycle: system → light → dark → system
    if (theme === 'system') setTheme('light')
    else if (theme === 'light') setTheme('dark')
    else setTheme('system')
  }, [theme, setTheme])

  const isCollapsed = state === 'collapsed'
  const [searchOpen, setSearchOpen] = useState(false)
  const [createOrgOpen, setCreateOrgOpen] = useState(false)
  const [orgName, setOrgName] = useState('')

  const createWorkspace = useCreateWorkspace()

  const navigateToWorkspace = (org: schemas['Workspace']) => {
    router.push(`/dashboard/${org.slug}`)
  }

  // ── Workspace Creation ──

  const handleCreateWorkspace = useCallback(() => {
    const trimmed = orgName.trim()
    if (trimmed.length < 3) return

    const slug = trimmed
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')

    if (slug.length < 3) {
      toast({
        title: 'Invalid name',
        description: 'Name must contain at least 3 alphanumeric characters.',
      })
      return
    }

    createWorkspace.mutate(
      { name: trimmed, slug, default_presentment_currency: 'usd' },
      {
        onSuccess: (result) => {
          if (result.data) {
            setCreateOrgOpen(false)
            setOrgName('')
            router.push(`/dashboard/${result.data.slug}`)
          }
          if (result.error) {
            const errorBody = result.error as {
              detail?: string | Array<{ msg?: string }>
            }
            const detail = Array.isArray(errorBody?.detail)
              ? errorBody.detail[0]?.msg
              : errorBody?.detail
            toast({
              title: 'Failed to create workspace',
              description:
                detail ?? 'The name may already be taken. Try a different one.',
            })
          }
        },
      },
    )
  }, [createWorkspace, router, orgName])

  // ── Keyboard Shortcuts ──

  const isTopBannerVisible = CONFIG.IS_SANDBOX || isImpersonating

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setSearchOpen(true)
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  // ── Render ──

  return (
    <Sidebar variant="inset" collapsible="icon">
      <SidebarHeader
        className={twMerge(
          'flex flex-row items-center justify-between group-data-[collapsible=icon]:flex-row group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:justify-between group-data-[collapsible=icon]:gap-y-4 md:pt-3.5 group-data-[collapsible=icon]:md:flex-col group-data-[collapsible=icon]:md:items-start group-data-[collapsible=icon]:md:justify-start',
          isTopBannerVisible ? 'md:pt-10' : '',
        )}
      >
        <RapidlyLogotype
          size={32}
          href={
            workspace
              ? ROUTES.DASHBOARD.org(workspace.slug)
              : ROUTES.DASHBOARD.ROOT
          }
        />
        <div className="flex flex-row items-center gap-2 group-data-[collapsible=icon]:flex-row group-data-[collapsible=icon]:md:flex-col-reverse">
          <NotificationsPopover />
          <SidebarTrigger />
        </div>
      </SidebarHeader>

      <SidebarContent className="gap-4 px-2 py-4">
        {type === 'workspace' && workspace && (
          <>
            <button
              onClick={() => setSearchOpen(true)}
              className="flex cursor-pointer items-center gap-4 overflow-hidden rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm transition-colors group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-2 hover:bg-slate-50 dark:border-slate-900 dark:bg-slate-950 dark:hover:bg-slate-950"
            >
              <Icon
                icon="solar:magnifer-linear"
                className="shrink-0 text-[1em] text-slate-500 dark:text-slate-400"
              />
              <span className="flex flex-1 items-center gap-4 group-data-[collapsible=icon]:hidden">
                <span className="flex-1 text-left text-slate-500">
                  Search...
                </span>
                <kbd className="pointer-events-none inline-flex h-5 items-center gap-1 rounded border border-slate-200 bg-slate-100 px-1.5 font-mono text-[11px] text-slate-600 select-none dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
                  <span className="text-sm">⌘</span>K
                </kbd>
              </span>
            </button>
            <OmniSearch
              open={searchOpen}
              onOpenChange={setSearchOpen}
              workspace={workspace}
            />
          </>
        )}
        <div className="flex flex-col items-center gap-2">
          {type === 'account' && <AccountNavigation />}
          {type === 'workspace' && workspace && (
            <WorkspaceNavigation workspace={workspace} />
          )}
        </div>
      </SidebarContent>
      <SidebarFooter>
        <button
          onClick={toggleTheme}
          className="hover:text-foreground flex cursor-pointer flex-row items-center overflow-hidden rounded-lg border border-transparent px-2 text-sm text-slate-500 transition-colors dark:border-transparent dark:hover:text-slate-400"
          aria-label="Toggle theme"
        >
          {theme === 'system' ? (
            <Icon icon="solar:monitor-linear" className="shrink-0 text-[1em]" />
          ) : resolvedTheme === 'dark' ? (
            <Icon icon="solar:sun-2-linear" className="shrink-0 text-[1em]" />
          ) : (
            <Icon icon="solar:moon-linear" className="shrink-0 text-[1em]" />
          )}
          <span
            className="ml-4 truncate font-medium group-data-[collapsible=icon]:hidden"
            suppressHydrationWarning
          >
            {theme === 'system'
              ? 'System'
              : theme === 'dark'
                ? 'Dark'
                : 'Light'}
          </span>
        </button>
        <Link
          href="mailto:support@rapidly.tech"
          className="hover:text-foreground flex cursor-pointer flex-row items-center overflow-hidden rounded-lg border border-transparent px-2 text-sm text-slate-500 transition-colors dark:border-transparent dark:hover:text-slate-400"
        >
          <Icon
            icon="solar:question-circle-linear"
            className="shrink-0 text-[1em]"
          />
          <span className="ml-4 truncate font-medium group-data-[collapsible=icon]:hidden">
            Support
          </span>
        </Link>
        <Link
          className="hover:text-foreground flex flex-row items-center overflow-hidden rounded-lg border border-transparent px-2 text-sm text-slate-500 transition-colors dark:border-transparent dark:hover:text-slate-400"
          href={CONFIG.DOCS_BASE_URL}
          target="_blank"
        >
          <Icon
            icon="solar:arrow-right-up-linear"
            className="shrink-0 text-[1em]"
          />
          <span className="ml-4 truncate font-medium group-data-[collapsible=icon]:hidden">
            Documentation
          </span>
        </Link>
        <Separator />
        {type === 'workspace' && workspace && (
          <SidebarMenu>
            <SidebarMenuItem>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <SidebarMenuButton className="group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:p-1!">
                    <Avatar
                      name={workspace.name}
                      avatar_url={workspace.avatar_url}
                      className="h-6 w-6 shrink-0"
                    />
                    <span className="min-w-0 truncate group-data-[collapsible=icon]:hidden">
                      {workspace.name}
                    </span>
                    <Icon
                      icon="solar:alt-arrow-down-linear"
                      className="ml-auto h-4 w-4 group-data-[collapsible=icon]:hidden"
                    />
                  </SidebarMenuButton>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  side="top"
                  align={isCollapsed ? 'start' : 'center'}
                  className="w-(--radix-popper-anchor-width) min-w-[200px]"
                >
                  {workspaces.map((org) => (
                    <DropdownMenuItem
                      key={org.id}
                      className="flex flex-row items-center gap-x-2"
                      onClick={() => navigateToWorkspace(org)}
                    >
                      <Avatar
                        name={org.name}
                        avatar_url={org.avatar_url}
                        className="h-6 w-6"
                      />
                      <span className="min-w-0 truncate">{org.name}</span>
                    </DropdownMenuItem>
                  ))}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => setCreateOrgOpen(true)}>
                    New Workspace
                  </DropdownMenuItem>
                  {!CONFIG.IS_SANDBOX && CONFIG.SANDBOX_URL && (
                    <DropdownMenuItem
                      onClick={() => router.push(`${CONFIG.SANDBOX_URL}/start`)}
                    >
                      Go to Sandbox
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={() =>
                      router.push(`${CONFIG.BASE_URL}/api/auth/logout`)
                    }
                  >
                    Logout
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </SidebarMenuItem>
          </SidebarMenu>
        )}
      </SidebarFooter>

      <Dialog
        open={createOrgOpen}
        onOpenChange={(open) => {
          setCreateOrgOpen(open)
          if (!open) setOrgName('')
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New Workspace</DialogTitle>
            <DialogDescription>
              Create a new workspace to manage separately.
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleCreateWorkspace()
            }}
          >
            <Input
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              placeholder="Workspace name"
              minLength={3}
              autoFocus
            />
            <DialogFooter className="mt-4">
              <Button
                type="submit"
                disabled={
                  orgName.trim().length < 3 || createWorkspace.isPending
                }
                loading={createWorkspace.isPending}
              >
                Create
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Sidebar>
  )
}
