/**
 * Tool system for the Collab v2 whiteboard.
 *
 * Every interactive behaviour (pan, rect, ellipse, freedraw, arrow,
 * eraser, select, …) is a ``Tool``. The canvas component dispatches
 * pointer events to the active tool; the tool mutates the ``ElementStore``
 * and/or the local selection state through ``ToolCtx``. Tools never
 * touch the canvas directly — the renderer repaints on store observes.
 *
 * Design decisions
 * ----------------
 * - **No re-entrancy.** A pointer-down picks the active tool for that
 *   gesture. Subsequent pointer-moves and pointer-up go to the same
 *   tool even if the user flips the tool picker mid-drag.
 * - **Local UI state lives on the tool**, not in the store. A half-
 *   drawn rect's current size belongs to the rect tool's private
 *   state until pointer-up commits it.
 * - **ToolCtx is a value object.** The canvas builds a fresh ctx for
 *   each gesture so tools can't accidentally retain stale references
 *   across renderer swaps.
 */

import type { ElementStore } from '../element-store'
import type { Renderer } from '../renderer'
import type { Viewport } from '../viewport'

export type ToolId =
  | 'hand'
  | 'select'
  | 'rect'
  | 'ellipse'
  | 'diamond'
  | 'arrow'
  | 'line'
  | 'freedraw'
  | 'text'
  | 'sticky'
  | 'eraser'

export interface ToolCtx {
  readonly store: ElementStore
  readonly renderer: Renderer
  /** Current viewport at the start of the gesture. Tools that need the
   *  *live* viewport (e.g. a hand tool that updates it) should call
   *  ``renderer.getViewport()`` — this field is a snapshot. */
  readonly viewport: Viewport
  /** Convert a screen-space point (canvas-local CSS pixels) to world
   *  coords using the current viewport. */
  screenToWorld(screenX: number, screenY: number): { x: number; y: number }
  /** Force a repaint (e.g. after a tool updates its private preview). */
  invalidate(): void
}

export interface Tool {
  readonly id: ToolId
  /** CSS cursor token shown on the canvas while this tool is active. */
  readonly cursor: string
  onPointerDown(ctx: ToolCtx, e: PointerEvent): void
  onPointerMove(ctx: ToolCtx, e: PointerEvent): void
  onPointerUp(ctx: ToolCtx, e: PointerEvent): void
  onKeyDown?(ctx: ToolCtx, e: KeyboardEvent): void
  /** Called when the user switches tools mid-gesture, presses Escape,
   *  or navigates away. Tools should discard any in-progress preview
   *  and leave the store untouched. */
  onCancel?(ctx: ToolCtx): void
}
