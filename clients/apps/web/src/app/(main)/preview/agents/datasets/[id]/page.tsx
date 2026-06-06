'use client'

import {
  type AssertionStrategy,
  type Dataset,
  type DatasetCase,
  useDataset,
  useDatasetCases,
  useTriggerEval,
} from '@/hooks/api/agents'
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
          <TriggerEvalSection dataset={dataset} />
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
  return (
    <header className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <h1 className="text-3xl font-semibold text-slate-900 dark:text-slate-100">
          {dataset.name}
        </h1>
        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          {caseCount} case{caseCount === 1 ? '' : 's'}
        </span>
      </div>
      {dataset.description && (
        <p className="max-w-2xl text-base leading-relaxed text-slate-600 dark:text-slate-400">
          {dataset.description}
        </p>
      )}
    </header>
  )
}

function TriggerEvalSection({ dataset }: { dataset: Dataset }) {
  const [open, setOpen] = useState(false)
  const [workflowVersionId, setWorkflowVersionId] = useState('')
  const [strategy, setStrategy] = useState<AssertionStrategy>('exact_match')
  const [judgeModelId, setJudgeModelId] = useState('openai:gpt-4o-mini')
  const trigger = useTriggerEval()
  const router = useRouter()

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

      <Field label="Workflow version id">
        <input
          type="text"
          required
          value={workflowVersionId}
          onChange={(e) => setWorkflowVersionId(e.target.value)}
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 font-mono text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
          placeholder="paste UUID from /workflows"
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
          disabled={trigger.isPending}
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
}: {
  cases: DatasetCase[]
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
  caseItem: DatasetCase
  index: number
}) {
  // Each case is collapsed by default — operators scan the
  // list, expand the one they care about, then drill into
  // the JSON.
  const [open, setOpen] = useState(false)
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
        <div className="grid gap-4 border-t border-slate-100 px-4 py-3 sm:grid-cols-2 dark:border-slate-800">
          <JsonPanel title="Input" data={caseItem.input_data} />
          <JsonPanel
            title="Expected output"
            data={caseItem.expected_output}
            placeholder="No expected output (qualitative case)"
          />
        </div>
      )}
    </li>
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
