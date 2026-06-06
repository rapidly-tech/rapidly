'use client'

import { usePathname } from 'next/navigation'
import { useEffect } from 'react'

// Progressive enhancement applied to the rendered article DOM:
// - copy button on every code block
// - copy-link anchor on every slugged heading
// Runs on the client after each docs navigation; everything degrades
// gracefully without JS (plain code blocks, plain headings).
export const DocsArticleEnhancer = () => {
  const pathname = usePathname()

  useEffect(() => {
    const article = document.querySelector('article.docs-article')
    if (!article) return

    // ── Copy buttons on code blocks ──
    const pres = article.querySelectorAll<HTMLPreElement>(
      'pre:not([data-docs-copy])',
    )
    pres.forEach((pre) => {
      pre.dataset.docsCopy = 'true'
      pre.classList.add('group', 'relative')

      const button = document.createElement('button')
      button.type = 'button'
      button.ariaLabel = 'Copy code'
      button.textContent = 'Copy'
      button.className =
        'absolute top-2 right-2 rounded-md border border-slate-700 bg-slate-800/80 px-2 py-1 text-xs text-slate-300 opacity-0 transition-opacity group-hover:opacity-100 hover:text-white'
      button.addEventListener('click', () => {
        navigator.clipboard
          .writeText(pre.querySelector('code')?.innerText ?? pre.innerText)
          .then(() => {
            button.textContent = 'Copied!'
            setTimeout(() => {
              button.textContent = 'Copy'
            }, 1500)
          })
      })
      pre.appendChild(button)
    })

    // ── Copy-link anchors on headings ──
    const headings = article.querySelectorAll<HTMLHeadingElement>(
      'h2[id]:not([data-docs-anchor]), h3[id]:not([data-docs-anchor])',
    )
    headings.forEach((heading) => {
      heading.dataset.docsAnchor = 'true'
      heading.classList.add('group', 'scroll-mt-28')

      const anchor = document.createElement('a')
      anchor.href = `#${heading.id}`
      anchor.ariaLabel = 'Link to this section'
      anchor.textContent = '#'
      anchor.className =
        'ml-2 text-emerald-500 no-underline opacity-0 transition-opacity group-hover:opacity-100'
      heading.appendChild(anchor)
    })
  }, [pathname])

  return null
}
