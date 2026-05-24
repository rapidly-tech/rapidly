'use client'

/**
 * Collab editor — textarea bound to ``Y.Text`` (PR 18).
 *
 * The binding is 30 lines of DOM glue: we observe Yjs changes to push
 * them into the textarea, and we intercept native edit events to push
 * them into Yjs. We deliberately avoid ``y-textarea`` / ``y-prosemirror``
 * so nothing gets pulled in that bundles its own CRDT provider.
 *
 * Tradeoff: this implementation uses ``setValue + setSelectionRange``
 * which is "correct but not diff-accurate" — two users typing rapidly
 * can still watch each other's cursors jump. That's OK for v1 because
 * the CRDT resolves correctly at the text layer; the cursor jump is
 * purely a UI nit fixed by a richer binding in a later PR.
 */

import { useEffect, useRef, useState } from 'react'
import type * as Y from 'yjs'

interface CollabEditorProps {
  doc: Y.Doc
  onSelectionChange?: (anchor: number | null) => void
}

export function CollabEditor({ doc, onSelectionChange }: CollabEditorProps) {
  const yText = doc.getText('t')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [value, setValue] = useState<string>(yText.toString())

  // Push remote updates into the textarea. We restore the selection
  // because React re-setting ``value`` collapses the cursor to 0.
  useEffect(() => {
    const observer = () => {
      const next = yText.toString()
      const ta = textareaRef.current
      const selStart = ta?.selectionStart ?? 0
      const selEnd = ta?.selectionEnd ?? 0
      setValue(next)
      // Restore selection after React commits. Queue on the next tick
      // so React has flushed the value assignment.
      queueMicrotask(() => {
        if (!ta) return
        try {
          ta.setSelectionRange(
            Math.min(selStart, next.length),
            Math.min(selEnd, next.length),
          )
        } catch {
          /* selection APIs throw in some headless environments */
        }
      })
    }
    yText.observe(observer)
    // Initial sync in case updates landed before mount.
    setValue(yText.toString())
    return () => {
      yText.unobserve(observer)
    }
  }, [yText])

  function onChange(e: React.ChangeEvent<HTMLTextAreaElement>): void {
    const nextValue = e.target.value
    const prevValue = yText.toString()
    // Compute the smallest (prefix, suffix) diff — not optimal but good
    // enough for keystroke-scale edits and much cheaper than a real
    // structural diff. The Yjs transaction collapses sibling ops.
    let start = 0
    while (
      start < prevValue.length &&
      start < nextValue.length &&
      prevValue[start] === nextValue[start]
    ) {
      start++
    }
    let endPrev = prevValue.length
    let endNext = nextValue.length
    while (
      endPrev > start &&
      endNext > start &&
      prevValue[endPrev - 1] === nextValue[endNext - 1]
    ) {
      endPrev--
      endNext--
    }
    doc.transact(() => {
      if (endPrev > start) yText.delete(start, endPrev - start)
      if (endNext > start) yText.insert(start, nextValue.slice(start, endNext))
    })
  }

  function onSelect(): void {
    const ta = textareaRef.current
    if (!ta) return
    onSelectionChange?.(ta.selectionStart)
  }

  return (
    <textarea
      ref={textareaRef}
      value={value}
      onChange={onChange}
      onSelect={onSelect}
      placeholder="Start typing — every participant sees edits appear in real time…"
      className="rp-text-primary placeholder:rp-text-muted glass-elevated min-h-[400px] w-full resize-y rounded-2xl border border-(--beige-border)/30 bg-white p-4 font-mono text-sm leading-relaxed shadow-xs focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30 focus:outline-none dark:border-white/6 dark:bg-white/3"
      spellCheck={false}
    />
  )
}
