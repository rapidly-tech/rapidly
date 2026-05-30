import { describe, expect, it } from 'vitest'

import type { Run } from '@/hooks/api/agents'

import { buildRunsCsv } from './runs-list-export'

function makeRun(overrides: Partial<Run> = {}): Run {
  return {
    id: 'run-id',
    workflow_version_id: 'workflow-version-id',
    status: 'succeeded',
    triggered_by_kind: 'user',
    triggered_by_id: 'user-id',
    started_at: '2026-05-29T10:00:00.000Z',
    completed_at: '2026-05-29T10:00:01.500Z',
    error_message: null,
    created_at: '2026-05-29T10:00:00.000Z',
    ...overrides,
  }
}

describe('buildRunsCsv', () => {
  it('emits a header row followed by one row per run', () => {
    const csv = buildRunsCsv([makeRun({ id: 'a' }), makeRun({ id: 'b' })])
    const lines = csv.split('\r\n')
    expect(lines).toHaveLength(3)
    expect(lines[0]).toBe(
      'id,status,triggered_by_kind,triggered_by_id,started_at,completed_at,duration_ms,error_message',
    )
  })

  it('computes duration_ms as the integer ms diff', () => {
    const csv = buildRunsCsv([
      makeRun({
        started_at: '2026-05-29T10:00:00.000Z',
        completed_at: '2026-05-29T10:00:01.500Z',
      }),
    ])
    // duration_ms is column 6 (zero-indexed).
    expect(csv.split('\r\n')[1].split(',')[6]).toBe('1500')
  })

  it('clamps negative durations to zero', () => {
    const csv = buildRunsCsv([
      makeRun({
        started_at: '2026-05-29T10:00:05.000Z',
        completed_at: '2026-05-29T10:00:00.000Z',
      }),
    ])
    expect(csv.split('\r\n')[1].split(',')[6]).toBe('0')
  })

  it('emits empty cells for null timestamps and triggered_by_id', () => {
    const csv = buildRunsCsv([
      makeRun({
        started_at: null,
        completed_at: null,
        triggered_by_id: null,
        error_message: null,
      }),
    ])
    const cells = csv.split('\r\n')[1].split(',')
    // triggered_by_id (3), started_at (4), completed_at (5),
    // duration_ms (6), error_message (7).
    expect(cells[3]).toBe('')
    expect(cells[4]).toBe('')
    expect(cells[5]).toBe('')
    expect(cells[6]).toBe('')
    expect(cells[7]).toBe('')
  })

  it('CSV-escapes a comma inside an error_message', () => {
    const csv = buildRunsCsv([
      makeRun({
        status: 'failed',
        error_message: 'step echo1 failed, retry skipped',
      }),
    ])
    expect(csv.split('\r\n')[1]).toContain('"step echo1 failed, retry skipped"')
  })

  it('CSV-escapes embedded quotes in an error_message', () => {
    const csv = buildRunsCsv([
      makeRun({ status: 'failed', error_message: 'node "echo" failed' }),
    ])
    expect(csv.split('\r\n')[1]).toContain('"node ""echo"" failed"')
  })

  it('preserves caller-supplied order', () => {
    // The workflow detail's runs list renders created_at-desc
    // and the exporter must not re-sort.
    const csv = buildRunsCsv([
      makeRun({ id: 'newer' }),
      makeRun({ id: 'older' }),
    ])
    const rows = csv.split('\r\n').slice(1)
    expect(rows[0].split(',')[0]).toBe('newer')
    expect(rows[1].split(',')[0]).toBe('older')
  })

  it('returns just the header when given an empty array', () => {
    expect(buildRunsCsv([])).toBe(
      'id,status,triggered_by_kind,triggered_by_id,started_at,completed_at,duration_ms,error_message',
    )
  })
})
