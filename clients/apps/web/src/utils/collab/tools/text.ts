/**
 * Text-placement tool (Phase 7a).
 *
 * Click creates a new text element at the cursor with a ``prompt()``
 * fallback for the actual string. Hacky by design — Phase 7b
 * replaces the prompt with an inline contenteditable overlay.
 *
 * Why ship it like this now: a text adapter that renders but has no
 * tool to create elements is half a feature; ``prompt`` gets the
 * round-trip working end-to-end (element → store → renderer) before
 * the editor UI lands.
 */

import {
  DEFAULT_FONT_FAMILY,
  DEFAULT_FONT_SIZE,
  DEFAULT_TEXT_ALIGN,
} from '../elements'
import { measureText } from '../shapes/text'
import type { Tool, ToolCtx } from './types'

export const textTool: Tool = {
  id: 'text',
  cursor: 'text',

  onPointerDown(ctx, e) {
    const { x, y } = worldPoint(ctx, e)
    const text = promptForText()
    if (!text) return

    // Measure against a detached 2D context so we get the same font
    // metrics the renderer will use.
    const canvas =
      typeof document !== 'undefined' ? document.createElement('canvas') : null
    const measureCtx = canvas?.getContext('2d') ?? null
    let size = { width: 200, height: DEFAULT_FONT_SIZE * 1.2 }
    if (measureCtx) {
      size = measureText(
        measureCtx,
        text,
        DEFAULT_FONT_FAMILY,
        DEFAULT_FONT_SIZE,
      )
    }

    ctx.store.create({
      type: 'text',
      x,
      y,
      width: size.width,
      height: size.height,
      text,
      fontFamily: DEFAULT_FONT_FAMILY,
      fontSize: DEFAULT_FONT_SIZE,
      textAlign: DEFAULT_TEXT_ALIGN,
    })
  },

  // The text tool is single-click only — no drag semantics. We
  // deliberately no-op pointerMove/pointerUp so dragging across the
  // canvas doesn't spawn a trail of prompts.
  onPointerMove() {},
  onPointerUp() {},
}

function worldPoint(ctx: ToolCtx, e: PointerEvent): { x: number; y: number } {
  const rect = (e.target as HTMLElement).getBoundingClientRect()
  return ctx.screenToWorld(e.clientX - rect.left, e.clientY - rect.top)
}

function promptForText(): string | null {
  if (typeof window === 'undefined' || typeof window.prompt !== 'function') {
    return null
  }
  const v = window.prompt('Text:')
  if (v === null) return null
  const trimmed = v.trim()
  return trimmed.length === 0 ? null : v
}
