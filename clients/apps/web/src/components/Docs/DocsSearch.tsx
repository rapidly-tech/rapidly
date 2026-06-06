'use client'

import { Icon } from '@iconify/react'
import * as Dialog from '@radix-ui/react-dialog'
import {
  Command,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@rapidly-tech/ui/components/primitives/command'
import { useRouter } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'

interface IndexHeading {
  id: string
  text: string
  level: number
}

interface IndexPage {
  href: string
  title: string
  description: string
  section: string
  headings: IndexHeading[]
  body: string
}

interface DocsSearchResult {
  href: string
  title: string
  subtitle: string
  section: string
  score: number
}

// Client-side search over the build-time docs index
// (src/generated/docs-index.json — regenerate with `pnpm docs:index`).
// Scoring: title match > heading match (deep-links to the anchor) >
// body match (shows an excerpt around the hit).
const searchIndex = (pages: IndexPage[], query: string): DocsSearchResult[] => {
  const q = query.trim().toLowerCase()
  if (!q) return []

  const results: DocsSearchResult[] = []
  for (const page of pages) {
    const titleIdx = page.title.toLowerCase().indexOf(q)
    if (titleIdx !== -1) {
      results.push({
        href: page.href,
        title: page.title,
        subtitle: page.description,
        section: page.section,
        score: titleIdx === 0 ? 100 : 80,
      })
      continue
    }

    const heading = page.headings.find((h) => h.text.toLowerCase().includes(q))
    if (heading) {
      results.push({
        href: `${page.href}#${heading.id}`,
        title: `${page.title} → ${heading.text}`,
        subtitle: page.description,
        section: page.section,
        score: 60,
      })
      continue
    }

    const bodyIdx = page.body.toLowerCase().indexOf(q)
    if (bodyIdx !== -1) {
      const start = Math.max(0, bodyIdx - 40)
      const excerpt =
        (start > 0 ? '…' : '') +
        page.body.slice(start, bodyIdx + q.length + 60).trim() +
        '…'
      results.push({
        href: page.href,
        title: page.title,
        subtitle: excerpt,
        section: page.section,
        score: 30,
      })
    }
  }

  return results.sort((a, b) => b.score - a.score).slice(0, 12)
}

export const DocsSearch = ({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) => {
  const router = useRouter()
  const [query, setQuery] = useState('')
  const [pages, setPages] = useState<IndexPage[]>([])

  // Load the index lazily on first open so it never weighs down the
  // initial docs bundle.
  useEffect(() => {
    if (!open || pages.length > 0) return
    import('@/generated/docs-index.json').then((mod) =>
      setPages(mod.default.pages as IndexPage[]),
    )
  }, [open, pages.length])

  const results = useMemo(() => searchIndex(pages, query), [pages, query])

  const grouped = useMemo(() => {
    const bySection: Record<string, DocsSearchResult[]> = {}
    for (const r of results) {
      ;(bySection[r.section] ??= []).push(r)
    }
    return bySection
  }, [results])

  const handleSelect = (href: string) => {
    router.push(href)
    onOpenChange(false)
    setQuery('')
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 fixed inset-0 z-50 bg-black/50" />
        <Dialog.Content className="data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 fixed top-[15%] left-[50%] z-50 w-full max-w-2xl translate-x-[-50%] overflow-hidden rounded-xl border border-slate-200/80 bg-white p-0 shadow-2xl ring-1 ring-black/5 dark:border-slate-900/80 dark:bg-slate-950 dark:ring-white/5">
          <Dialog.DialogTitle className="sr-only">
            Search docs
          </Dialog.DialogTitle>
          <Command
            className="**:[[cmdk-group-heading]]:text-xxs rounded-xl border-none **:[[cmdk-group-heading]]:px-0 **:[[cmdk-group-heading]]:py-2 **:[[cmdk-group-heading]]:font-medium **:[[cmdk-group-heading]]:tracking-wider **:[[cmdk-group-heading]]:text-slate-500! **:[[cmdk-group-heading]]:uppercase dark:**:[[cmdk-group-heading]]:text-slate-400! **:[[cmdk-group]]:px-3 **:[[cmdk-input]]:h-14 **:[[cmdk-item]]:px-2 **:[[cmdk-item]]:py-3"
            shouldFilter={false}
          >
            <div className="flex grow items-center px-4">
              <CommandInput
                placeholder="Search docs..."
                value={query}
                onValueChange={setQuery}
                wrapperClassName="border-none grow"
                className="flex w-full grow border-0 text-base placeholder:text-slate-400 focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0 dark:placeholder:text-slate-500"
              />
            </div>
            <CommandList className="max-h-96 border-t border-slate-100 dark:border-slate-900">
              {query && results.length === 0 && (
                <p className="px-5 py-6 text-sm text-slate-500 dark:text-slate-400">
                  No results for “{query}”
                </p>
              )}
              {Object.entries(grouped).map(([section, items]) => (
                <CommandGroup key={section} heading={section}>
                  {items.map((r) => (
                    <CommandItem
                      key={r.href}
                      value={r.href}
                      onSelect={() => handleSelect(r.href)}
                      className="cursor-pointer"
                    >
                      <Icon
                        icon="solar:document-text-linear"
                        className="shrink-0 text-slate-400"
                      />
                      <div className="min-w-0">
                        <p className="truncate font-medium">{r.title}</p>
                        {r.subtitle && (
                          <p className="truncate text-xs text-slate-500 dark:text-slate-400">
                            {r.subtitle}
                          </p>
                        )}
                      </div>
                    </CommandItem>
                  ))}
                </CommandGroup>
              ))}
            </CommandList>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

/** Sidebar trigger: opens the docs search palette; bound to ⌘K / Ctrl-K. */
export const DocsSearchButton = () => {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setOpen((v) => !v)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex w-full items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500 transition-colors hover:border-emerald-300 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400 dark:hover:border-emerald-800"
      >
        <Icon icon="solar:magnifer-linear" />
        <span className="grow text-left">Search docs…</span>
        <kbd className="rounded border border-slate-200 px-1.5 py-0.5 font-mono text-xs dark:border-slate-700">
          ⌘K
        </kbd>
      </button>
      <DocsSearch open={open} onOpenChange={setOpen} />
    </>
  )
}
