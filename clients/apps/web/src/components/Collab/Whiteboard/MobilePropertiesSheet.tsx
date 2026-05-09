'use client'

/**
 * Bottom-sheet wrapper around ``PropertiesPanel`` for phone-width
 * viewports.
 *
 * Phase 26c hides the right-hand properties sidebar on phones so the
 * canvas gets full width. This sheet puts the same controls behind a
 * toolbar button — tap opens a slide-up modal, tap the backdrop or
 * Esc closes. One component, one render, no new state machine.
 *
 * Accessibility
 * -------------
 * ``role=""dialog""`` + ``aria-modal`` + ``aria-labelledby`` so screen
 * readers announce it as a modal. Focus moves to the close button on
 * open and restores to the previously-focused element on close —
 * matches ``ShortcutsOverlay`` (Phase 14b).
 */

import { useEffect, useRef, useState } from 'react'

import type { ElementStore } from '@/utils/collab/element-store'
import type { SelectionState } from '@/utils/collab/selection'
import { createSwipeDismiss } from '@/utils/collab/swipe-dismiss'

import { PropertiesPanel } from './PropertiesPanel'

interface Props {
  open: boolean
  store: ElementStore
  selection: SelectionState
  onClose: () => void
}

export function MobilePropertiesSheet({
  open,
  store,
  selection,
  onClose,
}: Props) {
  const closeBtnRef = useRef<HTMLButtonElement | null>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)
  const swipeRef = useRef(createSwipeDismiss())
  const [translateY, setTranslateY] = useState(0)

  useEffect(() => {
    if (!open) return
    previousFocusRef.current = document.activeElement as HTMLElement | null
    closeBtnRef.current?.focus()
    swipeRef.current.reset()
    setTranslateY(0)
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      previousFocusRef.current?.focus?.()
    }
  }, [open, onClose])

  if (!open) return null

  const onGrabPointerDown = (e: React.PointerEvent<HTMLDivElement>): void => {
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    swipeRef.current.onPointerDown(e.clientY, performance.now())
  }
  const onGrabPointerMove = (e: React.PointerEvent<HTMLDivElement>): void => {
    const update = swipeRef.current.onPointerMove(e.clientY, performance.now())
    if (update) setTranslateY(update.translateY)
  }
  const onGrabPointerUp = (e: React.PointerEvent<HTMLDivElement>): void => {
    const target = e.target as HTMLElement
    if (target.hasPointerCapture(e.pointerId)) {
      target.releasePointerCapture(e.pointerId)
    }
    const release = swipeRef.current.onPointerUp(e.clientY, performance.now())
    if (release.dismiss) {
      onClose()
    } else {
      setTranslateY(0)
    }
  }

  return (
    <div
      role="presentation"
      onClick={onClose}
      className="fixed inset-0 z-40 flex items-end justify-center bg-slate-900/40 backdrop-blur-sm md:hidden"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="collab-mobile-properties-title"
        onClick={(e) => e.stopPropagation()}
        style={{
          transform: `translateY(${translateY}px)`,
          transition: translateY === 0 ? 'transform 150ms ease-out' : 'none',
        }}
        className="flex max-h-[75vh] w-full flex-col rounded-t-xl border-t border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900"
      >
        {/* Grab-handle zone — drag down to dismiss. The pill itself is
            visual; the surrounding pad is the actual hit area so a
            finger doesn't need to hit the thin bar. */}
        <div
          onPointerDown={onGrabPointerDown}
          onPointerMove={onGrabPointerMove}
          onPointerUp={onGrabPointerUp}
          onPointerCancel={onGrabPointerUp}
          className="flex cursor-grab touch-none justify-center pt-2 pb-1 active:cursor-grabbing"
        >
          <span className="h-1.5 w-10 rounded-full bg-slate-300 dark:bg-slate-600" />
        </div>
        <div className="flex items-center justify-between px-4 py-2">
          <h2
            id="collab-mobile-properties-title"
            className="text-sm font-semibold text-slate-900 dark:text-slate-100"
          >
            Style
          </h2>
          <button
            ref={closeBtnRef}
            type="button"
            onClick={onClose}
            aria-label="Close style panel"
            className="rounded-md px-2 py-1 text-sm text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
          >
            ✕
          </button>
        </div>
        <div className="overflow-y-auto">
          <PropertiesPanel store={store} selection={selection} />
        </div>
      </div>
    </div>
  )
}
