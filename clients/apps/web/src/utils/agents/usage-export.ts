/**
 * CSV export for the LLM usage rollup page.
 *
 * Matches the shape of the other agents CSV exporters
 * (eval-export, run-export, eval-runs-export, runs-list-
 * export). Reuses ``csvEscape`` so RFC-4180 quoting stays
 * consistent across all 5 export surfaces — operators can
 * paste one into a sheet that already has formulas
 * referencing another and the column types line up.
 */

import type { UsageRollupRow } from '@/hooks/api/agents'
import { csvEscape } from './eval-export'

const CSV_HEADERS = [
  'provider',
  'model',
  'credential_id',
  'credential_name',
  'workspace_id',
  'input_tokens',
  'output_tokens',
  'total_tokens',
  'call_count',
] as const

/**
 * Build a CSV string from a usage rollup window.
 *
 * - The first line is the column header per ``CSV_HEADERS``.
 * - One row per ``UsageRollupRow``.
 * - ``credential_id`` may be null (env-resolved / explicit
 *   secret); rendered as empty string so the column stays
 *   aligned. ``credential_name`` resolves via the supplied
 *   map; rows without a known name leave it blank rather
 *   than dumping the short UUID — operators sorting by
 *   credential_name in a spreadsheet shouldn't see fake
 *   "0a1b2c3d…" buckets.
 */
export function buildUsageCsv(
  rows: UsageRollupRow[],
  credentialNames: Map<string, string>,
): string {
  const body = rows.map((r) => {
    const credName =
      r.credential_id !== null
        ? (credentialNames.get(r.credential_id) ?? '')
        : ''
    return [
      r.provider,
      r.model,
      r.credential_id ?? '',
      credName,
      r.workspace_id,
      String(r.input_tokens),
      String(r.output_tokens),
      String(r.total_tokens),
      String(r.call_count),
    ]
      .map(csvEscape)
      .join(',')
  })
  return [CSV_HEADERS.join(','), ...body].join('\r\n')
}
