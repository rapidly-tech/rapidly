'use client'

import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'
import { twMerge } from 'tailwind-merge'

interface TocEntry {
  id: string
  text: string
  level: number
}

// Builds the "On this page" rail from the rendered article headings.
// Heading ids come from rehype-slug in the shared MDX pipeline.
export const DocsToc = () => {
  const pathname = usePathname()
  const [entries, setEntries] = useState<TocEntry[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)

  useEffect(() => {
    setActiveId(null)
    const headings = Array.from(
      document.querySelectorAll<HTMLHeadingElement>(
        'article.docs-article h2[id], article.docs-article h3[id]',
      ),
    )
    setEntries(
      headings.map((h) => {
        // Read the text without the copy-link anchor that
        // DocsArticleEnhancer appends to each heading.
        const clone = h.cloneNode(true) as HTMLElement
        clone.querySelectorAll('a').forEach((a) => a.remove())
        return {
          id: h.id,
          text: clone.textContent?.trim() ?? '',
          level: h.tagName === 'H2' ? 2 : 3,
        }
      }),
    )

    const observer = new IntersectionObserver(
      (intersections) => {
        const visible = intersections.find((i) => i.isIntersecting)
        if (visible) setActiveId(visible.target.id)
      },
      { rootMargin: '0% 0% -70% 0%' },
    )
    headings.forEach((h) => observer.observe(h))
    return () => observer.disconnect()
  }, [pathname])

  if (entries.length === 0) return null

  return (
    <nav className="flex flex-col gap-1 text-sm" aria-label="On this page">
      <p className="font-medium text-slate-900 dark:text-white">On this page</p>
      {entries.map((entry) => (
        <a
          key={entry.id}
          href={`#${entry.id}`}
          className={twMerge(
            'py-0.5 transition-colors',
            entry.level === 3 && 'pl-3',
            activeId === entry.id
              ? 'font-medium text-slate-900 dark:text-white'
              : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white',
          )}
        >
          {entry.text}
        </a>
      ))}
    </nav>
  )
}
