import { describe, expect, it } from 'vitest'

import type { UsageRollupRow } from '@/hooks/api/agents'

import { buildUsageCsv } from './usage-export'

const HEADER =
  'provider,model,credential_id,credential_name,workspace_id,input_tokens,output_tokens,total_tokens,call_count'

function row(overrides: Partial<UsageRollupRow> = {}): UsageRollupRow {
  return {
    workspace_id: 'ws-1',
    credential_id: 'cred-1',
    provider: 'openai',
    model: 'gpt-4o-mini',
    input_tokens: 100,
    output_tokens: 50,
    total_tokens: 150,
    call_count: 2,
    ...overrides,
  }
}

describe('buildUsageCsv', () => {
  it('emits the header even when there are zero rows', () => {
    expect(buildUsageCsv([], new Map())).toBe(HEADER)
  })

  it('resolves credential_id → credential_name via the supplied map', () => {
    const csv = buildUsageCsv(
      [row({ credential_id: 'cred-1' })],
      new Map([['cred-1', 'production']]),
    )
    const dataLine = csv.split('\r\n')[1]
    expect(dataLine).toBe(
      'openai,gpt-4o-mini,cred-1,production,ws-1,100,50,150,2',
    )
  })

  it('renders an unknown credential_id with an empty name column', () => {
    // Operators sorting by credential_name shouldn't see fake
    // "0a1b2c3d…" buckets — better to leave the column blank.
    const csv = buildUsageCsv(
      [row({ credential_id: 'cred-unknown' })],
      new Map(),
    )
    const dataLine = csv.split('\r\n')[1]
    expect(dataLine).toBe('openai,gpt-4o-mini,cred-unknown,,ws-1,100,50,150,2')
  })

  it('renders a null credential_id with empty id + empty name', () => {
    // Env-resolved / explicit secrets have credential_id = null.
    const csv = buildUsageCsv([row({ credential_id: null })], new Map())
    const dataLine = csv.split('\r\n')[1]
    expect(dataLine).toBe('openai,gpt-4o-mini,,,ws-1,100,50,150,2')
  })

  it('CSV-escapes credential names that contain commas', () => {
    // A credential named "prod, eu" should land as a quoted
    // cell so the comma doesn't bleed into the next column.
    const csv = buildUsageCsv([row()], new Map([['cred-1', 'prod, eu']]))
    const dataLine = csv.split('\r\n')[1]
    expect(dataLine).toContain('"prod, eu"')
  })

  it('CSV-escapes credential names that contain double quotes', () => {
    const csv = buildUsageCsv([row()], new Map([['cred-1', 'prod "v2"']]))
    const dataLine = csv.split('\r\n')[1]
    // Embedded double-quotes are doubled per RFC 4180.
    expect(dataLine).toContain('"prod ""v2"""')
  })

  it('uses CRLF line endings between header and rows', () => {
    // RFC 4180 says lines are separated by CRLF. Some
    // spreadsheet importers will refuse plain LF in
    // strict mode.
    const csv = buildUsageCsv([row()], new Map())
    expect(csv).toContain('\r\n')
    expect(csv.split('\r\n').length).toBe(2)
  })

  it('preserves numeric columns as strings without locale formatting', () => {
    // ``100000`` should not become ``"100,000"`` — that would
    // wreck downstream sum formulas. Numbers go in unformatted.
    const csv = buildUsageCsv([row({ input_tokens: 100000 })], new Map())
    expect(csv).toContain(',100000,')
  })

  it('emits one row per UsageRollupRow', () => {
    const csv = buildUsageCsv(
      [row({ model: 'gpt-4o-mini' }), row({ model: 'gpt-4o' })],
      new Map(),
    )
    expect(csv.split('\r\n').length).toBe(3) // header + 2
  })
})
