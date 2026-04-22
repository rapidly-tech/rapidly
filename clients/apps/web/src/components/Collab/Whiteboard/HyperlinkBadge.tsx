'use client'

/**
 * Floating hyperlink badge for the Collab v2 demo.
 *
 * When the user selects a single element that carries a ``link``
 * field, this badge pins itself to the element's top-right corner in
 * screen-space and lets them jump to the URL with a click. Using a
 * DOM anchor (instead of painting into the canvas) keeps the
 * affordance accessible — screen readers announce the link and
 * ``rel="noopener noreferrer"`` is enforced by the browser.
 */

import { useEffect, useState } from 'react'

import type { ElementStore } from '@/utils/collab/element-store'
import { hasLink } from '@/utils/collab/hyperlinks'
import type { Renderer } from '@/utils/collab/renderer'
import type { SelectionState } from '@/utils/collab/selection'

interface Props {
  store: ElementStore
  selection: SelectionState
  renderer: Renderer
}

export function HyperlinkBadge({ store, selection, renderer }: Props) {
  const [, tick] = useState(0)

  // Re-run layout whenever the selection, element, or viewport changes.
  useEffect(() => {
    const offSel = selection.subscribe(() => tick((n) => n + 1))
    const offStore = store.observe(() => tick((n) => n + 1))
    return () => {
      offSel()
      offStore()
    }
  }, [store, selection])

  if (selection.size !== 1) return null
  const [id] = selection.snapshot
  const el = store.get(id)
  if (!el || !hasLink(el)) return null

  const vp = renderer.getViewport()
  // Top-right corner in world coords → screen coords.
  const worldX = el.x + el.width
  const worldY = el.y
  const screenX = (worldX - vp.scrollX) * vp.scale
  const screenY = (worldY - vp.scrollY) * vp.scale

  return (
    <a
      href={el.link}
      target="_blank"
      rel="noopener noreferrer"
      title={el.link}
      className="pointer-events-auto absolute flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-indigo-600 shadow-sm hover:text-indigo-800 dark:border-slate-700 dark:bg-slate-900"
      style={{
        // Offset up + right so the badge doesn't sit on top of the
        // resize handle on the same corner.
        left: screenX + 6,
        top: Math.max(0, screenY - 26),
      }}
    >
      <LinkIcon />
      <span className="max-w-[160px] truncate">
        {displayHost(el.link ?? '')}
      </span>
    </a>
  )
}

function displayHost(url: string): string {
  try {
    const parsed = new URL(url)
    if (parsed.protocol === 'mailto:') return parsed.pathname || url
    return parsed.host + (parsed.pathname === '/' ? '' : parsed.pathname)
  } catch {
    return url
  }
}

function LinkIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  )
}
