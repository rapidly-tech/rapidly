'use client'

import { CopyId } from '@/components/agents/CopyId'
import { JsonPanel } from '@/components/agents/JsonPanel'
import {
  type EvalRun,
  type EvalRunStatus,
  type Run,
  type RunStatus,
  type TriggeredByKind,
  type Workflow,
  type WorkflowVersion,
  useArchiveWorkflow,
  useCancelRun,
  useDeleteWorkflow,
  useEvalRuns,
  usePublishVersion,
  useRuns,
  useSetCurrentVersion,
  useTriggerRun,
  useUnarchiveWorkflow,
  useUpdateWorkflow,
  useWorkflow,
  useWorkflowVersions,
} from '@/hooks/api/agents'
import { useListWorkspaces } from '@/hooks/api/org'
import {
  formatDuration,
  formatRelative,
  formatTimestamp,
} from '@/utils/agents/datetime'
import { buildRunsCsv } from '@/utils/agents/runs-list-export'
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

  // Status filter for the runs list. ``null`` is "all"; chip-
  // driven. Kept here at the page level (not inside RunsSection)
  // so it can also drive the empty-state copy below.
  const [statusFilter, setStatusFilter] = useState<RunStatus | null>(null)

  // Triggered-by filter — manual ("user") vs eval vs webhook /
  // schedule / sub_workflow. Lets operators triaging a flaky
  // workflow distinguish their own test runs from production
  // traffic.
  const [triggeredByFilter, setTriggeredByFilter] =
    useState<TriggeredByKind | null>(null)

  // Version picker. ``null`` defaults to the workflow's
  // current_version_id once it's loaded; operators can flip to
  // any past version to inspect its run history. We don't fall
  // back automatically when the workflow rolls forward — the
  // operator's last selection sticks.
  const [versionFilter, setVersionFilter] = useState<string | null>(null)
  const activeVersionId = versionFilter ?? workflow?.current_version_id ?? null

  // Runs are listed per workflow_version.
  const runsQuery = useRuns(
    {
      workflow_version_id: activeVersionId ?? undefined,
      status: statusFilter ?? undefined,
      triggered_by_kind: triggeredByFilter ?? undefined,
      limit: 25,
      page: 1,
    },
    !!activeVersionId,
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
          {workflow.current_version_id && workflow.archived_at === null && (
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
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            triggeredByFilter={triggeredByFilter}
            onTriggeredByFilterChange={setTriggeredByFilter}
            activeVersionId={activeVersionId}
            onVersionFilterChange={setVersionFilter}
          />
          {workflow.current_version_id && (
            <EvalHistorySection
              workflowVersionId={workflow.current_version_id}
            />
          )}
          <ArchiveSection workflow={workflow} />
          <DangerZone workflow={workflow} />
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
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(workflow.name)
  const [description, setDescription] = useState(workflow.description ?? '')
  const update = useUpdateWorkflow(workflow.id)

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = name.trim()
    if (trimmed.length === 0) return
    update.mutate(
      {
        name: trimmed,
        // Empty description → null so we don't store ''. The backend
        // treats `null` and missing-from-payload the same (no change),
        // but we want explicit clear semantics here.
        description: description.trim() === '' ? null : description.trim(),
      },
      { onSuccess: () => setEditing(false) },
    )
  }

  if (editing) {
    return (
      <header className="flex flex-col gap-3">
        <form
          onSubmit={submit}
          className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
        >
          <input
            type="text"
            required
            minLength={1}
            maxLength={256}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-lg font-semibold text-slate-900 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100"
          />
          <textarea
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description"
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
          />
          {update.isError && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">
              {(update.error as Error).message}
            </div>
          )}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={update.isPending || name.trim().length === 0}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {update.isPending ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              onClick={() => {
                setEditing(false)
                setName(workflow.name)
                setDescription(workflow.description ?? '')
              }}
              className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              Cancel
            </button>
          </div>
        </form>
      </header>
    )
  }

  return (
    <header className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-3">
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
            {workflow.archived_at && (
              <span className="rounded-md bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
                Archived
              </span>
            )}
          </div>
          {workflow.description && (
            <p className="max-w-2xl text-base leading-relaxed text-slate-600 dark:text-slate-400">
              {workflow.description}
            </p>
          )}
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Created {formatRelative(workflow.created_at)}
            {workflow.updated_at !== workflow.created_at && (
              <> · Updated {formatRelative(workflow.updated_at)}</>
            )}
          </p>
          <WorkspaceLine workspaceId={workflow.workspace_id} />
          <CopyId id={workflow.id} label="workflow ID" />
        </div>
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="shrink-0 rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          Edit
        </button>
      </div>
    </header>
  )
}

function ArchiveSection({ workflow }: { workflow: Workflow }) {
  const archive = useArchiveWorkflow()
  const unarchive = useUnarchiveWorkflow()
  const isArchived = workflow.archived_at !== null
  const mutation = isArchived ? unarchive : archive

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-amber-200 bg-amber-50/40 p-5 dark:border-amber-900/40 dark:bg-amber-900/10">
      <h2 className="text-sm font-medium text-amber-800 dark:text-amber-300">
        {isArchived ? 'Archived' : 'Archive'}
      </h2>
      <p className="text-xs text-amber-800/80 dark:text-amber-300/80">
        {isArchived
          ? 'This workflow is archived — it stays queryable so past runs resolve their parent, but the workflows list hides it by default. Unarchive to restore it to the catalog.'
          : 'Archiving tucks the workflow away from the workflows list without losing it. Past runs and versions stay queryable; you can unarchive anytime. Use Delete (below) for the destructive path.'}
      </p>
      {mutation.isError && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900/50 dark:bg-amber-900/20 dark:text-amber-300">
          {(mutation.error as Error).message}
        </div>
      )}
      <button
        type="button"
        onClick={() => mutation.mutate(workflow.id)}
        disabled={mutation.isPending}
        className="self-start rounded-lg border border-amber-300 px-4 py-2 text-sm font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-50 dark:border-amber-700 dark:text-amber-200 dark:hover:bg-amber-900/30"
      >
        {mutation.isPending
          ? isArchived
            ? 'Unarchiving…'
            : 'Archiving…'
          : isArchived
            ? 'Unarchive'
            : 'Archive workflow'}
      </button>
    </section>
  )
}

function DangerZone({ workflow }: { workflow: Workflow }) {
  const del = useDeleteWorkflow()
  const router = useRouter()
  const [confirmText, setConfirmText] = useState('')

  const canDelete = confirmText.trim() === workflow.name

  const onDelete = () => {
    if (!canDelete) return
    del.mutate(workflow.id, {
      onSuccess: () => {
        router.push('/preview/agents/workflows')
      },
    })
  }

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-red-200 bg-red-50/50 p-5 dark:border-red-900/40 dark:bg-red-900/10">
      <h2 className="text-sm font-medium text-red-700 dark:text-red-300">
        Danger zone
      </h2>
      <p className="text-xs text-red-700/80 dark:text-red-300/80">
        Deleting a workflow soft-deletes its versions and runs. Past run results
        remain queryable by ID but stop appearing in list views. To confirm,
        type the workflow name below.
      </p>
      <input
        type="text"
        value={confirmText}
        onChange={(e) => setConfirmText(e.target.value)}
        placeholder={workflow.name}
        className="w-full max-w-md rounded-lg border border-red-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-red-900/40 dark:bg-slate-900 dark:text-slate-200"
      />
      {del.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">
          {(del.error as Error).message}
        </div>
      )}
      <button
        type="button"
        onClick={onDelete}
        disabled={!canDelete || del.isPending}
        className="self-start rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
      >
        {del.isPending ? 'Deleting…' : 'Delete workflow'}
      </button>
    </section>
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

const STATUS_FILTERS: { label: string; value: RunStatus | null }[] = [
  { label: 'All', value: null },
  { label: 'Running', value: 'running' },
  { label: 'Succeeded', value: 'succeeded' },
  { label: 'Failed', value: 'failed' },
  { label: 'Cancelled', value: 'cancelled' },
  { label: 'Awaiting human', value: 'awaiting_human' },
]

const TRIGGERED_BY_FILTERS: {
  label: string
  value: TriggeredByKind | null
}[] = [
  { label: 'Any source', value: null },
  { label: 'Manual', value: 'user' },
  { label: 'Eval', value: 'eval' },
  { label: 'Webhook', value: 'webhook' },
  { label: 'Schedule', value: 'schedule' },
]

function RunsSection({
  workflow,
  runs,
  isLoading,
  isError,
  errorMessage,
  statusFilter,
  onStatusFilterChange,
  triggeredByFilter,
  onTriggeredByFilterChange,
  activeVersionId,
  onVersionFilterChange,
}: {
  workflow: Workflow
  runs: Run[]
  isLoading: boolean
  isError: boolean
  errorMessage?: string
  statusFilter: RunStatus | null
  onStatusFilterChange: (status: RunStatus | null) => void
  triggeredByFilter: TriggeredByKind | null
  onTriggeredByFilterChange: (kind: TriggeredByKind | null) => void
  activeVersionId: string | null
  onVersionFilterChange: (versionId: string | null) => void
}) {
  const statusLabel =
    STATUS_FILTERS.find((f) => f.value === statusFilter)?.label.toLowerCase() ??
    'matching'
  const triggeredByLabel =
    TRIGGERED_BY_FILTERS.find(
      (f) => f.value === triggeredByFilter,
    )?.label.toLowerCase() ?? null

  // Empty-state copy adapts to whichever filter is active.
  // When both fire and produce zero rows, we say both;
  // when neither, just "no runs".
  const emptyMessage = (() => {
    if (statusFilter && triggeredByFilter)
      return `No ${statusLabel} runs from ${triggeredByLabel} triggers.`
    if (statusFilter) return `No ${statusLabel} runs for the selected version.`
    if (triggeredByFilter)
      return `No runs from ${triggeredByLabel} triggers for the selected version.`
    return 'No runs for the selected version.'
  })()

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
          Recent runs
        </h2>
        {activeVersionId && (
          <div className="flex flex-wrap items-center gap-2">
            <RunsVersionPicker
              workflowId={workflow.id}
              activeVersionId={activeVersionId}
              currentVersionId={workflow.current_version_id}
              onChange={onVersionFilterChange}
            />
            <RunsStatusFilter
              value={statusFilter}
              onChange={onStatusFilterChange}
            />
          </div>
        )}
      </div>
      {activeVersionId && (
        <RunsTriggeredByFilter
          value={triggeredByFilter}
          onChange={onTriggeredByFilterChange}
        />
      )}

      {activeVersionId && (statusFilter || triggeredByFilter) && (
        <button
          type="button"
          onClick={() => {
            // Clears status + triggered-by chip filters. The
            // version picker stays put — it's a "what am I
            // looking at" selector, not a filter.
            onStatusFilterChange(null)
            onTriggeredByFilterChange(null)
          }}
          className="self-start text-xs text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 dark:hover:text-emerald-300"
        >
          Clear filters
        </button>
      )}

      {!activeVersionId ? (
        <EmptyRuns message="This workflow has no published version yet — publish a version to trigger runs." />
      ) : isLoading ? (
        <RunsSkeleton />
      ) : isError ? (
        <ErrorBanner message={errorMessage ?? 'Unknown error'} />
      ) : runs.length === 0 ? (
        <EmptyRuns message={emptyMessage} />
      ) : (
        <>
          <div className="flex items-center justify-end">
            <ExportRunsCsv runs={runs} workflowId={workflow.id} />
          </div>
          <RunsList runs={runs} workflowId={workflow.id} />
        </>
      )}
    </section>
  )
}

function ExportRunsCsv({
  runs,
  workflowId,
}: {
  runs: Run[]
  workflowId: string
}) {
  const onExport = () => {
    const csv = buildRunsCsv(runs)
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    // Filename tags the workflow's short id so a folder of
    // exports stays addressable across workflows.
    a.download = `workflow-${workflowId.slice(0, 8)}-runs.csv`
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
      title="Exports the runs visible in this section (current filter + version)."
    >
      Export CSV
    </button>
  )
}

function RunsTriggeredByFilter({
  value,
  onChange,
}: {
  value: TriggeredByKind | null
  onChange: (kind: TriggeredByKind | null) => void
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {TRIGGERED_BY_FILTERS.map((filter) => {
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

function RunsVersionPicker({
  workflowId,
  activeVersionId,
  currentVersionId,
  onChange,
}: {
  workflowId: string
  activeVersionId: string
  currentVersionId: string | null
  onChange: (versionId: string | null) => void
}) {
  const versionsQuery = useWorkflowVersions(workflowId, {
    limit: 50,
    page: 1,
  })
  const versions: WorkflowVersion[] = versionsQuery.data?.data ?? []

  // No picker until we have ≥2 versions — single-version
  // workflows would just show a noop dropdown.
  if (versions.length < 2) return null

  return (
    <select
      value={activeVersionId}
      onChange={(e) => {
        const next = e.target.value
        // Selecting the current version maps to ``null`` so the
        // page can keep tracking it automatically if the workflow
        // rolls forward later.
        onChange(next === currentVersionId ? null : next)
      }}
      className="rounded-md border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
    >
      {versions.map((v) => (
        <option key={v.id} value={v.id}>
          v{v.version_number}
          {v.id === currentVersionId ? ' (current)' : ''}
        </option>
      ))}
    </select>
  )
}

function RunsStatusFilter({
  value,
  onChange,
}: {
  value: RunStatus | null
  onChange: (status: RunStatus | null) => void
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

const TERMINAL_RUN_STATUSES: RunStatus[] = ['succeeded', 'failed', 'cancelled']

function RunsList({ runs, workflowId }: { runs: Run[]; workflowId: string }) {
  return (
    <ul className="grid gap-2">
      {runs.map((run) => (
        <RunRow key={run.id} run={run} workflowId={workflowId} />
      ))}
    </ul>
  )
}

function RunRow({ run, workflowId }: { run: Run; workflowId: string }) {
  const cancel = useCancelRun()
  const canCancel = !TERMINAL_RUN_STATUSES.includes(run.status)
  return (
    <li className="grid grid-cols-[auto_1fr_auto_auto] items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 transition hover:border-emerald-400 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-emerald-600">
      <StatusPill status={run.status} />
      <Link
        href={`/preview/agents/workflows/${workflowId}/runs/${run.id}`}
        className="flex min-w-0 flex-col gap-0.5"
      >
        <span className="truncate font-mono text-xs text-slate-700 dark:text-slate-300">
          {run.id}
        </span>
        <span className="text-xs text-slate-500 dark:text-slate-400">
          Triggered by {run.triggered_by_kind} ·{' '}
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
      <span className="text-xs text-slate-400 dark:text-slate-500">
        {formatDuration(run.started_at, run.completed_at)}
      </span>
      {canCancel ? (
        <button
          type="button"
          onClick={() => {
            if (confirm(`Cancel run ${run.id.slice(0, 8)}?`)) {
              cancel.mutate(run.id)
            }
          }}
          disabled={cancel.isPending}
          className="rounded-md border border-rose-200 px-2 py-0.5 text-xs font-medium text-rose-600 hover:bg-rose-50 disabled:opacity-50 dark:border-rose-900/50 dark:text-rose-400 dark:hover:bg-rose-900/20"
        >
          {cancel.isPending ? '…' : 'Cancel'}
        </button>
      ) : (
        // Empty cell keeps the grid alignment consistent across
        // rows whether the cancel button is present or not.
        <span aria-hidden="true" />
      )}
    </li>
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

/** Header-line workspace badge. Renders nothing while the
 *  workspaces list is loading, then either the workspace name
 *  (if it matches a readable workspace) or a truncated id
 *  fallback. Useful for multi-workspace operators landing on
 *  a workflow via a deep link — they otherwise have no header
 *  cue about which workspace it belongs to. */
function WorkspaceLine({ workspaceId }: { workspaceId: string }) {
  const query = useListWorkspaces({ limit: 50, page: 1 })
  const match = query.data?.data.find((w) => w.id === workspaceId)
  if (query.isLoading) return null
  const label = match?.name ?? `id ${workspaceId.slice(0, 8)}`
  return (
    <p className="text-xs text-slate-500 dark:text-slate-400">
      Workspace: <span className="font-medium">{label}</span>
    </p>
  )
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
        <JsonPanel
          title={`v${version.version_number} graph`}
          data={version.graph_json}
          maxHeightClass="max-h-96"
        />
      )}
    </li>
  )
}

function EvalHistorySection({
  workflowVersionId,
}: {
  workflowVersionId: string
}) {
  // 10 most recent eval-runs against this workflow version. The
  // eval-runs endpoint already accepts workflow_version_id; pure
  // UI over that.
  const query = useEvalRuns({
    workflow_version_id: workflowVersionId,
    limit: 10,
    page: 1,
  })
  const runs: EvalRun[] = query.data?.data ?? []

  if (query.isLoading) {
    return (
      <section className="flex flex-col gap-3">
        <EvalHistoryHeader workflowVersionId={workflowVersionId} />
        <div className="h-24 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      </section>
    )
  }
  if (query.isError || runs.length === 0) {
    // Hide on error/empty — symmetric with the dataset-detail
    // history section. No chrome when there's nothing to show.
    return null
  }

  return (
    <section className="flex flex-col gap-3">
      <EvalHistoryHeader
        workflowVersionId={workflowVersionId}
        total={query.data?.meta.total}
      />
      <ul className="flex flex-col gap-2">
        {runs.map((run) => (
          <EvalHistoryRow key={run.id} run={run} />
        ))}
      </ul>
    </section>
  )
}

function EvalHistoryHeader({
  workflowVersionId,
  total,
}: {
  workflowVersionId: string
  total?: number
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
        Eval history (current version)
      </h2>
      {typeof total === 'number' && total > 10 && (
        <Link
          href={`/preview/agents/eval-runs?workflow_version_id=${workflowVersionId}`}
          className="text-xs text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 dark:hover:text-emerald-300"
        >
          See all {total} →
        </Link>
      )}
    </div>
  )
}

function EvalHistoryRow({ run }: { run: EvalRun }) {
  const passRate =
    run.case_count > 0
      ? Math.round((run.pass_count / run.case_count) * 100)
      : null
  return (
    <li>
      <Link
        href={`/preview/agents/eval-runs/${run.id}`}
        className="grid grid-cols-[auto_1fr_auto] items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 transition hover:border-emerald-400 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-emerald-600"
      >
        <EvalStatusPill status={run.status} />
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="truncate text-sm text-slate-700 dark:text-slate-300">
            {run.assertion_strategy}
          </span>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {run.started_at ? formatRelative(run.started_at) : 'not started'}
          </span>
        </div>
        <span className="flex items-baseline gap-2 text-sm">
          {run.case_count > 0 ? (
            <>
              <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                {run.pass_count}
              </span>
              <span className="text-xs text-slate-400 dark:text-slate-500">
                / {run.case_count}
              </span>
              {passRate !== null && (
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  · {passRate}%
                </span>
              )}
              {run.error_count > 0 && (
                <span className="text-xs text-rose-600 dark:text-rose-400">
                  · {run.error_count} err
                </span>
              )}
            </>
          ) : (
            <span className="text-xs text-slate-400 dark:text-slate-500">
              no cases
            </span>
          )}
        </span>
      </Link>
    </li>
  )
}

const EVAL_STATUS_STYLES: Record<EvalRunStatus, string> = {
  pending: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
  running:
    'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  succeeded:
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  failed: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300',
  cancelled:
    'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400',
}

function EvalStatusPill({ status }: { status: EvalRunStatus }) {
  return (
    <span
      className={`rounded-md px-2 py-0.5 text-xs font-medium ${EVAL_STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  )
}
