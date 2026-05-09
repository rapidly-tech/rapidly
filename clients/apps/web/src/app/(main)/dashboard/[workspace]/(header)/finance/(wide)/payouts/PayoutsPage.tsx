'use client'

import AccountBanner from '@/components/Transactions/AccountBanner'
import { useStripePayouts } from '@/hooks/api/stripeConnect'
import { schemas } from '@rapidly-tech/client'
import { formatCurrency } from '@rapidly-tech/currency'
import {
  DataTable,
  DataTableColumnHeader,
} from '@rapidly-tech/ui/components/data/DataTable'
import FormattedDateTime from '@rapidly-tech/ui/components/data/FormattedDateTime'
import { Status } from '@rapidly-tech/ui/components/feedback/Status'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { ColumnDef } from '@tanstack/react-table'
import { useState } from 'react'

const payoutStatusColor = (status: string) => {
  switch (status) {
    case 'paid':
      return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400'
    case 'pending':
      return 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400'
    case 'in_transit':
      return 'bg-slate-200 text-slate-700 dark:bg-slate-900 dark:text-slate-400'
    case 'canceled':
    case 'failed':
      return 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400'
    default:
      return ''
  }
}

const columns: ColumnDef<schemas['StripePayout']>[] = [
  {
    accessorKey: 'created',
    enableSorting: false,
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Date" />
    ),
    cell: ({ getValue }) => (
      <FormattedDateTime datetime={getValue() as string} resolution="time" />
    ),
  },
  {
    accessorKey: 'amount',
    enableSorting: false,
    header: ({ column }) => (
      <DataTableColumnHeader
        column={column}
        title="Amount"
        className="flex justify-end"
      />
    ),
    cell: ({ row: { original } }) => (
      <div className="flex flex-row justify-end font-medium">
        {formatCurrency(original.amount, original.currency)}
      </div>
    ),
  },
  {
    accessorKey: 'status',
    enableSorting: false,
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Status" />
    ),
    cell: ({ getValue }) => {
      const status = getValue() as string
      return (
        <Status
          status={status.replace('_', ' ')}
          className={payoutStatusColor(status)}
        />
      )
    },
  },
  {
    accessorKey: 'arrival_date',
    enableSorting: false,
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Arrival Date" />
    ),
    cell: ({ getValue }) => (
      <FormattedDateTime datetime={getValue() as string} resolution="day" />
    ),
  },
  {
    accessorKey: 'method',
    enableSorting: false,
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Method" />
    ),
    cell: ({ getValue }) => (
      <span className="capitalize">{getValue() as string}</span>
    ),
  },
]

export default function ClientPage({
  workspace,
}: {
  workspace: schemas['Workspace']
}) {
  const [startingAfter, setStartingAfter] = useState<string | undefined>()
  const [history, setHistory] = useState<string[]>([])

  const { data: payouts, isLoading } = useStripePayouts(workspace.id, {
    limit: 20,
    starting_after: startingAfter,
  })

  const handleNextPage = () => {
    if (payouts?.items && payouts.items.length > 0) {
      const lastId = payouts.items[payouts.items.length - 1].id
      setHistory((prev) => [...prev, startingAfter ?? ''])
      setStartingAfter(lastId)
    }
  }

  const handlePrevPage = () => {
    if (history.length > 0) {
      const prev = history[history.length - 1]
      setHistory((h) => h.slice(0, -1))
      setStartingAfter(prev || undefined)
    }
  }

  return (
    <div className="flex flex-col gap-y-8">
      <AccountBanner workspace={workspace} />

      <DataTable
        columns={columns}
        data={payouts?.items ?? []}
        pageCount={-1}
        pagination={{ pageIndex: history.length, pageSize: 20 }}
        onPaginationChange={() => {}}
        sorting={[]}
        onSortingChange={() => {}}
        isLoading={isLoading}
      />

      <div className="flex items-center justify-end gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={handlePrevPage}
          disabled={history.length === 0}
        >
          Previous
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleNextPage}
          disabled={!payouts?.has_more}
        >
          Next
        </Button>
      </div>
    </div>
  )
}
