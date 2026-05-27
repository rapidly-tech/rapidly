'use client'

import { type Dataset, useCreateDataset, useDatasets } from '@/hooks/api/agents'
import { useListWorkspaces } from '@/hooks/api/org'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'

export default function DatasetsListPage() {
  const [search, setSearch] = useState('')
  const query = useDatasets({
    name: search.trim() || undefined,
    limit: 50,
    page: 1,
  })
  const datasets: Dataset[] = query.data?.data ?? []
  const workspacesQuery = useListWorkspaces({ limit: 50, page: 1 })
  const workspaceId = workspacesQuery.data?.data?.[0]?.id ?? null

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-16">
      <Header />

      {workspaceId && <CreateForm workspaceId={workspaceId} />}

      <SearchInput value={search} onChange={setSearch} />

      {query.isLoading ? (
        <Skeleton />
      ) : query.isError ? (
        <ErrorBanner message={(query.error as Error).message} />
      ) : datasets.length === 0 ? (
        search.trim() ? (
          <EmptySearch query={search.trim()} />
        ) : (
          <Empty />
        )
      ) : (
        <DatasetList datasets={datasets} />
      )}
    </main>
  )
}

function SearchInput({
  value,
  onChange,
}: {
  value: string
  onChange: (next: string) => void
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
        Search
      </label>
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Filter datasets by name…"
        className="w-full max-w-md rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
      />
    </div>
  )
}

function EmptySearch({ query }: { query: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
      No datasets match{' '}
      <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono dark:bg-slate-800">
        {query}
      </code>
      .
    </div>
  )
}

function CreateForm({ workspaceId }: { workspaceId: string }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const create = useCreateDataset()
  const router = useRouter()

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    create.mutate(
      {
        workspace_id: workspaceId,
        name: name.trim(),
        description: description.trim() || null,
      },
      {
        onSuccess: (dataset) => {
          router.push(`/preview/agents/datasets/${dataset.id}`)
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
        + New dataset
      </button>
    )
  }

  return (
    <form
      onSubmit={submit}
      className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
    >
      <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
        New dataset
      </h2>
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
          placeholder="rfi-triage-golden-set"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
          Description (optional)
        </label>
        <textarea
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
          placeholder="What workflows is this dataset for?"
        />
      </div>
      {create.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">
          {(create.error as Error).message}
        </div>
      )}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={create.isPending}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          {create.isPending ? 'Creating…' : 'Create'}
        </button>
        <button
          type="button"
          onClick={() => {
            setOpen(false)
            setName('')
            setDescription('')
          }}
          className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          Cancel
        </button>
      </div>
    </form>
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
        Use the &ldquo;+ New dataset&rdquo; button above to create one. Cases
        are added via{' '}
        <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-slate-700 dark:bg-slate-800 dark:text-slate-300">
          POST /api/v1/agents/datasets/{'{id}'}/cases
        </code>{' '}
        until the case authoring UI lands.
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
