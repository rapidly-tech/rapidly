'use client'

import { Icon } from '@iconify/react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useMemo } from 'react'
import { docsNav } from './nav'

const flatPages = docsNav.flatMap((section) =>
  section.items.map((item) => ({ ...item, section: section.title })),
)

const useCurrentPage = () => {
  const pathname = usePathname()
  return useMemo(() => {
    const index = flatPages.findIndex((p) => p.href === pathname)
    return {
      current: index === -1 ? null : flatPages[index],
      prev: index > 0 ? flatPages[index - 1] : null,
      next:
        index !== -1 && index < flatPages.length - 1
          ? flatPages[index + 1]
          : null,
    }
  }, [pathname])
}

/** Section › Page breadcrumb rendered above the article title. */
export const DocsBreadcrumbs = () => {
  const { current } = useCurrentPage()
  if (!current) return null

  return (
    <nav
      aria-label="Breadcrumb"
      className="mb-4 flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400"
    >
      <Link
        href="/docs"
        className="transition-colors hover:text-slate-900 dark:hover:text-white"
      >
        Docs
      </Link>
      <Icon icon="solar:alt-arrow-right-linear" className="size-3" />
      <span>{current.section}</span>
      <Icon icon="solar:alt-arrow-right-linear" className="size-3" />
      <span className="text-slate-900 dark:text-white">{current.title}</span>
    </nav>
  )
}

/** Previous / next page links rendered below the article body. */
export const DocsPagination = () => {
  const { current, prev, next } = useCurrentPage()
  if (!current) return null

  return (
    <nav
      aria-label="Docs pagination"
      className="mt-12 flex gap-3 border-t border-slate-200 pt-6 dark:border-slate-800"
    >
      {prev && (
        <Link
          href={prev.href}
          className="flex min-w-0 flex-1 flex-col gap-1 rounded-lg border border-slate-200 p-4 no-underline transition-colors hover:border-emerald-300 dark:border-slate-800 dark:hover:border-emerald-800"
        >
          <span className="text-xs text-slate-500 dark:text-slate-400">
            ← Previous
          </span>
          <span className="truncate font-medium text-slate-900 dark:text-white">
            {prev.title}
          </span>
        </Link>
      )}
      {next && (
        <Link
          href={next.href}
          className="ml-auto flex min-w-0 flex-1 flex-col gap-1 rounded-lg border border-slate-200 p-4 text-right no-underline transition-colors hover:border-emerald-300 dark:border-slate-800 dark:hover:border-emerald-800"
        >
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Next →
          </span>
          <span className="truncate font-medium text-slate-900 dark:text-white">
            {next.title}
          </span>
        </Link>
      )}
    </nav>
  )
}
