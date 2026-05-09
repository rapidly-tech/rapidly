'use client'

// ── Imports ──

import { DashboardBody } from '@/components/Layout/DashboardLayout'
import Pagination from '@/components/Pagination/Pagination'
import { useFileShareSessions } from '@/hooks/api/fileShareSessions'
import { useMetrics } from '@/hooks/api/metrics'
import { useDebouncedCallback } from '@/hooks/utils'
import {
  DataTablePaginationState,
  DataTableSortingState,
  serializeSearchParams,
  sortingStateToQueryParam,
} from '@/utils/datatable'
import { Icon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import { formatCurrency } from '@rapidly-tech/currency'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Input from '@rapidly-tech/ui/components/forms/Input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@rapidly-tech/ui/components/forms/Select'
import { motion } from 'framer-motion'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useQueryState } from 'nuqs'
import { useCallback, useMemo, useState } from 'react'
import { twMerge } from 'tailwind-merge'

// ── Helpers ──

const statusBadgeClass = (status: string): string => {
  switch (status) {
    case 'active':
    case 'completed':
      return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400'
    case 'created':
      return 'bg-slate-200 text-slate-700 dark:bg-slate-900 dark:text-slate-400'
    case 'expired':
      return 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400'
    case 'destroyed':
    case 'reported':
      return 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400'
    default:
      return 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400'
  }
}

const motionVariants = {
  variants: {
    initial: { opacity: 0 },
    animate: { opacity: 1, transition: { duration: 0.3 } },
    exit: { opacity: 0, transition: { duration: 0.3 } },
  },
}

// ── Sub-Components ──

function StatCard({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <div className="glass-elevated flex flex-col gap-1 rounded-2xl bg-slate-50 px-5 py-4 shadow-xs lg:rounded-3xl dark:bg-slate-900">
      <span className="text-sm text-slate-500 dark:text-slate-400">
        {title}
      </span>
      <span className="rp-text-primary text-xl font-medium">{children}</span>
    </div>
  )
}

function SessionRow({
  session,
  workspaceSlug,
}: {
  session: schemas['FileShareSessionSchema']
  workspaceSlug: string
}) {
  const displayName = session.title || session.file_name || session.short_slug

  return (
    <Link
      href={`/dashboard/${workspaceSlug}/files/${session.id}`}
      className="glass-elevated flex items-center justify-between rounded-2xl bg-slate-50 px-5 py-4 shadow-xs transition-colors lg:rounded-3xl dark:bg-slate-900"
    >
      <div className="flex items-center gap-4">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="rp-text-primary text-sm font-medium">
              {displayName}
            </span>
            <span
              className={twMerge(
                'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
                statusBadgeClass(session.status),
              )}
            >
              {session.status}
            </span>
          </div>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {session.short_slug}
            {session.file_name && displayName !== session.file_name && (
              <> &middot; {session.file_name}</>
            )}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-6">
        <div className="flex flex-col items-end gap-1">
          <span className="rp-text-primary text-sm">
            {session.download_count}
            {session.max_downloads > 0
              ? ` / ${session.max_downloads}`
              : ''}{' '}
            downloads
          </span>
          {session.price_cents != null && session.price_cents > 0 ? (
            <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
              ${(session.price_cents / 100).toFixed(2)}{' '}
              {session.currency.toUpperCase()}
            </span>
          ) : (
            <span className="text-xs text-slate-400 dark:text-slate-500">
              Free
            </span>
          )}
        </div>
        <span className="text-xs text-slate-500 dark:text-slate-400">
          {new Date(session.created_at).toLocaleDateString()}
        </span>
      </div>
    </Link>
  )
}

// ── Main Component ──

export default function FileShareInsightsPage({
  workspace,
  pagination,
  sorting,
  query: _query,
}: {
  workspace: schemas['Workspace']
  pagination: DataTablePaginationState
  sorting: DataTableSortingState
  query: string | undefined
}) {
  const [query, setQuery] = useState(_query ?? '')
  const [statusFilter, setStatusFilter] = useQueryState('status', {
    defaultValue: 'all',
  })

  const router = useRouter()
  const pathname = usePathname()

  // ── Pagination & Sorting ──

  const onPageChange = useCallback(
    (page: number) => {
      const searchParams = serializeSearchParams(pagination, sorting)
      searchParams.set('page', page.toString())
      if (query) {
        searchParams.set('query', query)
      } else {
        searchParams.delete('query')
      }
      router.replace(`${pathname}?${searchParams}`)
    },
    [pagination, router, sorting, pathname, query],
  )

  const onSortingChange = useCallback(
    (value: string) => {
      const desc = value.startsWith('-')
      const id = desc ? value.slice(1) : value
      const newSorting: DataTableSortingState = [{ id, desc }]
      const searchParams = serializeSearchParams(
        { ...pagination, pageIndex: 0 },
        newSorting,
      )
      if (query) {
        searchParams.set('query', query)
      } else {
        searchParams.delete('query')
      }
      router.replace(`${pathname}?${searchParams}`)
    },
    [pagination, router, pathname, query],
  )

  const currentSortingValue =
    sorting.length > 0
      ? `${sorting[0].desc ? '-' : ''}${sorting[0].id}`
      : '-created_at'

  // ── Search ──

  const debouncedQueryChange = useDebouncedCallback(
    (query: string) => {
      const searchParams = serializeSearchParams(pagination, sorting)
      if (query) {
        searchParams.set('query', query)
      } else {
        searchParams.delete('query')
      }
      router.replace(`${pathname}?${searchParams}`)
    },
    500,
    [pagination, sorting, query, router, pathname],
  )

  const onQueryChange = useCallback(
    (query: string) => {
      setQuery(query)
      debouncedQueryChange(query)
    },
    [debouncedQueryChange],
  )

  // ── Data Queries ──

  const sessions = useFileShareSessions(
    {
      page: pagination.pageIndex + 1,
      limit: pagination.pageSize,
      sorting: sortingStateToQueryParam(sorting),
      status: statusFilter === 'all' ? undefined : statusFilter,
      query: query || undefined,
      workspace_id: workspace.id,
    },
    10_000,
  )

  const { data: metricsData } = useMetrics({
    startDate: new Date(workspace.created_at),
    endDate: new Date(),
    interval: 'month',
    workspace_id: workspace.id,
    metrics: [
      'file_share_sessions',
      'file_share_downloads',
      'file_share_revenue',
    ],
  })

  // ── Computed Stats ──

  const stats = useMemo(() => {
    const totalSessions = sessions.data?.meta?.total ?? 0
    const totalDownloads = metricsData?.totals.file_share_downloads ?? 0
    const totalRevenue = metricsData?.totals.file_share_revenue ?? 0
    const items = sessions.data?.data ?? []
    const activeSessions = items.filter((s) => s.status === 'active').length
    return { totalSessions, totalDownloads, totalRevenue, activeSessions }
  }, [metricsData, sessions.data])

  // ── Render ──

  return (
    <DashboardBody className="gap-y-8 pb-16 md:gap-y-12">
      {/* Stats */}
      <motion.div
        className="grid grid-cols-2 gap-4 md:grid-cols-4"
        initial="initial"
        animate="animate"
        exit="exit"
        transition={{ staggerChildren: 0.1 }}
      >
        <motion.div {...motionVariants}>
          <StatCard title="Total Files">{stats.totalSessions}</StatCard>
        </motion.div>
        <motion.div {...motionVariants}>
          <StatCard title="Total Downloads">{stats.totalDownloads}</StatCard>
        </motion.div>
        <motion.div {...motionVariants}>
          <StatCard title="Revenue">
            {formatCurrency(
              stats.totalRevenue,
              workspace.default_presentment_currency ?? 'usd',
              0,
            )}
          </StatCard>
        </motion.div>
        <motion.div {...motionVariants}>
          <StatCard title="Active Sessions">{stats.activeSessions}</StatCard>
        </motion.div>
      </motion.div>

      {/* Filters */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:gap-4">
        <Input
          className="w-full md:max-w-64"
          preSlot={<Icon icon="solar:magnifer-linear" className="h-4 w-4" />}
          placeholder="Search files"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
        />
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-full md:max-w-fit">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="created">Created</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="expired">Expired</SelectItem>
            <SelectItem value="destroyed">Destroyed</SelectItem>
          </SelectContent>
        </Select>
        <Select value={currentSortingValue} onValueChange={onSortingChange}>
          <SelectTrigger className="w-full md:max-w-fit">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="-created_at">Newest</SelectItem>
            <SelectItem value="created_at">Oldest</SelectItem>
            <SelectItem value="-download_count">Most Downloads</SelectItem>
            <SelectItem value="download_count">Least Downloads</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* File List */}
      {sessions.isLoading ? (
        <div className="flex flex-col gap-3">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="h-[72px] animate-pulse rounded-2xl bg-slate-100 dark:bg-slate-800"
            />
          ))}
        </div>
      ) : sessions.error ? (
        <div className="rounded-2xl bg-red-50 p-4 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
          Failed to load files: {sessions.error.message}
        </div>
      ) : sessions.data && sessions.data.data.length > 0 ? (
        <Pagination
          currentPage={pagination.pageIndex + 1}
          pageSize={pagination.pageSize}
          totalCount={sessions.data?.meta.total || 0}
          currentURL={serializeSearchParams(pagination, sorting)}
          onPageChange={onPageChange}
        >
          <motion.div
            className="flex flex-col gap-3"
            initial="initial"
            animate="animate"
            exit="exit"
            transition={{ staggerChildren: 0.05 }}
          >
            {sessions.data.data.map((session) => (
              <motion.div key={session.id} {...motionVariants}>
                <SessionRow session={session} workspaceSlug={workspace.slug} />
              </motion.div>
            ))}
          </motion.div>
        </Pagination>
      ) : (
        <motion.div
          className="glass-elevated flex flex-col items-center gap-y-6 rounded-2xl bg-slate-50 py-24 shadow-xs lg:rounded-3xl dark:bg-slate-900"
          {...motionVariants}
        >
          <Icon
            icon="solar:share-linear"
            className="h-12 w-12 text-slate-300 dark:text-slate-700"
          />
          <div className="flex flex-col items-center gap-y-2">
            <h3 className="rp-text-primary text-lg font-medium">
              No files yet
            </h3>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Send files from the home page or the Send Files tab
            </p>
          </div>
          <Link href={`/dashboard/${workspace.slug}/shares/send-files`}>
            <Button variant="secondary">Send Files</Button>
          </Link>
        </motion.div>
      )}
    </DashboardBody>
  )
}
