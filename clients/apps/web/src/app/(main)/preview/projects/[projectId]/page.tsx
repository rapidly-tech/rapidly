'use client'

import {
  type ModuleStatus,
  type ProjectCycle,
  type ProjectCycleCreate,
  type ProjectModule,
  type ProjectModuleCreate,
  type ProjectPage,
  type ProjectPageCreate,
  type ProjectState,
  type ProjectStateCreate,
  type WorkItem,
  type WorkItemCreate,
  useCreateProjectCycle,
  useCreateProjectModule,
  useCreateProjectPage,
  useCreateProjectState,
  useCreateWorkItem,
  useProject,
  useProjectCycles,
  useProjectModules,
  useProjectPages,
  useProjectStates,
  useReassignWorkItem,
  useWorkItems,
} from '@/hooks/api/projects'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Input from '@rapidly-tech/ui/components/forms/Input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@rapidly-tech/ui/components/primitives/dialog'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'

const DEFAULT_STATE_GROUPS: {
  name: string
  group: ProjectStateCreate['group']
  color: string
  sequence: number
  is_default: boolean
}[] = [
  {
    name: 'Backlog',
    group: 'backlog',
    color: '#94a3b8',
    sequence: 1000,
    is_default: true,
  },
  {
    name: 'Todo',
    group: 'unstarted',
    color: '#64748b',
    sequence: 2000,
    is_default: false,
  },
  {
    name: 'In Progress',
    group: 'started',
    color: '#f59e0b',
    sequence: 3000,
    is_default: false,
  },
  {
    name: 'Done',
    group: 'completed',
    color: '#10b981',
    sequence: 4000,
    is_default: false,
  },
  {
    name: 'Cancelled',
    group: 'cancelled',
    color: '#ef4444',
    sequence: 5000,
    is_default: false,
  },
]

export default function ProjectDetailPage() {
  const params = useParams<{ projectId: string }>()
  const projectId = params.projectId

  const projectQuery = useProject(projectId)
  const project = projectQuery.data

  const statesQuery = useProjectStates(
    projectId ? { project_id: [projectId], limit: 50, page: 1 } : undefined,
    !!projectId,
  )
  // Memoised so downstream ``stateById`` keeps a stable identity across renders.
  const states: ProjectState[] = useMemo(
    () => statesQuery.data?.data ?? [],
    [statesQuery.data],
  )
  const stateById = useMemo(
    () => Object.fromEntries(states.map((s) => [s.id, s] as const)),
    [states],
  )

  const workItemsQuery = useWorkItems(
    projectId ? { project_id: [projectId], limit: 100, page: 1 } : undefined,
    !!projectId,
  )
  const workItems: WorkItem[] = workItemsQuery.data?.data ?? []

  if (projectQuery.isLoading) {
    return (
      <main className="mx-auto w-full max-w-5xl px-6 py-12">
        <div className="h-32 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      </main>
    )
  }

  if (!project) {
    return (
      <main className="mx-auto w-full max-w-5xl px-6 py-12">
        <p className="text-slate-600 dark:text-slate-300">Project not found.</p>
        <Link
          href="/preview/projects"
          className="text-sm text-emerald-600 hover:underline dark:text-emerald-400"
        >
          ← Back to projects
        </Link>
      </main>
    )
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <Link
          href="/preview/projects"
          className="text-sm text-slate-500 hover:text-emerald-600 dark:text-slate-400 dark:hover:text-emerald-400"
        >
          ← Projects
        </Link>
        <div className="flex items-baseline justify-between gap-4">
          <div className="flex items-baseline gap-3">
            <span className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-sm text-slate-700 dark:bg-slate-800 dark:text-slate-300">
              {project.identifier}
            </span>
            <h1 className="text-3xl font-semibold text-slate-900 dark:text-slate-100">
              {project.name}
            </h1>
          </div>
          {states.length > 0 && (
            <CreateWorkItemDialog projectId={project.id} states={states} />
          )}
        </div>
        {project.description && (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {project.description}
          </p>
        )}
      </header>

      {states.length === 0 && statesQuery.isFetched && (
        <SetupStatesPrompt projectId={project.id} />
      )}

      {states.length > 0 && <CyclesSection projectId={project.id} />}

      {states.length > 0 && <ModulesSection projectId={project.id} />}

      {states.length > 0 && (
        <PagesSection projectId={project.id} identifier={project.identifier} />
      )}

      {states.length > 0 && (
        <WorkItemsSection
          project={project}
          states={states}
          stateById={stateById}
          workItems={workItems}
          isLoading={workItemsQuery.isLoading}
          isFetched={workItemsQuery.isFetched}
        />
      )}
    </main>
  )
}

// ── Cycles section ──

function CyclesSection({ projectId }: { projectId: string }) {
  const cyclesQuery = useProjectCycles(
    { project_id: [projectId], limit: 50, page: 1 },
    true,
  )
  const cycles: ProjectCycle[] = cyclesQuery.data?.data ?? []

  if (cyclesQuery.isLoading) {
    return (
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium tracking-wider text-slate-500 uppercase dark:text-slate-400">
          Cycles
        </h2>
        <div className="h-20 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      </section>
    )
  }

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium tracking-wider text-slate-500 uppercase dark:text-slate-400">
          Cycles
        </h2>
        <CreateCycleDialog projectId={projectId} />
      </div>
      {cycles.length === 0 ? (
        <p className="text-sm text-slate-400 dark:text-slate-500">
          No cycles yet. Use “New Cycle” to time-box the next sprint.
        </p>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {cycles.map((c) => (
            <CycleCard key={c.id} cycle={c} />
          ))}
        </ul>
      )}
    </section>
  )
}

function CycleCard({ cycle }: { cycle: ProjectCycle }) {
  const status = cycleStatus(cycle)
  return (
    <li className="flex flex-col gap-1 rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-medium text-slate-900 dark:text-slate-100">
          {cycle.name}
        </span>
        <CycleStatusPill status={status} />
      </div>
      <span className="text-xs text-slate-500 dark:text-slate-400">
        {formatRange(cycle.start_date, cycle.end_date)}
      </span>
      {cycle.description && (
        <p className="line-clamp-2 text-sm text-slate-500 dark:text-slate-400">
          {cycle.description}
        </p>
      )}
    </li>
  )
}

type CycleStatus = 'planning' | 'active' | 'completed' | 'archived'

function cycleStatus(cycle: ProjectCycle): CycleStatus {
  if (cycle.archived_at) return 'archived'
  const now = Date.now()
  const start = cycle.start_date ? Date.parse(cycle.start_date) : null
  const end = cycle.end_date ? Date.parse(cycle.end_date) : null
  if (end !== null && end < now) return 'completed'
  if (start !== null && start <= now && (end === null || end >= now))
    return 'active'
  return 'planning'
}

function CycleStatusPill({ status }: { status: CycleStatus }) {
  const palette: Record<CycleStatus, string> = {
    planning:
      'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
    active:
      'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
    completed:
      'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
    archived:
      'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400',
  }
  return (
    <span
      className={
        'rounded-full px-2 py-0.5 text-[10px] font-medium tracking-wider uppercase ' +
        palette[status]
      }
    >
      {status}
    </span>
  )
}

function formatRange(
  start: string | null | undefined,
  end: string | null | undefined,
): string {
  if (!start && !end) return 'No dates set'
  const opts: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' }
  const s = start ? new Date(start).toLocaleDateString(undefined, opts) : '—'
  const e = end ? new Date(end).toLocaleDateString(undefined, opts) : '—'
  return `${s} → ${e}`
}

function CreateCycleDialog({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const mutation = useCreateProjectCycle()

  const reset = () => {
    setName('')
    setDescription('')
    setStartDate('')
    setEndDate('')
    mutation.reset()
  }

  const submit = async () => {
    const body: ProjectCycleCreate = {
      project_id: projectId,
      name: name.trim(),
      description: description.trim() || null,
      start_date: startDate ? new Date(startDate).toISOString() : null,
      end_date: endDate ? new Date(endDate).toISOString() : null,
    }
    try {
      await mutation.mutateAsync(body)
      setOpen(false)
      reset()
    } catch {
      // surfaced inline below
    }
  }

  const errorMessage = useMemo(() => {
    if (!mutation.isError) return null
    const err = mutation.error as unknown as {
      detail?: string
      message?: string
    }
    return err?.detail ?? err?.message ?? 'Something went wrong.'
  }, [mutation.isError, mutation.error])

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) reset()
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm" variant="secondary">
          New Cycle
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create a cycle</DialogTitle>
          <DialogDescription>
            Time-box the next sprint. Dates are optional.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Name
            </span>
            <Input
              value={name}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setName(e.target.value)
              }
              placeholder="Sprint 1"
              maxLength={255}
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                Start
              </span>
              <input
                type="date"
                value={startDate}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setStartDate(e.target.value)
                }
                className="rounded-md border border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                End
              </span>
              <input
                type="date"
                value={endDate}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setEndDate(e.target.value)
                }
                className="rounded-md border border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              />
            </label>
          </div>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Description
            </span>
            <Input
              value={description}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setDescription(e.target.value)
              }
              placeholder="Optional"
              maxLength={4096}
            />
          </label>
          {errorMessage && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-300">
              {errorMessage}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button
            variant="secondary"
            type="button"
            onClick={() => setOpen(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={submit}
            disabled={!name.trim() || mutation.isPending}
          >
            {mutation.isPending ? 'Creating…' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Modules section ──

const MODULE_STATUSES: ModuleStatus[] = [
  'planned',
  'in_progress',
  'paused',
  'completed',
  'cancelled',
]

function ModulesSection({ projectId }: { projectId: string }) {
  const modulesQuery = useProjectModules(
    { project_id: [projectId], limit: 50, page: 1 },
    true,
  )
  const modules: ProjectModule[] = modulesQuery.data?.data ?? []

  if (modulesQuery.isLoading) {
    return (
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium tracking-wider text-slate-500 uppercase dark:text-slate-400">
          Modules
        </h2>
        <div className="h-20 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      </section>
    )
  }

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium tracking-wider text-slate-500 uppercase dark:text-slate-400">
          Modules
        </h2>
        <CreateModuleDialog projectId={projectId} />
      </div>
      {modules.length === 0 ? (
        <p className="text-sm text-slate-400 dark:text-slate-500">
          No modules yet. Use “New Module” to group work items by deliverable.
        </p>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {modules.map((m) => (
            <ModuleCard key={m.id} module={m} />
          ))}
        </ul>
      )}
    </section>
  )
}

function ModuleCard({ module }: { module: ProjectModule }) {
  return (
    <li className="flex flex-col gap-1 rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-medium text-slate-900 dark:text-slate-100">
          {module.name}
        </span>
        <ModuleStatusPill status={module.status} />
      </div>
      <span className="text-xs text-slate-500 dark:text-slate-400">
        {formatRange(module.start_date, module.target_date)}
      </span>
      {module.description && (
        <p className="line-clamp-2 text-sm text-slate-500 dark:text-slate-400">
          {module.description}
        </p>
      )}
    </li>
  )
}

function ModuleStatusPill({ status }: { status: ModuleStatus }) {
  const palette: Record<ModuleStatus, string> = {
    planned:
      'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
    in_progress:
      'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
    paused:
      'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
    completed:
      'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
    cancelled: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  }
  return (
    <span
      className={
        'rounded-full px-2 py-0.5 text-[10px] font-medium tracking-wider uppercase ' +
        palette[status]
      }
    >
      {status.replace('_', ' ')}
    </span>
  )
}

function CreateModuleDialog({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [status, setStatus] = useState<ModuleStatus>('planned')
  const [startDate, setStartDate] = useState('')
  const [targetDate, setTargetDate] = useState('')
  const mutation = useCreateProjectModule()

  const reset = () => {
    setName('')
    setDescription('')
    setStatus('planned')
    setStartDate('')
    setTargetDate('')
    mutation.reset()
  }

  const submit = async () => {
    const body: ProjectModuleCreate = {
      project_id: projectId,
      name: name.trim(),
      description: description.trim() || null,
      lead_id: null,
      status,
      start_date: startDate ? new Date(startDate).toISOString() : null,
      target_date: targetDate ? new Date(targetDate).toISOString() : null,
    }
    try {
      await mutation.mutateAsync(body)
      setOpen(false)
      reset()
    } catch {
      // surfaced inline
    }
  }

  const errorMessage = useMemo(() => {
    if (!mutation.isError) return null
    const err = mutation.error as unknown as {
      detail?: string
      message?: string
    }
    return err?.detail ?? err?.message ?? 'Something went wrong.'
  }, [mutation.isError, mutation.error])

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) reset()
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm" variant="secondary">
          New Module
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create a module</DialogTitle>
          <DialogDescription>
            Group work items by deliverable. Dates are optional; a module often
            spans several cycles.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Name
            </span>
            <Input
              value={name}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setName(e.target.value)
              }
              placeholder="Billing v2"
              maxLength={255}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Status
            </span>
            <select
              value={status}
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
                setStatus(e.target.value as ModuleStatus)
              }
              className="rounded-md border border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            >
              {MODULE_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s.replace('_', ' ')}
                </option>
              ))}
            </select>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                Start
              </span>
              <input
                type="date"
                value={startDate}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setStartDate(e.target.value)
                }
                className="rounded-md border border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                Target
              </span>
              <input
                type="date"
                value={targetDate}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setTargetDate(e.target.value)
                }
                className="rounded-md border border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              />
            </label>
          </div>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Description
            </span>
            <Input
              value={description}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setDescription(e.target.value)
              }
              placeholder="Optional"
              maxLength={4096}
            />
          </label>
          {errorMessage && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-300">
              {errorMessage}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button
            variant="secondary"
            type="button"
            onClick={() => setOpen(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={submit}
            disabled={!name.trim() || mutation.isPending}
          >
            {mutation.isPending ? 'Creating…' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Pages section ──

function PagesSection({
  projectId,
  identifier,
}: {
  projectId: string
  identifier: string
}) {
  const pagesQuery = useProjectPages(
    { project_id: [projectId], limit: 50, page: 1 },
    true,
  )
  const pages: ProjectPage[] = pagesQuery.data?.data ?? []

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium tracking-wider text-slate-500 uppercase dark:text-slate-400">
          Pages
        </h2>
        <CreatePageDialog projectId={projectId} />
      </div>
      {pagesQuery.isLoading && (
        <div className="h-16 animate-pulse rounded-md bg-slate-100 dark:bg-slate-800" />
      )}
      {pages.length === 0 && pagesQuery.isFetched && (
        <p className="text-sm text-slate-400 dark:text-slate-500">
          No pages yet. Use “New Page” to start a doc.
        </p>
      )}
      <ul className="grid gap-2">
        {pages.map((p) => (
          <li key={p.id}>
            <Link
              href={`/preview/projects/${projectId}/pages/${p.id}`}
              className="flex items-center gap-3 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm transition hover:border-emerald-400 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-emerald-600"
            >
              <span className="font-mono text-xs text-slate-400 dark:text-slate-500">
                /{p.slug}
              </span>
              <span className="flex-1 truncate text-slate-900 dark:text-slate-100">
                {p.name}
              </span>
              {p.access === 'private' && (
                <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] tracking-wider text-slate-500 uppercase dark:bg-slate-800 dark:text-slate-400">
                  private
                </span>
              )}
              {p.is_locked && (
                <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] tracking-wider text-amber-700 uppercase dark:bg-amber-900/30 dark:text-amber-300">
                  locked
                </span>
              )}
            </Link>
          </li>
        ))}
      </ul>
      {/* identifier reserved for future ``ATL/pages/foo`` style breadcrumbs */}
      <span className="hidden">{identifier}</span>
    </section>
  )
}

function CreatePageDialog({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const mutation = useCreateProjectPage()

  const reset = () => {
    setName('')
    setSlug('')
    mutation.reset()
  }

  const submit = async () => {
    const body: ProjectPageCreate = {
      project_id: projectId,
      name: name.trim(),
      slug:
        slug.trim().toLowerCase() ||
        name
          .trim()
          .toLowerCase()
          .replace(/[^a-z0-9-]+/g, '-'),
      parent_id: null,
      description_json: null,
      description_html: null,
      access: 'public',
    }
    try {
      await mutation.mutateAsync(body)
      setOpen(false)
      reset()
    } catch {
      // surfaced inline
    }
  }

  const errorMessage = useMemo(() => {
    if (!mutation.isError) return null
    const err = mutation.error as unknown as {
      detail?: string
      message?: string
    }
    return err?.detail ?? err?.message ?? 'Something went wrong.'
  }, [mutation.isError, mutation.error])

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) reset()
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm" variant="secondary">
          New Page
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create a page</DialogTitle>
          <DialogDescription>
            Pages are project-scoped docs. Slug auto-derives from the name if
            you leave it blank.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Name
            </span>
            <Input
              value={name}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setName(e.target.value)
              }
              placeholder="Architecture overview"
              maxLength={255}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Slug
            </span>
            <Input
              value={slug}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setSlug(e.target.value.toLowerCase())
              }
              placeholder="architecture-overview"
              maxLength={255}
            />
          </label>
          {errorMessage && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-300">
              {errorMessage}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button
            variant="secondary"
            type="button"
            onClick={() => setOpen(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={submit}
            disabled={!name.trim() || mutation.isPending}
          >
            {mutation.isPending ? 'Creating…' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Work items section ──

type Layout = 'list' | 'kanban'

function WorkItemsSection({
  project,
  states,
  stateById,
  workItems,
  isLoading,
  isFetched,
}: {
  project: { id: string; identifier: string }
  states: ProjectState[]
  stateById: Record<string, ProjectState>
  workItems: WorkItem[]
  isLoading: boolean
  isFetched: boolean
}) {
  const [layout, setLayout] = useState<Layout>('list')
  const reassign = useReassignWorkItem()

  // The KanbanColumn fires a window event with the dropped item's id +
  // target state.  We promote it to a typed mutation here so the column
  // doesn't need to thread the mutation through props.
  useEffect(() => {
    const onMove = (event: Event) => {
      const detail = (
        event as CustomEvent<{
          workItemId: string
          newStateId: string
        }>
      ).detail
      if (!detail) return
      reassign.mutate({
        id: detail.workItemId,
        body: { state_id: detail.newStateId },
      })
    }
    window.addEventListener('rapidly:move-work-item', onMove)
    return () => window.removeEventListener('rapidly:move-work-item', onMove)
  }, [reassign])

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium tracking-wider text-slate-500 uppercase dark:text-slate-400">
          Work items
        </h2>
        <LayoutSwitcher value={layout} onChange={setLayout} />
      </div>

      {isLoading && (
        <div className="h-24 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      )}
      {workItems.length === 0 && isFetched && (
        <div className="rounded-lg border border-dashed border-slate-300 py-12 text-center dark:border-slate-700">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            No work items yet. Use the New Work Item button to create one.
          </p>
        </div>
      )}

      {workItems.length > 0 && layout === 'list' && (
        <ul className="grid gap-2">
          {workItems.map((w) => (
            <WorkItemRow
              key={w.id}
              workItem={w}
              state={stateById[w.state_id]}
              identifier={project.identifier}
              projectId={project.id}
            />
          ))}
        </ul>
      )}

      {workItems.length > 0 && layout === 'kanban' && (
        <KanbanBoard project={project} states={states} workItems={workItems} />
      )}
    </section>
  )
}

function LayoutSwitcher({
  value,
  onChange,
}: {
  value: Layout
  onChange: (l: Layout) => void
}) {
  const options: { id: Layout; label: string }[] = [
    { id: 'list', label: 'List' },
    { id: 'kanban', label: 'Kanban' },
  ]
  return (
    <div
      role="tablist"
      className="inline-flex overflow-hidden rounded-md border border-slate-200 text-xs dark:border-slate-700"
    >
      {options.map((o) => {
        const active = o.id === value
        return (
          <button
            key={o.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.id)}
            className={
              'px-3 py-1.5 transition ' +
              (active
                ? 'bg-emerald-500 text-white dark:bg-emerald-600'
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800')
            }
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

// ── Kanban ──

function KanbanBoard({
  project,
  states,
  workItems,
}: {
  project: { id: string; identifier: string }
  states: ProjectState[]
  workItems: WorkItem[]
}) {
  // Group by state in the state's own ordering (sequence then name).
  const sortedStates = useMemo(
    () =>
      [...states].sort((a, b) =>
        a.sequence === b.sequence
          ? a.name.localeCompare(b.name)
          : a.sequence - b.sequence,
      ),
    [states],
  )
  const byState = useMemo(() => {
    const map = new Map<string, WorkItem[]>()
    for (const s of sortedStates) map.set(s.id, [])
    for (const w of workItems) {
      const bucket = map.get(w.state_id)
      if (bucket) bucket.push(w)
    }
    return map
  }, [sortedStates, workItems])

  return (
    <div className="flex gap-3 overflow-x-auto pb-2">
      {sortedStates.map((s) => (
        <KanbanColumn
          key={s.id}
          state={s}
          workItems={byState.get(s.id) ?? []}
          identifier={project.identifier}
          projectId={project.id}
        />
      ))}
    </div>
  )
}

function KanbanColumn({
  state,
  workItems,
  identifier,
  projectId,
}: {
  state: ProjectState
  workItems: WorkItem[]
  identifier: string
  projectId: string
}) {
  const [isOver, setIsOver] = useState(false)

  const onDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    // Allow dropping by preventing the default (which would refuse the drop).
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    if (!isOver) setIsOver(true)
  }
  const onDragLeave = () => setIsOver(false)
  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsOver(false)
    const payload = e.dataTransfer.getData('application/x-rapidly-work-item')
    if (!payload) return
    try {
      const { id, currentStateId } = JSON.parse(payload) as {
        id: string
        currentStateId: string
      }
      if (currentStateId === state.id) return
      // Dispatch via a synthetic event the column doesn't otherwise care about.
      window.dispatchEvent(
        new CustomEvent('rapidly:move-work-item', {
          detail: { workItemId: id, newStateId: state.id },
        }),
      )
    } catch {
      // Ignore malformed payloads.
    }
  }

  return (
    <div
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      className={
        'flex w-72 shrink-0 flex-col gap-2 rounded-lg border p-3 transition ' +
        (isOver
          ? 'border-emerald-400 bg-emerald-50/40 dark:border-emerald-500 dark:bg-emerald-950/20'
          : 'border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-900/50')
      }
    >
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-700 dark:text-slate-200">
          <span
            className="size-1.5 rounded-full"
            style={{ backgroundColor: state.color }}
          />
          {state.name}
        </span>
        <span className="text-xs text-slate-400 dark:text-slate-500">
          {workItems.length}
        </span>
      </div>
      <ul className="flex flex-col gap-2">
        {workItems.map((w) => (
          <KanbanCard
            key={w.id}
            workItem={w}
            identifier={identifier}
            projectId={projectId}
          />
        ))}
        {workItems.length === 0 && (
          <li className="rounded-md border border-dashed border-slate-300 py-6 text-center text-xs text-slate-400 dark:border-slate-700">
            Drop here
          </li>
        )}
      </ul>
    </div>
  )
}

function KanbanCard({
  workItem,
  identifier,
  projectId,
}: {
  workItem: WorkItem
  identifier: string
  projectId: string
}) {
  const onDragStart = (e: React.DragEvent<HTMLAnchorElement>) => {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData(
      'application/x-rapidly-work-item',
      JSON.stringify({ id: workItem.id, currentStateId: workItem.state_id }),
    )
  }
  return (
    <li>
      <Link
        href={`/preview/projects/${projectId}/work-items/${workItem.id}`}
        draggable
        onDragStart={onDragStart}
        className="flex cursor-grab flex-col gap-1 rounded-md border border-slate-200 bg-white p-2 text-sm transition hover:border-emerald-400 active:cursor-grabbing dark:border-slate-800 dark:bg-slate-900 dark:hover:border-emerald-600"
      >
        <span className="font-mono text-[10px] text-slate-400 dark:text-slate-500">
          {identifier}-{workItem.sequence_number}
        </span>
        <span className="text-slate-900 dark:text-slate-100">
          {workItem.name}
        </span>
        <PriorityBadge priority={workItem.priority} />
      </Link>
    </li>
  )
}

// ── Work item row ──

function WorkItemRow({
  workItem,
  state,
  identifier,
  projectId,
}: {
  workItem: WorkItem
  state: ProjectState | undefined
  identifier: string
  projectId: string
}) {
  return (
    <li>
      <Link
        href={`/preview/projects/${projectId}/work-items/${workItem.id}`}
        className="flex items-center gap-3 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm transition hover:border-emerald-400 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-emerald-600"
      >
        <span className="font-mono text-xs text-slate-500 dark:text-slate-400">
          {identifier}-{workItem.sequence_number}
        </span>
        {state && (
          <span
            className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium"
            style={{
              backgroundColor: `${state.color}1a`,
              color: state.color,
            }}
          >
            <span
              className="size-1.5 rounded-full"
              style={{ backgroundColor: state.color }}
            />
            {state.name}
          </span>
        )}
        <span className="flex-1 truncate text-slate-900 dark:text-slate-100">
          {workItem.name}
        </span>
        <PriorityBadge priority={workItem.priority} />
      </Link>
    </li>
  )
}

function PriorityBadge({ priority }: { priority: WorkItem['priority'] }) {
  if (priority === 'none') return null
  const colour: Record<string, string> = {
    urgent: 'text-red-600 dark:text-red-400',
    high: 'text-amber-600 dark:text-amber-400',
    medium: 'text-slate-500 dark:text-slate-400',
    low: 'text-slate-400 dark:text-slate-500',
  }
  return (
    <span className={'text-xs ' + (colour[priority] ?? '')}>{priority}</span>
  )
}

// ── First-time state setup ──

function SetupStatesPrompt({ projectId }: { projectId: string }) {
  const mutation = useCreateProjectState()
  const [isSeeding, setIsSeeding] = useState(false)

  const seed = async () => {
    setIsSeeding(true)
    try {
      // Sequential — order matters and the count is small.
      for (const tpl of DEFAULT_STATE_GROUPS) {
        await mutation.mutateAsync({
          project_id: projectId,
          name: tpl.name,
          group: tpl.group,
          color: tpl.color,
          sequence: tpl.sequence,
          is_default: tpl.is_default,
          description: null,
        })
      }
    } finally {
      setIsSeeding(false)
    }
  }

  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-slate-300 py-10 text-center dark:border-slate-700">
      <h3 className="text-base font-medium text-slate-700 dark:text-slate-200">
        Set up workflow states
      </h3>
      <p className="max-w-md text-sm text-slate-500 dark:text-slate-400">
        Every work item lives in a state. Seed the project with five defaults
        (Backlog, Todo, In Progress, Done, Cancelled) or build your own from the
        API.
      </p>
      <Button onClick={seed} disabled={isSeeding}>
        {isSeeding ? 'Creating…' : 'Seed default states'}
      </Button>
    </div>
  )
}

// ── Work item create dialog ──

function CreateWorkItemDialog({
  projectId,
  states,
}: {
  projectId: string
  states: ProjectState[]
}) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const defaultState = states.find((s) => s.is_default) ?? states[0]
  const [stateId, setStateId] = useState<string>(defaultState?.id ?? '')
  const [priority, setPriority] = useState<WorkItem['priority']>('none')
  const mutation = useCreateWorkItem()

  const reset = () => {
    setName('')
    setStateId(defaultState?.id ?? '')
    setPriority('none')
    mutation.reset()
  }

  const submit = async () => {
    const body: WorkItemCreate = {
      project_id: projectId,
      name: name.trim(),
      state_id: stateId,
      priority,
      description_json: null,
      description_html: null,
      estimate_point_id: null,
      parent_id: null,
      start_date: null,
      target_date: null,
      sort_order: null,
      is_draft: false,
      assignee_ids: [],
      label_ids: [],
    }
    try {
      await mutation.mutateAsync(body)
      setOpen(false)
      reset()
    } catch {
      // Inline error message handles surfacing.
    }
  }

  const errorMessage = useMemo(() => {
    if (!mutation.isError) return null
    const err = mutation.error as unknown as {
      detail?: string
      message?: string
    }
    return err?.detail ?? err?.message ?? 'Something went wrong.'
  }, [mutation.isError, mutation.error])

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) reset()
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">New Work Item</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create a work item</DialogTitle>
          <DialogDescription>
            Pick a workflow state and priority. Assignees and labels come from
            the detail view.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Title
            </span>
            <Input
              value={name}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setName(e.target.value)
              }
              placeholder="What needs doing?"
              maxLength={512}
            />
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                State
              </span>
              <select
                value={stateId}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
                  setStateId(e.target.value)
                }
                className="rounded-md border border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              >
                {states.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                Priority
              </span>
              <select
                value={priority}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
                  setPriority(e.target.value as WorkItem['priority'])
                }
                className="rounded-md border border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              >
                <option value="none">None</option>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </label>
          </div>

          {errorMessage && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-300">
              {errorMessage}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="secondary"
            type="button"
            onClick={() => setOpen(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={submit}
            disabled={!name.trim() || !stateId || mutation.isPending}
          >
            {mutation.isPending ? 'Creating…' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
