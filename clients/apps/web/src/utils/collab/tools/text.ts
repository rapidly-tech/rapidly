/**
 * Text-placement tool (Phase 7b).
 *
 * Click creates an empty text element at the cursor and fires an edit
 * request through the ``text-editing`` broker. The host component
 * picks up the request, mounts a contenteditable overlay, and lets
 * the user type inline. On blur / Enter / Esc the overlay writes the
 * final string + AABB back to the store.
 *
 * The element is created with an empty ``text`` + placeholder-sized
 * AABB so something exists in the store during the edit. If the user
 * cancels with no typing, the overlay deletes the empty element on
 * teardown to keep the doc clean.
 */

import {
  DEFAULT_FONT_FAMILY,
  DEFAULT_FONT_SIZE,
  DEFAULT_TEXT_ALIGN,
} from '../elements'
import { requestEdit } from '../text-editing'
import type { Tool, ToolCtx } from './types'

/** Placeholder AABB for a just-created text element. The overlay
 *  resizes as the user types; we just need something selectable
 *  if the user cancels without typing. */
const PLACEHOLDER_WIDTH = 200
const PLACEHOLDER_HEIGHT = DEFAULT_FONT_SIZE * 1.2

export const textTool: Tool = {
  id: 'text',
  cursor: 'text',

  onPointerDown(ctx, e) {
    const { x, y } = worldPoint(ctx, e)
    const id = ctx.store.create({
      type: 'text',
      x,
      y,
      width: PLACEHOLDER_WIDTH,
      height: PLACEHOLDER_HEIGHT,
      text: '',
      fontFamily: DEFAULT_FONT_FAMILY,
      fontSize: DEFAULT_FONT_SIZE,
      textAlign: DEFAULT_TEXT_ALIGN,
    })
    requestEdit(id)
  },

  // Single-click tool — dragging shouldn't spawn a trail of editors.
  onPointerMove() {},
  onPointerUp() {},
}

function worldPoint(ctx: ToolCtx, e: PointerEvent): { x: number; y: number } {
  const rect = (e.target as HTMLElement).getBoundingClientRect()
  return ctx.screenToWorld(e.clientX - rect.left, e.clientY - rect.top)
}
