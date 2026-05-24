/**
 * Outline-panel filter — narrow the visible tree by substring
 * match against each row's label.
 *
 * Behaviour
 * ---------
 *   - Empty / whitespace-only query → return the tree unchanged.
 *   - Case-insensitive substring match against ``OutlineNode.label``.
 *   - A frame whose label doesn't match but whose children do is
 *     kept (with only the matching children visible) so users can
 *     drill into "Onboarding" by searching a child's name.
 *   - A frame that matches keeps all its children visible — the
 *     match scope is the frame, not the individual rows.
 *
 * Pure / synchronous. The panel runs the filter on every keystroke;
 * the cost is O(N) over the visible tree, which is fine at
 * whiteboard sizes.
 */

import type { OutlineNode } from './scene-outline'

/** Filter the outline tree against ``query``. Returns a new array
 *  of nodes — the original is left untouched so React's reference
 *  equality stays sound for memo'd consumers. */
export function filterOutline(
  tree: readonly OutlineNode[],
  query: string,
): OutlineNode[] {
  const trimmed = query.trim().toLowerCase()
  if (trimmed.length === 0) return tree.slice()
  const out: OutlineNode[] = []
  for (const node of tree) {
    const matched = nodeMatches(node, trimmed)
    if (node.children.length === 0) {
      if (matched) out.push(node)
      continue
    }
    // Frame branch — keep the frame when it matches OR when any
    // descendant does.
    if (matched) {
      // Frame matched as a whole → show its children unfiltered so
      // the user sees what's inside the matched container.
      out.push(node)
      continue
    }
    const matchingChildren = node.children.filter((c) =>
      nodeMatches(c, trimmed),
    )
    if (matchingChildren.length > 0) {
      out.push({ ...node, children: matchingChildren })
    }
  }
  return out
}

function nodeMatches(node: OutlineNode, lowered: string): boolean {
  return node.label.toLowerCase().includes(lowered)
}
