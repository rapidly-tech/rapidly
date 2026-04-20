/**
 * Public tool registry.
 *
 * Consumers pick one by id and dispatch pointer events through the
 * shared ``Tool`` interface. Keeping the registry here (not in a
 * React hook) lets server-rendered pages import it and it keeps
 * tests framework-agnostic.
 */

import { ellipseTool } from './ellipse'
import { handTool } from './hand'
import { rectTool } from './rect'
import { selectTool } from './select'
import type { Tool, ToolId } from './types'

const TOOLS: Partial<Record<ToolId, Tool>> = {
  hand: handTool,
  select: selectTool,
  rect: rectTool,
  ellipse: ellipseTool,
  // Remaining tools (diamond, arrow, line, freedraw, text, eraser)
  // land in subsequent phases.
}

export function toolFor(id: ToolId): Tool | null {
  return TOOLS[id] ?? null
}

export { currentMarqueeRect, hoverCursor } from './select'
export type { SelectToolCtx } from './select'
export type { Tool, ToolCtx, ToolId } from './types'
export { ellipseTool, handTool, rectTool, selectTool }
