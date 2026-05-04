/**
 * Keyboard shortcut catalogue for the Collab v2 whiteboard.
 *
 * Declarative so the overlay component and a future command-palette
 * search can share one source of truth. The component in
 * ``components/Collab/Whiteboard/ShortcutsOverlay.tsx`` renders this list
 * grouped by category; other consumers can flatten it.
 *
 * Each entry owns:
 *   - ``keys`` — human-readable combos (e.g. ``['⌘', 'K']``). Platform
 *     symbol substitution lives in ``formatKeys``.
 *   - ``description`` — one-line explanation shown to the user.
 *
 * Keep the list stable across platforms by using the canonical ``⌘``
 * / ``Ctrl`` split at render time rather than branching at the data
 * layer. That way the same record is true on every OS.
 */

export interface Shortcut {
  keys: readonly string[]
  description: string
}

export interface ShortcutCategory {
  label: string
  entries: readonly Shortcut[]
}

/** Full shortcut catalogue, ordered roughly by frequency of use so
 *  the overlay reads top-to-bottom for a new user. */
export const SHORTCUT_CATEGORIES: readonly ShortcutCategory[] = [
  {
    label: 'Tools',
    entries: [
      { keys: ['H'], description: 'Hand tool — drag to pan' },
      { keys: ['V'], description: 'Select tool' },
      { keys: ['Q'], description: 'Lasso (free-form area select)' },
      { keys: ['R'], description: 'Rectangle' },
      { keys: ['O'], description: 'Ellipse' },
      { keys: ['D'], description: 'Diamond' },
      { keys: ['L'], description: 'Line' },
      { keys: ['A'], description: 'Arrow' },
      { keys: ['P'], description: 'Pen (freehand)' },
      { keys: ['T'], description: 'Text' },
      { keys: ['S'], description: 'Sticky note' },
      { keys: ['E'], description: 'Eraser — drag over elements to delete' },
      { keys: ['K'], description: 'Toggle laser pointer' },
      { keys: ['1–8 / 0'], description: 'Excalidraw-style number aliases' },
    ],
  },
  {
    label: 'Editing',
    entries: [
      { keys: ['Mod', 'Z'], description: 'Undo' },
      { keys: ['Mod', 'Shift', 'Z'], description: 'Redo' },
      { keys: ['Backspace'], description: 'Delete selected' },
      { keys: ['Esc'], description: 'Cancel gesture / clear selection' },
      { keys: ['Mod', 'A'], description: 'Select all' },
      { keys: ['Mod', 'Shift', 'A'], description: 'Clear selection' },
      { keys: ['Mod', 'C'], description: 'Copy selection' },
      {
        keys: ['Mod', 'V'],
        description: 'Paste (in-app, cross-tab, or OS image)',
      },
      { keys: ['Mod', 'X'], description: 'Cut selection' },
      { keys: ['Mod', 'D'], description: 'Duplicate selection in place' },
      { keys: ['Arrows'], description: 'Nudge selection by 1 unit' },
      { keys: ['Shift', 'Arrows'], description: 'Nudge selection by 10 units' },
      {
        keys: ['Alt', 'drag'],
        description: 'Duplicate selection while dragging',
      },
    ],
  },
  {
    label: 'Structure',
    entries: [
      { keys: ['Mod', 'G'], description: 'Group selection' },
      {
        keys: ['Mod', 'Shift', 'G'],
        description: 'Ungroup (peel outer layer)',
      },
      { keys: ['Mod', ']'], description: 'Bring forward' },
      { keys: ['Mod', 'Shift', ']'], description: 'Bring to front' },
      { keys: ['Mod', '['], description: 'Send backward' },
      { keys: ['Mod', 'Shift', '['], description: 'Send to back' },
      { keys: ['Mod', 'K'], description: 'Set link on selection' },
      {
        keys: ['Mod', 'click'],
        description: 'Open the clicked element s link in a new tab',
      },
      {
        keys: ['Mod', 'L'],
        description: 'Toggle lock (Mod+Shift+L still works)',
      },
      {
        keys: ['Drag', 'rotation handle'],
        description: 'Rotate the selected element around its centre',
      },
      {
        keys: ['Shift', 'rotate'],
        description: 'Snap rotation to 15° increments',
      },
    ],
  },
  {
    label: 'View',
    entries: [
      { keys: ['Scroll'], description: 'Zoom at cursor' },
      { keys: ['Space', 'drag'], description: 'Pan' },
      { keys: ['Mod', '='], description: 'Zoom in' },
      { keys: ['Mod', '-'], description: 'Zoom out' },
      { keys: ['Mod', '0'], description: 'Reset zoom to 100%' },
      { keys: ['Shift', '1'], description: 'Zoom to fit all elements' },
      { keys: ['Shift', '2'], description: 'Zoom to selection (in viewport)' },
      { keys: ['Shift', '3'], description: 'Zoom to selection' },
    ],
  },
  {
    label: 'Collaboration',
    entries: [
      { keys: ['?'], description: 'Show this shortcuts overlay' },
      { keys: ['Mod', 'Shift', 'P'], description: 'Open command palette' },
    ],
  },
]

/** Format a shortcut's keys for display on the current platform.
 *  Replaces the ``Mod`` placeholder with ``⌘`` on macOS and ``Ctrl``
 *  elsewhere so the list reads naturally on every OS without keeping
 *  platform branches in the data. */
export function formatKeys(
  keys: readonly string[],
  platform: 'mac' | 'other' = detectPlatform(),
): string[] {
  return keys.map((k) => {
    if (k === 'Mod') return platform === 'mac' ? '⌘' : 'Ctrl'
    if (k === 'Shift' && platform === 'mac') return '⇧'
    if (k === 'Esc') return 'Esc'
    if (k === 'Backspace') return '⌫'
    return k
  })
}

/** Cheap + sync platform detection — reads ``navigator.platform`` on
 *  web, returns ``'other'`` in SSR. ``formatKeys`` calls this
 *  automatically when no override is passed. */
export function detectPlatform(): 'mac' | 'other' {
  if (typeof navigator === 'undefined') return 'other'
  const p = navigator.platform || ''
  return /Mac|iPhone|iPad/i.test(p) ? 'mac' : 'other'
}

/** Flat list — useful for command-palette style search. */
export function allShortcuts(): Shortcut[] {
  const out: Shortcut[] = []
  for (const cat of SHORTCUT_CATEGORIES) {
    for (const e of cat.entries) out.push(e)
  }
  return out
}
