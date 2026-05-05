'use client'

/**
 * Left-side outline panel — collapsible list of every element on the
 * scene, with frames acting as expandable groups containing their
 * declared children.
 *
 * Click a row to select that element + recentre the viewport on it.
 * The viewport jump uses the same path the scene-search palette
 * uses, just routed through ``onPick`` so the host can wire it
 * however it likes.
 */

import { type ReactElement, useMemo, useState } from 'react'

import type { CollabElement, ElementType } from '@/utils/collab/elements'
import {
  buildSceneOutline,
  type OutlineNode,
} from '@/utils/collab/scene-outline'

interface PickArg {
  elementId: string
  centerX: number
  centerY: number
}

interface Props {
  open: boolean
  elements: CollabElement[]
  /** Currently-selected element ids — rows render with a highlight. */
  selectedIds: ReadonlySet<string>
  onPick: (arg: PickArg) => void
  onClose: () => void
}

const ICONS: Record<ElementType, string> = {
  rect: '▭',
  ellipse: '◯',
  diamond: '◇',
  arrow: '→',
  line: '─',
  freedraw: '✎',
  text: 'T',
  sticky: '✦',
  image: '🖼',
  frame: '▣',
  embed: '▤',
}

export function OutlinePanel({
  open,
  elements,
  selectedIds,
  onPick,
  onClose,
}: Props) {
  const tree = useMemo(() => buildSceneOutline(elements), [elements])
  // Expanded frame ids — frames default open so the user can see
  // their contents at a glance the first time they open the panel.
  const [collapsedFrames, setCollapsedFrames] = useState<ReadonlySet<string>>(
    () => new Set(),
  )

  if (!open) return null

  const toggle = (frameId: string): void => {
    setCollapsedFrames((prev) => {
      const next = new Set(prev)
      if (next.has(frameId)) next.delete(frameId)
      else next.add(frameId)
      return next
    })
  }

  const pickRow = (id: string): void => {
    const el = elements.find((e) => e.id === id)
    if (!el) return
    onPick({
      elementId: id,
      centerX: el.x + el.width / 2,
      centerY: el.y + el.height / 2,
    })
  }

  return (
    <aside
      aria-label="Whiteboard outline"
      className="pointer-events-auto fixed top-20 left-4 z-30 flex max-h-[60vh] w-64 flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-md dark:border-slate-700 dark:bg-slate-900"
    >
      <header className="flex items-center justify-between border-b border-slate-200 px-3 py-2 dark:border-slate-700">
        <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">
          Outline
        </span>
        <button
          type="button"
          onClick={onClose}
          className="rounded text-xs text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
          aria-label="Close outline"
        >
          ×
        </button>
      </header>
      <ul className="overflow-y-auto py-1 text-sm">
        {tree.length === 0 ? (
          <li className="px-3 py-3 text-xs text-slate-500 dark:text-slate-400">
            Nothing on the canvas yet.
          </li>
        ) : (
          tree.map((node) =>
            renderNode(node, 0, {
              collapsedFrames,
              toggle,
              pickRow,
              selectedIds,
            }),
          )
        )}
      </ul>
    </aside>
  )
}

interface RenderCtx {
  collapsedFrames: ReadonlySet<string>
  toggle: (id: string) => void
  pickRow: (id: string) => void
  selectedIds: ReadonlySet<string>
}

function renderNode(
  node: OutlineNode,
  depth: number,
  ctx: RenderCtx,
): ReactElement {
  const isFrame = node.kind === 'frame'
  const isCollapsed = ctx.collapsedFrames.has(node.id)
  const isSelected = ctx.selectedIds.has(node.id)
  const indent = depth * 12 + 8
  return (
    <li key={node.id}>
      <button
        type="button"
        onClick={() => {
          if (isFrame) ctx.toggle(node.id)
          ctx.pickRow(node.id)
        }}
        style={{ paddingLeft: indent }}
        className={
          'flex w-full items-center gap-2 px-3 py-1 text-left text-xs ' +
          (isSelected
            ? 'bg-indigo-50 text-indigo-900 dark:bg-indigo-950/40 dark:text-indigo-100'
            : 'text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800')
        }
      >
        {isFrame ? (
          <span className="inline-block w-3 text-slate-400">
            {isCollapsed ? '▸' : '▾'}
          </span>
        ) : (
          <span className="inline-block w-3" />
        )}
        <span className="inline-block w-4 text-slate-400">
          {ICONS[node.kind]}
        </span>
        <span className="truncate">{node.label}</span>
      </button>
      {isFrame && !isCollapsed
        ? node.children.map((child) => renderNode(child, depth + 1, ctx))
        : null}
    </li>
  )
}
