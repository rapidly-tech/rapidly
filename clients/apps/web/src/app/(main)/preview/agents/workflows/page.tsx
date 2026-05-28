'use client'

import {
  type Workflow,
  useCreateWorkflow,
  useWorkflows,
} from '@/hooks/api/agents'
import { useListWorkspaces } from '@/hooks/api/org'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'

const PAGE_SIZE = 20

type PublishFilter = 'all' | 'published' | 'draft'

export default function WorkflowsListPage() {
  const workspacesQuery = useListWorkspaces({ limit: 50, page: 1 })
  const workspaces = workspacesQuery.data?.data ?? []
  const [pickedWorkspaceId, setPickedWorkspaceId] = useState<string | null>(
    null,
  )
  const activeWorkspaceId = pickedWorkspaceId ?? workspaces[0]?.id ?? null

  const [search, setSearch] = useState('')
  const [publishFilter, setPublishFilter] = useState<PublishFilter>('all')
  const [page, setPage] = useState(1)
  // Reset to page 1 when any filter changes — keeps the user
  // from being stranded on page 4 of "foo" if the new filter
  // has only 2 pages.
  const onSearchChange = (next: string) => {
    setSearch(next)
    setPage(1)
  }
  const onPublishFilterChange = (next: PublishFilter) => {
    setPublishFilter(next)
    setPage(1)
  }
  const onWorkspaceChange = (next: string | null) => {
    setPickedWorkspaceId(next)
    setPage(1)
  }

  const query = useWorkflows(
    {
      workspace_id: activeWorkspaceId ?? undefined,
      name: search.trim() || undefined,
      has_version:
        publishFilter === 'published'
          ? true
          : publishFilter === 'draft'
            ? false
            : undefined,
      limit: PAGE_SIZE,
      page,
    },
    !!activeWorkspaceId,
  )
  const workflows: Workflow[] = query.data?.data ?? []
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
      <PublishFilterChips
        value={publishFilter}
        onChange={onPublishFilterChange}
      />

      {query.isLoading ? (
        <LoadingSkeleton />
      ) : query.isError ? (
        <ErrorBanner message={(query.error as Error).message} />
      ) : workflows.length === 0 ? (
        search.trim() ? (
          <EmptySearch query={search.trim()} />
        ) : publishFilter !== 'all' ? (
          <EmptyFiltered publishFilter={publishFilter} />
        ) : (
          <EmptyState />
        )
      ) : (
        <>
          <WorkflowList workflows={workflows} />
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

function PublishFilterChips({
  value,
  onChange,
}: {
  value: PublishFilter
  onChange: (next: PublishFilter) => void
}) {
  const filters: { label: string; value: PublishFilter }[] = [
    { label: 'All', value: 'all' },
    { label: 'Published', value: 'published' },
    { label: 'Draft', value: 'draft' },
  ]
  return (
    <div className="flex flex-wrap gap-1.5">
      {filters.map((f) => {
        const active = f.value === value
        return (
          <button
            key={f.value}
            type="button"
            onClick={() => onChange(f.value)}
            className={
              active
                ? 'rounded-full bg-emerald-600 px-3 py-1 text-xs font-medium text-white'
                : 'rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800'
            }
          >
            {f.label}
          </button>
        )
      })}
    </div>
  )
}

function EmptyFiltered({ publishFilter }: { publishFilter: PublishFilter }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
      No <span className="font-mono">{publishFilter}</span> workflows.
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
        placeholder="Filter workflows by name…"
        className="w-full max-w-md rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
      />
    </div>
  )
}

function EmptySearch({ query }: { query: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
      No workflows match{' '}
      <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono dark:bg-slate-800">
        {query}
      </code>
      .
    </div>
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
  // Only render when the operator can see more than one workspace.
  // Single-workspace users get no chrome — same contract as the
  // credentials page switcher.
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
  const [description, setDescription] = useState('')
  const create = useCreateWorkflow()
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
        onSuccess: (workflow) => {
          // Land operators on the new workflow's detail page so
          // they can drop straight into publishing a version /
          // triggering a run.
          router.push(`/preview/agents/workflows/${workflow.id}`)
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
        + New workflow
      </button>
    )
  }

  return (
    <form
      onSubmit={submit}
      className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
    >
      <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
        New workflow
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
          placeholder="rfi-triage"
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
          placeholder="What does this workflow do?"
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
        Workflows
      </h1>
      <p className="max-w-2xl text-base leading-relaxed text-slate-600 dark:text-slate-400">
        Author and run agent workflows against your dataset of test cases. Each
        workflow is a graph of nodes — LLM calls, RAG searches, HTTP requests,
        code, and control-flow primitives — that drive a sequence of work from a
        single trigger.
      </p>
    </header>
  )
}

function WorkflowList({ workflows }: { workflows: Workflow[] }) {
  return (
    <ul className="grid gap-3">
      {workflows.map((workflow) => (
        <li key={workflow.id}>
          <Link
            href={`/preview/agents/workflows/${workflow.id}`}
            className="group flex flex-col gap-2 rounded-lg border border-slate-200 bg-white p-5 transition hover:border-emerald-400 hover:shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:hover:border-emerald-600"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-lg font-medium text-slate-900 dark:text-slate-100">
                {workflow.name}
              </span>
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
              <p className="text-sm text-slate-600 dark:text-slate-400">
                {workflow.description}
              </p>
            )}
            <span className="text-xs text-slate-400 dark:text-slate-500">
              Created {formatDate(workflow.created_at)}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

function LoadingSkeleton() {
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
      Failed to load workflows: {message}
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-12 text-center dark:border-slate-800 dark:bg-slate-900/50">
      <p className="text-sm text-slate-500 dark:text-slate-400">
        No workflows yet.
      </p>
      <p className="max-w-md text-xs text-slate-400 dark:text-slate-500">
        Workflows are authored via the API today; the in-editor builder ships in
        a follow-up. Use{' '}
        <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-slate-700 dark:bg-slate-800 dark:text-slate-300">
          POST /api/v1/workflows
        </code>{' '}
        to create one.
      </p>
    </div>
  )
}

function formatDate(iso: string): string {
  // Render in the operator's locale so the list is glanceable;
  // exact-second timestamps belong on detail pages, not here.
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
