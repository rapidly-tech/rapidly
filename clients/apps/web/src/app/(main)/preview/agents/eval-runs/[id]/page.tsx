'use client'

import {
  type EvalRun,
  type EvalRunCase,
  type EvalRunStatus,
  useEvalRun,
  useEvalRunCases,
} from '@/hooks/api/agents'
import Link from 'next/link'
import { use, useState } from 'react'

export default function EvalRunDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const evalQuery = useEvalRun(id)
  const casesQuery = useEvalRunCases(id)

  const evalRun = evalQuery.data
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
  return (
    <header className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <h1 className="text-3xl font-semibold text-slate-900 dark:text-slate-100">
          Eval run
        </h1>
        <StatusPill status={evalRun.status} />
        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          {evalRun.assertion_strategy}
        </span>
      </div>
      <p className="font-mono text-xs text-slate-500 dark:text-slate-400">
        {evalRun.id}
      </p>
    </header>
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

function CasesSection({
  cases,
  isLoading,
  isError,
  errorMessage,
}: {
  cases: EvalRunCase[]
  isLoading: boolean
  isError: boolean
  errorMessage?: string
}) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
        Cases
      </h2>
      {isLoading ? (
        <CasesSkeleton />
      ) : isError ? (
        <ErrorBanner message={errorMessage ?? 'Unknown error'} />
      ) : cases.length === 0 ? (
        <EmptyCases />
      ) : (
        <ul className="flex flex-col gap-2">
          {cases.map((c, idx) => (
            <CaseRow key={c.id} caseItem={c} index={idx + 1} />
          ))}
        </ul>
      )}
    </section>
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

function JsonPanel({
  title,
  data,
  placeholder,
}: {
  title: string
  data: Record<string, unknown> | null
  placeholder?: string
}) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
        {title}
      </h3>
      {data === null ? (
        <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
          {placeholder ?? '—'}
        </p>
      ) : (
        <pre className="overflow-x-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-300">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
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
