/**
 * Single-key tool-activation shortcuts.
 *
 * Letter bindings:
 *
 *   H → hand     V → select    R → rect     O → ellipse
 *   D → diamond  L → line      A → arrow    P → freedraw
 *   T → text     S → sticky    E → eraser
 *
 * Number aliases for users who prefer the home-row digits:
 *
 *   1 → select   2 → rect      3 → diamond  4 → ellipse
 *   5 → arrow    6 → line      7 → freedraw 8 → text     0 → eraser
 *
 * Extracted as a pure map so the demo's keyboard handler, the
 * ``useCollabRoom`` hook, and a future command-palette all share one
 * source of truth. Adding a tool means one row here, no logic
 * changes in the consumers.
 */

import type { ToolId } from './tools'

export const TOOL_KEY_MAP: Readonly<Record<string, ToolId>> = {
  h: 'hand',
  v: 'select',
  q: 'lasso',
  r: 'rect',
  o: 'ellipse',
  d: 'diamond',
  l: 'line',
  a: 'arrow',
  p: 'freedraw',
  t: 'text',
  s: 'sticky',
  e: 'eraser',
  '1': 'select',
  '2': 'rect',
  '3': 'diamond',
  '4': 'ellipse',
  '5': 'arrow',
  '6': 'line',
  '7': 'freedraw',
  '8': 'text',
  '0': 'eraser',
}

/** Resolve a ``KeyboardEvent`` to a ``ToolId``. Returns ``null`` when
 *  the key has no binding, when any modifier is pressed (so Cmd+D
 *  still duplicates, Cmd+L is free for a future shortcut), or when
 *  the focus target is a form input — typing a letter into the text
 *  editor must not swap the tool.
 *
 *  Shift is allowed for letters that happen to be typed with it so
 *  e.g. holding shift while hitting ``R`` still activates the rect
 *  tool. Upper-case variants are normalised via ``toLowerCase``. */
export function toolIdForKey(e: {
  key: string
  metaKey?: boolean
  ctrlKey?: boolean
  altKey?: boolean
  shiftKey?: boolean
  target?: EventTarget | null
}): ToolId | null {
  if (e.metaKey || e.ctrlKey || e.altKey) return null
  // Shift+digit prints punctuation on most layouts (e.g. Shift+1 = '!')
  // so we'd never hit a number-key tool with shift held; we filter
  // it explicitly so Shift+1/2/3 stay free for zoom shortcuts.
  if (e.shiftKey && /^\d$/.test(e.key)) return null
  if (typeof e.key !== 'string' || e.key.length !== 1) return null
  const target = e.target as HTMLElement | null
  if (
    target &&
    (target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.isContentEditable)
  ) {
    return null
  }
  return TOOL_KEY_MAP[e.key.toLowerCase()] ?? null
}
