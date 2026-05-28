import { describe, expect, it } from 'vitest'

import type { NodeRun } from '@/hooks/api/agents'

import { buildNodeRunsCsv } from './run-export'

function makeNode(overrides: Partial<NodeRun> = {}): NodeRun {
  return {
    id: 'node-run-id',
    run_id: 'run-id',
    node_id: 'echo1',
    node_type: 'echo',
    status: 'succeeded',
    started_at: '2026-05-28T10:00:00.000Z',
    completed_at: '2026-05-28T10:00:01.500Z',
    input_data: { x: 1 },
    output_data: { x: 1 },
    error_message: null,
    created_at: '2026-05-28T10:00:00.000Z',
    ...overrides,
  }
}

describe('buildNodeRunsCsv', () => {
  it('emits a header row followed by one row per node, with 1-based step numbers', () => {
    const csv = buildNodeRunsCsv([
      makeNode({ node_id: 'a' }),
      makeNode({ node_id: 'b' }),
    ])
    const lines = csv.split('\n')
    expect(lines).toHaveLength(3)
    expect(lines[0]).toBe(
      'step,node_id,node_type,status,started_at,completed_at,duration_ms,error_message,input_data,output_data',
    )
    // First data row → step "1", second → step "2".
    expect(lines[1].split(',')[0]).toBe('1')
    expect(lines[2].split(',')[0]).toBe('2')
  })

  it('computes duration_ms as the integer diff in milliseconds', () => {
    const csv = buildNodeRunsCsv([
      makeNode({
        started_at: '2026-05-28T10:00:00.000Z',
        completed_at: '2026-05-28T10:00:01.500Z',
      }),
    ])
    const cells = csv.split('\n')[1].split(',')
    // duration_ms is column 6 (zero-indexed).
    expect(cells[6]).toBe('1500')
  })

  it('emits empty cells for null timestamps', () => {
    const csv = buildNodeRunsCsv([
      makeNode({
        started_at: null,
        completed_at: null,
      }),
    ])
    const row = csv.split('\n')[1]
    const cells = row.split(',')
    // started_at (4), completed_at (5), duration_ms (6)
    expect(cells[4]).toBe('')
    expect(cells[5]).toBe('')
    expect(cells[6]).toBe('')
  })

  it('clamps negative durations to zero', () => {
    // Shouldn't normally happen — guards a clock-skew or
    // ordering bug from emitting a misleading negative cell.
    const csv = buildNodeRunsCsv([
      makeNode({
        started_at: '2026-05-28T10:00:01.000Z',
        completed_at: '2026-05-28T10:00:00.000Z',
      }),
    ])
    const cells = csv.split('\n')[1].split(',')
    expect(cells[6]).toBe('0')
  })

  it('treats output_data === null as empty (skipped/failed step)', () => {
    const csv = buildNodeRunsCsv([
      makeNode({
        status: 'failed',
        output_data: null,
        error_message: 'boom',
      }),
    ])
    const row = csv.split('\n')[1]
    const cells = row.split(',')
    // output_data is the last column.
    expect(cells[cells.length - 1]).toBe('')
  })

  it('CSV-escapes a node_id that contains a comma', () => {
    const csv = buildNodeRunsCsv([makeNode({ node_id: 'a,b' })])
    const row = csv.split('\n')[1]
    expect(row).toContain('"a,b"')
  })

  it('CSV-escapes JSON cells (which always contain literal quotes)', () => {
    const csv = buildNodeRunsCsv([
      makeNode({
        input_data: { a: 1 },
        output_data: { b: 2 },
      }),
    ])
    const row = csv.split('\n')[1]
    expect(row).toContain('"{""a"":1}"')
    expect(row).toContain('"{""b"":2}"')
  })

  it('CSV-escapes an embedded quote inside an error_message', () => {
    const csv = buildNodeRunsCsv([
      makeNode({ status: 'failed', error_message: 'said "no"' }),
    ])
    expect(csv.split('\n')[1]).toContain('"said ""no"""')
  })

  it('returns just the header when given an empty array', () => {
    const csv = buildNodeRunsCsv([])
    expect(csv).toBe(
      'step,node_id,node_type,status,started_at,completed_at,duration_ms,error_message,input_data,output_data',
    )
  })

  it('preserves caller-supplied execution order in the step column', () => {
    // The exporter doesn't re-sort; the page passes nodes in
    // engine order. Verify we honor that and don't accidentally
    // shuffle by node_id alphabetically.
    const csv = buildNodeRunsCsv([
      makeNode({ node_id: 'z' }),
      makeNode({ node_id: 'a' }),
      makeNode({ node_id: 'm' }),
    ])
    const rows = csv.split('\n').slice(1)
    expect(rows[0].split(',')[1]).toBe('z')
    expect(rows[1].split(',')[1]).toBe('a')
    expect(rows[2].split(',')[1]).toBe('m')
  })
})
