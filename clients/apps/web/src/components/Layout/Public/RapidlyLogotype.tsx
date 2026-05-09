'use client'

import LogoIcon from '@/components/Brand/LogoIcon'
import LogoType from '@/components/Brand/LogoType'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { twMerge } from 'tailwind-merge'

/** Same-page logo click broadcasts this. Pages that own resettable
 *  state (e.g. the file-sharing landing) listen and reset in place
 *  without triggering a network round-trip. */
export const LOGO_HOME_RESET_EVENT = 'rapidly:logo-home-reset'

export const RapidlyLogotype = ({
  logoVariant = 'icon',
  size,
  className,
  logoClassName,
  href,
}: {
  logoVariant?: 'icon' | 'logotype'
  size?: number
  className?: string
  logoClassName?: string
  href?: string
}) => {
  const pathname = usePathname()

  const LogoComponent =
    logoVariant === 'logotype' ? (
      <LogoType
        className={twMerge('rp-text-primary -ml-2 md:ml-0', logoClassName)}
        width={size ?? 100}
      />
    ) : (
      <LogoIcon
        className={twMerge('rp-text-primary', logoClassName)}
        size={size ?? 42}
      />
    )

  if (!href) {
    return (
      <div
        className={twMerge('relative flex flex-row items-center', className)}
      >
        {LogoComponent}
      </div>
    )
  }

  const isSamePage = pathname === href

  // Same-page click: broadcast a reset event instead of doing a full
  // browser reload. The full <a href> reload was visibly slow
  // (~800-1500 ms for a logged-in user — middleware /api/users/me
  // round-trip + React re-hydration + client stats fetch). The
  // soft-reset event is instant; pages that need to reset their
  // local state listen for ``LOGO_HOME_RESET_EVENT``.
  const handleSamePageClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault()
    window.dispatchEvent(new Event(LOGO_HOME_RESET_EVENT))
  }

  return (
    <div className={twMerge('relative flex flex-row items-center', className)}>
      {isSamePage ? (
        <a href={href} aria-label="Rapidly home" onClick={handleSamePageClick}>
          {LogoComponent}
        </a>
      ) : (
        <Link href={href} aria-label="Rapidly home">
          {LogoComponent}
        </Link>
      )}
    </div>
  )
}
