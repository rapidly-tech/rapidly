'use client'

/**
 * Inline text-edit overlay (Phase 7b).
 *
 * Mounts a ``<textarea>`` absolutely positioned over the canvas at
 * the target text element's transformed rect. We avoid
 * ``contenteditable`` here because a plain textarea has saner IME +
 * browser undo behaviour out of the box; a future richer editor
 * (mixed fonts, bullets) can swap it for a ProseMirror / Slate
 * surface without disturbing the glue code.
 *
 * Lifecycle
 * ---------
 *  - Mount: read the element, size the textarea to match, focus +
 *    select the existing text so typing replaces placeholder content.
 *  - Edit: on every input, measure against a hidden canvas context
 *    and write (text, width, height) back to the store. The renderer
 *    observes + repaints; the static-canvas glyphs render underneath
 *    the live textarea which paints in front.
 *  - Commit: blur / Enter-without-shift / Esc. Empty text after
 *    commit → delete the element to keep the doc clean.
 *
 * The component is meant for the dev page today. Once production
 * Collab wires v2 in, this same component can move into the chamber
 * client with zero logic change.
 */

import { useEffect, useLayoutEffect, useRef, useState } from 'react'

import type { ElementStore } from '@/utils/collab/element-store'
import {
  type CollabElement,
  type FontFamily,
  type TextAlign,
} from '@/utils/collab/elements'
import type { Renderer } from '@/utils/collab/renderer'
import { fontCssFor, measureText } from '@/utils/collab/shapes/text'
import { requestEdit } from '@/utils/collab/text-editing'

/** The editor works with any element type that has ``text`` + font
 *  fields. Text and Sticky both qualify; future typed shapes with
 *  text (flowchart nodes?) can opt in by carrying the same fields. */
function isEditable(el: CollabElement | null): el is CollabElement & {
  text: string
  fontFamily: FontFamily
  fontSize: number
  textAlign: TextAlign
} {
  return el?.type === 'text' || el?.type === 'sticky'
}

interface TextEditorProps {
  id: string
  store: ElementStore
  renderer: Renderer
  /** Called after the edit commits (whether the element was kept or
   *  deleted). The host should clear its ``editingId`` state. */
  onDone: () => void
}

/** Draft state stored locally until commit. Keeping the string in
 *  local state + writing it to the store on every input means the
 *  textarea's own undo stack matches the Yjs updates one-for-one. */
export function TextEditor({ id, store, renderer, onDone }: TextEditorProps) {
  const taRef = useRef<HTMLTextAreaElement | null>(null)
  const measureCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const [draft, setDraft] = useState<string>(() => {
    const el = store.get(id)
    return isEditable(el) ? el.text : ''
  })

  // Focus + select-all on mount so typing replaces the placeholder.
  useLayoutEffect(() => {
    const ta = taRef.current
    if (!ta) return
    ta.focus({ preventScroll: true })
    ta.select()
  }, [])

  // Reposition on every render — cheap; the host re-renders us
  // whenever the store/viewport invalidates.
  useEffect(() => {
    // Intentionally empty — positioning is captured in render via
    // the live viewport read below.
  })

  const element = store.get(id)
  if (!isEditable(element)) {
    // Element was deleted out from under us — close on the next tick
    // so we don't setState during render.
    void queueMicrotask(onDone)
    return null
  }
  const textEl = element

  // Commit helper — writes the final draft (or deletes an empty
  // element) and unmounts via onDone.
  const commit = () => {
    const trimmed = draft.trim()
    if (trimmed.length === 0) {
      store.delete(id)
    } else {
      store.update(id, { text: draft })
    }
    requestEdit(null)
    onDone()
  }

  const cancel = () => {
    // If the element was just created and the user types nothing,
    // it's less surprising to drop it than to leave an empty textbox
    // hanging around.
    if (textEl.text.length === 0 && draft.length === 0) {
      store.delete(id)
    }
    requestEdit(null)
    onDone()
  }

  // Update store on every keystroke so other peers see the text grow
  // live (matches Excalidraw's "watch me type" feel). Text elements
  // auto-resize to the string; stickies keep their fixed size and
  // let the wrapper inside ``shapes/sticky.ts`` word-wrap.
  const onInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const next = e.target.value
    setDraft(next)

    if (textEl.type === 'sticky') {
      store.update(id, { text: next })
      return
    }

    const measureCanvas =
      measureCanvasRef.current ??
      (measureCanvasRef.current = document.createElement('canvas'))
    const mctx = measureCanvas.getContext('2d')
    const size = mctx
      ? measureText(mctx, next, textEl.fontFamily, textEl.fontSize)
      : { width: textEl.width, height: textEl.height }
    store.update(id, {
      text: next,
      width: size.width,
      height: size.height,
    })
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      commit()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      cancel()
    }
    // Keyboard events inside the textarea should not bubble to the
    // window-level Delete / Backspace handler that clears selection.
    e.stopPropagation()
  }

  // Screen-space placement + sizing. The renderer's viewport drives
  // where the textarea lands and how big it is.
  const vp = renderer.getViewport()
  const screenLeft = (textEl.x - vp.scrollX) * vp.scale
  const screenTop = (textEl.y - vp.scrollY) * vp.scale
  const screenWidth = textEl.width * vp.scale
  const screenHeight = textEl.height * vp.scale
  const screenFontSize = textEl.fontSize * vp.scale

  return (
    <textarea
      ref={taRef}
      value={draft}
      onChange={onInput}
      onKeyDown={onKeyDown}
      onBlur={commit}
      spellCheck={false}
      style={{
        position: 'absolute',
        left: `${screenLeft}px`,
        top: `${screenTop}px`,
        width: `${Math.max(screenWidth, 40)}px`,
        height: `${Math.max(screenHeight, screenFontSize * 1.4)}px`,
        fontFamily: fontCssFor(textEl.fontFamily as FontFamily),
        fontSize: `${screenFontSize}px`,
        textAlign: textEl.textAlign as TextAlign,
        color: textEl.strokeColor,
        opacity: textEl.opacity / 100,
        background: 'transparent',
        border: '1px dashed #4f46e5',
        outline: 'none',
        resize: 'none',
        padding: 0,
        margin: 0,
        lineHeight: 1.2,
        overflow: 'hidden',
        zIndex: 10,
        whiteSpace: 'pre',
      }}
      aria-label="Text element editor"
    />
  )
}
