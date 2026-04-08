/**
 * Bridges TanStack Table pagination / sorting state with URL search
 * parameters and backend API query parameters.
 */
import { PaginationState, SortingState } from '@tanstack/react-table'

// ── Re-exported type aliases ──

export type DataTablePaginationState = PaginationState
export type DataTableSortingState = SortingState

export type DataTableSearchParams = {
  page?: string
  limit?: string
  sorting?: string[] | string
}

// ── Sorting converters ──

/**
 * Converts TanStack Table sorting state into the compact query-string
 * format the API expects (e.g. `"-created_at"` for descending).
 */
export const sortingStateToQueryParam = <S extends string>(
  state: DataTableSortingState,
): S[] => state.map((col) => (col.desc ? `-${col.id}` : col.id) as S)

/**
 * Parses the compact query-string sort tokens back into TanStack
 * sorting state objects.
 */
const fromSortParam = (tokens: string[]): DataTableSortingState =>
  tokens.map((raw) => {
    const descending = raw.startsWith('-')
    return {
      id: descending ? raw.substring(1) : raw,
      desc: descending,
    }
  })

// ── URL <-> State helpers ──

/**
 * Extracts pagination and sorting state from URL search parameters,
 * falling back to the supplied defaults when values are absent.
 */
export const parseSearchParams = (
  searchParams: DataTableSearchParams,
  defaultSorting: DataTableSortingState = [],
  defaultPageSize: number = 20,
): { pagination: DataTablePaginationState; sorting: DataTableSortingState } => {
  const pageIndex = searchParams.page
    ? Math.max(0, Number.parseInt(searchParams.page, 10) - 1 || 0)
    : 0

  const pageSize = searchParams.limit
    ? Math.max(1, Number.parseInt(searchParams.limit, 10) || defaultPageSize)
    : defaultPageSize

  let sorting: DataTableSortingState
  if (searchParams.sorting) {
    const tokens = Array.isArray(searchParams.sorting)
      ? searchParams.sorting
      : [searchParams.sorting]
    sorting = fromSortParam(tokens)
  } else {
    sorting = defaultSorting
  }

  return { pagination: { pageIndex, pageSize }, sorting }
}

/**
 * Encodes pagination and sorting state into a URLSearchParams instance
 * suitable for `router.push` or `<Link>`.
 */
export const serializeSearchParams = (
  pagination: DataTablePaginationState,
  sorting: DataTableSortingState,
): URLSearchParams => {
  const out = new URLSearchParams()
  out.set('page', String(pagination.pageIndex + 1))
  out.set('limit', String(pagination.pageSize))

  for (const token of sortingStateToQueryParam(sorting)) {
    out.append('sorting', token)
  }

  return out
}

/**
 * Maps table state directly to the shape the backend list endpoints
 * expect (`page`, `limit`, `sorting`).
 */
export const getAPIParams = <S extends string>(
  pagination: DataTablePaginationState,
  sorting: DataTableSortingState,
): { page: number; limit: number; sorting: S[] } => ({
  page: pagination.pageIndex + 1,
  limit: pagination.pageSize,
  sorting: sortingStateToQueryParam(sorting),
})
