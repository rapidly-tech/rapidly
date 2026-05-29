/**
 * CSV export for the eval-runs list page (summary rows, not
 * per-case results — for per-case export see ``eval-export.ts``).
 *
 * Operators reporting pass-rate trends upstream want a quick
 * dump of "all the evals on screen" with their pass / fail /
 * error counts and timings; per-case JSON belongs in the
 * per-eval detail export.
 */

import type { EvalRun } from '@/hooks/api/agents'

import { csvEscape } from './eval-export'

const CSV_HEADERS = [
  'id',
  'status',
  'assertion_strategy',
  'case_count',
  'pass_count',
  'fail_count',
  'error_count',
  'pass_rate_percent',
  'started_at',
  'completed_at',
  'duration_ms',
  'error_message',
] as const

export function buildEvalRunsCsv(runs: EvalRun[]): string {
  const rows = runs.map((r) => [
    r.id,
    r.status,
    r.assertion_strategy,
    String(r.case_count),
    String(r.pass_count),
    String(r.fail_count),
    String(r.error_count),
    passRatePercent(r),
    r.started_at ?? '',
    r.completed_at ?? '',
    durationMs(r.started_at, r.completed_at),
    r.error_message ?? '',
  ])
  return [CSV_HEADERS, ...rows]
    .map((row) => row.map(csvEscape).join(','))
    .join('\n')
}

/** Pass rate as an integer percent, or ``""`` when there are
 *  no cases. Operators piping into spreadsheets get a number
 *  they can chart; the trailing ``%`` would force a string
 *  column. */
function passRatePercent(run: EvalRun): string {
  if (run.case_count === 0) return ''
  return String(Math.round((run.pass_count / run.case_count) * 100))
}

/** Integer ms diff; empty when either endpoint is null or
 *  unparsable. Matches the duration_ms column on the per-step
 *  CSV (run-export.ts). */
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
