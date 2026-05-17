'use client'

import { useListWorkspaces } from '@/hooks/api/org'
import {
  type Project,
  type ProjectCreate,
  type UserFavorite,
  useCreateProject,
  useCreateUserFavorite,
  useDeleteUserFavorite,
  useProjects,
  useUserFavorites,
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
import { useMemo, useState } from 'react'

export default function ProjectsListPage() {
  const workspacesQuery = useListWorkspaces({ limit: 50, page: 1 })
  const workspaces = workspacesQuery.data?.data ?? []

  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const activeWorkspaceId = workspaceId ?? workspaces[0]?.id ?? null

  const [search, setSearch] = useState('')
  const [includeArchived, setIncludeArchived] = useState(false)

  const projectsQuery = useProjects(
    activeWorkspaceId
      ? {
          workspace_id: [activeWorkspaceId],
          include_archived: includeArchived,
          limit: 50,
          page: 1,
        }
      : undefined,
    !!activeWorkspaceId,
  )
  // Stable reference for downstream memos — TanStack Query already
  // returns the same array reference across renders with identical
  // data, but the ``?? []`` fallback creates a fresh empty array on
  // every render unless we cache it.
  const projects: Project[] = useMemo(
    () => projectsQuery.data?.data ?? [],
    [projectsQuery.data],
  )

  const normalisedSearch = search.trim().toLowerCase()
  // Filter is client-side over the already-fetched page; the backend
  // list endpoint doesn't accept a name param yet, and the page size
  // (50) is the same limit the previous unfiltered view already had,
  // so behaviour is strictly additive.
  const visibleProjects = useMemo(() => {
    if (normalisedSearch === '') return projects
    return projects.filter(
      (p) =>
        p.name.toLowerCase().includes(normalisedSearch) ||
        p.identifier.toLowerCase().includes(normalisedSearch),
    )
  }, [projects, normalisedSearch])

  const favoritesQuery = useUserFavorites({
    entity_type: 'project',
    limit: 100,
    page: 1,
  })
  const favoriteByProjectId = useMemo(() => {
    const map = new Map<string, UserFavorite>()
    for (const fav of favoritesQuery.data?.data ?? []) {
      map.set(fav.entity_id, fav)
    }
    return map
  }, [favoritesQuery.data])

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <span className="text-xs font-medium tracking-wider text-emerald-600 uppercase dark:text-emerald-400">
          Rapidly · Preview
        </span>
        <div className="flex items-baseline justify-between gap-4">
          <h1 className="text-3xl font-semibold text-slate-900 dark:text-slate-100">
            Projects
          </h1>
          {activeWorkspaceId && (
            <CreateProjectDialog workspaceId={activeWorkspaceId} />
          )}
        </div>
        <WorkspacePicker
          workspaces={workspaces}
          activeWorkspaceId={activeWorkspaceId}
          onSelect={setWorkspaceId}
        />
      </header>

      {activeWorkspaceId && (
        <div className="flex flex-wrap items-center gap-3">
          <Input
            type="search"
            value={search}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setSearch(e.target.value)
            }
            placeholder="Search by name or identifier…"
            className="w-full max-w-md"
          />
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setIncludeArchived(e.target.checked)
              }
              className="accent-emerald-600"
            />
            Show archived
          </label>
        </div>
      )}

      {!activeWorkspaceId && !workspacesQuery.isLoading && (
        <EmptyState
          title="No workspace yet"
          description="Create a workspace in the dashboard before adding projects."
        />
      )}

      {projectsQuery.isLoading && <ListSkeleton />}

      {projects.length === 0 && projectsQuery.isFetched && (
        <EmptyState
          title="No projects in this workspace"
          description="Use the New Project button to create one."
        />
      )}

      {projects.length > 0 &&
        visibleProjects.length === 0 &&
        normalisedSearch !== '' && (
          <EmptyState
            title="No matches"
            description={`No project name or identifier contains "${search.trim()}".`}
          />
        )}

      <ul className="grid gap-3">
        {visibleProjects.map((p: Project) => (
          <ProjectRow
            key={p.id}
            project={p}
            favorite={favoriteByProjectId.get(p.id)}
          />
        ))}
      </ul>
    </main>
  )
}

// ── Workspace picker ──

function WorkspacePicker({
  workspaces,
  activeWorkspaceId,
  onSelect,
}: {
  workspaces: { id: string; name: string }[]
  activeWorkspaceId: string | null
  onSelect: (id: string) => void
}) {
  if (workspaces.length <= 1) return null
  return (
    <div className="flex flex-wrap gap-2">
      {workspaces.map((w) => {
        const active = w.id === activeWorkspaceId
        return (
          <button
            key={w.id}
            type="button"
            onClick={() => onSelect(w.id)}
            className={
              'rounded-md border px-3 py-1.5 text-sm transition ' +
              (active
                ? 'border-emerald-500 bg-emerald-50 text-emerald-700 dark:border-emerald-400 dark:bg-emerald-950/30 dark:text-emerald-300'
                : 'border-slate-200 text-slate-600 hover:border-slate-300 dark:border-slate-800 dark:text-slate-300 dark:hover:border-slate-700')
            }
          >
            {w.name}
          </button>
        )
      })}
    </div>
  )
}

// ── Project row ──

function ProjectRow({
  project,
  favorite,
}: {
  project: Project
  favorite: UserFavorite | undefined
}) {
  const create = useCreateUserFavorite()
  const remove = useDeleteUserFavorite()
  const pending = create.isPending || remove.isPending
  const isFavorite = favorite !== undefined

  const toggleFavorite = (e: React.MouseEvent) => {
    e.preventDefault()
    if (pending) return
    if (favorite) {
      remove.mutate(favorite.id)
    } else {
      create.mutate({ entity_type: 'project', entity_id: project.id })
    }
  }

  return (
    <li>
      <Link
        href={`/preview/projects/${project.id}`}
        className="flex items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white p-4 transition hover:border-emerald-400 hover:shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:hover:border-emerald-600"
      >
        <div className="flex min-w-0 flex-col">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={toggleFavorite}
              disabled={pending}
              aria-label={
                isFavorite ? 'Remove from favorites' : 'Add to favorites'
              }
              aria-pressed={isFavorite}
              className={
                'text-base leading-none transition disabled:opacity-50 ' +
                (isFavorite
                  ? 'text-emerald-500 hover:text-emerald-600 dark:text-emerald-400 dark:hover:text-emerald-300'
                  : 'text-slate-300 hover:text-emerald-500 dark:text-slate-600 dark:hover:text-emerald-400')
              }
            >
              {isFavorite ? '★' : '☆'}
            </button>
            <span className="rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-300">
              {project.identifier}
            </span>
            <span className="truncate text-base font-medium text-slate-900 dark:text-slate-100">
              {project.name}
            </span>
            {project.archived_at && (
              <span className="rounded-md bg-amber-100 px-1.5 py-0.5 text-xs text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
                archived
              </span>
            )}
          </div>
          {project.description && (
            <p className="mt-1 line-clamp-2 text-sm text-slate-500 dark:text-slate-400">
              {project.description}
            </p>
          )}
        </div>
        <span className="text-xs text-slate-400 dark:text-slate-500">
          /{project.slug}
        </span>
      </Link>
    </li>
  )
}

// ── Create dialog ──

function CreateProjectDialog({ workspaceId }: { workspaceId: string }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [identifier, setIdentifier] = useState('')
  const [slug, setSlug] = useState('')
  const [description, setDescription] = useState('')
  const mutation = useCreateProject()

  const reset = () => {
    setName('')
    setIdentifier('')
    setSlug('')
    setDescription('')
    mutation.reset()
  }

  const submit = async () => {
    const body: ProjectCreate = {
      workspace_id: workspaceId,
      name: name.trim(),
      identifier: identifier.trim().toUpperCase(),
      slug: slug.trim().toLowerCase(),
      description: description.trim() || null,
      visibility: 'private',
      emoji: null,
      color: null,
      cover_image_url: null,
      is_cycles_enabled: true,
      is_modules_enabled: true,
      is_views_enabled: true,
      is_pages_enabled: true,
      is_intake_enabled: false,
    }
    try {
      await mutation.mutateAsync(body)
      setOpen(false)
      reset()
    } catch {
      // Error surface is the form-level message below.
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
        <Button size="sm">New Project</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create a project</DialogTitle>
          <DialogDescription>
            Projects group work items, cycles, and pages inside a workspace.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <LabeledField label="Name">
            <Input
              value={name}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setName(e.target.value)
              }
              placeholder="Atlas"
              maxLength={255}
            />
          </LabeledField>
          <div className="grid grid-cols-2 gap-3">
            <LabeledField label="Identifier" hint="2–12 letters/digits">
              <Input
                value={identifier}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setIdentifier(e.target.value.toUpperCase())
                }
                placeholder="ATL"
                maxLength={12}
              />
            </LabeledField>
            <LabeledField label="Slug" hint="URL-safe, lowercase">
              <Input
                value={slug}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setSlug(e.target.value.toLowerCase())
                }
                placeholder="atlas"
                maxLength={64}
              />
            </LabeledField>
          </div>
          <LabeledField label="Description">
            <Input
              value={description}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setDescription(e.target.value)
              }
              placeholder="Optional"
              maxLength={4096}
            />
          </LabeledField>

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
            disabled={
              !name.trim() ||
              identifier.trim().length < 2 ||
              slug.trim().length < 2 ||
              mutation.isPending
            }
          >
            {mutation.isPending ? 'Creating…' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function LabeledField({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="flex items-baseline justify-between gap-2 text-sm font-medium text-slate-700 dark:text-slate-300">
        {label}
        {hint && (
          <span className="text-xs font-normal text-slate-400">{hint}</span>
        )}
      </span>
      {children}
    </label>
  )
}

// ── Misc ──

function ListSkeleton() {
  return (
    <ul className="grid gap-3">
      {[0, 1, 2].map((i) => (
        <li
          key={i}
          className="h-16 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800"
        />
      ))}
    </ul>
  )
}

function EmptyState({
  title,
  description,
}: {
  title: string
  description: string
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-slate-300 py-12 text-center dark:border-slate-700">
      <p className="text-base font-medium text-slate-700 dark:text-slate-200">
        {title}
      </p>
      <p className="max-w-md text-sm text-slate-500 dark:text-slate-400">
        {description}
      </p>
    </div>
  )
}
