'use client'

import {
  type NodeRun,
  type NodeRunStatus,
  type RunDetail,
  type RunStatus,
  useNodeRuns,
  useRun,
} from '@/hooks/api/agents'
import Link from 'next/link'
import { use } from 'react'

export default function RunDetailPage({
  params,
}: {
  params: Promise<{ id: string; runId: string }>
}) {
  const { id: workflowId, runId } = use(params)
  const runQuery = useRun(runId)
  const nodesQuery = useNodeRuns(runId)

  const run = runQuery.data
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
  return (
    <header className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <h1 className="text-3xl font-semibold text-slate-900 dark:text-slate-100">
          Run
        </h1>
        <RunStatusPill status={run.status} />
      </div>
      <p className="font-mono text-xs text-slate-500 dark:text-slate-400">
        {run.id}
      </p>
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

function NodeRunsSection({
  nodes,
  isLoading,
  isError,
  errorMessage,
}: {
  nodes: NodeRun[]
  isLoading: boolean
  isError: boolean
  errorMessage?: string
}) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
        Steps
      </h2>
      {isLoading ? (
        <RunsSkeleton />
      ) : isError ? (
        <ErrorBanner message={errorMessage ?? 'Unknown error'} />
      ) : nodes.length === 0 ? (
        <EmptyNodes />
      ) : (
        <NodeRunsList nodes={nodes} />
      )}
    </section>
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
        <li
          key={node.id}
          className="grid grid-cols-[auto_auto_1fr_auto] items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900"
        >
          <span className="font-mono text-xs text-slate-400 dark:text-slate-500">
            {idx + 1}
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
        </li>
      ))}
    </ol>
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

function JsonPanel({
  title,
  data,
}: {
  title: string
  data: Record<string, unknown>
}) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
        {title}
      </h3>
      <pre className="overflow-x-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-300">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
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

// ── Formatters ──────────────────────────────────────────────

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: 'numeric',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return iso
  }
}

function formatDuration(
  startedIso: string | null,
  completedIso: string | null,
): string {
  if (!startedIso) return '—'
  if (!completedIso) return 'running'
  const start = Date.parse(startedIso)
  const end = Date.parse(completedIso)
  if (Number.isNaN(start) || Number.isNaN(end)) return '—'
  const ms = end - start
  if (ms < 1000) return `${ms}ms`
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  return `${minutes}m ${seconds % 60}s`
}
