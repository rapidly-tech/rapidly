import { DocsArticleEnhancer } from '@/components/Docs/DocsArticleEnhancer'
import { DocsMobileNav } from '@/components/Docs/DocsMobileNav'
import {
  DocsBreadcrumbs,
  DocsPagination,
} from '@/components/Docs/DocsPageChrome'
import { DocsSearchButton } from '@/components/Docs/DocsSearch'
import { DocsSidebar } from '@/components/Docs/DocsSidebar'
import { DocsToc } from '@/components/Docs/DocsToc'
import { PropsWithChildren } from 'react'

// Docs render inside the landing shell — desktop nav, mobile topbar,
// and footer come from the (landing) layout, same as /about and
// /features. This layout adds the docs chrome: search, section
// sidebar, breadcrumbs, "On this page" rail, prev/next pagination.
export default function DocsLayout({ children }: PropsWithChildren) {
  return (
    <div className="mx-auto flex w-full max-w-7xl grow gap-10 px-0 py-8 md:px-8 md:pt-28">
      <aside className="sticky top-28 hidden h-[calc(100dvh-8rem)] w-56 shrink-0 flex-col gap-4 overflow-y-auto md:flex">
        <DocsSearchButton />
        <DocsSidebar />
      </aside>
      <div className="min-w-0 grow">
        <DocsMobileNav />
        <DocsBreadcrumbs />
        <article className="docs-article prose prose-slate dark:prose-invert max-w-3xl min-w-0">
          {children}
        </article>
        <DocsPagination />
        <DocsArticleEnhancer />
      </div>
      <aside className="sticky top-28 hidden h-[calc(100dvh-8rem)] w-52 shrink-0 overflow-y-auto xl:block">
        <DocsToc />
      </aside>
    </div>
  )
}
