/**
 * Public tool registry.
 *
 * Consumers pick one by id and dispatch pointer events through the
 * shared ``Tool`` interface. Keeping the registry here (not in a
 * React hook) lets server-rendered pages import it and it keeps
 * tests framework-agnostic.
 */

import { arrowTool } from './arrow'
import { diamondTool } from './diamond'
import { ellipseTool } from './ellipse'
import { eraserTool } from './eraser'
import { freedrawTool } from './freedraw'
import { handTool } from './hand'
import { lineTool } from './line'
import { rectTool } from './rect'
import { selectTool } from './select'
import { stickyTool } from './sticky'
import { textTool } from './text'
import type { Tool, ToolId } from './types'

const TOOLS: Partial<Record<ToolId, Tool>> = {
  hand: handTool,
  select: selectTool,
  rect: rectTool,
  ellipse: ellipseTool,
  diamond: diamondTool,
  line: lineTool,
  arrow: arrowTool,
  freedraw: freedrawTool,
  text: textTool,
  sticky: stickyTool,
  eraser: eraserTool,
}

export function toolFor(id: ToolId): Tool | null {
  return TOOLS[id] ?? null
}

export { currentMarqueeRect, currentSnapGuides, hoverCursor } from './select'
export type { SelectToolCtx } from './select'
export type { Tool, ToolCtx, ToolId } from './types'
export {
  arrowTool,
  diamondTool,
  ellipseTool,
  eraserTool,
  freedrawTool,
  handTool,
  lineTool,
  rectTool,
  selectTool,
  stickyTool,
  textTool,
}
