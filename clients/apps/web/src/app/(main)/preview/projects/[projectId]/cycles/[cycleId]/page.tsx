'use client'

import {
  type ProjectCycle,
  type ProjectState,
  type WorkItem,
  useArchiveProjectCycle,
  useCycleWorkItemIds,
  useProject,
  useProjectCycle,
  useProjectStates,
  useUpdateProjectCycle,
  useWorkItems,
} from '@/hooks/api/projects'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useMemo, useState } from 'react'

export default function CycleDetailPage() {
  const params = useParams<{ projectId: string; cycleId: string }>()
  const { projectId, cycleId } = params

  const projectQuery = useProject(projectId)
  const project = projectQuery.data

  const cycleQuery = useProjectCycle(cycleId)
  const cycle = cycleQuery.data

  const statesQuery = useProjectStates(
    projectId ? { project_id: [projectId], limit: 50, page: 1 } : undefined,
    !!projectId,
  )
  const states: ProjectState[] = useMemo(
    () => statesQuery.data?.data ?? [],
    [statesQuery.data],
  )
  const stateById = useMemo(
    () => Object.fromEntries(states.map((s) => [s.id, s] as const)),
    [states],
  )

  // Cycle membership is a separate endpoint returning a flat list of
  // work-item ids — we then resolve those against the project's
  // already-fetched work-items page rather than fanning out one
  // request per id.
  const memberIdsQuery = useCycleWorkItemIds(cycleId)
  const memberIds = useMemo(
    () => new Set<string>(memberIdsQuery.data ?? []),
    [memberIdsQuery.data],
  )

  const workItemsQuery = useWorkItems(
    projectId ? { project_id: [projectId], limit: 100, page: 1 } : undefined,
    !!projectId,
  )
  const allItems: WorkItem[] = useMemo(
    () => workItemsQuery.data?.data ?? [],
    [workItemsQuery.data],
  )
  const cycleItems = useMemo(
    () => allItems.filter((w) => memberIds.has(w.id)),
    [allItems, memberIds],
  )

  if (cycleQuery.isLoading || projectQuery.isLoading) {
    return (
      <main className="mx-auto w-full max-w-4xl px-6 py-12">
        <div className="h-32 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      </main>
    )
  }

  if (!cycle || !project) {
    return (
      <main className="mx-auto w-full max-w-4xl px-6 py-12">
        <p className="text-slate-600 dark:text-slate-300">Cycle not found.</p>
        {project && (
          <Link
            href={`/preview/projects/${project.id}`}
            className="text-sm text-emerald-600 hover:underline dark:text-emerald-400"
          >
            ← Back to project
          </Link>
        )}
      </main>
    )
  }

  const status = cycleStatus(cycle)

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <Link
            href={`/preview/projects/${project.id}`}
            className="text-sm text-slate-500 hover:text-emerald-600 dark:text-slate-400 dark:hover:text-emerald-400"
          >
            ← {project.name}
          </Link>
          <CycleHeaderActions cycle={cycle} />
        </div>
        <div className="flex items-baseline gap-3">
          <span className="text-xs font-medium tracking-wider text-slate-500 uppercase dark:text-slate-400">
            Cycle
          </span>
          <CycleStatusPill status={status} />
        </div>
        <CycleName cycle={cycle} />
        <CycleDates cycle={cycle} />
        {cycle.description && (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {cycle.description}
          </p>
        )}
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium tracking-wider text-slate-500 uppercase dark:text-slate-400">
          Work items{cycleItems.length > 0 ? ` · ${cycleItems.length}` : ''}
        </h2>
        {memberIdsQuery.isLoading || workItemsQuery.isLoading ? (
          <div className="h-16 animate-pulse rounded-md bg-slate-100 dark:bg-slate-800" />
        ) : cycleItems.length === 0 ? (
          <p className="text-sm text-slate-400 dark:text-slate-500">
            No work items assigned to this cycle yet. Open a work item and use
            the Cycles picker to add it.
          </p>
        ) : (
          <ul className="grid gap-1.5">
            {cycleItems.map((w) => {
              const s = stateById[w.state_id]
              return (
                <li key={w.id}>
                  <Link
                    href={`/preview/projects/${project.id}/work-items/${w.id}`}
                    className="flex items-center gap-3 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm transition hover:border-emerald-400 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-emerald-600"
                  >
                    <span className="font-mono text-xs text-slate-500 dark:text-slate-400">
                      {project.identifier}-{w.sequence_number}
                    </span>
                    {s && (
                      <span
                        className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium"
                        style={{
                          backgroundColor: `${s.color}1a`,
                          color: s.color,
                        }}
                      >
                        <span
                          className="size-1.5 rounded-full"
                          style={{ backgroundColor: s.color }}
                        />
                        {s.name}
                      </span>
                    )}
                    <span className="flex-1 truncate text-slate-900 dark:text-slate-100">
                      {w.name}
                    </span>
                  </Link>
                </li>
              )
            })}
          </ul>
        )}
        {/* Caveat: cycleItems is filtered from the project's first
            100-item page.  If the project exceeds that, a cycle member
            past the page can be missing here.  Tracked as a follow-up
            — the proper fix is a server-side ``id IN (...)`` filter on
            /api/work-items. */}
      </section>
    </main>
  )
}

function CycleHeaderActions({ cycle }: { cycle: ProjectCycle }) {
  const archive = useArchiveProjectCycle(cycle.id)
  const isArchived = !!cycle.archived_at
  return (
    <Button
      type="button"
      size="sm"
      variant="secondary"
      onClick={() => !isArchived && archive.mutate()}
      disabled={isArchived || archive.isPending}
      title={
        isArchived
          ? 'Already archived'
          : 'Hide this cycle from the default project view'
      }
    >
      {archive.isPending ? 'Archiving…' : isArchived ? 'Archived' : 'Archive'}
    </Button>
  )
}

function CycleName({ cycle }: { cycle: ProjectCycle }) {
  const mutation = useUpdateProjectCycle(cycle.id)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(cycle.name)

  const commit = async () => {
    const next = draft.trim()
    if (!next || next === cycle.name) {
      setDraft(cycle.name)
      setEditing(false)
      return
    }
    try {
      await mutation.mutateAsync({ name: next })
      setEditing(false)
    } catch {
      // Keep open; inline error visible.
    }
  }

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => {
          setDraft(cycle.name)
          setEditing(true)
        }}
        className="-mx-2 rounded-md px-2 py-1 text-left text-3xl font-semibold text-slate-900 transition hover:bg-slate-100 dark:text-slate-100 dark:hover:bg-slate-800"
        title="Click to rename"
      >
        {cycle.name}
      </button>
    )
  }

  return (
    <div className="flex flex-col gap-1">
      <input
        autoFocus
        value={draft}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
          setDraft(e.target.value)
        }
        onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            commit()
          } else if (e.key === 'Escape') {
            e.preventDefault()
            setDraft(cycle.name)
            mutation.reset()
            setEditing(false)
          }
        }}
        onBlur={commit}
        maxLength={512}
        className="-mx-2 rounded-md border border-emerald-300 bg-white px-2 py-1 text-3xl font-semibold text-slate-900 outline-none focus:ring-2 focus:ring-emerald-400 dark:border-emerald-600 dark:bg-slate-900 dark:text-slate-100"
      />
      {mutation.isError && (
        <span className="text-xs text-red-600 dark:text-red-400">
          Couldn&apos;t save. Press Esc to discard.
        </span>
      )}
    </div>
  )
}

function CycleDates({ cycle }: { cycle: ProjectCycle }) {
  const mutation = useUpdateProjectCycle(cycle.id)
  const valueOf = (raw: string | null | undefined) =>
    raw ? new Date(raw).toISOString().slice(0, 10) : ''
  const commit = (field: 'start_date' | 'end_date', next: string) => {
    mutation.mutate({ [field]: next === '' ? null : next })
  }
  return (
    <div className="flex flex-wrap items-center gap-3 text-sm text-slate-500 dark:text-slate-400">
      <label className="flex items-center gap-2">
        <span>Start</span>
        <input
          type="date"
          value={valueOf(cycle.start_date)}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            commit('start_date', e.target.value)
          }
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        />
      </label>
      <label className="flex items-center gap-2">
        <span>End</span>
        <input
          type="date"
          value={valueOf(cycle.end_date)}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            commit('end_date', e.target.value)
          }
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        />
      </label>
    </div>
  )
}

// Mirror of the inline ``cycleStatus`` / ``CycleStatusPill`` on the
// project detail page; duplicated here so this surface stands alone.

type CycleStatus = 'planning' | 'active' | 'completed' | 'archived'

function cycleStatus(cycle: ProjectCycle): CycleStatus {
  if (cycle.archived_at) return 'archived'
  const now = Date.now()
  const startMs = cycle.start_date ? new Date(cycle.start_date).getTime() : null
  const endMs = cycle.end_date ? new Date(cycle.end_date).getTime() : null
  if (endMs !== null && endMs < now) return 'completed'
  if (startMs !== null && startMs <= now) return 'active'
  return 'planning'
}

function CycleStatusPill({ status }: { status: CycleStatus }) {
  const styles: Record<CycleStatus, string> = {
    planning:
      'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
    active:
      'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
    completed:
      'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
    archived:
      'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  }
  return (
    <span
      className={
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ' +
        styles[status]
      }
    >
      {status}
    </span>
  )
}
