'use client'

/**
 * Right-click context menu for the whiteboard canvas. Each item
 * routes to the same callback the keyboard / palette uses, so the
 * three entry points can never drift.
 *
 * Visibility rules
 * ----------------
 *   - When the selection is empty we show only "Paste" (the
 *     destructive items would no-op, and the z-order / rename items
 *     have nothing to act on).
 *   - When at least one element is selected we show the full menu.
 *   - The lock / unlock toggle picks its label by reading the first
 *     selected element's ``locked`` flag.
 *
 * The menu closes on: Esc, click outside, or click on any item.
 */

import { useEffect, useRef } from 'react'

interface MenuItem {
  id: string
  label: string
  /** When ``false`` the item renders disabled (greyed out + no-op
   *  click). Used for items that depend on selection state without
   *  hiding them outright — preserves muscle-memory positioning. */
  enabled?: boolean
  /** Render a thin divider line above this item. */
  divider?: boolean
  onClick?: () => void
}

interface Props {
  /** Menu position in viewport pixels. The portal absolute-positions
   *  itself at ``(x, y)`` and clamps to the viewport edges so a
   *  near-corner right-click doesn't open offscreen. */
  x: number
  y: number
  items: readonly MenuItem[]
  onClose: () => void
}

export function CanvasContextMenu({ x, y, items, onClose }: Props) {
  const ref = useRef<HTMLDivElement | null>(null)

  // Esc closes; click-outside closes; once mounted we autofocus the
  // menu so keyboard users can navigate via Tab without an extra
  // click first.
  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    const onPointer = (e: PointerEvent): void => {
      if (!ref.current) return
      if (!ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onPointer, true)
    queueMicrotask(() => ref.current?.focus())
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onPointer, true)
    }
  }, [onClose])

  // Clamp to viewport so a right-click near the right / bottom edge
  // doesn't open offscreen. Approximate menu size with an estimate
  // (refined post-mount via the rect, but the estimate prevents the
  // first paint from flickering).
  const estW = 200
  const estH = items.length * 28 + 8
  const clampedX = Math.min(x, window.innerWidth - estW - 8)
  const clampedY = Math.min(y, window.innerHeight - estH - 8)

  return (
    <div
      ref={ref}
      role="menu"
      tabIndex={-1}
      onContextMenu={(e) => e.preventDefault()}
      className="fixed z-50 min-w-[12rem] rounded-md border border-slate-200 bg-white py-1 text-sm shadow-lg outline-none dark:border-slate-700 dark:bg-slate-900"
      style={{ left: clampedX, top: clampedY }}
    >
      {items.map((item) => (
        <div key={item.id}>
          {item.divider ? (
            <div className="my-1 border-t border-slate-200 dark:border-slate-700" />
          ) : null}
          <button
            type="button"
            role="menuitem"
            disabled={item.enabled === false}
            onClick={() => {
              if (item.enabled === false) return
              item.onClick?.()
              onClose()
            }}
            className={
              'block w-full px-3 py-1.5 text-left ' +
              (item.enabled === false
                ? 'cursor-not-allowed text-slate-400 dark:text-slate-600'
                : 'text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800')
            }
          >
            {item.label}
          </button>
        </div>
      ))}
    </div>
  )
}
