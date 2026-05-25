/**
 * Scene outline — turns the flat element list into a tree the user
 * can navigate from a side panel. Frames become collapsible groups
 * with their child elements indented underneath; everything not
 * owned by a frame sits at the root.
 *
 * Pure / renderer-agnostic. The React panel in
 * ``components/Collab/Whiteboard/OutlinePanel.tsx`` consumes this
 * shape; the click-to-select / jump path is wired in
 * ``CollabWhiteboard.tsx``.
 */

import type {
  CollabElement,
  EmbedElement,
  FrameElement,
  StickyElement,
  TextElement,
} from './elements'

export interface OutlineNode {
  /** Element id this row represents. */
  id: string
  /** Discriminator the panel uses to pick an icon. */
  kind: CollabElement['type']
  /** Human-readable label — text content, frame name, sticky text,
   *  or a fallback like ``Rectangle``. Capped at ~60 chars. */
  label: string
  /** Mirrors the element's ``hidden`` flag so the panel can render
   *  the eye toggle without re-reading the store. */
  hidden: boolean
  /** Mirrors the element's ``locked`` flag so the panel can render
   *  the lock toggle without re-reading the store. */
  locked: boolean
  /** Children when the node represents a frame; empty otherwise. */
  children: OutlineNode[]
}

const LABEL_MAX = 60

/** Build the outline tree. Frames hoist to root; their declared
 *  ``childIds`` become children. Elements not in any frame's
 *  ``childIds`` are placed at the root in their reading order
 *  (top-down, left-right of centre). */
export function buildSceneOutline(elements: CollabElement[]): OutlineNode[] {
  const byId = new Map<string, CollabElement>()
  for (const el of elements) byId.set(el.id, el)

  const claimed = new Set<string>()
  const frames: FrameElement[] = []
  for (const el of elements) {
    if (el.type === 'frame') {
      frames.push(el)
      for (const childId of el.childIds) claimed.add(childId)
    }
  }

  const orphans = elements.filter(
    (el) => el.type !== 'frame' && !claimed.has(el.id),
  )

  // Sort frames + orphans by reading order (top-down, left-right of
  // centre) so the outline reflects the visual layout. Frames and
  // orphans interleave at the root.
  const root: Array<{ el: CollabElement; node: OutlineNode }> = []
  for (const f of frames) {
    root.push({
      el: f,
      node: {
        id: f.id,
        kind: 'frame',
        label: clampLabel(f.name || 'Frame'),
        hidden: f.hidden === true,
        locked: f.locked === true,
        children: f.childIds
          .map((id) => byId.get(id))
          .filter((c): c is CollabElement => c !== undefined)
          .map((c) => toLeafNode(c)),
      },
    })
  }
  for (const o of orphans) {
    root.push({ el: o, node: toLeafNode(o) })
  }
  root.sort((a, b) => readingOrder(a.el, b.el))
  return root.map((r) => r.node)
}

function toLeafNode(el: CollabElement): OutlineNode {
  return {
    id: el.id,
    kind: el.type,
    label: clampLabel(displayLabel(el)),
    hidden: el.hidden === true,
    locked: el.locked === true,
    children: [],
  }
}

function displayLabel(el: CollabElement): string {
  // Explicit ``BaseElement.name`` wins over the type-derived
  // fallback so a renamed shape shows the user-chosen label.
  const explicit = (el as { name?: string }).name
  if (explicit && explicit.trim().length > 0 && el.type !== 'frame') {
    return explicit.trim()
  }
  switch (el.type) {
    case 'text':
      return (el as TextElement).text || 'Text'
    case 'sticky':
      return (el as StickyElement).text || 'Sticky note'
    case 'embed':
      return (el as EmbedElement).url || 'Embed'
    case 'frame':
      return (el as FrameElement).name || 'Frame'
    case 'rect':
      return 'Rectangle'
    case 'ellipse':
      return 'Ellipse'
    case 'diamond':
      return 'Diamond'
    case 'arrow':
      return 'Arrow'
    case 'line':
      return 'Line'
    case 'freedraw':
      return 'Drawing'
    case 'image':
      return 'Image'
    case 'pdf-underlay':
      return 'PDF underlay'
    case 'image-underlay':
      return 'Image underlay'
  }
}

function clampLabel(s: string): string {
  // Strip newlines so long sticky notes don't blow out the row.
  const flat = s.replace(/\s+/g, ' ').trim()
  if (flat.length <= LABEL_MAX) return flat
  return flat.slice(0, LABEL_MAX - 1) + '…'
}

function readingOrder(a: CollabElement, b: CollabElement): number {
  const ay = a.y + a.height / 2
  const by = b.y + b.height / 2
  if (ay !== by) return ay - by
  const ax = a.x + a.width / 2
  const bx = b.x + b.width / 2
  return ax - bx
}
