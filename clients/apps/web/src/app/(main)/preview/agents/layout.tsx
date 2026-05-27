'use client'

/**
 * Shared layout for every Agents chamber page.
 *
 * Renders a fixed-position sidebar with the chamber's top-level
 * sections (workflows, datasets, eval runs, credentials) and lets
 * each page own its own ``<main>``. The active section is keyed
 * off the path — we don't hand each page an "isActive" prop
 * because that would force every page to import the layout's
 * route map.
 *
 * Why /preview-only for now:
 *    The chamber's UI is still incomplete. Operators landing
 *    here from a shared link should see a consistent shell; the
 *    sidebar's links stay under /preview until the chamber
 *    promotes out of staging.
 */

import { cn } from '@rapidly-tech/ui/lib/utils'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

interface SidebarItem {
  href: string
  label: string
  matchPrefixes: string[]
}

const NAV: SidebarItem[] = [
  {
    href: '/preview/agents/workflows',
    label: 'Workflows',
    matchPrefixes: ['/preview/agents/workflows'],
  },
  {
    href: '/preview/agents/datasets',
    label: 'Datasets',
    matchPrefixes: ['/preview/agents/datasets'],
  },
  {
    href: '/preview/agents/eval-runs',
    label: 'Eval runs',
    matchPrefixes: ['/preview/agents/eval-runs'],
  },
  {
    href: '/preview/agents/vector-collections',
    label: 'Collections',
    matchPrefixes: ['/preview/agents/vector-collections'],
  },
  {
    href: '/preview/agents/credentials',
    label: 'Credentials',
    matchPrefixes: ['/preview/agents/credentials'],
  },
  {
    href: '/preview/agents/usage',
    label: 'Usage',
    matchPrefixes: ['/preview/agents/usage'],
  },
]

export default function AgentsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const pathname = usePathname()

  return (
    <div className="flex min-h-screen w-full bg-slate-50 dark:bg-slate-950">
      <aside className="hidden w-56 shrink-0 flex-col gap-1 border-r border-slate-200 bg-white px-3 py-8 sm:flex dark:border-slate-800 dark:bg-slate-900">
        <Link
          href="/preview/agents/workflows"
          className="mb-4 px-3 text-xs font-semibold tracking-wider text-emerald-600 uppercase dark:text-emerald-400"
        >
          Agents
        </Link>
        <nav className="flex flex-col gap-0.5">
          {NAV.map((item) => {
            const active = item.matchPrefixes.some((p) =>
              pathname.startsWith(p),
            )
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'rounded-md px-3 py-2 text-sm transition',
                  active
                    ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
                    : 'text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800',
                )}
              >
                {item.label}
              </Link>
            )
          })}
        </nav>
        <div className="mt-auto px-3 text-xs text-slate-400 dark:text-slate-500">
          Preview · in development
        </div>
      </aside>

      {/* Mobile-only top nav — sidebar hides under sm. */}
      <nav className="fixed top-0 z-10 flex w-full overflow-x-auto border-b border-slate-200 bg-white sm:hidden dark:border-slate-800 dark:bg-slate-900">
        {NAV.map((item) => {
          const active = item.matchPrefixes.some((p) => pathname.startsWith(p))
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'shrink-0 px-3 py-3 text-xs whitespace-nowrap transition',
                active
                  ? 'border-b-2 border-emerald-600 text-emerald-700 dark:text-emerald-300'
                  : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200',
              )}
            >
              {item.label}
            </Link>
          )
        })}
      </nav>

      <div className="flex-1 pt-12 sm:pt-0">{children}</div>
    </div>
  )
}
