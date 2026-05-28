'use client'

import {
  type VectorCollection,
  type VectorCollectionCreatePayload,
  useCreateVectorCollection,
  useDeleteVectorCollection,
  useUpdateVectorCollection,
  useVectorCollections,
} from '@/hooks/api/agents'
import { useListWorkspaces } from '@/hooks/api/org'
import { useState } from 'react'

const PAGE_SIZE = 20

export default function VectorCollectionsPage() {
  const workspacesQuery = useListWorkspaces({ limit: 50, page: 1 })
  const workspaces = workspacesQuery.data?.data ?? []
  const [pickedWorkspaceId, setPickedWorkspaceId] = useState<string | null>(
    null,
  )
  const activeWorkspaceId = pickedWorkspaceId ?? workspaces[0]?.id ?? null

  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const onSearchChange = (next: string) => {
    setSearch(next)
    setPage(1)
  }
  const onWorkspaceChange = (next: string | null) => {
    setPickedWorkspaceId(next)
    setPage(1)
  }

  const query = useVectorCollections({
    workspace_id: activeWorkspaceId ?? undefined,
    name: search.trim() || undefined,
    limit: PAGE_SIZE,
    page,
  })
  const collections: VectorCollection[] = query.data?.data ?? []
  const meta = query.data?.meta

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-16">
      <Header />

      <WorkspaceSwitcher
        workspaces={workspaces.map((w) => ({ id: w.id, name: w.name }))}
        activeId={activeWorkspaceId}
        onChange={onWorkspaceChange}
      />

      {activeWorkspaceId && <CreateForm workspaceId={activeWorkspaceId} />}

      <SearchInput value={search} onChange={onSearchChange} />

      {query.isLoading ? (
        <Skeleton />
      ) : query.isError ? (
        <ErrorBanner message={(query.error as Error).message} />
      ) : collections.length === 0 ? (
        search.trim() ? (
          <EmptySearch query={search.trim()} />
        ) : (
          <Empty />
        )
      ) : (
        <>
          <CollectionList collections={collections} />
          {meta && (
            <Pagination
              page={page}
              pages={meta.pages}
              total={meta.total}
              onPageChange={setPage}
            />
          )}
        </>
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
        placeholder="Filter collections by name…"
        className="w-full max-w-md rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
      />
    </div>
  )
}

function EmptySearch({ query }: { query: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
      No collections match{' '}
      <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono dark:bg-slate-800">
        {query}
      </code>
      .
    </div>
  )
}

function Pagination({
  page,
  pages,
  total,
  onPageChange,
}: {
  page: number
  pages: number
  total: number
  onPageChange: (next: number) => void
}) {
  if (pages <= 1) return null
  return (
    <div className="flex items-center justify-between gap-3 text-xs text-slate-500 dark:text-slate-400">
      <span>
        Page <span className="font-mono">{page}</span> of{' '}
        <span className="font-mono">{pages}</span> ·{' '}
        <span className="font-mono">{total}</span> total
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          ← Prev
        </button>
        <button
          type="button"
          onClick={() => onPageChange(Math.min(pages, page + 1))}
          disabled={page >= pages}
          className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          Next →
        </button>
      </div>
    </div>
  )
}

function Header() {
  return (
    <header className="flex flex-col gap-3">
      <span className="text-xs font-medium tracking-wider text-emerald-600 uppercase dark:text-emerald-400">
        Rapidly · Agents
      </span>
      <h1 className="text-4xl font-semibold text-slate-900 dark:text-slate-100">
        Vector collections
      </h1>
      <p className="max-w-2xl text-base leading-relaxed text-slate-600 dark:text-slate-400">
        Named bundles of embedded chunks that the rag_search node queries
        against. A collection pins its embedding model + dimension at create
        time — changing the model would invalidate every chunk.
      </p>
    </header>
  )
}

function WorkspaceSwitcher({
  workspaces,
  activeId,
  onChange,
}: {
  workspaces: { id: string; name: string }[]
  activeId: string | null
  onChange: (id: string) => void
}) {
  // Hidden for single-workspace operators (same contract as
  // the workflows + datasets + credentials switchers).
  if (workspaces.length <= 1) return null
  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
        Workspace
      </label>
      <select
        value={activeId ?? ''}
        onChange={(e) => onChange(e.target.value)}
        className="w-full max-w-md rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
      >
        {workspaces.map((w) => (
          <option key={w.id} value={w.id}>
            {w.name}
          </option>
        ))}
      </select>
    </div>
  )
}

function CreateForm({ workspaceId }: { workspaceId: string }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [embeddingModel, setEmbeddingModel] = useState(
    'openai:text-embedding-3-small',
  )
  const [dimensions, setDimensions] = useState('1536')
  const create = useCreateVectorCollection()

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const dim = parseInt(dimensions, 10)
    if (Number.isNaN(dim) || dim < 1) return
    const body: VectorCollectionCreatePayload = {
      workspace_id: workspaceId,
      name: name.trim(),
      embedding_model: embeddingModel.trim(),
      dimensions: dim,
    }
    create.mutate(body, {
      onSuccess: () => {
        setName('')
        setOpen(false)
      },
    })
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="self-start rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
      >
        + New collection
      </button>
    )
  }

  return (
    <form
      onSubmit={submit}
      className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
    >
      <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
        New vector collection
      </h2>
      <Field label="Name">
        <input
          type="text"
          required
          minLength={1}
          maxLength={256}
          value={name}
          onChange={(e) => setName(e.target.value)}
          className={inputClass}
          placeholder="construction-docs"
        />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Embedding model">
          <input
            type="text"
            required
            value={embeddingModel}
            onChange={(e) => setEmbeddingModel(e.target.value)}
            className={`${inputClass} font-mono text-xs`}
            placeholder="openai:text-embedding-3-small"
          />
        </Field>
        <Field label="Dimensions">
          <input
            type="number"
            required
            min={1}
            max={16000}
            value={dimensions}
            onChange={(e) => setDimensions(e.target.value)}
            className={`${inputClass} font-mono`}
          />
        </Field>
      </div>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        Embedding model + dimensions are immutable after create — changing
        either invalidates every chunk. Common combinations:{' '}
        <code className="rounded bg-slate-100 px-1 font-mono dark:bg-slate-800">
          openai:text-embedding-3-small
        </code>{' '}
        (1536),{' '}
        <code className="rounded bg-slate-100 px-1 font-mono dark:bg-slate-800">
          openai:text-embedding-3-large
        </code>{' '}
        (3072).
      </p>
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
          onClick={() => setOpen(false)}
          className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

const inputClass =
  'w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200'

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

function CollectionList({ collections }: { collections: VectorCollection[] }) {
  return (
    <ul className="grid gap-3">
      {collections.map((c) => (
        <CollectionRow key={c.id} collection={c} />
      ))}
    </ul>
  )
}

function CollectionRow({ collection }: { collection: VectorCollection }) {
  const del = useDeleteVectorCollection()
  const update = useUpdateVectorCollection(collection.id)
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(collection.name)

  const submitRename = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = name.trim()
    if (trimmed.length === 0 || trimmed === collection.name) {
      setEditing(false)
      setName(collection.name)
      return
    }
    update.mutate({ name: trimmed }, { onSuccess: () => setEditing(false) })
  }

  return (
    <li className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          {editing ? (
            <form onSubmit={submitRename} className="flex items-center gap-2">
              <input
                type="text"
                required
                minLength={1}
                maxLength={256}
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
                className="w-full rounded-md border border-slate-200 bg-white px-2 py-1 text-base font-medium text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              />
              <button
                type="submit"
                disabled={update.isPending}
                className="rounded-md bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {update.isPending ? 'Saving…' : 'Save'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setEditing(false)
                  setName(collection.name)
                }}
                className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                Cancel
              </button>
            </form>
          ) : (
            <span className="truncate text-lg font-medium text-slate-900 dark:text-slate-100">
              {collection.name}
            </span>
          )}
          <div className="flex flex-wrap gap-3 text-xs text-slate-500 dark:text-slate-400">
            <span>
              <span className="text-slate-400 dark:text-slate-500">model:</span>{' '}
              <span className="font-mono">{collection.embedding_model}</span>
            </span>
            <span>
              <span className="text-slate-400 dark:text-slate-500">dim:</span>{' '}
              <span className="font-mono">{collection.dimensions}</span>
            </span>
            <span>
              <span className="text-slate-400 dark:text-slate-500">id:</span>{' '}
              <span className="font-mono">{collection.id}</span>
            </span>
          </div>
          {update.isError && (
            <div className="mt-1 rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">
              {(update.error as Error).message}
            </div>
          )}
        </div>
        {!editing && (
          <div className="flex shrink-0 gap-2">
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              Rename
            </button>
            <button
              type="button"
              onClick={() => {
                if (
                  confirm(
                    `Delete collection "${collection.name}"? All chunks within will be cascade-deleted.`,
                  )
                ) {
                  del.mutate(collection.id)
                }
              }}
              disabled={del.isPending}
              className="rounded-md border border-rose-200 px-3 py-1 text-xs text-rose-600 hover:bg-rose-50 disabled:opacity-50 dark:border-rose-900/50 dark:text-rose-400 dark:hover:bg-rose-900/20"
            >
              Delete
            </button>
          </div>
        )}
      </div>
    </li>
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
      {message}
    </div>
  )
}

function Empty() {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-12 text-center dark:border-slate-800 dark:bg-slate-900/50">
      <p className="text-sm text-slate-500 dark:text-slate-400">
        No vector collections yet.
      </p>
      <p className="max-w-md text-xs text-slate-400 dark:text-slate-500">
        Create one above. Indexing source documents into a collection is still
        an API-only flow — POST{' '}
        <code className="rounded bg-slate-100 px-1 font-mono text-slate-700 dark:bg-slate-800 dark:text-slate-300">
          /api/v1/agents/vector-collections/{'{id}'}/index
        </code>{' '}
        with a file_id.
      </p>
    </div>
  )
}
