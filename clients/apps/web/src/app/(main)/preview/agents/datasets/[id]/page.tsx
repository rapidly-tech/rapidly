'use client'

import { CopyId } from '@/components/agents/CopyId'
import { JsonPanel } from '@/components/agents/JsonPanel'
import {
  type AssertionStrategy,
  type Dataset,
  type DatasetCase,
  type DatasetCaseCreatePayload,
  type EvalRun,
  type EvalRunStatus,
  postDatasetCase,
  useArchiveDataset,
  useCreateDatasetCase,
  useDataset,
  useDatasetCases,
  useDeleteDataset,
  useDeleteDatasetCase,
  useEvalRuns,
  useTriggerEval,
  useUnarchiveDataset,
  useUpdateDataset,
  useWorkflows,
} from '@/hooks/api/agents'
import { useListWorkspaces } from '@/hooks/api/org'
import { formatRelative } from '@/utils/agents/datetime'
import { useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { use, useState } from 'react'

export default function DatasetDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const datasetQuery = useDataset(id)
  const casesQuery = useDatasetCases(id)

  const dataset = datasetQuery.data
  const cases: DatasetCase[] = casesQuery.data ?? []

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-16">
      <BackLink />

      {datasetQuery.isLoading ? (
        <HeaderSkeleton />
      ) : datasetQuery.isError ? (
        <ErrorBanner message={(datasetQuery.error as Error).message} />
      ) : dataset ? (
        <>
          <DatasetHeader dataset={dataset} caseCount={cases.length} />
          {dataset.archived_at === null && (
            <TriggerEvalSection dataset={dataset} />
          )}
          <EvalHistorySection datasetId={dataset.id} />
          <CasesSection
            cases={cases}
            isLoading={casesQuery.isLoading}
            isError={casesQuery.isError}
            errorMessage={
              casesQuery.error instanceof Error
                ? casesQuery.error.message
                : undefined
            }
            datasetId={dataset.id}
            nextOrderIndex={
              cases.length > 0
                ? Math.max(...cases.map((c) => c.order_index)) + 1
                : 0
            }
          />
          <ArchiveSection dataset={dataset} />
          <DangerZone dataset={dataset} />
        </>
      ) : null}
    </main>
  )
}

function BackLink() {
  return (
    <Link
      href="/preview/agents/datasets"
      className="self-start text-xs font-medium tracking-wider text-emerald-600 uppercase hover:text-emerald-700 dark:text-emerald-400 dark:hover:text-emerald-300"
    >
      ← Datasets
    </Link>
  )
}

function DatasetHeader({
  dataset,
  caseCount,
}: {
  dataset: Dataset
  caseCount: number
}) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(dataset.name)
  const [description, setDescription] = useState(dataset.description ?? '')
  const update = useUpdateDataset(dataset.id)

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = name.trim()
    if (trimmed.length === 0) return
    update.mutate(
      {
        name: trimmed,
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
            maxLength={4096}
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
                setName(dataset.name)
                setDescription(dataset.description ?? '')
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
              {dataset.name}
            </h1>
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {caseCount} case{caseCount === 1 ? '' : 's'}
            </span>
            {dataset.archived_at && (
              <span className="rounded-md bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
                Archived
              </span>
            )}
          </div>
          {dataset.description && (
            <p className="max-w-2xl text-base leading-relaxed text-slate-600 dark:text-slate-400">
              {dataset.description}
            </p>
          )}
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Created {formatRelative(dataset.created_at)}
            {dataset.modified_at && (
              <> · Updated {formatRelative(dataset.modified_at)}</>
            )}
          </p>
          <WorkspaceLine workspaceId={dataset.workspace_id} />
          <CopyId id={dataset.id} label="dataset ID" />
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

function ArchiveSection({ dataset }: { dataset: Dataset }) {
  const archive = useArchiveDataset()
  const unarchive = useUnarchiveDataset()
  const isArchived = dataset.archived_at !== null
  const mutation = isArchived ? unarchive : archive

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-amber-200 bg-amber-50/40 p-5 dark:border-amber-900/40 dark:bg-amber-900/10">
      <h2 className="text-sm font-medium text-amber-800 dark:text-amber-300">
        {isArchived ? 'Archived' : 'Archive'}
      </h2>
      <p className="text-xs text-amber-800/80 dark:text-amber-300/80">
        {isArchived
          ? 'This dataset is archived — it stays queryable so past eval runs resolve their parent, but the datasets list hides it by default. Unarchive to restore it.'
          : 'Archiving tucks the dataset away from the datasets list without losing it. Past eval runs and cases stay queryable; you can unarchive anytime. Use Delete (below) for the destructive path.'}
      </p>
      {mutation.isError && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900/50 dark:bg-amber-900/20 dark:text-amber-300">
          {(mutation.error as Error).message}
        </div>
      )}
      <button
        type="button"
        onClick={() => mutation.mutate(dataset.id)}
        disabled={mutation.isPending}
        className="self-start rounded-lg border border-amber-300 px-4 py-2 text-sm font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-50 dark:border-amber-700 dark:text-amber-200 dark:hover:bg-amber-900/30"
      >
        {mutation.isPending
          ? isArchived
            ? 'Unarchiving…'
            : 'Archiving…'
          : isArchived
            ? 'Unarchive'
            : 'Archive dataset'}
      </button>
    </section>
  )
}

function DangerZone({ dataset }: { dataset: Dataset }) {
  const del = useDeleteDataset()
  const router = useRouter()
  const [confirmText, setConfirmText] = useState('')

  const canDelete = confirmText.trim() === dataset.name

  const onDelete = () => {
    if (!canDelete) return
    del.mutate(dataset.id, {
      onSuccess: () => {
        router.push('/preview/agents/datasets')
      },
    })
  }

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-red-200 bg-red-50/50 p-5 dark:border-red-900/40 dark:bg-red-900/10">
      <h2 className="text-sm font-medium text-red-700 dark:text-red-300">
        Danger zone
      </h2>
      <p className="text-xs text-red-700/80 dark:text-red-300/80">
        Deleting a dataset soft-deletes its cases and detaches any eval runs
        that referenced it. Past eval run results remain queryable by ID but
        stop appearing in list views. Type the dataset name to confirm.
      </p>
      <input
        type="text"
        value={confirmText}
        onChange={(e) => setConfirmText(e.target.value)}
        placeholder={dataset.name}
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
        {del.isPending ? 'Deleting…' : 'Delete dataset'}
      </button>
    </section>
  )
}

function EvalHistorySection({ datasetId }: { datasetId: string }) {
  // Show the 10 most recent eval-runs against this dataset. The
  // eval-runs list endpoint already accepts dataset_id; this is
  // pure UI on top.
  const query = useEvalRuns({ dataset_id: datasetId, limit: 10, page: 1 })
  const runs: EvalRun[] = query.data?.data ?? []

  if (query.isLoading) {
    return (
      <section className="flex flex-col gap-3">
        <SectionHeader datasetId={datasetId} />
        <div className="h-24 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      </section>
    )
  }

  if (query.isError || runs.length === 0) {
    // Hide entirely on error or empty — the section is "history";
    // no point taking up space when there's nothing to show.
    return null
  }

  return (
    <section className="flex flex-col gap-3">
      <SectionHeader datasetId={datasetId} total={query.data?.meta.total} />
      <ul className="flex flex-col gap-2">
        {runs.map((run) => (
          <EvalHistoryRow key={run.id} run={run} />
        ))}
      </ul>
    </section>
  )
}

function SectionHeader({
  datasetId,
  total,
}: {
  datasetId: string
  total?: number
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
        Eval history
      </h2>
      {typeof total === 'number' && total > 10 && (
        <Link
          href={`/preview/agents/eval-runs?dataset_id=${datasetId}`}
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

function TriggerEvalSection({ dataset }: { dataset: Dataset }) {
  const [open, setOpen] = useState(false)
  const [workflowVersionId, setWorkflowVersionId] = useState('')
  const [strategy, setStrategy] = useState<AssertionStrategy>('exact_match')
  const [judgeModelId, setJudgeModelId] = useState('openai:gpt-4o-mini')
  const trigger = useTriggerEval()
  const router = useRouter()

  // Workflows for the picker — operators pick the workflow,
  // the form auto-uses its current_version_id. Drafts (no
  // version) are listed but disabled with a hint. A paste-
  // UUID fallback is still rendered below for the rare case
  // an operator wants to eval an older version.
  //
  // Scoped to the dataset's workspace: cross-workspace picks
  // would fail server-side on the trigger. Archived workflows
  // are filtered client-side — the picker mirrors the user-
  // facing "active" default everywhere else.
  const workflowsQuery = useWorkflows({
    limit: 100,
    page: 1,
    workspace_id: dataset.workspace_id,
  })
  const pickableWorkflows = (workflowsQuery.data?.data ?? []).filter(
    (w) => w.archived_at === null,
  )
  // If every active workflow is a draft (no current_version_id),
  // the picker would render a list of disabled options with no
  // operator-actionable hint. Detect that here so the
  // placeholder copy can point at the right next step.
  const allDrafts =
    pickableWorkflows.length > 0 &&
    pickableWorkflows.every((w) => w.current_version_id === null)

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    trigger.mutate(
      {
        dataset_id: dataset.id,
        workflow_version_id: workflowVersionId.trim(),
        assertion_strategy: strategy,
        judge_model_id: strategy === 'llm_judge' ? judgeModelId.trim() : null,
      },
      {
        onSuccess: (run) => {
          router.push(`/preview/agents/eval-runs/${run.id}`)
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
        Run eval
      </button>
    )
  }

  return (
    <form
      onSubmit={submit}
      className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
    >
      <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
        Trigger eval run
      </h2>

      <Field label="Workflow">
        <select
          value={
            pickableWorkflows.find(
              (w) => w.current_version_id === workflowVersionId,
            )?.id ?? ''
          }
          onChange={(e) => {
            const w = pickableWorkflows.find((wf) => wf.id === e.target.value)
            setWorkflowVersionId(w?.current_version_id ?? '')
          }}
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
        >
          <option value="">
            {workflowsQuery.isLoading
              ? 'Loading…'
              : pickableWorkflows.length === 0
                ? 'No active workflows in this workspace'
                : allDrafts
                  ? 'All workflows are drafts — publish a version first'
                  : 'Select a workflow'}
          </option>
          {pickableWorkflows.map((w) => (
            <option key={w.id} value={w.id} disabled={!w.current_version_id}>
              {w.name}
              {!w.current_version_id ? ' (draft — no version)' : ''}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Or paste a specific workflow_version_id (optional)">
        <input
          type="text"
          value={workflowVersionId}
          onChange={(e) => setWorkflowVersionId(e.target.value)}
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 font-mono text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
          placeholder="uuid — auto-filled by the picker above"
        />
      </Field>

      <fieldset className="flex flex-col gap-2">
        <legend className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
          Assertion strategy
        </legend>
        {(
          [
            ['exact_match', 'Exact match', 'Python == on actual vs expected'],
            [
              'json_schema',
              'JSON Schema',
              'expected_output treated as a JSON Schema',
            ],
            [
              'llm_judge',
              'LLM judge',
              'grader LLM scores actual against expected as a rubric',
            ],
          ] as [AssertionStrategy, string, string][]
        ).map(([value, label, hint]) => (
          <label
            key={value}
            className="flex cursor-pointer items-start gap-2 text-sm text-slate-700 dark:text-slate-300"
          >
            <input
              type="radio"
              name="strategy"
              value={value}
              checked={strategy === value}
              onChange={() => setStrategy(value)}
              className="mt-0.5"
            />
            <span>
              <span className="font-medium">{label}</span>
              <span className="ml-2 text-xs text-slate-500 dark:text-slate-400">
                {hint}
              </span>
            </span>
          </label>
        ))}
      </fieldset>

      {strategy === 'llm_judge' && (
        <Field label="Judge model id">
          <input
            type="text"
            required
            value={judgeModelId}
            onChange={(e) => setJudgeModelId(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 font-mono text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
            placeholder="openai:gpt-4o-mini"
          />
        </Field>
      )}

      {trigger.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">
          {(trigger.error as Error).message}
        </div>
      )}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={
            trigger.isPending ||
            workflowVersionId.trim().length === 0 ||
            (strategy === 'llm_judge' && judgeModelId.trim().length === 0)
          }
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          {trigger.isPending ? 'Submitting…' : 'Trigger'}
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

function Field({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
        {label}
      </label>
      {children}
    </div>
  )
}

function CasesSection({
  cases,
  isLoading,
  isError,
  errorMessage,
  datasetId,
  nextOrderIndex,
}: {
  cases: DatasetCase[]
  isLoading: boolean
  isError: boolean
  errorMessage?: string
  datasetId: string
  nextOrderIndex: number
}) {
  const [search, setSearch] = useState('')
  const trimmed = search.trim().toLowerCase()
  // Client-side filter — the cases endpoint returns the full
  // (unpaginated) list, and a dataset with thousands of cases
  // is out of v1 scope anyway. Case-insensitive substring.
  const visible = trimmed
    ? cases.filter((c) => c.name.toLowerCase().includes(trimmed))
    : cases

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
          Cases
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <AddCaseForm datasetId={datasetId} nextOrderIndex={nextOrderIndex} />
          <BulkAddCases datasetId={datasetId} nextOrderIndex={nextOrderIndex} />
        </div>
      </div>
      {cases.length > 0 && (
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter cases by name…"
          className="w-full max-w-md rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
        />
      )}
      {isLoading ? (
        <CasesSkeleton />
      ) : isError ? (
        <ErrorBanner message={errorMessage ?? 'Unknown error'} />
      ) : cases.length === 0 ? (
        <EmptyCases />
      ) : visible.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
          No cases match{' '}
          <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono dark:bg-slate-800">
            {search.trim()}
          </code>
          .
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {visible.map((c) => (
            <CaseRow
              key={c.id}
              caseItem={c}
              // Show the persisted order_index, not the array
              // position. After deletes the two diverge — the array
              // becomes [0,1,5,7] while ``indexOf(c)+1`` would say
              // 1,2,3,4. CSV exports + the bulk-add nextOrderIndex
              // math both key off order_index, so the UI should
              // too. M5.88i fix.
              index={c.order_index}
              datasetId={datasetId}
            />
          ))}
        </ul>
      )}
    </section>
  )
}

function AddCaseForm({
  datasetId,
  nextOrderIndex,
}: {
  datasetId: string
  nextOrderIndex: number
}) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [inputText, setInputText] = useState('{\n  "text": "example input"\n}')
  const [expectedText, setExpectedText] = useState('')
  const [parseError, setParseError] = useState<string | null>(null)
  const create = useCreateDatasetCase(datasetId)

  const reset = () => {
    setName('')
    setInputText('{\n  "text": "example input"\n}')
    setExpectedText('')
    setParseError(null)
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    setParseError(null)

    // Parse input JSON. Required + must be an object so the
    // backend's ``input_data: dict`` constraint passes.
    let inputData: Record<string, unknown>
    try {
      const parsed = JSON.parse(inputText)
      if (
        typeof parsed !== 'object' ||
        parsed === null ||
        Array.isArray(parsed)
      ) {
        setParseError('input must be a JSON object')
        return
      }
      inputData = parsed as Record<string, unknown>
    } catch (err) {
      setParseError(
        `input JSON parse failed: ${err instanceof Error ? err.message : 'unknown'}`,
      )
      return
    }

    // Expected output is optional — empty textarea → null
    // (qualitative case). Otherwise parse + require object.
    let expectedData: Record<string, unknown> | null = null
    if (expectedText.trim()) {
      try {
        const parsed = JSON.parse(expectedText)
        if (
          typeof parsed !== 'object' ||
          parsed === null ||
          Array.isArray(parsed)
        ) {
          setParseError('expected_output must be a JSON object')
          return
        }
        expectedData = parsed as Record<string, unknown>
      } catch (err) {
        setParseError(
          `expected JSON parse failed: ${err instanceof Error ? err.message : 'unknown'}`,
        )
        return
      }
    }

    create.mutate(
      {
        name: name.trim(),
        input_data: inputData,
        expected_output: expectedData,
        order_index: nextOrderIndex,
      },
      {
        onSuccess: () => {
          reset()
          setOpen(false)
        },
      },
    )
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="rounded-md border border-emerald-500 px-3 py-1 text-xs font-medium text-emerald-600 hover:bg-emerald-50 dark:border-emerald-600 dark:text-emerald-400 dark:hover:bg-emerald-900/20"
      >
        + Add case
      </button>
    )
  }

  return (
    <form
      onSubmit={submit}
      className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:col-span-full dark:border-slate-800 dark:bg-slate-900"
    >
      <h3 className="text-sm font-medium text-slate-700 dark:text-slate-300">
        Add case
      </h3>
      <div className="flex flex-col gap-1">
        <label className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
          Name
        </label>
        <input
          type="text"
          required
          minLength={1}
          maxLength={256}
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
          placeholder="case-rfi-with-concrete-spec"
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <label className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
            Input (JSON)
          </label>
          <textarea
            rows={8}
            required
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 font-mono text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
            Expected output (JSON, optional)
          </label>
          <textarea
            rows={8}
            value={expectedText}
            onChange={(e) => setExpectedText(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 font-mono text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
            placeholder="Leave blank for qualitative cases"
          />
        </div>
      </div>
      {(parseError || create.isError) && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">
          {parseError ?? (create.error as Error).message}
        </div>
      )}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={create.isPending || name.trim().length === 0}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          {create.isPending ? 'Adding…' : 'Add case'}
        </button>
        <button
          type="button"
          onClick={() => {
            reset()
            setOpen(false)
          }}
          className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

type BulkRowResult =
  | { kind: 'pending' }
  | { kind: 'ok' }
  | { kind: 'error'; message: string }

function BulkAddCases({
  datasetId,
  nextOrderIndex,
}: {
  datasetId: string
  nextOrderIndex: number
}) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState(
    '[\n  {\n    "name": "case-1",\n    "input_data": { "text": "..." },\n    "expected_output": { "text": "..." }\n  }\n]',
  )
  const [parseError, setParseError] = useState<string | null>(null)
  const [results, setResults] = useState<BulkRowResult[]>([])
  const [submitting, setSubmitting] = useState(false)
  const qc = useQueryClient()

  const reset = () => {
    setParseError(null)
    setResults([])
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    reset()

    let parsed: unknown
    try {
      parsed = JSON.parse(text)
    } catch (err) {
      setParseError(
        `JSON parse failed: ${err instanceof Error ? err.message : 'unknown'}`,
      )
      return
    }
    if (!Array.isArray(parsed)) {
      setParseError('Top-level value must be a JSON array of case objects.')
      return
    }
    if (parsed.length === 0) {
      setParseError('Array is empty — nothing to import.')
      return
    }

    // Validate each row's shape up-front so we don't half-import
    // and leave the operator with a fail-then-retry scenario.
    const payloads: DatasetCaseCreatePayload[] = []
    for (let i = 0; i < parsed.length; i++) {
      const row = parsed[i]
      if (typeof row !== 'object' || row === null || Array.isArray(row)) {
        setParseError(`Row ${i + 1}: must be a JSON object.`)
        return
      }
      const r = row as Record<string, unknown>
      if (typeof r.name !== 'string' || r.name.trim().length === 0) {
        setParseError(`Row ${i + 1}: missing or empty "name".`)
        return
      }
      if (
        typeof r.input_data !== 'object' ||
        r.input_data === null ||
        Array.isArray(r.input_data)
      ) {
        setParseError(`Row ${i + 1}: "input_data" must be a JSON object.`)
        return
      }
      if (
        r.expected_output !== undefined &&
        r.expected_output !== null &&
        (typeof r.expected_output !== 'object' ||
          Array.isArray(r.expected_output))
      ) {
        setParseError(
          `Row ${i + 1}: "expected_output" must be a JSON object, null, or omitted.`,
        )
        return
      }
      payloads.push({
        name: r.name.trim(),
        input_data: r.input_data as Record<string, unknown>,
        expected_output:
          r.expected_output === undefined
            ? null
            : (r.expected_output as Record<string, unknown> | null),
        order_index: nextOrderIndex + i,
      })
    }

    // Sequential POSTs to keep order_index strictly monotonic.
    // For 50–100 cases this is a couple seconds; if we ever
    // need bulk perf we'd add a server-side bulk endpoint.
    setSubmitting(true)
    setResults(payloads.map(() => ({ kind: 'pending' as const })))
    for (let i = 0; i < payloads.length; i++) {
      try {
        await postDatasetCase({ datasetId, body: payloads[i] })
        setResults((prev) => {
          const next = [...prev]
          next[i] = { kind: 'ok' }
          return next
        })
      } catch (err) {
        const message = err instanceof Error ? err.message : 'unknown error'
        setResults((prev) => {
          const next = [...prev]
          next[i] = { kind: 'error', message }
          return next
        })
        // Stop on first failure — the next-index sequence would
        // skip if the server already assigned order. Operators
        // can fix the bad row and re-paste the rest.
        break
      }
    }
    qc.invalidateQueries({ queryKey: ['agents-datasets', 'cases', datasetId] })
    setSubmitting(false)
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="rounded-md border border-emerald-500 px-3 py-1 text-xs font-medium text-emerald-600 hover:bg-emerald-50 dark:border-emerald-600 dark:text-emerald-400 dark:hover:bg-emerald-900/20"
      >
        + Bulk add
      </button>
    )
  }

  const okCount = results.filter((r) => r.kind === 'ok').length
  const errored = results.find((r) => r.kind === 'error') as
    | { kind: 'error'; message: string }
    | undefined

  return (
    <form
      onSubmit={submit}
      className="flex w-full flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:col-span-full dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-medium text-slate-700 dark:text-slate-300">
          Bulk add cases
        </h3>
        <span className="text-xs text-slate-500 dark:text-slate-400">
          JSON array of{' '}
          <code className="rounded bg-slate-100 px-1 font-mono dark:bg-slate-800">
            {'{ name, input_data, expected_output? }'}
          </code>
        </span>
      </div>
      <textarea
        rows={14}
        required
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 font-mono text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
      />
      {parseError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">
          {parseError}
        </div>
      )}
      {results.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs dark:border-slate-700 dark:bg-slate-950">
          <span className="text-slate-700 dark:text-slate-300">
            {okCount} / {results.length} created
          </span>
          {errored && (
            <span className="ml-2 text-rose-600 dark:text-rose-400">
              · stopped on first error: {errored.message}
            </span>
          )}
        </div>
      )}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          {submitting ? 'Importing…' : 'Import all'}
        </button>
        <button
          type="button"
          onClick={() => {
            setOpen(false)
            reset()
          }}
          className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          Close
        </button>
      </div>
    </form>
  )
}

function CaseRow({
  caseItem,
  index,
  datasetId,
}: {
  caseItem: DatasetCase
  index: number
  datasetId: string
}) {
  // Each case is collapsed by default — operators scan the
  // list, expand the one they care about, then drill into
  // the JSON.
  const [open, setOpen] = useState(false)
  const del = useDeleteDatasetCase(datasetId)
  return (
    <li className="rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-3 px-4 py-3 text-left"
      >
        <span className="font-mono text-xs text-slate-400 dark:text-slate-500">
          {index}
        </span>
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="truncate text-sm text-slate-700 dark:text-slate-300">
            {caseItem.name}
          </span>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {caseItem.expected_output === null
              ? 'Qualitative — no expected output'
              : 'Expected output set'}
          </span>
        </div>
        <span className="text-xs text-slate-400 dark:text-slate-500">
          {open ? 'Hide' : 'View'}
        </span>
      </button>
      {open && (
        <div className="border-t border-slate-100 px-4 py-3 dark:border-slate-800">
          <div className="grid gap-4 sm:grid-cols-2">
            <JsonPanel title="Input" data={caseItem.input_data} />
            <JsonPanel
              title="Expected output"
              data={caseItem.expected_output}
              placeholder="No expected output (qualitative case)"
            />
          </div>
          <div className="mt-3 flex justify-end">
            <button
              type="button"
              onClick={() => {
                if (
                  confirm(
                    `Delete case "${caseItem.name}"? Past eval runs that referenced this case keep their scores but the case can't be re-evaluated.`,
                  )
                ) {
                  del.mutate(caseItem.id)
                }
              }}
              disabled={del.isPending}
              className="rounded-md border border-rose-200 px-3 py-1 text-xs font-medium text-rose-600 hover:bg-rose-50 disabled:opacity-50 dark:border-rose-900/50 dark:text-rose-400 dark:hover:bg-rose-900/20"
            >
              {del.isPending ? 'Deleting…' : 'Delete case'}
            </button>
          </div>
          {del.isError && (
            <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">
              Delete failed: {(del.error as Error).message}
            </div>
          )}
        </div>
      )}
    </li>
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

function CasesSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="h-12 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800"
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

function EmptyCases() {
  return (
    <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
      No cases yet. Add fixtures via{' '}
      <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono dark:bg-slate-800">
        POST /api/v1/agents/datasets/{'{id}'}/cases
      </code>
      .
    </div>
  )
}

/** Header-line workspace badge. Mirrors the WorkspaceLine on
 *  the workflow detail page so multi-workspace operators
 *  landing via deep link have an immediate cue about which
 *  workspace owns the dataset. */
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
