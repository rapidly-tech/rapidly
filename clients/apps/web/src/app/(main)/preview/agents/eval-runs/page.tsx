'use client'

import {
  type EvalRun,
  type EvalRunStatus,
  useEvalRuns,
} from '@/hooks/api/agents'
import Link from 'next/link'
import { useState } from 'react'

const PAGE_SIZE = 20

export default function EvalRunsListPage() {
  const [statusFilter, setStatusFilter] = useState<EvalRunStatus | null>(null)
  const [page, setPage] = useState(1)
  const onStatusChange = (next: EvalRunStatus | null) => {
    setStatusFilter(next)
    setPage(1)
  }

  const query = useEvalRuns({
    status: statusFilter ?? undefined,
    limit: PAGE_SIZE,
    page,
  })
  const runs: EvalRun[] = query.data?.data ?? []
  const meta = query.data?.meta

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-16">
      <Header />

      <StatusFilter value={statusFilter} onChange={onStatusChange} />

      {query.isLoading ? (
        <Skeleton />
      ) : query.isError ? (
        <ErrorBanner message={(query.error as Error).message} />
      ) : runs.length === 0 ? (
        statusFilter ? (
          <EmptyFiltered status={statusFilter} />
        ) : (
          <Empty />
        )
      ) : (
        <>
          <EvalRunList runs={runs} />
          {meta && (
            <Pagination
              page={page}
              pages={meta.pages}
              total={meta.total}
              onPageChange={setPage}
            />
          )}
        </>
      )}
    </main>
  )
}

function Pagination({
  page,
  pages,
  total,
  onPageChange,
}: {
  page: number
  pages: number
  total: number
  onPageChange: (next: number) => void
}) {
  if (pages <= 1) return null
  return (
    <div className="flex items-center justify-between gap-3 text-xs text-slate-500 dark:text-slate-400">
      <span>
        Page <span className="font-mono">{page}</span> of{' '}
        <span className="font-mono">{pages}</span> ·{' '}
        <span className="font-mono">{total}</span> total
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          ← Prev
        </button>
        <button
          type="button"
          onClick={() => onPageChange(Math.min(pages, page + 1))}
          disabled={page >= pages}
          className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          Next →
        </button>
      </div>
    </div>
  )
}

const STATUS_FILTERS: { label: string; value: EvalRunStatus | null }[] = [
  { label: 'All', value: null },
  { label: 'Running', value: 'running' },
  { label: 'Succeeded', value: 'succeeded' },
  { label: 'Failed', value: 'failed' },
  { label: 'Cancelled', value: 'cancelled' },
]

function StatusFilter({
  value,
  onChange,
}: {
  value: EvalRunStatus | null
  onChange: (status: EvalRunStatus | null) => void
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {STATUS_FILTERS.map((filter) => {
        const active = filter.value === value
        return (
          <button
            key={filter.label}
            type="button"
            onClick={() => onChange(filter.value)}
            className={
              active
                ? 'rounded-full bg-emerald-600 px-3 py-1 text-xs font-medium text-white'
                : 'rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800'
            }
          >
            {filter.label}
          </button>
        )
      })}
    </div>
  )
}

function EmptyFiltered({ status }: { status: EvalRunStatus }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
      No <span className="font-mono">{status}</span> eval runs.
    </div>
  )
}

function Header() {
  return (
    <header className="flex flex-col gap-3">
      <span className="text-xs font-medium tracking-wider text-emerald-600 uppercase dark:text-emerald-400">
        Rapidly · Agents
      </span>
      <h1 className="text-4xl font-semibold text-slate-900 dark:text-slate-100">
        Eval runs
      </h1>
      <p className="max-w-2xl text-base leading-relaxed text-slate-600 dark:text-slate-400">
        Each eval run drives a workflow version against every case in a dataset.
        Three assertion strategies are available — exact-match, JSON-schema, and
        LLM-judge.
      </p>
    </header>
  )
}

function EvalRunList({ runs }: { runs: EvalRun[] }) {
  return (
    <ul className="grid gap-2">
      {runs.map((run) => (
        <li key={run.id}>
          <Link
            href={`/preview/agents/eval-runs/${run.id}`}
            className="grid grid-cols-[auto_1fr_auto] items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 transition hover:border-emerald-400 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-emerald-600"
          >
            <StatusPill status={run.status} />
            <div className="flex min-w-0 flex-col gap-0.5">
              <span className="truncate font-mono text-xs text-slate-700 dark:text-slate-300">
                {run.id}
              </span>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                {run.assertion_strategy} ·{' '}
                {run.started_at
                  ? formatRelative(run.started_at)
                  : 'not started'}
              </span>
            </div>
            <PassFailBadge run={run} />
          </Link>
        </li>
      ))}
    </ul>
  )
}

function PassFailBadge({ run }: { run: EvalRun }) {
  if (run.case_count === 0) {
    return (
      <span className="text-xs text-slate-400 dark:text-slate-500">
        no cases
      </span>
    )
  }
  // Show pass / total at-a-glance; errors render in red beside
  // the pass count when present so operators don't miss them.
  return (
    <span className="flex items-baseline gap-2 text-sm">
      <span className="font-semibold text-emerald-600 dark:text-emerald-400">
        {run.pass_count}
      </span>
      <span className="text-xs text-slate-400 dark:text-slate-500">
        / {run.case_count}
      </span>
      {run.error_count > 0 && (
        <span className="text-xs text-rose-600 dark:text-rose-400">
          · {run.error_count} err
        </span>
      )}
    </span>
  )
}

const STATUS_STYLES: Record<EvalRunStatus, string> = {
  pending: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
  running:
    'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  succeeded:
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  failed: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300',
  cancelled:
    'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400',
}

function StatusPill({ status }: { status: EvalRunStatus }) {
  return (
    <span
      className={`rounded-md px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  )
}

function Skeleton() {
  return (
    <div className="flex flex-col gap-2">
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className="h-14 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800"
        />
      ))}
    </div>
  )
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">
      Failed: {message}
    </div>
  )
}

function Empty() {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-12 text-center dark:border-slate-800 dark:bg-slate-900/50">
      <p className="text-sm text-slate-500 dark:text-slate-400">
        No eval runs yet.
      </p>
      <p className="max-w-md text-xs text-slate-400 dark:text-slate-500">
        Trigger one via{' '}
        <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-slate-700 dark:bg-slate-800 dark:text-slate-300">
          POST /api/v1/agents/eval-runs
        </code>{' '}
        with a dataset_id + workflow_version_id.
      </p>
    </div>
  )
}

function formatRelative(iso: string): string {
  const now = Date.now()
  const then = Date.parse(iso)
  if (Number.isNaN(then)) return iso
  const seconds = Math.max(0, Math.floor((now - then) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}
