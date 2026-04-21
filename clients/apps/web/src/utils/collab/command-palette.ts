/**
 * Command palette — a keyboard-first action launcher for the Collab
 * v2 whiteboard.
 *
 * The module owns:
 *  - ``Command`` — the shape every command registers in (id, label,
 *    run, optional keywords, optional shortcut hint).
 *  - ``matchCommands`` — pure fuzzy filter used by the palette UI.
 *    Takes a query and a command list, returns the subset sorted by
 *    relevance (prefix > word-start > contains). Deterministic and
 *    test-friendly.
 *  - No UI: ``components/Collab/dev/CommandPalette.tsx`` renders the
 *    modal on top of this data layer.
 *
 * Design notes
 * ------------
 * Why a tiny custom matcher instead of a fuzzy-match library?
 * Commands are a short list (~20–50) so an O(n) scan is free, and
 * the palette's correctness hinges on predictable ranking — a pure
 * function is easier to test than a black-box library.
 */

export interface Command {
  id: string
  /** Human-readable name shown in the palette. */
  label: string
  /** Action to run when the user picks the command. Async-safe. */
  run: () => void | Promise<void>
  /** Extra search terms so ""paste image"" finds a command labelled
   *  ""Paste from clipboard"", etc. */
  keywords?: readonly string[]
  /** Optional category shown as a small tag in the palette. */
  category?: string
  /** Optional key-combo hint shown on the right-hand side, e.g.
   *  ``['Mod', 'K']``. Follows the same ``Mod`` convention as
   *  ``shortcuts.ts``. */
  shortcut?: readonly string[]
}

/** Filter + rank commands by how well they match ``query``. An empty
 *  query returns the full list untouched so the palette shows all
 *  commands on first open. */
export function matchCommands(
  query: string,
  commands: readonly Command[],
): Command[] {
  const q = query.trim().toLowerCase()
  if (q === '') return [...commands]

  type Scored = { cmd: Command; score: number }
  const scored: Scored[] = []

  for (const cmd of commands) {
    const score = scoreCommand(q, cmd)
    if (score > 0) scored.push({ cmd, score })
  }

  // Stable by score desc, then by original order (lower index first).
  scored.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score
    return commands.indexOf(a.cmd) - commands.indexOf(b.cmd)
  })

  return scored.map((s) => s.cmd)
}

/** Score one command against a lowercased query. Ranking:
 *    100 — label starts with query
 *     70 — word in label starts with query
 *     40 — label contains query
 *     20 — any keyword contains query
 *      0 — no match (caller drops). */
function scoreCommand(q: string, cmd: Command): number {
  const label = cmd.label.toLowerCase()
  if (label.startsWith(q)) return 100
  for (const word of label.split(/\s+/)) {
    if (word.startsWith(q)) return 70
  }
  if (label.includes(q)) return 40
  if (cmd.keywords) {
    for (const kw of cmd.keywords) {
      if (kw.toLowerCase().includes(q)) return 20
    }
  }
  return 0
}

/** Narrow a list of commands to a unique ``id`` set. Guards against
 *  duplicates when consumers compose multiple command sources (e.g.
 *  tool keys + export actions + custom project commands). */
export function dedupeCommands(commands: readonly Command[]): Command[] {
  const seen = new Set<string>()
  const out: Command[] = []
  for (const c of commands) {
    if (seen.has(c.id)) continue
    seen.add(c.id)
    out.push(c)
  }
  return out
}
