'use client'

import {
  type Run,
  type RunStatus,
  type Workflow,
  type WorkflowVersion,
  usePublishVersion,
  useRuns,
  useSetCurrentVersion,
  useTriggerRun,
  useWorkflow,
  useWorkflowVersions,
} from '@/hooks/api/agents'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { use, useState } from 'react'

export default function WorkflowDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const workflowQuery = useWorkflow(id)
  const workflow = workflowQuery.data

  // Runs are listed per workflow_version. Use the workflow's
  // current_version_id when available — drafts without a
  // published version can't have runs.
  const runsQuery = useRuns(
    {
      workflow_version_id: workflow?.current_version_id ?? undefined,
      limit: 25,
      page: 1,
    },
    !!workflow?.current_version_id,
  )
  const runs: Run[] = runsQuery.data?.data ?? []

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-16">
      <BackLink />

      {workflowQuery.isLoading ? (
        <HeaderSkeleton />
      ) : workflowQuery.isError ? (
        <ErrorBanner message={(workflowQuery.error as Error).message} />
      ) : workflow ? (
        <>
          <WorkflowHeader workflow={workflow} />
          <PublishVersionSection workflow={workflow} />
          <VersionHistorySection workflow={workflow} />
          {workflow.current_version_id && (
            <TriggerRunSection workflow={workflow} />
          )}
          <RunsSection
            workflow={workflow}
            runs={runs}
            isLoading={runsQuery.isLoading}
            isError={runsQuery.isError}
            errorMessage={
              runsQuery.error instanceof Error
                ? runsQuery.error.message
                : undefined
            }
          />
        </>
      ) : null}
    </main>
  )
}

function BackLink() {
  return (
    <Link
      href="/preview/agents/workflows"
      className="self-start text-xs font-medium tracking-wider text-emerald-600 uppercase hover:text-emerald-700 dark:text-emerald-400 dark:hover:text-emerald-300"
    >
      ← Workflows
    </Link>
  )
}

function WorkflowHeader({ workflow }: { workflow: Workflow }) {
  return (
    <header className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <h1 className="text-3xl font-semibold text-slate-900 dark:text-slate-100">
          {workflow.name}
        </h1>
        {workflow.current_version_id ? (
          <span className="rounded-md bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
            Published
          </span>
        ) : (
          <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
            Draft
          </span>
        )}
      </div>
      {workflow.description && (
        <p className="max-w-2xl text-base leading-relaxed text-slate-600 dark:text-slate-400">
          {workflow.description}
        </p>
      )}
    </header>
  )
}

const STARTER_GRAPH = `{
  "nodes": [
    {
      "id": "echo1",
      "type": "echo",
      "config": {}
    }
  ],
  "edges": []
}`

function PublishVersionSection({ workflow }: { workflow: Workflow }) {
  const [open, setOpen] = useState(false)
  const [graphText, setGraphText] = useState(STARTER_GRAPH)
  const [parseError, setParseError] = useState<string | null>(null)
  const publish = usePublishVersion(workflow.id)

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    setParseError(null)
    let parsed: unknown
    try {
      parsed = JSON.parse(graphText)
    } catch (err) {
      setParseError(
        `JSON parse failed: ${err instanceof Error ? err.message : 'unknown'}`,
      )
      return
    }
    if (
      typeof parsed !== 'object' ||
      parsed === null ||
      Array.isArray(parsed) ||
      !('nodes' in parsed) ||
      !('edges' in parsed)
    ) {
      setParseError('graph_json must be an object with nodes + edges arrays')
      return
    }
    const obj = parsed as { nodes: unknown; edges: unknown }
    if (!Array.isArray(obj.nodes) || !Array.isArray(obj.edges)) {
      setParseError('graph_json.nodes and .edges must be arrays')
      return
    }

    publish.mutate(
      { graph_json: { nodes: obj.nodes, edges: obj.edges } },
      {
        onSuccess: () => setOpen(false),
      },
    )
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="self-start rounded-lg border border-emerald-500 px-4 py-2 text-sm font-medium text-emerald-600 hover:bg-emerald-50 dark:border-emerald-600 dark:text-emerald-400 dark:hover:bg-emerald-900/20"
      >
        {workflow.current_version_id
          ? 'Publish new version'
          : 'Publish first version'}
      </button>
    )
  }

  return (
    <form
      onSubmit={submit}
      className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
    >
      <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
        Publish version
      </h2>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        Paste a graph JSON with{' '}
        <code className="rounded bg-slate-100 px-1 font-mono dark:bg-slate-800">
          nodes
        </code>{' '}
        and{' '}
        <code className="rounded bg-slate-100 px-1 font-mono dark:bg-slate-800">
          edges
        </code>{' '}
        arrays. The new version becomes the workflow&apos;s current version on
        success — runs triggered after will execute against this graph.
      </p>
      <textarea
        rows={14}
        required
        value={graphText}
        onChange={(e) => setGraphText(e.target.value)}
        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 font-mono text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
      />
      {(parseError || publish.isError) && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">
          {parseError ?? (publish.error as Error).message}
        </div>
      )}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={publish.isPending}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          {publish.isPending ? 'Publishing…' : 'Publish'}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

function TriggerRunSection({ workflow }: { workflow: Workflow }) {
  const [open, setOpen] = useState(false)
  const [inputText, setInputText] = useState('{\n  "text": "your input"\n}')
  const [parseError, setParseError] = useState<string | null>(null)
  const trigger = useTriggerRun(workflow.id)
  const router = useRouter()

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    setParseError(null)
    let inputData: Record<string, unknown>
    try {
      const parsed = JSON.parse(inputText)
      if (
        typeof parsed !== 'object' ||
        parsed === null ||
        Array.isArray(parsed)
      ) {
        setParseError('input_data must be a JSON object')
        return
      }
      inputData = parsed as Record<string, unknown>
    } catch (err) {
      setParseError(
        `JSON parse failed: ${err instanceof Error ? err.message : 'unknown'}`,
      )
      return
    }

    trigger.mutate(
      { input_data: inputData },
      {
        onSuccess: (run) => {
          router.push(`/preview/agents/workflows/${workflow.id}/runs/${run.id}`)
        },
      },
    )
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="self-start rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
      >
        Trigger run
      </button>
    )
  }

  return (
    <form
      onSubmit={submit}
      className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
    >
      <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
        Trigger run
      </h2>
      <div className="flex flex-col gap-1">
        <label className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
          Input (JSON object)
        </label>
        <textarea
          rows={6}
          required
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 font-mono text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
        />
      </div>
      {(parseError || trigger.isError) && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">
          {parseError ?? (trigger.error as Error).message}
        </div>
      )}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={trigger.isPending}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          {trigger.isPending ? 'Triggering…' : 'Trigger'}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

function RunsSection({
  workflow,
  runs,
  isLoading,
  isError,
  errorMessage,
}: {
  workflow: Workflow
  runs: Run[]
  isLoading: boolean
  isError: boolean
  errorMessage?: string
}) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
        Recent runs
      </h2>

      {!workflow.current_version_id ? (
        <EmptyRuns message="This workflow has no published version yet — publish a version to trigger runs." />
      ) : isLoading ? (
        <RunsSkeleton />
      ) : isError ? (
        <ErrorBanner message={errorMessage ?? 'Unknown error'} />
      ) : runs.length === 0 ? (
        <EmptyRuns message="No runs yet. Click Trigger run above to fire one." />
      ) : (
        <RunsList runs={runs} workflowId={workflow.id} />
      )}
    </section>
  )
}

function RunsList({ runs, workflowId }: { runs: Run[]; workflowId: string }) {
  return (
    <ul className="grid gap-2">
      {runs.map((run) => (
        <li key={run.id}>
          <Link
            href={`/preview/agents/workflows/${workflowId}/runs/${run.id}`}
            className="grid grid-cols-[auto_1fr_auto] items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 transition hover:border-emerald-400 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-emerald-600"
          >
            <StatusPill status={run.status} />
            <div className="flex min-w-0 flex-col gap-0.5">
              <span className="truncate font-mono text-xs text-slate-700 dark:text-slate-300">
                {run.id}
              </span>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                Triggered by {run.triggered_by_kind} ·{' '}
                {run.started_at
                  ? formatRelative(run.started_at)
                  : 'not started'}
              </span>
            </div>
            <span className="text-xs text-slate-400 dark:text-slate-500">
              {formatDuration(run.started_at, run.completed_at)}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

const STATUS_STYLES: Record<RunStatus, string> = {
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

function StatusPill({ status }: { status: RunStatus }) {
  return (
    <span
      className={`rounded-md px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  )
}

function HeaderSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      <div className="h-9 w-64 animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
      <div className="h-5 w-96 animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
    </div>
  )
}

function RunsSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className="h-16 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800"
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

function EmptyRuns({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
      {message}
    </div>
  )
}

function formatRelative(iso: string): string {
  // Coarse relative time — "5m ago", "2h ago", "3d ago" — for
  // glanceable freshness. Exact timestamps belong on the run
  // detail page (M5.x), not the list.
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

function VersionHistorySection({ workflow }: { workflow: Workflow }) {
  const query = useWorkflowVersions(workflow.id, { limit: 25, page: 1 })
  const versions: WorkflowVersion[] = query.data?.data ?? []

  if (query.isLoading) {
    return (
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
          Version history
        </h2>
        <div className="h-24 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      </section>
    )
  }

  if (query.isError) {
    return (
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
          Version history
        </h2>
        <ErrorBanner message={(query.error as Error).message} />
      </section>
    )
  }

  if (versions.length === 0) {
    return null
  }

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
        Version history
      </h2>
      <ul className="flex flex-col gap-2">
        {versions.map((version) => (
          <VersionRow
            key={version.id}
            workflow={workflow}
            version={version}
            isCurrent={version.id === workflow.current_version_id}
          />
        ))}
      </ul>
    </section>
  )
}

function VersionRow({
  workflow,
  version,
  isCurrent,
}: {
  workflow: Workflow
  version: WorkflowVersion
  isCurrent: boolean
}) {
  const setCurrent = useSetCurrentVersion(workflow.id)
  const [showGraph, setShowGraph] = useState(false)

  // Node + edge counts are useful at-a-glance even when the
  // graph itself isn't expanded — they signal "how big is this
  // version" without forcing the operator to open the JSON.
  const graph = version.graph_json as {
    nodes?: unknown[]
    edges?: unknown[]
  }
  const nodeCount = Array.isArray(graph.nodes) ? graph.nodes.length : 0
  const edgeCount = Array.isArray(graph.edges) ? graph.edges.length : 0

  return (
    <li className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-medium text-slate-900 dark:text-slate-100">
              v{version.version_number}
            </span>
            {isCurrent && (
              <span className="rounded-md bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                Current
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-3 text-xs text-slate-500 dark:text-slate-400">
            <span>
              <span className="text-slate-400 dark:text-slate-500">
                created:
              </span>{' '}
              {formatTimestamp(version.created_at)}
            </span>
            <span>
              <span className="text-slate-400 dark:text-slate-500">nodes:</span>{' '}
              <span className="font-mono">{nodeCount}</span>
            </span>
            <span>
              <span className="text-slate-400 dark:text-slate-500">edges:</span>{' '}
              <span className="font-mono">{edgeCount}</span>
            </span>
            <span>
              <span className="text-slate-400 dark:text-slate-500">id:</span>{' '}
              <span className="font-mono">{version.id.slice(0, 8)}</span>
            </span>
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={() => setShowGraph((v) => !v)}
            className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {showGraph ? 'Hide graph' : 'View graph'}
          </button>
          {!isCurrent && (
            <button
              type="button"
              onClick={() => {
                if (
                  confirm(
                    `Roll workflow back to v${version.version_number}? New runs will execute against this version's graph.`,
                  )
                ) {
                  setCurrent.mutate(version.id)
                }
              }}
              disabled={setCurrent.isPending}
              className="rounded-md border border-emerald-300 px-3 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50 dark:border-emerald-700 dark:text-emerald-300 dark:hover:bg-emerald-900/20"
            >
              {setCurrent.isPending ? 'Setting…' : 'Set as current'}
            </button>
          )}
        </div>
      </div>
      {showGraph && (
        <pre className="max-h-96 overflow-auto rounded-md bg-slate-50 p-3 font-mono text-xs leading-relaxed text-slate-700 dark:bg-slate-950 dark:text-slate-300">
          {JSON.stringify(version.graph_json, null, 2)}
        </pre>
      )}
    </li>
  )
}

function formatTimestamp(iso: string): string {
  const ms = Date.parse(iso)
  if (Number.isNaN(ms)) return iso
  return new Date(ms).toLocaleString()
}
