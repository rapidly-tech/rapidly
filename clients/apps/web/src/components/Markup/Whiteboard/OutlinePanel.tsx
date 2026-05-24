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

import type { CollabElement, ElementType } from '@/utils/markup/elements'
import { filterOutline } from '@/utils/markup/outline-filter'
import {
  buildSceneOutline,
  type OutlineNode,
} from '@/utils/markup/scene-outline'

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
  /** Toggle visibility on a single element. The panel's eye button
   *  fires this — the host wires it through ``setHidden``. */
  onToggleHidden: (id: string) => void
  /** Toggle the lock flag on a single element. */
  onToggleLocked: (id: string) => void
  /** Bump z-index by ±1 — host wires through ``bringForward`` /
   *  ``sendBackward``. */
  onBringForward: (id: string) => void
  onSendBackward: (id: string) => void
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
  'pdf-underlay': '📄',
}

export function OutlinePanel({
  open,
  elements,
  selectedIds,
  onPick,
  onToggleHidden,
  onToggleLocked,
  onBringForward,
  onSendBackward,
  onClose,
}: Props) {
  const tree = useMemo(() => buildSceneOutline(elements), [elements])
  // Expanded frame ids — frames default open so the user can see
  // their contents at a glance the first time they open the panel.
  const [collapsedFrames, setCollapsedFrames] = useState<ReadonlySet<string>>(
    () => new Set(),
  )
  // Substring filter — narrows the visible rows by matching each
  // node's label. Empty / whitespace-only query disables the
  // filter (renders the full tree).
  const [filter, setFilter] = useState('')
  const visibleTree = useMemo(() => filterOutline(tree, filter), [tree, filter])

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
      <div className="border-b border-slate-200 px-2 py-1.5 dark:border-slate-700">
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter…"
          aria-label="Filter outline"
          className="w-full rounded border border-slate-200 bg-transparent px-2 py-1 text-xs text-slate-700 outline-none placeholder:text-slate-400 focus:border-indigo-500 dark:border-slate-700 dark:text-slate-200 dark:placeholder:text-slate-500"
        />
      </div>
      <ul className="overflow-y-auto py-1 text-sm">
        {visibleTree.length === 0 ? (
          <li className="px-3 py-3 text-xs text-slate-500 dark:text-slate-400">
            {tree.length === 0 ? 'Nothing on the canvas yet.' : 'No matches.'}
          </li>
        ) : (
          visibleTree.map((node) =>
            renderNode(node, 0, {
              collapsedFrames,
              toggle,
              pickRow,
              selectedIds,
              onToggleHidden,
              onToggleLocked,
              onBringForward,
              onSendBackward,
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
  onToggleHidden: (id: string) => void
  onToggleLocked: (id: string) => void
  onBringForward: (id: string) => void
  onSendBackward: (id: string) => void
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
    <li key={node.id} className="group/row flex items-stretch">
      <button
        type="button"
        onClick={() => {
          if (isFrame) ctx.toggle(node.id)
          ctx.pickRow(node.id)
        }}
        style={{ paddingLeft: indent }}
        className={
          'flex flex-1 items-center gap-2 px-3 py-1 text-left text-xs ' +
          (node.hidden ? 'opacity-50 ' : '') +
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
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          ctx.onSendBackward(node.id)
        }}
        aria-label="Send backward"
        title="Send backward"
        className="px-1 text-xs text-slate-400 opacity-0 group-hover/row:opacity-100 hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-300"
      >
        ↓
      </button>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          ctx.onBringForward(node.id)
        }}
        aria-label="Bring forward"
        title="Bring forward"
        className="px-1 text-xs text-slate-400 opacity-0 group-hover/row:opacity-100 hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-300"
      >
        ↑
      </button>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          ctx.onToggleLocked(node.id)
        }}
        aria-label={node.locked ? 'Unlock element' : 'Lock element'}
        title={node.locked ? 'Unlock element' : 'Lock element'}
        className={
          'px-1 text-xs text-slate-400 hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-300 ' +
          (node.locked ? '' : 'opacity-0 group-hover/row:opacity-100')
        }
      >
        {node.locked ? '🔒' : '🔓'}
      </button>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          ctx.onToggleHidden(node.id)
        }}
        aria-label={node.hidden ? 'Show element' : 'Hide element'}
        title={node.hidden ? 'Show element' : 'Hide element'}
        className={
          'px-2 text-xs text-slate-400 hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-300 ' +
          // Always-visible when hidden so the user can find their way
          // back; otherwise only-on-row-hover so the panel stays
          // visually quiet.
          (node.hidden ? '' : 'opacity-0 group-hover/row:opacity-100')
        }
      >
        {node.hidden ? '∅' : '◉'}
      </button>
      {isFrame && !isCollapsed
        ? node.children.map((child) => renderNode(child, depth + 1, ctx))
        : null}
    </li>
  )
}
