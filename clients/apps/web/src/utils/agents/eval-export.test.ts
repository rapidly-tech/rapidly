import { describe, expect, it } from 'vitest'

import type { EvalRunCase } from '@/hooks/api/agents'

import { buildCasesCsv, classifyCase, csvEscape } from './eval-export'

function makeCase(overrides: Partial<EvalRunCase> = {}): EvalRunCase {
  return {
    id: 'eval-case-id',
    eval_run_id: 'eval-run-id',
    case_id: 'case-id',
    run_id: 'run-id',
    case_name: 'sample-case',
    case_input_data: { x: 1 },
    case_expected_output: { x: 1 },
    actual_output: { x: 1 },
    passed: true,
    error_message: null,
    judge_reason: null,
    duration_ms: 42,
    created_at: '2026-05-28T00:00:00Z',
    ...overrides,
  }
}

describe('classifyCase', () => {
  it('returns "errored" when error_message is set even if passed is false', () => {
    // Errored takes precedence so triagers don't double-count
    // a row in both Errored and Failed.
    const c = makeCase({ error_message: 'engine blew up', passed: false })
    expect(classifyCase(c)).toBe('errored')
  })

  it('returns "passed" for passed === true', () => {
    expect(classifyCase(makeCase({ passed: true }))).toBe('passed')
  })

  it('returns "failed" for passed === false', () => {
    expect(classifyCase(makeCase({ passed: false }))).toBe('failed')
  })

  it('returns "qualitative" when passed is null and no error', () => {
    expect(
      classifyCase(makeCase({ passed: null, case_expected_output: null })),
    ).toBe('qualitative')
  })
})

describe('csvEscape', () => {
  it('returns the value verbatim when no special chars', () => {
    expect(csvEscape('hello')).toBe('hello')
    expect(csvEscape('123')).toBe('123')
    expect(csvEscape('')).toBe('')
  })

  it('wraps in quotes when the cell contains a comma', () => {
    expect(csvEscape('a,b')).toBe('"a,b"')
  })

  it('wraps and doubles internal double-quotes', () => {
    expect(csvEscape('say "hi"')).toBe('"say ""hi"""')
  })

  it('wraps when the cell contains a newline (CR or LF)', () => {
    expect(csvEscape('a\nb')).toBe('"a\nb"')
    expect(csvEscape('a\r\nb')).toBe('"a\r\nb"')
  })

  it('does not double-escape when there is no embedded quote but quote-trigger chars exist', () => {
    expect(csvEscape('a, b')).toBe('"a, b"')
  })
})

describe('buildCasesCsv', () => {
  it('emits a header row followed by one row per case', () => {
    const csv = buildCasesCsv([
      makeCase({ case_name: 'one' }),
      makeCase({ case_name: 'two' }),
    ])
    const lines = csv.split('\n')
    expect(lines).toHaveLength(3)
    expect(lines[0]).toBe(
      'case_name,outcome,passed,duration_ms,error_message,judge_reason,input_data,expected_output,actual_output',
    )
  })

  it('renders boolean passed as "true" / "false" / "" for null', () => {
    const csv = buildCasesCsv([
      makeCase({ case_name: 'a', passed: true }),
      makeCase({ case_name: 'b', passed: false }),
      makeCase({
        case_name: 'c',
        passed: null,
        case_expected_output: null,
      }),
    ])
    const rows = csv.split('\n').slice(1)
    // Column index 2 is the "passed" cell.
    expect(rows[0].split(',')[2]).toBe('true')
    expect(rows[1].split(',')[2]).toBe('false')
    expect(rows[2].split(',')[2]).toBe('')
  })

  it('emits empty cells for null duration / error_message / judge_reason', () => {
    const csv = buildCasesCsv([
      makeCase({
        case_name: 'a',
        duration_ms: null,
        error_message: null,
        judge_reason: null,
      }),
    ])
    const row = csv.split('\n')[1]
    const cells = row.split(',')
    // duration_ms (idx 3), error_message (4), judge_reason (5)
    expect(cells[3]).toBe('')
    expect(cells[4]).toBe('')
    expect(cells[5]).toBe('')
  })

  it('JSON-stringifies input_data and treats null expected/actual as empty', () => {
    const csv = buildCasesCsv([
      makeCase({
        case_name: 'a',
        case_input_data: { x: 1 },
        case_expected_output: null,
        actual_output: null,
      }),
    ])
    const row = csv.split('\n')[1]
    // The JSON itself contains `"` so the cell gets CSV-wrapped
    // and the embedded quotes get doubled per RFC 4180.
    expect(row).toContain('"{""x"":1}"')
    // Last two cells should be empty (expected + actual null).
    const cells = row.split(',')
    expect(cells[cells.length - 2]).toBe('')
    expect(cells[cells.length - 1]).toBe('')
  })

  it('CSV-escapes a case name that contains a comma', () => {
    const csv = buildCasesCsv([makeCase({ case_name: 'name, with comma' })])
    const row = csv.split('\n')[1]
    expect(row.startsWith('"name, with comma"')).toBe(true)
  })

  it('CSV-escapes an embedded quote inside an error_message', () => {
    const csv = buildCasesCsv([makeCase({ error_message: 'said "no"' })])
    const row = csv.split('\n')[1]
    expect(row).toContain('"said ""no"""')
  })

  it('CSV-escapes a JSON payload that contains a comma', () => {
    // Two keys → JSON.stringify produces {"a":1,"b":2}, which
    // contains a literal comma; the cell must be wrapped.
    const csv = buildCasesCsv([
      makeCase({
        case_input_data: { a: 1, b: 2 },
      }),
    ])
    const row = csv.split('\n')[1]
    expect(row).toContain('"{""a"":1,""b"":2}"')
  })

  it('returns just the header when given an empty array', () => {
    const csv = buildCasesCsv([])
    expect(csv).toBe(
      'case_name,outcome,passed,duration_ms,error_message,judge_reason,input_data,expected_output,actual_output',
    )
  })

  it('round-trips through a CSV parser-style split correctly', () => {
    // Spot-check: a row with no special chars should split
    // by comma into exactly 9 cells.
    const csv = buildCasesCsv([
      makeCase({
        case_name: 'plain',
        case_input_data: { k: 'v' },
        case_expected_output: { k: 'v' },
        actual_output: { k: 'v' },
      }),
    ])
    const cells = csv.split('\n')[1].split(',')
    expect(cells).toHaveLength(9)
    expect(cells[0]).toBe('plain')
    expect(cells[1]).toBe('passed')
  })
})
