/**
 * Pure helpers used by the eval-run detail's CSV export +
 * outcome filter. Extracted from the page component so the
 * pure functions can be unit-tested without pulling Next.js
 * route context into the test runtime.
 */

import type { EvalRunCase } from '@/hooks/api/agents'

export type CaseOutcome = 'passed' | 'failed' | 'errored' | 'qualitative'

/**
 * Map an EvalRunCase to a four-way outcome.
 *
 * Order is significant: an errored case may also have
 * ``passed === false`` (the engine never got far enough to
 * score), but we want it surfaced as "errored" so operators
 * triaging failures don't double-count.
 */
export function classifyCase(caseItem: EvalRunCase): CaseOutcome {
  if (caseItem.error_message) return 'errored'
  if (caseItem.passed === true) return 'passed'
  if (caseItem.passed === false) return 'failed'
  return 'qualitative'
}

/**
 * Escape a single CSV cell per RFC 4180.
 *
 * - If the cell contains a comma, double-quote, CR, or LF,
 *   wrap the whole thing in double-quotes.
 * - Embedded double-quotes are escaped by doubling.
 * - Otherwise return the value verbatim.
 */
export function csvEscape(value: string): string {
  if (/[",\r\n]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`
  }
  return value
}

const CSV_HEADERS = [
  'case_name',
  'outcome',
  'passed',
  'duration_ms',
  'error_message',
  'judge_reason',
  'input_data',
  'expected_output',
  'actual_output',
] as const

/**
 * Build the CSV body string for an array of EvalRunCase rows.
 *
 * Columns are picked for downstream reporting: outcome +
 * score-relevant fields first, then the raw JSON payloads so
 * an analyst can drill in if needed. JSON columns are
 * ``JSON.stringify``'d into one cell each — most spreadsheet
 * tools handle the embedded quoting fine after CSV escape.
 */
export function buildCasesCsv(cases: EvalRunCase[]): string {
  const rows = cases.map((c) => [
    c.case_name,
    classifyCase(c),
    c.passed === null ? '' : c.passed ? 'true' : 'false',
    c.duration_ms === null ? '' : String(c.duration_ms),
    c.error_message ?? '',
    c.judge_reason ?? '',
    JSON.stringify(c.case_input_data),
    c.case_expected_output === null
      ? ''
      : JSON.stringify(c.case_expected_output),
    c.actual_output === null ? '' : JSON.stringify(c.actual_output),
  ])
  return [CSV_HEADERS, ...rows]
    .map((row) => row.map(csvEscape).join(','))
    .join('\n')
}
