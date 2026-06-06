import { DocsSidebar } from '@/components/Docs/DocsSidebar'
import { DocsToc } from '@/components/Docs/DocsToc'
import { PropsWithChildren } from 'react'

// Docs render inside the landing shell — desktop nav, mobile topbar,
// and footer come from the (landing) layout, same as /about and
// /features. This layout adds the docs chrome: section sidebar on the
// left, "On this page" rail on the right.
export default function DocsLayout({ children }: PropsWithChildren) {
  return (
    <div className="mx-auto flex w-full max-w-7xl grow gap-10 px-0 py-8 md:px-8 md:pt-28">
      <aside className="sticky top-28 hidden h-[calc(100dvh-8rem)] w-56 shrink-0 overflow-y-auto md:block">
        <DocsSidebar />
      </aside>
      <article className="docs-article prose prose-slate dark:prose-invert max-w-3xl min-w-0 grow">
        {children}
      </article>
      <aside className="sticky top-28 hidden h-[calc(100dvh-8rem)] w-52 shrink-0 overflow-y-auto xl:block">
        <DocsToc />
      </aside>
    </div>
  )
}
