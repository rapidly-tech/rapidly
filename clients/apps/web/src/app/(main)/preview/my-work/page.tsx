'use client'

import {
  type Project,
  type WorkItem,
  useProjects,
  useWorkItems,
} from '@/hooks/api/projects'
import Link from 'next/link'
import { useMemo } from 'react'

export default function MyWorkPage() {
  const workItemsQuery = useWorkItems({
    assigned_to_me: true,
    limit: 100,
    page: 1,
  })
  const workItems: WorkItem[] = workItemsQuery.data?.data ?? []

  // Pull every project we have access to so we can stamp each row with
  // its parent project's identifier badge.  One small extra fetch beats
  // either a backend join or a per-row request.
  const projectsQuery = useProjects({ limit: 200, page: 1 })
  const projectsById = useMemo(() => {
    const map = new Map<string, Project>()
    for (const p of projectsQuery.data?.data ?? []) map.set(p.id, p)
    return map
  }, [projectsQuery.data])

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <Link
          href="/preview"
          className="text-sm text-slate-500 hover:text-emerald-600 dark:text-slate-400 dark:hover:text-emerald-400"
        >
          ← Preview
        </Link>
        <h1 className="text-3xl font-semibold text-slate-900 dark:text-slate-100">
          My work
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Open work items assigned to you across every project you can see.
        </p>
      </header>

      {workItemsQuery.isLoading && <ListSkeleton />}

      {!workItemsQuery.isLoading && workItems.length === 0 && <EmptyState />}

      {workItems.length > 0 && (
        <ul className="grid gap-2">
          {workItems.map((wi) => (
            <WorkItemRow
              key={wi.id}
              workItem={wi}
              project={projectsById.get(wi.project_id)}
            />
          ))}
        </ul>
      )}
    </main>
  )
}

function WorkItemRow({
  workItem,
  project,
}: {
  workItem: WorkItem
  project: Project | undefined
}) {
  return (
    <li>
      <Link
        href={`/preview/projects/${workItem.project_id}/work-items/${workItem.id}`}
        className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 transition hover:border-emerald-400 hover:shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:hover:border-emerald-600"
      >
        {project && (
          <span className="rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-300">
            {project.identifier}-{workItem.sequence_number}
          </span>
        )}
        <span className="flex-1 truncate text-sm text-slate-900 dark:text-slate-100">
          {workItem.name}
        </span>
        {project && (
          <span className="hidden text-xs text-slate-400 sm:inline dark:text-slate-500">
            {project.name}
          </span>
        )}
      </Link>
    </li>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-slate-200 bg-slate-50 px-6 py-12 text-center dark:border-slate-800 dark:bg-slate-900/50">
      <p className="text-sm text-slate-500 dark:text-slate-400">
        Nothing assigned to you right now.
      </p>
      <Link
        href="/preview/projects"
        className="text-sm text-emerald-600 hover:underline dark:text-emerald-400"
      >
        Browse projects →
      </Link>
    </div>
  )
}

function ListSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className="h-12 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800"
        />
      ))}
    </div>
  )
}
