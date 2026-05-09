'use client'

import {
  type Cell,
  type ColumnDef,
  type OnChangeFn,
  type PaginationState,
  type Row,
  type RowSelectionState,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getExpandedRowModel,
  useReactTable,
} from '@tanstack/react-table'

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/primitives/table'
import { twMerge } from 'tailwind-merge'
import { DataTablePagination } from './DataTablePagination'

// -- Public type exports --

export interface ReactQueryLoading {
  isFetching: boolean
  isFetched: boolean
  isLoading: boolean
  status: string
  fetchStatus: string
}

export type DataTableColumnDef<TData, TValue = unknown> = ColumnDef<
  TData,
  TValue
>
export type DataTablePaginationState = PaginationState
export type DataTableSortingState = SortingState

// -- Prop contract --

interface DataTableConfig<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
  rowCount?: number
  pageCount?: number
  pagination?: PaginationState
  onPaginationChange?: OnChangeFn<PaginationState>
  sorting?: SortingState
  onSortingChange?: OnChangeFn<SortingState>
  getSubRows?: (row: TData) => TData[] | undefined
  className?: string
  wrapperClassName?: string
  headerClassName?: string
  isLoading: boolean | ReactQueryLoading
  getCellColSpan?: (cell: Cell<TData, unknown>) => number
  getRowId?: (originalRow: TData, index: number, parent?: Row<TData>) => string
  rowSelection?: RowSelectionState
  enableRowSelection?: boolean
  onRowSelectionChange?: OnChangeFn<RowSelectionState>
  onRowClick?: (row: Row<TData>) => void
}

// -- Helpers --

/** A React-Query whose enabled flag was never set true shows pending+idle. */
function isQueryEffectivelyDisabled(q: ReactQueryLoading): boolean {
  return q.status === 'pending' && q.fetchStatus === 'idle'
}

/** Normalise the loading prop to a plain boolean. */
function resolveLoadingState(flag: boolean | ReactQueryLoading): boolean {
  if (typeof flag === 'boolean') return flag
  if (isQueryEffectivelyDisabled(flag)) return false
  return !flag.isFetched || flag.isLoading
}

/** Determine the cursor class for a row based on selection/click config. */
function rowCursorClass(
  isSelectable: boolean | undefined,
  hasClickHandler: boolean,
  canSelect: boolean,
): string | undefined {
  if (!isSelectable && !hasClickHandler) return undefined
  return canSelect ? 'cursor-pointer' : ''
}

// -- Component --

export function DataTable<TData, TValue>({
  columns,
  data,
  rowCount,
  pageCount,
  pagination,
  onPaginationChange,
  sorting,
  onSortingChange,
  getSubRows,
  className,
  wrapperClassName,
  headerClassName,
  isLoading,
  getCellColSpan,
  getRowId,
  rowSelection,
  enableRowSelection,
  onRowSelectionChange,
  onRowClick,
}: DataTableConfig<TData, TValue>) {
  const grid = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
    manualPagination: true,
    manualSorting: true,
    rowCount,
    pageCount,
    onPaginationChange,
    onSortingChange,
    getSubRows,
    getRowId,
    enableRowSelection,
    onRowSelectionChange,
    enableMultiRowSelection: false,
    state: { pagination, sorting, rowSelection },
  })

  const showLoader = resolveLoadingState(isLoading)
  const rows = grid.getRowModel().rows
  const hasRows = rows.length > 0

  return (
    <div className={twMerge('flex flex-col gap-6', className)}>
      <div
        className={twMerge(
          'overflow-hidden rounded-2xl border border-white/8 bg-white/4 backdrop-blur-2xl backdrop-saturate-150 dark:border-white/6 dark:bg-white/3',
          wrapperClassName,
        )}
      >
        <Table className="w-full table-auto">
          <TableHeader>
            {grid.getHeaderGroups().map((group) => (
              <TableRow
                key={group.id}
                className={twMerge(
                  'bg-white/5 backdrop-blur-xl dark:bg-white/3',
                  headerClassName,
                )}
              >
                {group.headers.map((col) => (
                  <TableHead
                    key={col.id}
                    style={{ width: col.column.getSize() }}
                  >
                    {col.isPlaceholder
                      ? null
                      : flexRender(
                          col.column.columnDef.header,
                          col.getContext(),
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>

          <TableBody>
            {showLoader ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                  aria-busy="true"
                >
                  <span role="status">Loading...</span>
                </TableCell>
              </TableRow>
            ) : hasRows ? (
              rows.map((row) => {
                const clickAction = onRowClick
                  ? () => onRowClick(row)
                  : enableRowSelection
                    ? row.getToggleSelectedHandler()
                    : undefined

                return (
                  <TableRow
                    key={row.id}
                    className={rowCursorClass(
                      enableRowSelection,
                      !!onRowClick,
                      row.getCanSelect(),
                    )}
                    data-state={
                      enableRowSelection && row.getIsSelected()
                        ? 'selected'
                        : undefined
                    }
                    onClick={clickAction}
                  >
                    {row.getVisibleCells().map((cell) => {
                      const span = getCellColSpan ? getCellColSpan(cell) : 1
                      if (span === 0) return null
                      return (
                        <TableCell
                          key={cell.id}
                          colSpan={span}
                          style={{ width: cell.column.getSize() }}
                        >
                          {flexRender(
                            cell.column.columnDef.cell,
                            cell.getContext(),
                          )}
                        </TableCell>
                      )
                    })}
                  </TableRow>
                )
              })
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  No Results
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {pagination ? <DataTablePagination table={grid} /> : null}
    </div>
  )
}
