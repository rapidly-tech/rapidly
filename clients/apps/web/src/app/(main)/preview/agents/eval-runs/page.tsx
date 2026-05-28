'use client'

import { Pagination } from '@/components/agents/ListControls'
import {
  type AssertionStrategy,
  type EvalRun,
  type EvalRunStatus,
  useCancelEvalRun,
  useDataset,
  useEvalRuns,
} from '@/hooks/api/agents'
import { formatRelative } from '@/utils/agents/datetime'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { useState } from 'react'

const PAGE_SIZE = 20

export default function EvalRunsListPage() {
  const searchParams = useSearchParams()
  const router = useRouter()
  // dataset_id + workflow_version_id arrive via URL from links
  // like the dataset detail's "See all N →" or the workflow
  // detail's eval-history section. Status stays UI-only because
  // it changes too fast to round-trip through the router.
  const datasetId = searchParams.get('dataset_id') ?? null
  const workflowVersionId = searchParams.get('workflow_version_id') ?? null

  const [statusFilter, setStatusFilter] = useState<EvalRunStatus | null>(null)
  const [strategyFilter, setStrategyFilter] =
    useState<AssertionStrategy | null>(null)
  const [page, setPage] = useState(1)
  const onStatusChange = (next: EvalRunStatus | null) => {
    setStatusFilter(next)
    setPage(1)
  }
  const onStrategyChange = (next: AssertionStrategy | null) => {
    setStrategyFilter(next)
    setPage(1)
  }
  const clearFilters = () => {
    router.push('/preview/agents/eval-runs')
    setPage(1)
  }

  const query = useEvalRuns({
    dataset_id: datasetId ?? undefined,
    workflow_version_id: workflowVersionId ?? undefined,
    status: statusFilter ?? undefined,
    assertion_strategy: strategyFilter ?? undefined,
    limit: PAGE_SIZE,
    page,
  })
  const runs: EvalRun[] = query.data?.data ?? []
  const meta = query.data?.meta

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-16">
      <Header />

      {datasetId && (
        <DatasetFilterBadge datasetId={datasetId} onClear={clearFilters} />
      )}

      {workflowVersionId && (
        <WorkflowVersionFilterBadge
          workflowVersionId={workflowVersionId}
          onClear={clearFilters}
        />
      )}

      <StatusFilter value={statusFilter} onChange={onStatusChange} />
      <StrategyFilter value={strategyFilter} onChange={onStrategyChange} />

      {query.isLoading ? (
        <Skeleton />
      ) : query.isError ? (
        <ErrorBanner message={(query.error as Error).message} />
      ) : runs.length === 0 ? (
        statusFilter || strategyFilter ? (
          <EmptyFiltered status={statusFilter} strategy={strategyFilter} />
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

const STRATEGY_FILTERS: { label: string; value: AssertionStrategy | null }[] = [
  { label: 'Any strategy', value: null },
  { label: 'Exact match', value: 'exact_match' },
  { label: 'JSON schema', value: 'json_schema' },
  { label: 'LLM judge', value: 'llm_judge' },
]

function StrategyFilter({
  value,
  onChange,
}: {
  value: AssertionStrategy | null
  onChange: (next: AssertionStrategy | null) => void
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {STRATEGY_FILTERS.map((filter) => {
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

function DatasetFilterBadge({
  datasetId,
  onClear,
}: {
  datasetId: string
  onClear: () => void
}) {
  // useDataset returns 404 if the operator pasted a non-existent
  // id; in that case we still render the badge but show the raw
  // id so they can clear the filter.
  const datasetQuery = useDataset(datasetId)
  const label = datasetQuery.data?.name ?? `id ${datasetId.slice(0, 8)}`
  return <FilterBadge label="Dataset" value={label} onClear={onClear} />
}

function WorkflowVersionFilterBadge({
  workflowVersionId,
  onClear,
}: {
  workflowVersionId: string
  onClear: () => void
}) {
  // No useWorkflowVersion(id) hook today — versions are nested
  // under their workflow and the existing useWorkflowVersions
  // hook lists per-workflow rather than a single by-id. The id
  // is opaque to operators anyway; the short-form is enough to
  // identify which version is being filtered.
  return (
    <FilterBadge
      label="Workflow version"
      value={`id ${workflowVersionId.slice(0, 8)}`}
      onClear={onClear}
    />
  )
}

function FilterBadge({
  label,
  value,
  onClear,
}: {
  label: string
  value: string
  onClear: () => void
}) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs dark:border-emerald-900/40 dark:bg-emerald-900/10">
      <span className="text-slate-500 dark:text-slate-400">{label}:</span>
      <span className="font-medium text-emerald-700 dark:text-emerald-300">
        {value}
      </span>
      <button
        type="button"
        onClick={onClear}
        className="ml-auto rounded-md px-2 py-0.5 text-slate-500 hover:bg-emerald-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-emerald-900/30 dark:hover:text-slate-200"
        aria-label={`Clear ${label.toLowerCase()} filter`}
      >
        ✕ Clear
      </button>
    </div>
  )
}

function EmptyFiltered({
  status,
  strategy,
}: {
  status: EvalRunStatus | null
  strategy: AssertionStrategy | null
}) {
  // Empty copy adapts to whichever filter combination produced
  // the empty result. Both → "No <status> <strategy> eval runs.";
  // single → just that filter; neither shouldn't reach this
  // component (caller falls back to <Empty />).
  const parts: string[] = ['No']
  if (status) parts.push(status)
  if (strategy) parts.push(strategy)
  parts.push('eval runs.')
  return (
    <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
      <span className="font-mono">{parts.join(' ')}</span>
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

const TERMINAL_EVAL_STATUSES: EvalRunStatus[] = [
  'succeeded',
  'failed',
  'cancelled',
]

function EvalRunList({ runs }: { runs: EvalRun[] }) {
  return (
    <ul className="grid gap-2">
      {runs.map((run) => (
        <EvalRunRow key={run.id} run={run} />
      ))}
    </ul>
  )
}

function EvalRunRow({ run }: { run: EvalRun }) {
  const cancel = useCancelEvalRun()
  const canCancel = !TERMINAL_EVAL_STATUSES.includes(run.status)
  return (
    <li className="grid grid-cols-[auto_1fr_auto_auto] items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 transition hover:border-emerald-400 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-emerald-600">
      <StatusPill status={run.status} />
      <Link
        href={`/preview/agents/eval-runs/${run.id}`}
        className="flex min-w-0 flex-col gap-0.5"
      >
        <span className="truncate font-mono text-xs text-slate-700 dark:text-slate-300">
          {run.id}
        </span>
        <span className="text-xs text-slate-500 dark:text-slate-400">
          {run.assertion_strategy} ·{' '}
          {run.started_at ? formatRelative(run.started_at) : 'not started'}
        </span>
        {run.error_message && (
          <span
            className="truncate text-xs text-rose-600 dark:text-rose-400"
            title={run.error_message}
          >
            {run.error_message}
          </span>
        )}
      </Link>
      <PassFailBadge run={run} />
      {canCancel ? (
        <button
          type="button"
          onClick={() => {
            if (confirm(`Cancel eval run ${run.id.slice(0, 8)}?`)) {
              cancel.mutate(run.id)
            }
          }}
          disabled={cancel.isPending}
          className="rounded-md border border-rose-200 px-2 py-0.5 text-xs font-medium text-rose-600 hover:bg-rose-50 disabled:opacity-50 dark:border-rose-900/50 dark:text-rose-400 dark:hover:bg-rose-900/20"
        >
          {cancel.isPending ? '…' : 'Cancel'}
        </button>
      ) : (
        // Empty cell keeps the grid alignment consistent
        // across rows (same trick as the workflow runs list,
        // M5.46).
        <span aria-hidden="true" />
      )}
    </li>
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
