/**
 * Sticky-note placement tool.
 *
 * Click creates a fixed-size sticky with a default yellow fill and
 * an empty text body; the text editor overlay opens immediately via
 * the edit broker. Matches the text tool's UX, just with a visible
 * background so the note reads as a "post-it" rather than free text.
 */

import {
  DEFAULT_FONT_FAMILY,
  DEFAULT_FONT_SIZE,
  DEFAULT_TEXT_ALIGN,
} from '../elements'
import { requestEdit } from '../text-editing'
import type { Tool, ToolCtx } from './types'

const STICKY_SIZE = 160
const STICKY_FILL = '#fef3c7'

export const stickyTool: Tool = {
  id: 'sticky',
  cursor: 'crosshair',

  onPointerDown(ctx, e) {
    const { x, y } = worldPoint(ctx, e)
    const id = ctx.store.create({
      type: 'sticky',
      x,
      y,
      width: STICKY_SIZE,
      height: STICKY_SIZE,
      fillColor: STICKY_FILL,
      fillStyle: 'solid',
      text: '',
      fontFamily: DEFAULT_FONT_FAMILY,
      fontSize: DEFAULT_FONT_SIZE,
      textAlign: DEFAULT_TEXT_ALIGN,
    })
    requestEdit(id)
  },

  onPointerMove() {},
  onPointerUp() {},
}

function worldPoint(ctx: ToolCtx, e: PointerEvent): { x: number; y: number } {
  const rect = (e.target as HTMLElement).getBoundingClientRect()
  return ctx.screenToWorld(e.clientX - rect.left, e.clientY - rect.top)
}
