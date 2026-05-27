'use client'

import { type Dataset, useDatasets } from '@/hooks/api/agents'
import Link from 'next/link'

export default function DatasetsListPage() {
  const query = useDatasets({ limit: 50, page: 1 })
  const datasets: Dataset[] = query.data?.data ?? []

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-16">
      <Header />

      {query.isLoading ? (
        <Skeleton />
      ) : query.isError ? (
        <ErrorBanner message={(query.error as Error).message} />
      ) : datasets.length === 0 ? (
        <Empty />
      ) : (
        <DatasetList datasets={datasets} />
      )}
    </main>
  )
}

function Header() {
  return (
    <header className="flex flex-col gap-3">
      <span className="text-xs font-medium tracking-wider text-emerald-600 uppercase dark:text-emerald-400">
        Rapidly · Agents
      </span>
      <h1 className="text-4xl font-semibold text-slate-900 dark:text-slate-100">
        Datasets
      </h1>
      <p className="max-w-2xl text-base leading-relaxed text-slate-600 dark:text-slate-400">
        Named bundles of input/expected-output fixtures the eval runner drives a
        workflow against. A dataset is reusable across workflows and versions —
        the same fixture compares two versions side-by-side.
      </p>
    </header>
  )
}

function DatasetList({ datasets }: { datasets: Dataset[] }) {
  return (
    <ul className="grid gap-3">
      {datasets.map((d) => (
        <li key={d.id}>
          <Link
            href={`/preview/agents/datasets/${d.id}`}
            className="group flex flex-col gap-2 rounded-lg border border-slate-200 bg-white p-5 transition hover:border-emerald-400 hover:shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:hover:border-emerald-600"
          >
            <span className="text-lg font-medium text-slate-900 dark:text-slate-100">
              {d.name}
            </span>
            {d.description && (
              <p className="text-sm text-slate-600 dark:text-slate-400">
                {d.description}
              </p>
            )}
            <span className="text-xs text-slate-400 dark:text-slate-500">
              Created {formatDate(d.created_at)}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

function Skeleton() {
  return (
    <div className="flex flex-col gap-3">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="h-24 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800"
        />
      ))}
    </div>
  )
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">
      Failed to load datasets: {message}
    </div>
  )
}

function Empty() {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-12 text-center dark:border-slate-800 dark:bg-slate-900/50">
      <p className="text-sm text-slate-500 dark:text-slate-400">
        No datasets yet.
      </p>
      <p className="max-w-md text-xs text-slate-400 dark:text-slate-500">
        Datasets are authored via the API today; the in-editor builder ships in
        a follow-up. Use{' '}
        <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-slate-700 dark:bg-slate-800 dark:text-slate-300">
          POST /api/v1/agents/datasets
        </code>{' '}
        to create one.
      </p>
    </div>
  )
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return iso
  }
}
