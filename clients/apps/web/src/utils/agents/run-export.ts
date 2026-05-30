/**
 * CSV export for the run detail page's Steps list.
 *
 * Mirrors the eval-cases CSV export (M5.36 / M5.37) but for
 * NodeRun rows. csvEscape is re-used from eval-export to keep
 * the RFC-4180 quoting rules in one place.
 */

import type { NodeRun } from '@/hooks/api/agents'

import { csvEscape } from './eval-export'

const CSV_HEADERS = [
  'step',
  'node_id',
  'node_type',
  'status',
  'started_at',
  'completed_at',
  'duration_ms',
  'error_message',
  'input_data',
  'output_data',
] as const

/**
 * Build the CSV body string for a sorted array of NodeRun rows.
 *
 * Caller is expected to pass the rows in execution order
 * (oldest-first); the CSV preserves that. A 1-based ``step``
 * column matches the in-UI numbering operators see.
 */
export function buildNodeRunsCsv(nodes: NodeRun[]): string {
  const rows = nodes.map((n, idx) => [
    String(idx + 1),
    n.node_id,
    n.node_type,
    n.status,
    n.started_at ?? '',
    n.completed_at ?? '',
    nodeDurationMs(n.started_at, n.completed_at),
    n.error_message ?? '',
    JSON.stringify(n.input_data),
    n.output_data === null ? '' : JSON.stringify(n.output_data),
  ])
  return [CSV_HEADERS, ...rows]
    .map((row) => row.map(csvEscape).join(','))
    .join('\r\n')
}

/** Returns ``""`` when either endpoint is null or unparsable;
 *  otherwise the integer ms diff as a string. */
function nodeDurationMs(
  startedIso: string | null,
  completedIso: string | null,
): string {
  if (!startedIso || !completedIso) return ''
  const start = Date.parse(startedIso)
  const end = Date.parse(completedIso)
  if (Number.isNaN(start) || Number.isNaN(end)) return ''
  return String(Math.max(0, end - start))
}
