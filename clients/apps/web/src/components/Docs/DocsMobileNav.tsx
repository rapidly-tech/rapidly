'use client'

import { Icon } from '@iconify/react'
import { usePathname } from 'next/navigation'
import { useEffect, useRef } from 'react'
import { DocsSidebar } from './DocsSidebar'

/** Collapsible section navigation shown above the article on small
 * screens, where the sidebar rail is hidden. Closes on navigation. */
export const DocsMobileNav = () => {
  const pathname = usePathname()
  const ref = useRef<HTMLDetailsElement>(null)

  useEffect(() => {
    if (ref.current) ref.current.open = false
  }, [pathname])

  return (
    <details
      ref={ref}
      className="mb-6 rounded-lg border border-slate-200 md:hidden dark:border-slate-800"
    >
      <summary className="flex cursor-pointer items-center gap-2 px-4 py-3 text-sm font-medium text-slate-900 select-none dark:text-white">
        <Icon icon="solar:hamburger-menu-linear" />
        Browse docs
      </summary>
      <div className="max-h-[60dvh] overflow-y-auto border-t border-slate-200 p-4 dark:border-slate-800">
        <DocsSidebar />
      </div>
    </details>
  )
}
