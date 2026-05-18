'use client'

import {
  type ModuleStatus,
  type ProjectModule,
  type ProjectState,
  type WorkItem,
  useArchiveProjectModule,
  useModuleWorkItemIds,
  useProject,
  useProjectModule,
  useProjectStates,
  useUpdateProjectModule,
  useWorkItems,
} from '@/hooks/api/projects'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useMemo, useState } from 'react'

const MODULE_STATUSES: ModuleStatus[] = [
  'planned',
  'in_progress',
  'paused',
  'completed',
  'cancelled',
]

export default function ModuleDetailPage() {
  const params = useParams<{ projectId: string; moduleId: string }>()
  const { projectId, moduleId } = params

  const projectQuery = useProject(projectId)
  const project = projectQuery.data

  const moduleQuery = useProjectModule(moduleId)
  // Renamed to ``projectModule`` everywhere to dodge Next.js's
  // ``no-assign-module-variable`` rule that warns when the local
  // identifier ``module`` shadows the CommonJS global.
  const projectModule = moduleQuery.data

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

  // Same membership pattern as the cycle detail page (#675): resolve
  // the id list locally against the project's already-fetched 100-item
  // work-items page rather than fanning out one fetch per id.
  const memberIdsQuery = useModuleWorkItemIds(moduleId)
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
  const moduleItems = useMemo(
    () => allItems.filter((w) => memberIds.has(w.id)),
    [allItems, memberIds],
  )

  if (moduleQuery.isLoading || projectQuery.isLoading) {
    return (
      <main className="mx-auto w-full max-w-4xl px-6 py-12">
        <div className="h-32 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      </main>
    )
  }

  if (!projectModule || !project) {
    return (
      <main className="mx-auto w-full max-w-4xl px-6 py-12">
        <p className="text-slate-600 dark:text-slate-300">Module not found.</p>
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
          <ModuleHeaderActions projectModule={projectModule} />
        </div>
        <div className="flex items-baseline gap-3">
          <span className="text-xs font-medium tracking-wider text-slate-500 uppercase dark:text-slate-400">
            Module
          </span>
          <ModuleStatusPicker projectModule={projectModule} />
        </div>
        <ModuleName projectModule={projectModule} />
        <ModuleDates projectModule={projectModule} />
        {projectModule.description && (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {projectModule.description}
          </p>
        )}
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium tracking-wider text-slate-500 uppercase dark:text-slate-400">
          Work items{moduleItems.length > 0 ? ` · ${moduleItems.length}` : ''}
        </h2>
        {memberIdsQuery.isLoading || workItemsQuery.isLoading ? (
          <div className="h-16 animate-pulse rounded-md bg-slate-100 dark:bg-slate-800" />
        ) : moduleItems.length === 0 ? (
          <p className="text-sm text-slate-400 dark:text-slate-500">
            No work items assigned to this module yet. Open a work item and use
            the Modules picker to add it.
          </p>
        ) : (
          <ul className="grid gap-1.5">
            {moduleItems.map((w) => {
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
        {/* Same 100-item-page caveat as the cycle detail page. */}
      </section>
    </main>
  )
}

function ModuleHeaderActions({
  projectModule,
}: {
  projectModule: ProjectModule
}) {
  const archive = useArchiveProjectModule(projectModule.id)
  const isArchived = !!projectModule.archived_at
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
          : 'Hide this module from the default project view'
      }
    >
      {archive.isPending ? 'Archiving…' : isArchived ? 'Archived' : 'Archive'}
    </Button>
  )
}

function ModuleStatusPicker({
  projectModule,
}: {
  projectModule: ProjectModule
}) {
  // Module status is a tracked enum (planned / in_progress / paused /
  // completed / cancelled), not derived from dates the way cycle
  // status is — so a dropdown PATCH lets the owner mark progress
  // explicitly.
  const mutation = useUpdateProjectModule(projectModule.id)
  return (
    <select
      value={projectModule.status}
      onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
        mutation.mutate({ status: e.target.value as ModuleStatus })
      }
      className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
    >
      {MODULE_STATUSES.map((s) => (
        <option key={s} value={s}>
          {s.replace('_', ' ')}
        </option>
      ))}
    </select>
  )
}

function ModuleName({ projectModule }: { projectModule: ProjectModule }) {
  const mutation = useUpdateProjectModule(projectModule.id)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(projectModule.name)

  const commit = async () => {
    const next = draft.trim()
    if (!next || next === projectModule.name) {
      setDraft(projectModule.name)
      setEditing(false)
      return
    }
    try {
      await mutation.mutateAsync({ name: next })
      setEditing(false)
    } catch {
      // Keep input open; inline error visible.
    }
  }

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => {
          setDraft(projectModule.name)
          setEditing(true)
        }}
        className="-mx-2 rounded-md px-2 py-1 text-left text-3xl font-semibold text-slate-900 transition hover:bg-slate-100 dark:text-slate-100 dark:hover:bg-slate-800"
        title="Click to rename"
      >
        {projectModule.name}
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
            setDraft(projectModule.name)
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

function ModuleDates({ projectModule }: { projectModule: ProjectModule }) {
  const mutation = useUpdateProjectModule(projectModule.id)
  const valueOf = (raw: string | null | undefined) =>
    raw ? new Date(raw).toISOString().slice(0, 10) : ''
  const commit = (field: 'start_date' | 'target_date', next: string) => {
    mutation.mutate({ [field]: next === '' ? null : next })
  }
  return (
    <div className="flex flex-wrap items-center gap-3 text-sm text-slate-500 dark:text-slate-400">
      <label className="flex items-center gap-2">
        <span>Start</span>
        <input
          type="date"
          value={valueOf(projectModule.start_date)}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            commit('start_date', e.target.value)
          }
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        />
      </label>
      <label className="flex items-center gap-2">
        <span>Target</span>
        <input
          type="date"
          value={valueOf(projectModule.target_date)}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            commit('target_date', e.target.value)
          }
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        />
      </label>
    </div>
  )
}
