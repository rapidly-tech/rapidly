'use client'

import LogoIcon from '@/components/Brand/LogoIcon'
import LogoType from '@/components/Brand/LogoType'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { twMerge } from 'tailwind-merge'

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

  // Use plain <a> when linking to the current page (forces full reload to reset state).
  // Use Next.js <Link> otherwise for fast client-side navigation.
  const isSamePage = pathname === href

  return (
    <div className={twMerge('relative flex flex-row items-center', className)}>
      {isSamePage ? (
        <a href={href} aria-label="Rapidly home">
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
