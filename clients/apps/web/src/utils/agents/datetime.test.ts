import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'

import {
  formatDuration,
  formatRelative,
  formatTime,
  formatTimestamp,
} from './datetime'

// Pin Date.now so the "X ago" assertions are deterministic.
// Picked a wall-clock value: 2026-05-28T12:00:00Z.
const NOW = Date.UTC(2026, 4, 28, 12, 0, 0)

describe('formatRelative', () => {
  beforeAll(() => {
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
  })
  afterAll(() => {
    vi.useRealTimers()
  })

  it('returns "Xs ago" under a minute', () => {
    expect(formatRelative(new Date(NOW - 30_000).toISOString())).toBe('30s ago')
  })

  it('clamps a future timestamp to "0s ago" instead of negative', () => {
    // Guards against clock skew on the server vs client. A
    // negative ms diff would otherwise read "-15s ago".
    expect(formatRelative(new Date(NOW + 15_000).toISOString())).toBe('0s ago')
  })

  it('returns "Xm ago" under an hour', () => {
    expect(formatRelative(new Date(NOW - 5 * 60_000).toISOString())).toBe(
      '5m ago',
    )
  })

  it('returns "Xh ago" under a day', () => {
    expect(formatRelative(new Date(NOW - 3 * 60 * 60_000).toISOString())).toBe(
      '3h ago',
    )
  })

  it('returns "Xd ago" beyond a day', () => {
    expect(
      formatRelative(new Date(NOW - 2 * 24 * 60 * 60_000).toISOString()),
    ).toBe('2d ago')
  })

  it('returns the input verbatim when unparsable', () => {
    expect(formatRelative('not-a-date')).toBe('not-a-date')
  })
})

describe('formatDuration', () => {
  it('returns "—" when started_at is null', () => {
    expect(formatDuration(null, null)).toBe('—')
    expect(formatDuration(null, '2026-05-28T12:00:01.000Z')).toBe('—')
  })

  it('returns "running" when completed_at is null but started_at is set', () => {
    expect(formatDuration('2026-05-28T12:00:00.000Z', null)).toBe('running')
  })

  it('returns sub-second durations as "Xms"', () => {
    expect(
      formatDuration('2026-05-28T12:00:00.000Z', '2026-05-28T12:00:00.250Z'),
    ).toBe('250ms')
  })

  it('returns whole-second durations under a minute as "Xs"', () => {
    expect(
      formatDuration('2026-05-28T12:00:00.000Z', '2026-05-28T12:00:30.000Z'),
    ).toBe('30s')
  })

  it('returns sub-minute durations as "Xm Ys" beyond a minute', () => {
    expect(
      formatDuration('2026-05-28T12:00:00.000Z', '2026-05-28T12:02:30.000Z'),
    ).toBe('2m 30s')
  })

  it('returns "—" when either timestamp is unparsable', () => {
    expect(formatDuration('not-a-date', '2026-05-28T12:00:01.000Z')).toBe('—')
    expect(formatDuration('2026-05-28T12:00:00.000Z', 'still-not')).toBe('—')
  })
})

describe('formatTime', () => {
  it('returns a non-empty string for a valid ISO', () => {
    // Locale strings vary by Node runtime / CLDR version — pin
    // structure (non-empty, doesn't crash) rather than exact
    // format, mirroring the formatters.test.ts pattern in
    // sibling utils.
    expect(formatTime('2026-05-28T12:00:00.000Z').length).toBeGreaterThan(0)
  })

  it('returns the input verbatim on invalid date', () => {
    expect(formatTime('not-a-date')).toBe('not-a-date')
  })
})

describe('formatTimestamp', () => {
  it('returns a non-empty string for a valid ISO', () => {
    expect(formatTimestamp('2026-05-28T12:00:00.000Z').length).toBeGreaterThan(
      0,
    )
  })

  it('returns the input verbatim when unparsable', () => {
    expect(formatTimestamp('not-a-date')).toBe('not-a-date')
  })
})
