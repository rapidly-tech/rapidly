import { describe, expect, it } from 'vitest'

import {
  getAPIParams,
  parseSearchParams,
  serializeSearchParams,
  sortingStateToQueryParam,
} from './datatable'

describe('sortingStateToQueryParam', () => {
  it('encodes ascending columns by id', () => {
    expect(
      sortingStateToQueryParam([{ id: 'created_at', desc: false }]),
    ).toEqual(['created_at'])
  })

  it('encodes descending columns with a leading "-"', () => {
    expect(
      sortingStateToQueryParam([{ id: 'created_at', desc: true }]),
    ).toEqual(['-created_at'])
  })

  it('preserves multi-column sort order', () => {
    expect(
      sortingStateToQueryParam([
        { id: 'name', desc: false },
        { id: 'created_at', desc: true },
      ]),
    ).toEqual(['name', '-created_at'])
  })

  it('returns an empty array for empty sorting', () => {
    expect(sortingStateToQueryParam([])).toEqual([])
  })
})

describe('parseSearchParams — pagination', () => {
  it('defaults to page 1 (pageIndex 0) with default page size when no params', () => {
    expect(parseSearchParams({})).toEqual({
      pagination: { pageIndex: 0, pageSize: 20 },
      sorting: [],
    })
  })

  it('translates 1-based "page" to 0-based pageIndex', () => {
    expect(parseSearchParams({ page: '3' }).pagination.pageIndex).toBe(2)
  })

  it('clamps page to pageIndex 0 for non-positive inputs', () => {
    expect(parseSearchParams({ page: '0' }).pagination.pageIndex).toBe(0)
    expect(parseSearchParams({ page: '-5' }).pagination.pageIndex).toBe(0)
    expect(
      parseSearchParams({ page: 'not-a-number' }).pagination.pageIndex,
    ).toBe(0)
  })

  it('respects a valid limit', () => {
    expect(parseSearchParams({ limit: '50' }).pagination.pageSize).toBe(50)
  })

  it('falls back to defaultPageSize when limit parses to zero (0 is falsy)', () => {
    // ``Number.parseInt('0') || 25`` → 25 because ``0`` is falsy.
    expect(parseSearchParams({ limit: '0' }, [], 25).pagination.pageSize).toBe(
      25,
    )
  })

  it('clamps a negative limit to 1 (the Math.max floor, not defaultPageSize)', () => {
    // Negative numbers are truthy, so the ``|| default`` fallback doesn't
    // fire; ``Math.max(1, -5)`` then clamps the floor to 1.
    expect(parseSearchParams({ limit: '-5' }, [], 25).pagination.pageSize).toBe(
      1,
    )
  })

  it('falls back to defaultPageSize when limit is non-numeric (NaN)', () => {
    // ``Number.parseInt('abc', 10) || 25`` → 25
    expect(
      parseSearchParams({ limit: 'not-a-number' }, [], 25).pagination.pageSize,
    ).toBe(25)
  })

  it('honours a custom defaultPageSize', () => {
    expect(parseSearchParams({}, [], 50).pagination.pageSize).toBe(50)
  })
})

describe('parseSearchParams — sorting', () => {
  it('falls back to defaultSorting when no sorting param', () => {
    const fallback = [{ id: 'created_at', desc: true }]
    expect(parseSearchParams({}, fallback).sorting).toEqual(fallback)
  })

  it('parses a single sorting token as a string', () => {
    expect(parseSearchParams({ sorting: '-name' }).sorting).toEqual([
      { id: 'name', desc: true },
    ])
  })

  it('parses an array of sorting tokens', () => {
    expect(
      parseSearchParams({ sorting: ['name', '-created_at'] }).sorting,
    ).toEqual([
      { id: 'name', desc: false },
      { id: 'created_at', desc: true },
    ])
  })

  it('treats a bare token (no leading "-") as ascending', () => {
    expect(parseSearchParams({ sorting: 'email' }).sorting).toEqual([
      { id: 'email', desc: false },
    ])
  })
})

describe('serializeSearchParams', () => {
  it('writes page as 1-based and limit straight through', () => {
    const sp = serializeSearchParams({ pageIndex: 2, pageSize: 50 }, [])
    expect(sp.get('page')).toBe('3')
    expect(sp.get('limit')).toBe('50')
  })

  it('appends one "sorting" key per column', () => {
    const sp = serializeSearchParams({ pageIndex: 0, pageSize: 20 }, [
      { id: 'name', desc: false },
      { id: 'created_at', desc: true },
    ])
    expect(sp.getAll('sorting')).toEqual(['name', '-created_at'])
  })

  it('omits sorting entries when the state is empty', () => {
    const sp = serializeSearchParams({ pageIndex: 0, pageSize: 20 }, [])
    expect(sp.getAll('sorting')).toEqual([])
    expect(sp.get('page')).toBe('1')
  })

  it('round-trips through parseSearchParams', () => {
    const pagination = { pageIndex: 4, pageSize: 30 }
    const sorting = [
      { id: 'name', desc: false },
      { id: 'created_at', desc: true },
    ]
    const sp = serializeSearchParams(pagination, sorting)
    const parsed = parseSearchParams({
      page: sp.get('page')!,
      limit: sp.get('limit')!,
      sorting: sp.getAll('sorting'),
    })
    expect(parsed.pagination).toEqual(pagination)
    expect(parsed.sorting).toEqual(sorting)
  })
})

describe('getAPIParams', () => {
  it('maps pageIndex+1 → page and pageSize → limit', () => {
    const out = getAPIParams({ pageIndex: 2, pageSize: 50 }, [])
    expect(out.page).toBe(3)
    expect(out.limit).toBe(50)
    expect(out.sorting).toEqual([])
  })

  it('encodes sorting via sortingStateToQueryParam', () => {
    const out = getAPIParams({ pageIndex: 0, pageSize: 20 }, [
      { id: 'name', desc: false },
      { id: 'created_at', desc: true },
    ])
    expect(out.sorting).toEqual(['name', '-created_at'])
  })
})
