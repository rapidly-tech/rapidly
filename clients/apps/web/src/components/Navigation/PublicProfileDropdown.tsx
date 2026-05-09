'use client'

import { useListWorkspaces } from '@/hooks/api'
import { CONFIG } from '@/utils/config'
import { useOutsideClick } from '@/utils/useOutsideClick'
import { Icon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import Avatar from '@rapidly-tech/ui/components/data/Avatar'
import { Separator } from '@rapidly-tech/ui/components/primitives/separator'
import Link from 'next/link'
import { useCallback, useMemo, useRef, useState } from 'react'
import { twMerge } from 'tailwind-merge'
import { LinkItem, ListItem, Profile } from './Navigation'

const AVATAR_BORDER_CLASSES =
  'dark:border-slate-900 dark:hover:border-slate-800 relative flex shrink-0 cursor-pointer flex-row items-center rounded-full border-2 border-slate-50 shadow-xs transition-colors hover:border-slate-200'

const DROPDOWN_BASE =
  'dark:bg-slate-950 dark:text-slate-400 dark:border-slate-800 absolute z-50 w-[300px] overflow-hidden rounded-3xl bg-white p-2 shadow-xl dark:border'

const resolveDropdownPosition = (anchor?: 'topbar' | 'bottombar'): string =>
  anchor === 'bottombar' ? 'bottom-12 left-0' : 'top-12 right-0'

const DropdownMenu = ({
  user,
  hasWorkspaces,
}: {
  user: schemas['UserRead']
  hasWorkspaces: boolean
}) => (
  <>
    <Link href={`${CONFIG.FRONTEND_BASE_URL}/start`} className="w-full">
      <ListItem current={true}>
        <Profile name={user.email} avatar_url={user.avatar_url} />
      </ListItem>
    </Link>

    <ul className="mt-2 flex w-full flex-col">
      {hasWorkspaces && (
        <LinkItem
          href={`${CONFIG.FRONTEND_BASE_URL}/dashboard`}
          icon={<Icon icon="solar:widget-2-linear" className="text-[1em]" />}
        >
          <span className="mx-2 text-sm">Dashboard</span>
        </LinkItem>
      )}
      <LinkItem
        href={`${CONFIG.FRONTEND_BASE_URL}/dashboard/account`}
        icon={<Icon icon="solar:user-linear" className="text-[1em]" />}
      >
        <span className="mx-2 text-sm">Account</span>
      </LinkItem>

      <Separator className="my-2" />

      <LinkItem
        href={`${CONFIG.BASE_URL}/api/auth/logout`}
        icon={<Icon icon="solar:logout-3-linear" className="h-4 w-4" />}
      >
        <span className="mx-2 py-2">Log out</span>
      </LinkItem>
    </ul>
  </>
)

const PublicProfileDropdown = ({
  className,
  authenticatedUser,
  anchor,
}: {
  className?: string
  authenticatedUser: schemas['UserRead'] | undefined
  anchor?: 'topbar' | 'bottombar'
}) => {
  const containerClassName = useMemo(
    () => twMerge('relative', className),
    [className],
  )
  const [isOpen, setOpen] = useState(false)
  const dropdownRef = useRef(null)

  const closeDropdown = useCallback(() => setOpen(false), [])
  const openDropdown = useCallback(() => setOpen(true), [])

  useOutsideClick([dropdownRef], closeDropdown)

  const workspaces = useListWorkspaces({}, !!authenticatedUser)

  const workspaceCount = workspaces.data?.data.length ?? 0
  const hasWorkspaces = workspaceCount > 0

  if (!authenticatedUser) {
    return <></>
  }

  const dropdownClasses = twMerge(
    DROPDOWN_BASE,
    resolveDropdownPosition(anchor),
  )

  return (
    <div className={containerClassName}>
      <div
        className={AVATAR_BORDER_CLASSES}
        onClick={openDropdown}
        role="button"
        tabIndex={0}
        aria-label="Open profile menu"
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') openDropdown()
        }}
      >
        <Avatar
          className="h-8 w-8"
          name={authenticatedUser.email}
          avatar_url={authenticatedUser.avatar_url}
        />
      </div>

      {isOpen && (
        <div ref={dropdownRef} className={dropdownClasses}>
          <DropdownMenu
            user={authenticatedUser}
            hasWorkspaces={hasWorkspaces}
          />
        </div>
      )}
    </div>
  )
}

export default PublicProfileDropdown
