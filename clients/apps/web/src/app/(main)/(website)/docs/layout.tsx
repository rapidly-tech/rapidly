import { DocsSidebar } from '@/components/Docs/DocsSidebar'
import { DocsToc } from '@/components/Docs/DocsToc'
import { RapidlyLogotype } from '@/components/Layout/Public/RapidlyLogotype'
import Link from 'next/link'
import { PropsWithChildren } from 'react'

export default function DocsLayout({ children }: PropsWithChildren) {
  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-7xl flex-col px-4 md:px-8">
      <header className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b border-slate-200 bg-white/80 py-4 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
        <div className="flex items-baseline gap-3">
          <RapidlyLogotype logoVariant="logotype" size={90} href="/" />
          <span className="text-sm font-medium text-slate-500 dark:text-slate-400">
            Docs
          </span>
        </div>
        <Link
          href="/dashboard"
          className="text-sm text-slate-500 transition-colors hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
        >
          Dashboard →
        </Link>
      </header>
      <div className="flex grow gap-10 py-8">
        <aside className="sticky top-20 hidden h-[calc(100dvh-7rem)] w-56 shrink-0 overflow-y-auto md:block">
          <DocsSidebar />
        </aside>
        <article className="docs-article prose prose-slate dark:prose-invert max-w-3xl min-w-0 grow">
          {children}
        </article>
        <aside className="sticky top-20 hidden h-[calc(100dvh-7rem)] w-52 shrink-0 overflow-y-auto xl:block">
          <DocsToc />
        </aside>
      </div>
    </div>
  )
}
