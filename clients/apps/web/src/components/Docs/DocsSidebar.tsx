'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { twMerge } from 'tailwind-merge'
import { docsNav } from './nav'

export const DocsSidebar = () => {
  const pathname = usePathname()

  return (
    <nav className="flex flex-col gap-6 text-sm" aria-label="Docs">
      {docsNav.map((section) => (
        <div key={section.title} className="flex flex-col gap-1">
          <p className="px-2 font-medium text-slate-900 dark:text-white">
            {section.title}
          </p>
          {section.items.map((item) => {
            const active = pathname === item.href
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? 'page' : undefined}
                className={twMerge(
                  'rounded-md px-2 py-1 transition-colors',
                  active
                    ? 'bg-slate-900/5 font-medium text-slate-900 dark:bg-white/10 dark:text-white'
                    : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white',
                )}
              >
                {item.title}
              </Link>
            )
          })}
        </div>
      ))}
    </nav>
  )
}
