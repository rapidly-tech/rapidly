'use client'

import {
  CopyAsCurlButton,
  bashSingleQuoteEscape,
} from '@/components/agents/CopyAsCurlButton'
import { CopyId } from '@/components/agents/CopyId'
import { JsonPanel } from '@/components/agents/JsonPanel'
import {
  type EvalRun,
  type EvalRunCase,
  type EvalRunStatus,
  useCancelEvalRun,
  useDataset,
  useEvalRun,
  useEvalRunCases,
} from '@/hooks/api/agents'
import { formatDuration, formatTime } from '@/utils/agents/datetime'
import {
  type CaseOutcome,
  buildCasesCsv,
  classifyCase,
} from '@/utils/agents/eval-export'
import Link from 'next/link'
import { use, useState } from 'react'

const TERMINAL_EVAL: EvalRunStatus[] = ['succeeded', 'failed', 'cancelled']

export default function EvalRunDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const evalQuery = useEvalRun(id)
  const evalRun = evalQuery.data
  const isActive = evalRun ? !TERMINAL_EVAL.includes(evalRun.status) : false
  const casesQuery = useEvalRunCases(id, { isEvalActive: isActive })

  const cases: EvalRunCase[] = casesQuery.data ?? []

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-16">
      <BackLink />

      {evalQuery.isLoading ? (
        <HeaderSkeleton />
      ) : evalQuery.isError ? (
        <ErrorBanner message={(evalQuery.error as Error).message} />
      ) : evalRun ? (
        <>
          <Header evalRun={evalRun} />
          <SummaryStats evalRun={evalRun} />
          {evalRun.error_message && (
            <RunError message={evalRun.error_message} />
          )}
          <CasesSection
            evalRunId={evalRun.id}
            cases={cases}
            isLoading={casesQuery.isLoading}
            isError={casesQuery.isError}
            errorMessage={
              casesQuery.error instanceof Error
                ? casesQuery.error.message
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
      href="/preview/agents/eval-runs"
      className="self-start text-xs font-medium tracking-wider text-emerald-600 uppercase hover:text-emerald-700 dark:text-emerald-400 dark:hover:text-emerald-300"
    >
      ← Eval runs
    </Link>
  )
}

function Header({ evalRun }: { evalRun: EvalRun }) {
  const cancel = useCancelEvalRun()
  const canCancel = !TERMINAL_EVAL.includes(evalRun.status)
  return (
    <header className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-semibold text-slate-900 dark:text-slate-100">
              Eval run
            </h1>
            <StatusPill status={evalRun.status} />
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {evalRun.assertion_strategy}
            </span>
          </div>
          <ContextLinks evalRun={evalRun} />
          <CopyId id={evalRun.id} label="eval run ID" />
          <CopyEvalAsCurl evalRun={evalRun} />
        </div>
        {canCancel && (
          <button
            type="button"
            onClick={() => {
              if (
                confirm(
                  'Cancel this eval run? Cases already scored keep their results; remaining cases are skipped.',
                )
              ) {
                cancel.mutate(evalRun.id)
              }
            }}
            disabled={cancel.isPending}
            className="shrink-0 rounded-md border border-rose-200 px-3 py-1 text-xs font-medium text-rose-600 hover:bg-rose-50 disabled:opacity-50 dark:border-rose-900/50 dark:text-rose-400 dark:hover:bg-rose-900/20"
          >
            {cancel.isPending ? 'Cancelling…' : 'Cancel'}
          </button>
        )}
      </div>
      {cancel.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">
          Cancel failed: {(cancel.error as Error).message}
        </div>
      )}
    </header>
  )
}

function ContextLinks({ evalRun }: { evalRun: EvalRun }) {
  // Resolve dataset name via useDataset — same hook the
  // dataset-filter badge on the eval-runs list uses (M5.31).
  // Falls back to the short id when the dataset is unknown or
  // still loading; the short id is enough to copy / paste even
  // without the name.
  const datasetQuery = useDataset(evalRun.dataset_id)
  const datasetLabel =
    datasetQuery.data?.name ?? `id ${evalRun.dataset_id.slice(0, 8)}`

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
      <span>
        Dataset:{' '}
        <Link
          href={`/preview/agents/datasets/${evalRun.dataset_id}`}
          className="font-medium text-emerald-700 hover:text-emerald-800 dark:text-emerald-300 dark:hover:text-emerald-200"
        >
          {datasetLabel}
        </Link>
      </span>
      <span>
        Workflow version:{' '}
        <Link
          // No workflow detail route by version-id alone (versions
          // are nested under their workflow), so the cross-link
          // lands on the eval-runs list filtered to siblings of the
          // same version — the operator can see what else has run
          // against the same pinned graph.
          href={`/preview/agents/eval-runs?workflow_version_id=${evalRun.workflow_version_id}`}
          className="font-mono font-medium text-emerald-700 hover:text-emerald-800 dark:text-emerald-300 dark:hover:text-emerald-200"
        >
          id {evalRun.workflow_version_id.slice(0, 8)}
        </Link>
      </span>
    </div>
  )
}

function CopyEvalAsCurl({ evalRun }: { evalRun: EvalRun }) {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? '<base-url>'
  const payload: Record<string, unknown> = {
    workflow_version_id: evalRun.workflow_version_id,
    dataset_id: evalRun.dataset_id,
    assertion_strategy: evalRun.assertion_strategy,
  }
  // judge_model_id is only meaningful (and only required) for the
  // llm_judge strategy. Omit it elsewhere so a re-run with
  // exact_match doesn't leak an irrelevant model id.
  if (evalRun.assertion_strategy === 'llm_judge' && evalRun.judge_model_id) {
    payload.judge_model_id = evalRun.judge_model_id
  }
  const body = JSON.stringify(payload, null, 2)
  const command = [
    `curl -X POST '${baseUrl}/api/v1/agents/eval-runs/' \\`,
    `  -H 'Content-Type: application/json' \\`,
    `  --cookie 'sid=<your-session-cookie>' \\`,
    `  -d '${bashSingleQuoteEscape(body)}'`,
  ].join('\n')
  return (
    <CopyAsCurlButton
      command={command}
      title="Copies a curl command that re-triggers this eval with the same dataset + workflow_version + strategy. Replace the session cookie value before running."
    />
  )
}

function SummaryStats({ evalRun }: { evalRun: EvalRun }) {
  const passRate =
    evalRun.case_count > 0
      ? Math.round((evalRun.pass_count / evalRun.case_count) * 100)
      : null
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
      <Stat label="Cases" value={String(evalRun.case_count)} />
      <Stat
        label="Passed"
        value={String(evalRun.pass_count)}
        intent="success"
      />
      <Stat label="Failed" value={String(evalRun.fail_count)} intent="danger" />
      <Stat
        label="Errored"
        value={String(evalRun.error_count)}
        intent={evalRun.error_count > 0 ? 'danger' : 'muted'}
      />
      <Stat
        label="Pass rate"
        value={passRate !== null ? `${passRate}%` : '—'}
      />
      <Stat
        label="Started"
        value={evalRun.started_at ? formatTime(evalRun.started_at) : '—'}
      />
      <Stat
        label="Completed"
        value={evalRun.completed_at ? formatTime(evalRun.completed_at) : '—'}
      />
      <Stat
        label="Duration"
        value={formatDuration(evalRun.started_at, evalRun.completed_at)}
      />
    </dl>
  )
}

function Stat({
  label,
  value,
  intent = 'default',
}: {
  label: string
  value: string
  intent?: 'default' | 'success' | 'danger' | 'muted'
}) {
  const valueClass =
    intent === 'success'
      ? 'text-emerald-600 dark:text-emerald-400'
      : intent === 'danger'
        ? 'text-rose-600 dark:text-rose-400'
        : intent === 'muted'
          ? 'text-slate-400 dark:text-slate-500'
          : 'text-slate-700 dark:text-slate-200'
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
        {label}
      </dt>
      <dd className={`text-lg font-semibold ${valueClass}`}>{value}</dd>
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

const CASE_FILTERS: { label: string; value: CaseOutcome | null }[] = [
  { label: 'All', value: null },
  { label: 'Passed', value: 'passed' },
  { label: 'Failed', value: 'failed' },
  { label: 'Errored', value: 'errored' },
  { label: 'Qualitative', value: 'qualitative' },
]

function CasesSection({
  evalRunId,
  cases,
  isLoading,
  isError,
  errorMessage,
}: {
  evalRunId: string
  cases: EvalRunCase[]
  isLoading: boolean
  isError: boolean
  errorMessage?: string
}) {
  const [outcome, setOutcome] = useState<CaseOutcome | null>(null)
  const [search, setSearch] = useState('')
  const trimmedSearch = search.trim().toLowerCase()

  // Tag every case with its outcome once so the chip counts +
  // the visible-row filter use the same classification — no
  // chance of "chip says 3 failed, list shows 4".
  const classified = cases.map((c) => ({
    caseItem: c,
    outcome: classifyCase(c),
  }))
  const counts: Record<CaseOutcome, number> = {
    passed: 0,
    failed: 0,
    errored: 0,
    qualitative: 0,
  }
  for (const { outcome } of classified) counts[outcome] += 1

  const visible = classified.filter((c) => {
    if (outcome !== null && c.outcome !== outcome) return false
    if (
      trimmedSearch &&
      !c.caseItem.case_name.toLowerCase().includes(trimmedSearch)
    )
      return false
    return true
  })

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
          Cases
        </h2>
        {cases.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <CaseFilter value={outcome} onChange={setOutcome} counts={counts} />
            <ExportCsvButton evalRunId={evalRunId} cases={cases} />
          </div>
        )}
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
      {cases.length > 0 && (outcome !== null || trimmedSearch) && (
        <button
          type="button"
          onClick={() => {
            setOutcome(null)
            setSearch('')
          }}
          className="self-start text-xs text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 dark:hover:text-emerald-300"
        >
          Clear filters
        </button>
      )}
      {isLoading ? (
        <CasesSkeleton />
      ) : isError ? (
        <ErrorBanner message={errorMessage ?? 'Unknown error'} />
      ) : cases.length === 0 ? (
        <EmptyCases />
      ) : visible.length === 0 ? (
        <EmptyCasesFiltered
          outcome={outcome}
          search={trimmedSearch ? search.trim() : null}
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {visible.map(({ caseItem }, idx) => (
            <CaseRow key={caseItem.id} caseItem={caseItem} index={idx + 1} />
          ))}
        </ul>
      )}
    </section>
  )
}

function EmptyCasesFiltered({
  outcome,
  search,
}: {
  outcome: CaseOutcome | null
  search: string | null
}) {
  // Both filter axes can fire together. Compose the empty
  // banner so operators see which filter is hiding rows.
  return (
    <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
      No
      {outcome && <> {outcome}</>} cases
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

function CaseFilter({
  value,
  onChange,
  counts,
}: {
  value: CaseOutcome | null
  onChange: (next: CaseOutcome | null) => void
  counts: Record<CaseOutcome, number>
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {CASE_FILTERS.map((filter) => {
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

function ExportCsvButton({
  evalRunId,
  cases,
}: {
  evalRunId: string
  cases: EvalRunCase[]
}) {
  const onExport = () => {
    const csv = buildCasesCsv(cases)
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    // Filename keeps the short eval-run id so a folder of
    // exports stays addressable. Full id would be unwieldy.
    a.download = `eval-run-${evalRunId.slice(0, 8)}-cases.csv`
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

function CaseRow({
  caseItem,
  index,
}: {
  caseItem: EvalRunCase
  index: number
}) {
  const [open, setOpen] = useState(false)
  return (
    <li className="rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="grid w-full grid-cols-[auto_auto_1fr_auto] items-center gap-3 px-4 py-3 text-left"
      >
        <span className="font-mono text-xs text-slate-400 dark:text-slate-500">
          {index}
        </span>
        <CaseStatusPill caseItem={caseItem} />
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="truncate text-sm text-slate-700 dark:text-slate-300">
            {caseItem.case_name}
          </span>
          {caseItem.judge_reason && (
            <span className="truncate text-xs text-slate-500 dark:text-slate-400">
              {caseItem.judge_reason}
            </span>
          )}
          {caseItem.error_message && (
            <span className="truncate text-xs text-rose-600 dark:text-rose-400">
              {caseItem.error_message}
            </span>
          )}
        </div>
        <span className="text-xs text-slate-400 dark:text-slate-500">
          {open ? 'Hide' : 'View'}
        </span>
      </button>
      {open && (
        <div className="grid gap-4 border-t border-slate-100 px-4 py-3 sm:grid-cols-3 dark:border-slate-800">
          <JsonPanel title="Input" data={caseItem.case_input_data} />
          <JsonPanel
            title="Expected"
            data={caseItem.case_expected_output}
            placeholder="Qualitative case"
          />
          <JsonPanel
            title="Actual"
            data={caseItem.actual_output}
            placeholder="—"
          />
        </div>
      )}
    </li>
  )
}

function CaseStatusPill({ caseItem }: { caseItem: EvalRunCase }) {
  if (caseItem.error_message) {
    return (
      <span className="rounded-md bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-700 dark:bg-rose-900/30 dark:text-rose-300">
        error
      </span>
    )
  }
  if (caseItem.passed === true) {
    return (
      <span className="rounded-md bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
        pass
      </span>
    )
  }
  if (caseItem.passed === false) {
    return (
      <span className="rounded-md bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-700 dark:bg-rose-900/30 dark:text-rose-300">
        fail
      </span>
    )
  }
  // passed === null + no error: qualitative case (no
  // expected_output, runner recorded actual without scoring).
  return (
    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
      qualitative
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

function HeaderSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      <div className="h-9 w-48 animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
      <div className="h-4 w-80 animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
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
      No cases recorded yet — the runner may still be in flight.
    </div>
  )
}
