import { describe, expect, it } from 'vitest'

import type { EvalRun } from '@/hooks/api/agents'

import { buildEvalRunsCsv } from './eval-runs-export'

function makeRun(overrides: Partial<EvalRun> = {}): EvalRun {
  return {
    id: 'eval-run-id',
    workspace_id: 'workspace-id',
    dataset_id: 'dataset-id',
    workflow_version_id: 'workflow-version-id',
    status: 'succeeded',
    assertion_strategy: 'exact_match',
    judge_model_id: null,
    case_count: 10,
    pass_count: 8,
    fail_count: 2,
    error_count: 0,
    started_at: '2026-05-29T10:00:00.000Z',
    completed_at: '2026-05-29T10:00:05.000Z',
    error_message: null,
    created_at: '2026-05-29T10:00:00.000Z',
    ...overrides,
  }
}

describe('buildEvalRunsCsv', () => {
  it('emits a header row followed by one row per eval-run', () => {
    const csv = buildEvalRunsCsv([makeRun({ id: 'a' }), makeRun({ id: 'b' })])
    const lines = csv.split('\n')
    expect(lines).toHaveLength(3)
    expect(lines[0]).toBe(
      'id,status,assertion_strategy,case_count,pass_count,fail_count,error_count,pass_rate_percent,started_at,completed_at,duration_ms,error_message',
    )
  })

  it('rounds pass_rate to an integer percent', () => {
    const csv = buildEvalRunsCsv([makeRun({ case_count: 3, pass_count: 2 })])
    const cells = csv.split('\n')[1].split(',')
    // 2/3 → 67% rounded.
    expect(cells[7]).toBe('67')
  })

  it('emits empty pass_rate cell when case_count is 0', () => {
    // Cases-yet-to-arrive eval (status pending). A "0%" cell
    // would be misleading — empty conveys "rate undefined" so
    // the spreadsheet aggregator can skip it.
    const csv = buildEvalRunsCsv([makeRun({ case_count: 0, pass_count: 0 })])
    expect(csv.split('\n')[1].split(',')[7]).toBe('')
  })

  it('computes duration_ms as the integer diff', () => {
    const csv = buildEvalRunsCsv([
      makeRun({
        started_at: '2026-05-29T10:00:00.000Z',
        completed_at: '2026-05-29T10:00:05.000Z',
      }),
    ])
    // duration_ms is column 10 (zero-indexed).
    expect(csv.split('\n')[1].split(',')[10]).toBe('5000')
  })

  it('clamps negative durations to zero', () => {
    const csv = buildEvalRunsCsv([
      makeRun({
        started_at: '2026-05-29T10:00:05.000Z',
        completed_at: '2026-05-29T10:00:00.000Z',
      }),
    ])
    expect(csv.split('\n')[1].split(',')[10]).toBe('0')
  })

  it('emits empty cells for null timestamps', () => {
    const csv = buildEvalRunsCsv([
      makeRun({ started_at: null, completed_at: null }),
    ])
    const cells = csv.split('\n')[1].split(',')
    // started_at (8), completed_at (9), duration_ms (10)
    expect(cells[8]).toBe('')
    expect(cells[9]).toBe('')
    expect(cells[10]).toBe('')
  })

  it('CSV-escapes an error_message that contains a comma', () => {
    const csv = buildEvalRunsCsv([
      makeRun({
        status: 'failed',
        error_message: 'engine blew up, retry skipped',
      }),
    ])
    expect(csv.split('\n')[1]).toContain('"engine blew up, retry skipped"')
  })

  it('CSV-escapes embedded quotes inside an error_message', () => {
    const csv = buildEvalRunsCsv([
      makeRun({ status: 'failed', error_message: 'said "no"' }),
    ])
    expect(csv.split('\n')[1]).toContain('"said ""no"""')
  })

  it('returns just the header when given an empty array', () => {
    const csv = buildEvalRunsCsv([])
    expect(csv).toBe(
      'id,status,assertion_strategy,case_count,pass_count,fail_count,error_count,pass_rate_percent,started_at,completed_at,duration_ms,error_message',
    )
  })

  it('preserves caller-supplied order', () => {
    // Caller is the eval-runs list page which renders rows in
    // created_at-desc order; the exporter must not re-sort.
    const csv = buildEvalRunsCsv([
      makeRun({ id: 'newer' }),
      makeRun({ id: 'older' }),
    ])
    const rows = csv.split('\n').slice(1)
    expect(rows[0].split(',')[0]).toBe('newer')
    expect(rows[1].split(',')[0]).toBe('older')
  })
})
