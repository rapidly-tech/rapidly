'use client'

import { CopyId } from '@/components/agents/CopyId'
import { JsonPanel } from '@/components/agents/JsonPanel'
import {
  type NodeRun,
  type NodeRunStatus,
  type RunDetail,
  type RunStatus,
  useCancelRun,
  useNodeRuns,
  useRun,
} from '@/hooks/api/agents'
import { formatDuration, formatTime } from '@/utils/agents/datetime'
import { buildNodeRunsCsv } from '@/utils/agents/run-export'
import Link from 'next/link'
import { use, useState } from 'react'

const TERMINAL: RunStatus[] = ['succeeded', 'failed', 'cancelled']

export default function RunDetailPage({
  params,
}: {
  params: Promise<{ id: string; runId: string }>
}) {
  const { id: workflowId, runId } = use(params)
  const runQuery = useRun(runId)
  const run = runQuery.data
  const isActive = run ? !TERMINAL.includes(run.status) : false
  const nodesQuery = useNodeRuns(runId, { isRunActive: isActive })

  const nodes: NodeRun[] = nodesQuery.data?.data ?? []

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-16">
      <BackLink workflowId={workflowId} />

      {runQuery.isLoading ? (
        <HeaderSkeleton />
      ) : runQuery.isError ? (
        <ErrorBanner message={(runQuery.error as Error).message} />
      ) : run ? (
        <>
          <RunHeader run={run} />
          {run.error_message && <RunError message={run.error_message} />}
          <NodeRunsSection
            runId={run.id}
            nodes={nodes}
            isLoading={nodesQuery.isLoading}
            isError={nodesQuery.isError}
            errorMessage={
              nodesQuery.error instanceof Error
                ? nodesQuery.error.message
                : undefined
            }
          />
          <IOPanels run={run} />
        </>
      ) : null}
    </main>
  )
}

function BackLink({ workflowId }: { workflowId: string }) {
  return (
    <Link
      href={`/preview/agents/workflows/${workflowId}`}
      className="self-start text-xs font-medium tracking-wider text-emerald-600 uppercase hover:text-emerald-700 dark:text-emerald-400 dark:hover:text-emerald-300"
    >
      ← Workflow
    </Link>
  )
}

function RunHeader({ run }: { run: RunDetail }) {
  const cancelMutation = useCancelRun()
  const canCancel = !TERMINAL.includes(run.status)
  return (
    <header className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <h1 className="text-3xl font-semibold text-slate-900 dark:text-slate-100">
          Run
        </h1>
        <RunStatusPill status={run.status} />
        {canCancel && (
          <button
            type="button"
            onClick={() => {
              if (confirm('Cancel this run?')) {
                cancelMutation.mutate(run.id)
              }
            }}
            disabled={cancelMutation.isPending}
            className="ml-auto rounded-md border border-rose-200 px-3 py-1 text-xs text-rose-600 hover:bg-rose-50 disabled:opacity-50 dark:border-rose-900/50 dark:text-rose-400 dark:hover:bg-rose-900/20"
          >
            {cancelMutation.isPending ? 'Cancelling…' : 'Cancel run'}
          </button>
        )}
      </div>
      <CopyId id={run.id} label="run ID" />
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
        <Stat label="Triggered by" value={run.triggered_by_kind} />
        <Stat
          label="Started"
          value={run.started_at ? formatTime(run.started_at) : '—'}
        />
        <Stat
          label="Completed"
          value={run.completed_at ? formatTime(run.completed_at) : '—'}
        />
        <Stat
          label="Duration"
          value={formatDuration(run.started_at, run.completed_at)}
        />
      </dl>
    </header>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
        {label}
      </dt>
      <dd className="text-slate-700 dark:text-slate-200">{value}</dd>
    </div>
  )
}

function RunError({ message }: { message: string }) {
  return (
    <section className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">
      <h2 className="mb-1 text-xs font-medium tracking-wider uppercase">
        Error
      </h2>
      <p className="font-mono">{message}</p>
    </section>
  )
}

const NODE_STATUS_FILTERS: { label: string; value: NodeRunStatus | null }[] = [
  { label: 'All', value: null },
  { label: 'Failed', value: 'failed' },
  { label: 'Succeeded', value: 'succeeded' },
  { label: 'Running', value: 'running' },
  { label: 'Skipped', value: 'skipped' },
]

function NodeRunsSection({
  runId,
  nodes,
  isLoading,
  isError,
  errorMessage,
}: {
  runId: string
  nodes: NodeRun[]
  isLoading: boolean
  isError: boolean
  errorMessage?: string
}) {
  const [statusFilter, setStatusFilter] = useState<NodeRunStatus | null>(null)
  const [search, setSearch] = useState('')
  const trimmedSearch = search.trim().toLowerCase()

  // Sort once here so both the export and the visible list
  // see the same execution order; chip filter applies *after*
  // sort.
  const sorted = [...nodes].sort((a, b) =>
    a.created_at.localeCompare(b.created_at),
  )

  // Count per status so the chips can show the at-a-glance
  // distribution — operators triaging a 30-step run want to
  // know "are there 3 failed nodes here?" without filtering.
  const counts: Record<NodeRunStatus, number> = {
    pending: 0,
    running: 0,
    succeeded: 0,
    failed: 0,
    skipped: 0,
    awaiting_human: 0,
  }
  for (const n of nodes) counts[n.status] += 1

  // Both filter axes combine. Search matches node_id OR
  // node_type so operators can grep either the workflow's
  // node-instance handle (echo1) or its kind (echo).
  const visible = sorted.filter((n) => {
    if (statusFilter && n.status !== statusFilter) return false
    if (
      trimmedSearch &&
      !n.node_id.toLowerCase().includes(trimmedSearch) &&
      !n.node_type.toLowerCase().includes(trimmedSearch)
    )
      return false
    return true
  })

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
          Steps
        </h2>
        {nodes.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <NodeStatusFilter
              value={statusFilter}
              onChange={setStatusFilter}
              counts={counts}
            />
            <ExportStepsCsv runId={runId} nodes={sorted} />
          </div>
        )}
      </div>
      {nodes.length > 0 && (
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter steps by node_id or node_type…"
          className="w-full max-w-md rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
        />
      )}
      {nodes.length > 0 && (statusFilter !== null || trimmedSearch) && (
        <button
          type="button"
          onClick={() => {
            setStatusFilter(null)
            setSearch('')
          }}
          className="self-start text-xs text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 dark:hover:text-emerald-300"
        >
          Clear filters
        </button>
      )}
      {isLoading ? (
        <RunsSkeleton />
      ) : isError ? (
        <ErrorBanner message={errorMessage ?? 'Unknown error'} />
      ) : nodes.length === 0 ? (
        <EmptyNodes />
      ) : visible.length === 0 ? (
        <EmptyFilteredNodes
          status={statusFilter}
          search={trimmedSearch ? search.trim() : null}
        />
      ) : (
        <NodeRunsList nodes={visible} />
      )}
    </section>
  )
}

function ExportStepsCsv({ runId, nodes }: { runId: string; nodes: NodeRun[] }) {
  const onExport = () => {
    const csv = buildNodeRunsCsv(nodes)
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    // Short id keeps a folder of exports addressable; full id
    // would be unwieldy.
    a.download = `run-${runId.slice(0, 8)}-steps.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }
  return (
    <button
      type="button"
      onClick={onExport}
      className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
    >
      Export CSV
    </button>
  )
}

function NodeStatusFilter({
  value,
  onChange,
  counts,
}: {
  value: NodeRunStatus | null
  onChange: (next: NodeRunStatus | null) => void
  counts: Record<NodeRunStatus, number>
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {NODE_STATUS_FILTERS.map((filter) => {
        const active = filter.value === value
        const count = filter.value === null ? null : counts[filter.value]
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
            {count !== null && (
              <span className="ml-1 font-mono text-[10px] opacity-70">
                {count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

function EmptyFilteredNodes({
  status,
  search,
}: {
  status: NodeRunStatus | null
  search: string | null
}) {
  // Composes per active axis. Status only, search only, or both.
  return (
    <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
      No
      {status && (
        <>
          {' '}
          <span className="font-mono">{status}</span>
        </>
      )}{' '}
      steps
      {search && (
        <>
          {' '}
          match{' '}
          <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono dark:bg-slate-800">
            {search}
          </code>
        </>
      )}
      .
    </div>
  )
}

function NodeRunsList({ nodes }: { nodes: NodeRun[] }) {
  // Sorted oldest-first by created_at — matches the engine's
  // execution order so operators read top-to-bottom as the
  // workflow actually ran.
  const sorted = [...nodes].sort((a, b) =>
    a.created_at.localeCompare(b.created_at),
  )
  return (
    <ol className="flex flex-col gap-2">
      {sorted.map((node, idx) => (
        <NodeRunRow key={node.id} node={node} index={idx + 1} />
      ))}
    </ol>
  )
}

function NodeRunRow({ node, index }: { node: NodeRun; index: number }) {
  // Each step row expands inline to show its input/output JSON.
  // Operators triaging a failing step want the input the node
  // saw (to repro outside the engine) and the output (to
  // confirm the failure mode); collapsed-by-default keeps the
  // overall timeline scannable.
  const [open, setOpen] = useState(false)
  return (
    <li className="rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="grid w-full grid-cols-[auto_auto_1fr_auto_auto] items-center gap-3 px-4 py-3 text-left"
      >
        <span className="font-mono text-xs text-slate-400 dark:text-slate-500">
          {index}
        </span>
        <NodeStatusPill status={node.status} />
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="truncate text-sm text-slate-700 dark:text-slate-300">
            {node.node_id}{' '}
            <span className="text-slate-400 dark:text-slate-500">
              ({node.node_type})
            </span>
          </span>
          {node.error_message && (
            <span className="truncate text-xs text-rose-600 dark:text-rose-400">
              {node.error_message}
            </span>
          )}
        </div>
        <span className="text-xs text-slate-400 dark:text-slate-500">
          {formatDuration(node.started_at, node.completed_at)}
        </span>
        <span className="text-xs text-slate-400 dark:text-slate-500">
          {open ? 'Hide' : 'View'}
        </span>
      </button>
      {open && (
        <div className="grid gap-4 border-t border-slate-100 px-4 py-3 sm:grid-cols-2 dark:border-slate-800">
          <JsonPanel title="Input" data={node.input_data} />
          <JsonPanel
            title="Output"
            data={node.output_data}
            placeholder={
              node.status === 'skipped'
                ? 'Skipped — no output'
                : node.status === 'failed'
                  ? 'Failed before producing output'
                  : '—'
            }
          />
        </div>
      )}
    </li>
  )
}

function IOPanels({ run }: { run: RunDetail }) {
  return (
    <section className="grid gap-4 sm:grid-cols-2">
      <JsonPanel title="Input" data={run.input_data} />
      <JsonPanel title="Output" data={run.output_data} />
    </section>
  )
}

// ── Status pills (run + node have different status enums) ────

const RUN_STATUS_STYLES: Record<RunStatus, string> = {
  pending: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
  running:
    'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  succeeded:
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  failed: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300',
  cancelled:
    'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400',
  awaiting_human:
    'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300',
}

function RunStatusPill({ status }: { status: RunStatus }) {
  return (
    <span
      className={`rounded-md px-2 py-0.5 text-xs font-medium ${RUN_STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  )
}

const NODE_STATUS_STYLES: Record<NodeRunStatus, string> = {
  pending: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
  running:
    'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  succeeded:
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  failed: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300',
  skipped: 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400',
  awaiting_human:
    'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300',
}

function NodeStatusPill({ status }: { status: NodeRunStatus }) {
  return (
    <span
      className={`rounded-md px-2 py-0.5 text-xs font-medium ${NODE_STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  )
}

// ── State variants ──────────────────────────────────────────

function HeaderSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      <div className="h-9 w-32 animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
      <div className="h-4 w-80 animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
    </div>
  )
}

function RunsSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {[0, 1, 2].map((i) => (
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

function EmptyNodes() {
  return (
    <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
      No steps recorded yet.
    </div>
  )
}
