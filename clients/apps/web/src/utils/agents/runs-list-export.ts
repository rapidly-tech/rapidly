/**
 * CSV export for the workflow detail's Recent runs section
 * (the summary rows, not per-step results — per-step lives in
 * ``run-export.ts``).
 *
 * Operators triaging a flaky workflow want to share or analyze
 * a chunk of recent run history with stakeholders; the row
 * shape mirrors the per-eval ``eval-runs-export.ts`` shape so
 * the two CSVs stack neatly side-by-side.
 */

import type { Run } from '@/hooks/api/agents'

import { csvEscape } from './eval-export'

const CSV_HEADERS = [
  'id',
  'status',
  'triggered_by_kind',
  'triggered_by_id',
  'started_at',
  'completed_at',
  'duration_ms',
  'error_message',
] as const

export function buildRunsCsv(runs: Run[]): string {
  const rows = runs.map((r) => [
    r.id,
    r.status,
    r.triggered_by_kind,
    r.triggered_by_id ?? '',
    r.started_at ?? '',
    r.completed_at ?? '',
    durationMs(r.started_at, r.completed_at),
    r.error_message ?? '',
  ])
  return [CSV_HEADERS, ...rows]
    .map((row) => row.map(csvEscape).join(','))
    .join('\n')
}

/** Integer ms diff; ``""`` when either endpoint is null or
 *  unparsable. Matches the ``duration_ms`` column on the
 *  per-step CSV (run-export.ts) and the per-eval CSV
 *  (eval-runs-export.ts). */
function durationMs(
  startedIso: string | null,
  completedIso: string | null,
): string {
  if (!startedIso || !completedIso) return ''
  const start = Date.parse(startedIso)
  const end = Date.parse(completedIso)
  if (Number.isNaN(start) || Number.isNaN(end)) return ''
  return String(Math.max(0, end - start))
}
