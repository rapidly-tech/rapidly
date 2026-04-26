/**
 * Hand / pan tool.
 *
 * Click-drag pans the viewport. The tool doesn't touch the store —
 * it calls ``renderer.setViewport`` directly.
 */

import { panByScreen, type Viewport } from '../viewport'
import type { Tool } from './types'

interface PanState {
  startX: number
  startY: number
  startVP: Viewport
}

let panState: PanState | null = null

export const handTool: Tool = {
  id: 'hand',
  cursor: 'grab',

  onPointerDown(ctx, e) {
    panState = {
      startX: e.clientX,
      startY: e.clientY,
      startVP: ctx.renderer.getViewport(),
    }
  },

  onPointerMove(ctx, e) {
    if (!panState) return
    const next = panByScreen(
      panState.startVP,
      e.clientX - panState.startX,
      e.clientY - panState.startY,
    )
    ctx.renderer.setViewport(next)
  },

  onPointerUp() {
    panState = null
  },

  onCancel() {
    panState = null
  },
}
