'use client'

import { DateRange } from '@/components/Metrics/DateRangePicker'
import { toast } from '@/components/Toast/use-toast'
import {
  useListWebhooksDeliveries,
  useRedeliverWebhookEvent,
} from '@/hooks/api'
import {
  DataTablePaginationState,
  DataTableSortingState,
  getAPIParams,
  serializeSearchParams,
} from '@/utils/datatable'
import { Icon } from '@iconify/react'
import { operations, schemas } from '@rapidly-tech/client'
import {
  DataTable,
  DataTableColumnDef,
  DataTableColumnHeader,
} from '@rapidly-tech/ui/components/data/DataTable'
import FormattedDateTime from '@rapidly-tech/ui/components/data/FormattedDateTime'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { type Cell, type CellContext, type Row } from '@tanstack/react-table'
import { useRouter } from 'next/navigation'
import React, { useCallback, useMemo } from 'react'
import { twMerge } from 'tailwind-merge'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DeliveriesTableProps {
  workspace: schemas['Workspace']
  endpoint: schemas['WebhookEndpoint']
  pagination: DataTablePaginationState
  sorting: DataTableSortingState
  dateRange?: DateRange
  succeeded?: boolean
  httpCodeClass?: NonNullable<
    operations['webhooks:list_webhook_deliveries']['parameters']['query']
  >['http_code_class']
  eventTypes?: NonNullable<
    operations['webhooks:list_webhook_deliveries']['parameters']['query']
  >['event_type']
  query?: string
}

type DeliveryRow = schemas['WebhookDelivery'] & {
  isSubRow?: boolean
}

// ---------------------------------------------------------------------------
// Deliveries Table
// ---------------------------------------------------------------------------

const DeliveriesTable: React.FC<DeliveriesTableProps> = ({
  workspace,
  endpoint,
  pagination,
  sorting,
  dateRange,
  succeeded,
  httpCodeClass,
  eventTypes,
  query,
}) => {
  const router = useRouter()

  const buildUrl = useCallback(
    (p: DataTablePaginationState, s: DataTableSortingState) =>
      `/dashboard/${workspace.slug}/settings/webhooks/endpoints/${endpoint.id}?${serializeSearchParams(p, s)}`,
    [workspace.slug, endpoint.id],
  )

  const setPagination = useCallback(
    (
      updater:
        | DataTablePaginationState
        | ((old: DataTablePaginationState) => DataTablePaginationState),
    ) => {
      const next = typeof updater === 'function' ? updater(pagination) : updater
      router.push(buildUrl(next, sorting))
    },
    [pagination, sorting, router, buildUrl],
  )

  const setSorting = useCallback(
    (
      updater:
        | DataTableSortingState
        | ((old: DataTableSortingState) => DataTableSortingState),
    ) => {
      const next = typeof updater === 'function' ? updater(sorting) : updater
      router.push(buildUrl(pagination, next))
    },
    [pagination, sorting, router, buildUrl],
  )

  // --- Data fetching ---
  const deliveriesHook = useListWebhooksDeliveries({
    endpoint_id: endpoint.id,
    ...getAPIParams(pagination, sorting),
    ...(dateRange?.from
      ? { start_timestamp: dateRange.from.toISOString() }
      : {}),
    ...(dateRange?.to ? { end_timestamp: dateRange.to.toISOString() } : {}),
    ...(succeeded !== undefined ? { succeeded } : {}),
    ...(httpCodeClass ? { http_code_class: httpCodeClass } : {}),
    ...(eventTypes && eventTypes.length > 0 ? { event_type: eventTypes } : {}),
    ...(query ? { query } : {}),
  })

  const deliveries: DeliveryRow[] = deliveriesHook.data?.data || []
  const rowCount = deliveriesHook.data?.meta.total ?? 0
  const pageCount = deliveriesHook.data?.meta.pages ?? 1

  // --- Column definitions ---
  const columns: DataTableColumnDef<DeliveryRow>[] = useMemo(
    () => [
      {
        id: 'expand',
        enableSorting: false,
        size: 50,
        cell: ({ row }: { row: Row<DeliveryRow> }) => {
          if (!row.getCanExpand()) return null
          return (
            <button
              onClick={row.getToggleExpandedHandler()}
              className="cursor-pointer"
              aria-label={row.getIsExpanded() ? 'Collapse row' : 'Expand row'}
            >
              {row.getIsExpanded() ? (
                <Icon
                  icon="solar:alt-arrow-down-linear"
                  className="h-5 w-5 text-slate-500 dark:text-slate-400"
                />
              ) : (
                <Icon
                  icon="solar:alt-arrow-right-linear"
                  className="h-5 w-5 text-slate-500 dark:text-slate-400"
                />
              )}
            </button>
          )
        },
      },
      {
        accessorKey: 'id',
        header: ({ column }) => (
          <DataTableColumnHeader column={column} title="ID" />
        ),
        cell: (props) => {
          const { original: delivery } = props.row
          if (delivery.isSubRow) return <ExpandedRow {...props} />
          return <span className="text-xs">{delivery.id}</span>
        },
      },
      {
        id: 'http_code',
        enableSorting: false,
        size: 50,
        header: ({ column }) => (
          <DataTableColumnHeader column={column} title="Status" />
        ),
        cell: ({ row }: { row: Row<DeliveryRow> }) => {
          const { original: delivery } = row
          if (delivery.isSubRow) return null

          if (delivery.http_code) {
            const ok = delivery.http_code >= 200 && delivery.http_code <= 299
            return (
              <span
                className={twMerge(ok ? 'text-emerald-500' : 'text-red-500')}
              >
                {delivery.http_code}
              </span>
            )
          }
          return <span>Failed</span>
        },
      },
      {
        accessorKey: 'webhook_event',
        enableSorting: false,
        header: ({ column }) => (
          <DataTableColumnHeader column={column} title="Type" />
        ),
        cell: ({ row }: { row: Row<DeliveryRow> }) => {
          if (row.original.isSubRow) return null
          return <pre>{row.original.webhook_event.type}</pre>
        },
      },
      {
        accessorKey: 'created_at',
        enableSorting: false,
        header: ({ column }) => (
          <DataTableColumnHeader column={column} title="Sent At" />
        ),
        cell: ({ row }: { row: Row<DeliveryRow> }) => {
          if (row.original.isSubRow) return null
          return (
            <FormattedDateTime
              datetime={row.original.created_at}
              resolution="time"
              dateStyle="short"
              timeStyle="short"
            />
          )
        },
      },
    ],
    [],
  )

  // --- Render ---
  if (!deliveries || pageCount === undefined) return null

  return (
    <DataTable
      columns={columns}
      data={deliveries}
      rowCount={rowCount}
      pageCount={pageCount}
      pagination={pagination}
      onPaginationChange={setPagination}
      sorting={sorting}
      onSortingChange={setSorting}
      getRowId={(row: DeliveryRow) => row.id}
      getCellColSpan={(cell: Cell<DeliveryRow, unknown>) => {
        if (cell.row.original.isSubRow) {
          return cell.column.id === 'id' ? 5 : 0
        }
        return 1
      }}
      getSubRows={(row: DeliveryRow) =>
        row.isSubRow
          ? undefined
          : [{ ...row, isSubRow: true, id: `${row.id}_subrow` }]
      }
      isLoading={deliveriesHook}
    />
  )
}

export default DeliveriesTable

// ---------------------------------------------------------------------------
// Expanded row — shows event details, payload, and redeliver action
// ---------------------------------------------------------------------------

const ExpandedRow = (props: CellContext<DeliveryRow, unknown>) => {
  const { original: delivery } = props.row

  const isArchived = delivery.webhook_event.is_archived
  const payload = delivery.webhook_event.payload
    ? JSON.stringify(JSON.parse(delivery.webhook_event.payload), undefined, 2)
    : null

  const redeliver = useRedeliverWebhookEvent()

  const handleRedeliver = useCallback(
    async (e: React.MouseEvent<HTMLButtonElement>) => {
      e.preventDefault()
      e.stopPropagation()

      const { error } = await redeliver.mutateAsync({
        id: delivery.webhook_event.id,
      })

      if (error) {
        toast({
          title: 'Redelivery Failed',
          description: `Unable to redeliver webhook event: ${error.detail}`,
        })
        return
      }

      toast({
        title: 'Redelivery Scheduled',
        description: 'The webhook event has been queued for redelivery',
      })
    },
    [redeliver, delivery.webhook_event.id],
  )

  return (
    <div className="flex flex-col gap-y-4">
      <div className="grid w-fit grid-cols-2 gap-2 text-sm">
        <div>Event ID</div>
        <code className="text-xs">{delivery.webhook_event.id}</code>
        <div>Event Timestamp</div>
        <code className="text-xs">{delivery.webhook_event.created_at}</code>
        <div>Delivery ID</div>
        <code className="text-xs">{delivery.id}</code>
        <div>Sent at</div>
        <code className="text-xs">{delivery.created_at}</code>
      </div>

      {!isArchived && (
        <div>
          <Button
            variant="default"
            onClick={handleRedeliver}
            loading={redeliver.isPending}
          >
            Redeliver
          </Button>
        </div>
      )}

      <hr />
      <div className="font-medium">Payload</div>
      {payload ? (
        <pre className="text-xs whitespace-pre-wrap">{payload}</pre>
      ) : (
        <div className="text-sm text-slate-500 italic">Archived event</div>
      )}

      {delivery.response && (
        <>
          <hr />
          <div className="font-medium">Response</div>
          <pre className="text-xs whitespace-pre-wrap">{delivery.response}</pre>
        </>
      )}
    </div>
  )
}
