'use client'

import {
  type ProjectCycle,
  type ProjectModule,
  type ProjectState,
  type WorkItem,
  type WorkItemActivity,
  type WorkItemComment,
  type WorkItemRelation,
  type WorkItemRelationType,
  useCreateWorkItemComment,
  useCreateWorkItemRelation,
  useDeleteWorkItemRelation,
  useProject,
  useProjectCycles,
  useProjectModules,
  useProjectStates,
  useUpdateWorkItem,
  useWorkItem,
  useWorkItemActivities,
  useWorkItemComments,
  useWorkItemRelations,
  useWorkItems,
} from '@/hooks/api/projects'
import { getQueryClient } from '@/utils/api/query'
import { api } from '@/utils/client'
import { resolveResponse } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { useMutation, useQueries } from '@tanstack/react-query'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useMemo, useState } from 'react'

export default function WorkItemDetailPage() {
  const params = useParams<{ projectId: string; workItemId: string }>()
  const { projectId, workItemId } = params

  const projectQuery = useProject(projectId)
  const project = projectQuery.data

  const workItemQuery = useWorkItem(workItemId)
  const workItem = workItemQuery.data

  const statesQuery = useProjectStates(
    projectId ? { project_id: [projectId], limit: 50, page: 1 } : undefined,
    !!projectId,
  )
  const states: ProjectState[] = useMemo(
    () => statesQuery.data?.data ?? [],
    [statesQuery.data],
  )
  const state = workItem
    ? states.find((s) => s.id === workItem.state_id)
    : undefined

  if (workItemQuery.isLoading || projectQuery.isLoading) {
    return (
      <main className="mx-auto w-full max-w-4xl px-6 py-12">
        <div className="h-32 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      </main>
    )
  }

  if (!workItem || !project) {
    return (
      <main className="mx-auto w-full max-w-4xl px-6 py-12">
        <p className="text-slate-600 dark:text-slate-300">
          Work item not found.
        </p>
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
        <Link
          href={`/preview/projects/${project.id}`}
          className="text-sm text-slate-500 hover:text-emerald-600 dark:text-slate-400 dark:hover:text-emerald-400"
        >
          ← {project.name}
        </Link>
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-sm text-slate-500 dark:text-slate-400">
            {project.identifier}-{workItem.sequence_number}
          </span>
          {state && <StatePill state={state} />}
        </div>
        <h1 className="text-3xl font-semibold text-slate-900 dark:text-slate-100">
          {workItem.name}
        </h1>
        <Metadata workItem={workItem} states={states} />
      </header>

      <Description workItem={workItem} />

      <Memberships workItem={workItem} projectId={project.id} />

      <Comments workItemId={workItem.id} />

      <Relations workItem={workItem} projectId={project.id} />

      <ActivityFeed workItemId={workItem.id} states={states} />
    </main>
  )
}

// ── Memberships (cycles + modules) ──

function Memberships({
  workItem,
  projectId,
}: {
  workItem: WorkItem
  projectId: string
}) {
  const cyclesQuery = useProjectCycles(
    { project_id: [projectId], limit: 100, page: 1 },
    true,
  )
  const cycles: ProjectCycle[] = useMemo(
    () => cyclesQuery.data?.data ?? [],
    [cyclesQuery.data],
  )

  const modulesQuery = useProjectModules(
    { project_id: [projectId], limit: 100, page: 1 },
    true,
  )
  const modules: ProjectModule[] = useMemo(
    () => modulesQuery.data?.data ?? [],
    [modulesQuery.data],
  )

  // Fan-out: one query per cycle / module fetches its work-item-ids.
  // TanStack Query dedupes + caches per ID, so reloads are cheap.
  const cycleMembership = useQueries({
    queries: cycles.map((c) => ({
      queryKey: ['project_cycles', 'work_item_ids', c.id],
      queryFn: () =>
        resolveResponse(
          api.GET('/api/project-cycles/{id}/work-items', {
            params: { path: { id: c.id } },
          }),
        ),
    })),
  })
  const moduleMembership = useQueries({
    queries: modules.map((m) => ({
      queryKey: ['project_modules', 'work_item_ids', m.id],
      queryFn: () =>
        resolveResponse(
          api.GET('/api/project-modules/{id}/work-items', {
            params: { path: { id: m.id } },
          }),
        ),
    })),
  })

  const inCycleIds = useMemo(() => {
    const set = new Set<string>()
    cycles.forEach((c, i) => {
      const ids = cycleMembership[i]?.data
      if (Array.isArray(ids) && ids.includes(workItem.id)) set.add(c.id)
    })
    return set
  }, [cycles, cycleMembership, workItem.id])

  const inModuleIds = useMemo(() => {
    const set = new Set<string>()
    modules.forEach((m, i) => {
      const ids = moduleMembership[i]?.data
      if (Array.isArray(ids) && ids.includes(workItem.id)) set.add(m.id)
    })
    return set
  }, [modules, moduleMembership, workItem.id])

  return (
    <section className="grid gap-6 sm:grid-cols-2">
      <MembershipColumn
        label="Cycles"
        kind="cycle"
        membership={cycles.map((c) => ({
          id: c.id,
          name: c.name,
          assigned: inCycleIds.has(c.id),
        }))}
        workItemId={workItem.id}
      />
      <MembershipColumn
        label="Modules"
        kind="module"
        membership={modules.map((m) => ({
          id: m.id,
          name: m.name,
          assigned: inModuleIds.has(m.id),
        }))}
        workItemId={workItem.id}
      />
    </section>
  )
}

type MembershipKind = 'cycle' | 'module'

function membershipUrl(kind: MembershipKind): string {
  return kind === 'cycle'
    ? '/api/project-cycles/{id}/work-items'
    : '/api/project-modules/{id}/work-items'
}

function membershipInvalidateKey(kind: MembershipKind): string[] {
  return kind === 'cycle' ? ['project_cycles'] : ['project_modules']
}

function MembershipColumn({
  label,
  kind,
  membership,
  workItemId,
}: {
  label: string
  kind: MembershipKind
  membership: { id: string; name: string; assigned: boolean }[]
  workItemId: string
}) {
  const [pickerOpen, setPickerOpen] = useState(false)
  const assigned = membership.filter((m) => m.assigned)
  const available = membership.filter((m) => !m.assigned)

  // One mutation that closes over ``kind`` — the id is supplied at
  // mutate time so a single hook serves every chip + the picker.
  const addMutation = useMutation({
    mutationFn: ({ id, ids }: { id: string; ids: string[] }) =>
      kind === 'cycle'
        ? api.POST('/api/project-cycles/{id}/work-items', {
            params: { path: { id } },
            body: { work_item_ids: ids },
          })
        : api.POST('/api/project-modules/{id}/work-items', {
            params: { path: { id } },
            body: { work_item_ids: ids },
          }),
    onSuccess: () => {
      getQueryClient().invalidateQueries({
        queryKey: membershipInvalidateKey(kind),
      })
    },
  })
  const removeMutation = useMutation({
    mutationFn: ({ id, ids }: { id: string; ids: string[] }) =>
      kind === 'cycle'
        ? api.DELETE('/api/project-cycles/{id}/work-items', {
            params: { path: { id } },
            body: { work_item_ids: ids },
          })
        : api.DELETE('/api/project-modules/{id}/work-items', {
            params: { path: { id } },
            body: { work_item_ids: ids },
          }),
    onSuccess: () => {
      getQueryClient().invalidateQueries({
        queryKey: membershipInvalidateKey(kind),
      })
    },
  })
  // Acknowledge the URL helper; it's exported for future debugging
  // (the route names are mirrored in the mutation factories above).
  void membershipUrl

  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-sm font-medium tracking-wider text-slate-500 uppercase dark:text-slate-400">
        {label}
      </h2>
      {assigned.length === 0 && !pickerOpen ? (
        <p className="text-sm text-slate-400 dark:text-slate-500">
          Not in any {label.toLowerCase()} yet.
        </p>
      ) : (
        <ul className="flex flex-wrap gap-1.5">
          {assigned.map((m) => (
            <li key={m.id}>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                {m.name}
                <button
                  type="button"
                  onClick={() =>
                    removeMutation.mutate({ id: m.id, ids: [workItemId] })
                  }
                  disabled={removeMutation.isPending}
                  className="text-slate-400 hover:text-red-600 dark:hover:text-red-400"
                  aria-label={`Remove from ${m.name}`}
                >
                  ×
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
      {pickerOpen ? (
        <div className="flex flex-col gap-2 rounded-md border border-slate-200 p-2 dark:border-slate-800">
          <select
            defaultValue=""
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
              const id = e.target.value
              if (!id) return
              addMutation.mutate({ id, ids: [workItemId] })
              setPickerOpen(false)
            }}
            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="">Pick one…</option>
            {available.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setPickerOpen(false)}
          >
            Cancel
          </Button>
        </div>
      ) : (
        available.length > 0 && (
          <button
            type="button"
            onClick={() => setPickerOpen(true)}
            className="self-start text-xs text-emerald-600 hover:underline dark:text-emerald-400"
          >
            + Add to {label.toLowerCase().slice(0, -1)}
          </button>
        )
      )}
    </div>
  )
}

// ── Activity feed ──

function ActivityFeed({
  workItemId,
  states,
}: {
  workItemId: string
  states: ProjectState[]
}) {
  const activitiesQuery = useWorkItemActivities(
    { work_item_id: workItemId, limit: 100, page: 1 },
    true,
  )
  const activities: WorkItemActivity[] = activitiesQuery.data?.data ?? []
  const stateById = useMemo(
    () => Object.fromEntries(states.map((s) => [s.id, s] as const)),
    [states],
  )

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-medium tracking-wider text-slate-500 uppercase dark:text-slate-400">
        Activity
      </h2>
      {activitiesQuery.isLoading && (
        <div className="h-12 animate-pulse rounded-md bg-slate-100 dark:bg-slate-800" />
      )}
      {activities.length === 0 && activitiesQuery.isFetched && (
        <p className="text-sm text-slate-400 dark:text-slate-500">
          No activity yet.
        </p>
      )}
      {activities.length > 0 && (
        <ol className="flex flex-col gap-1.5 border-l border-slate-200 pl-4 dark:border-slate-800">
          {activities.map((a) => (
            <ActivityRow key={a.id} activity={a} stateById={stateById} />
          ))}
        </ol>
      )}
    </section>
  )
}

function ActivityRow({
  activity,
  stateById,
}: {
  activity: WorkItemActivity
  stateById: Record<string, ProjectState>
}) {
  const label = formatActivity(activity, stateById)
  return (
    <li className="relative flex items-baseline gap-2 text-sm">
      <span className="absolute -left-[19px] mt-1 size-2 rounded-full bg-slate-300 dark:bg-slate-600" />
      <span className="text-slate-700 dark:text-slate-200">{label}</span>
      <span className="ml-auto text-xs text-slate-400 dark:text-slate-500">
        {new Date(activity.created_at).toLocaleString()}
      </span>
    </li>
  )
}

function formatActivity(
  a: WorkItemActivity,
  stateById: Record<string, ProjectState>,
): React.ReactNode {
  const actor = a.actor_id ? actorTag(a.actor_id) : 'System'
  switch (a.verb) {
    case 'created':
      return <>{actor} created this work item.</>
    case 'state_changed':
      return (
        <>
          {actor} changed state from{' '}
          <StateName id={a.old_value} stateById={stateById} /> to{' '}
          <StateName id={a.new_value} stateById={stateById} />.
        </>
      )
    case 'priority_changed':
      return (
        <>
          {actor} changed priority from{' '}
          <code className="font-mono text-xs text-slate-500">
            {a.old_value}
          </code>{' '}
          to{' '}
          <code className="font-mono text-xs text-slate-500">
            {a.new_value}
          </code>
          .
        </>
      )
    case 'comment_added':
      return <>{actor} added a comment.</>
    case 'archived':
      return <>{actor} archived this work item.</>
    case 'unarchived':
      return <>{actor} restored this work item.</>
    case 'assignee_added':
      return <>{actor} added an assignee.</>
    case 'assignee_removed':
      return <>{actor} removed an assignee.</>
    case 'label_added':
      return <>{actor} added a label.</>
    case 'label_removed':
      return <>{actor} removed a label.</>
    case 'updated':
      return (
        <>
          {actor} updated{' '}
          <code className="font-mono text-xs text-slate-500">
            {a.field ?? 'fields'}
          </code>
          .
        </>
      )
    default:
      return (
        <>
          {actor} did something ({a.verb}).
        </>
      )
  }
}

function actorTag(userId: string): string {
  // Until we resolve user → display name, show the first 8 chars of the UUID.
  return `User ${userId.slice(0, 8)}`
}

function StateName({
  id,
  stateById,
}: {
  id: string | null | undefined
  stateById: Record<string, ProjectState>
}) {
  if (!id) return <span className="font-medium text-slate-500">—</span>
  const state = stateById[id]
  if (!state) {
    return (
      <span className="font-mono text-xs text-slate-400">{id.slice(0, 8)}</span>
    )
  }
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-xs font-medium"
      style={{
        backgroundColor: `${state.color}1a`,
        color: state.color,
      }}
    >
      <span
        className="size-1 rounded-full"
        style={{ backgroundColor: state.color }}
      />
      {state.name}
    </span>
  )
}

// ── State / metadata ──

function StatePill({ state }: { state: ProjectState }) {
  return (
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
  )
}

function Metadata({
  workItem,
  states,
}: {
  workItem: WorkItem
  states: ProjectState[]
}) {
  const updateMutation = useUpdateWorkItem(workItem.id)
  const onStateChange = (stateId: string) => {
    updateMutation.mutate({ state_id: stateId })
  }
  const onPriorityChange = (p: WorkItem['priority']) => {
    updateMutation.mutate({ priority: p })
  }

  return (
    <div className="flex flex-wrap items-center gap-4 text-sm text-slate-500 dark:text-slate-400">
      <label className="flex items-center gap-2">
        <span>State</span>
        <select
          value={workItem.state_id}
          onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
            onStateChange(e.target.value)
          }
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        >
          {states.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-2">
        <span>Priority</span>
        <select
          value={workItem.priority}
          onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
            onPriorityChange(e.target.value as WorkItem['priority'])
          }
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        >
          <option value="none">none</option>
          <option value="low">low</option>
          <option value="medium">medium</option>
          <option value="high">high</option>
          <option value="urgent">urgent</option>
        </select>
      </label>
      <TargetDateEditor workItem={workItem} />
    </div>
  )
}

function TargetDateEditor({ workItem }: { workItem: WorkItem }) {
  const mutation = useUpdateWorkItem(workItem.id)
  // The backend stores a date; we always feed the input a YYYY-MM-DD
  // string and send the same shape back (or null when cleared).  Both
  // null and an ISO datetime survive the round trip — we just slice
  // the first 10 chars for display.
  const value = workItem.target_date
    ? new Date(workItem.target_date).toISOString().slice(0, 10)
    : ''

  const onChange = (next: string) => {
    mutation.mutate({ target_date: next === '' ? null : next })
  }

  return (
    <label className="flex items-center gap-2">
      <span>Due</span>
      <input
        type="date"
        value={value}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
          onChange(e.target.value)
        }
        className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
      />
      {workItem.target_date && (
        <button
          type="button"
          onClick={() => onChange('')}
          aria-label="Clear due date"
          className="text-xs text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300"
          title="Clear due date"
        >
          ✕
        </button>
      )}
    </label>
  )
}

// ── Description ──

function Description({ workItem }: { workItem: WorkItem }) {
  const mutation = useUpdateWorkItem(workItem.id)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(workItem.description_html ?? '')

  const save = async () => {
    await mutation.mutateAsync({ description_html: draft || null })
    setEditing(false)
  }

  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium tracking-wider text-slate-500 uppercase dark:text-slate-400">
          Description
        </h2>
        {!editing && (
          <Button
            size="sm"
            variant="secondary"
            onClick={() => {
              setDraft(workItem.description_html ?? '')
              setEditing(true)
            }}
          >
            Edit
          </Button>
        )}
      </div>
      {editing ? (
        <div className="flex flex-col gap-2">
          <textarea
            value={draft}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
              setDraft(e.target.value)
            }
            rows={6}
            className="w-full rounded-md border border-slate-300 bg-white p-3 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            placeholder="Write a description…"
          />
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setEditing(false)}
            >
              Cancel
            </Button>
            <Button size="sm" onClick={save} disabled={mutation.isPending}>
              {mutation.isPending ? 'Saving…' : 'Save'}
            </Button>
          </div>
        </div>
      ) : workItem.description_html ? (
        <div
          className="prose prose-sm dark:prose-invert rounded-md border border-slate-200 bg-white p-4 text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
          // The HTML originates from the same user; phase 1 ships server-trusted
          // content.  A future iteration will route through a Tiptap-driven
          // editor that sanitises on the client and the server.
          dangerouslySetInnerHTML={{ __html: workItem.description_html }}
        />
      ) : (
        <p className="text-sm text-slate-400 dark:text-slate-500">
          No description.
        </p>
      )}
    </section>
  )
}

// ── Comments ──

function Comments({ workItemId }: { workItemId: string }) {
  const commentsQuery = useWorkItemComments(
    { work_item_id: workItemId, limit: 100, page: 1 },
    true,
  )
  const comments: WorkItemComment[] = commentsQuery.data?.data ?? []

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-medium tracking-wider text-slate-500 uppercase dark:text-slate-400">
        Comments
      </h2>
      <CommentComposer workItemId={workItemId} />
      {commentsQuery.isLoading && (
        <div className="h-12 animate-pulse rounded-md bg-slate-100 dark:bg-slate-800" />
      )}
      {comments.length === 0 && commentsQuery.isFetched && (
        <p className="text-sm text-slate-400 dark:text-slate-500">
          No comments yet.
        </p>
      )}
      <ul className="flex flex-col gap-3">
        {comments.map((c) => (
          <li
            key={c.id}
            className="rounded-md border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900"
          >
            <div className="mb-1 flex items-baseline gap-2 text-xs text-slate-400 dark:text-slate-500">
              <span className="font-mono">{c.actor_id.slice(0, 8)}</span>
              <span>{new Date(c.created_at).toLocaleString()}</span>
            </div>
            <div
              className="prose prose-sm dark:prose-invert text-slate-700 dark:text-slate-300"
              dangerouslySetInnerHTML={{ __html: c.body_html }}
            />
          </li>
        ))}
      </ul>
    </section>
  )
}

function CommentComposer({ workItemId }: { workItemId: string }) {
  const mutation = useCreateWorkItemComment()
  const [draft, setDraft] = useState('')

  const submit = async () => {
    if (!draft.trim()) return
    await mutation.mutateAsync({
      work_item_id: workItemId,
      body_html: draft.trim(),
      body_json: null,
    })
    setDraft('')
  }

  return (
    <div className="flex flex-col gap-2">
      <textarea
        value={draft}
        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
          setDraft(e.target.value)
        }
        rows={3}
        placeholder="Leave a comment…"
        className="w-full rounded-md border border-slate-300 bg-white p-3 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
      />
      <div className="flex justify-end">
        <Button
          size="sm"
          onClick={submit}
          disabled={!draft.trim() || mutation.isPending}
        >
          {mutation.isPending ? 'Posting…' : 'Post comment'}
        </Button>
      </div>
    </div>
  )
}

// ── Relations ──

const RELATION_LABEL: Record<WorkItemRelationType, string> = {
  blocks: 'blocks',
  relates_to: 'relates to',
  duplicates: 'duplicates',
}

function Relations({
  workItem,
  projectId,
}: {
  workItem: WorkItem
  projectId: string
}) {
  const relationsQuery = useWorkItemRelations(
    { work_item_id: workItem.id, limit: 100, page: 1 },
    true,
  )
  const relations: WorkItemRelation[] = relationsQuery.data?.data ?? []

  const workItemsQuery = useWorkItems(
    { project_id: [projectId], limit: 100, page: 1 },
    true,
  )
  const allWorkItems: WorkItem[] = useMemo(
    () => workItemsQuery.data?.data ?? [],
    [workItemsQuery.data],
  )
  const byId = useMemo(
    () => Object.fromEntries(allWorkItems.map((w) => [w.id, w] as const)),
    [allWorkItems],
  )

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium tracking-wider text-slate-500 uppercase dark:text-slate-400">
          Relations
        </h2>
        <CreateRelation
          sourceWorkItem={workItem}
          candidates={allWorkItems.filter((w) => w.id !== workItem.id)}
        />
      </div>
      {relations.length === 0 && relationsQuery.isFetched && (
        <p className="text-sm text-slate-400 dark:text-slate-500">
          No linked work items.
        </p>
      )}
      <ul className="flex flex-col gap-2">
        {relations.map((r) => {
          const incoming = r.related_id === workItem.id
          const otherId = incoming ? r.work_item_id : r.related_id
          const other = byId[otherId]
          return (
            <RelationRow
              key={r.id}
              relation={r}
              incoming={incoming}
              other={other}
              projectId={projectId}
            />
          )
        })}
      </ul>
    </section>
  )
}

function RelationRow({
  relation,
  incoming,
  other,
  projectId,
}: {
  relation: WorkItemRelation
  incoming: boolean
  other: WorkItem | undefined
  projectId: string
}) {
  const mutation = useDeleteWorkItemRelation(relation.id)
  const verb = incoming
    ? `is ${RELATION_LABEL[relation.relation_type]} by`
    : RELATION_LABEL[relation.relation_type]

  return (
    <li className="flex items-center justify-between gap-3 rounded-md border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex min-w-0 items-center gap-2">
        <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          {verb}
        </span>
        {other ? (
          <Link
            href={`/preview/projects/${projectId}/work-items/${other.id}`}
            className="truncate text-slate-700 hover:text-emerald-600 dark:text-slate-200 dark:hover:text-emerald-400"
          >
            {other.name}
          </Link>
        ) : (
          <span className="text-slate-400">unknown work item</span>
        )}
      </div>
      <button
        type="button"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        className="text-xs text-slate-400 hover:text-red-600 dark:hover:text-red-400"
      >
        Remove
      </button>
    </li>
  )
}

function CreateRelation({
  sourceWorkItem,
  candidates,
}: {
  sourceWorkItem: WorkItem
  candidates: WorkItem[]
}) {
  const [open, setOpen] = useState(false)
  const [relatedId, setRelatedId] = useState('')
  const [relationType, setRelationType] =
    useState<WorkItemRelationType>('relates_to')
  const mutation = useCreateWorkItemRelation()

  const submit = async () => {
    if (!relatedId) return
    try {
      await mutation.mutateAsync({
        work_item_id: sourceWorkItem.id,
        related_id: relatedId,
        relation_type: relationType,
      })
      setOpen(false)
      setRelatedId('')
      mutation.reset()
    } catch {
      // shown inline
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

  if (!open) {
    return (
      <Button
        size="sm"
        variant="secondary"
        onClick={() => setOpen(true)}
        disabled={candidates.length === 0}
      >
        Link work item
      </Button>
    )
  }

  return (
    <div className="flex flex-col gap-2 rounded-md border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="grid grid-cols-[max-content_1fr] gap-2">
        <select
          value={relationType}
          onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
            setRelationType(e.target.value as WorkItemRelationType)
          }
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        >
          <option value="relates_to">relates to</option>
          <option value="blocks">blocks</option>
          <option value="duplicates">duplicates</option>
        </select>
        <select
          value={relatedId}
          onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
            setRelatedId(e.target.value)
          }
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        >
          <option value="">Pick a work item…</option>
          {candidates.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
      {errorMessage && (
        <p className="rounded-md bg-red-50 px-2 py-1.5 text-xs text-red-700 dark:bg-red-900/20 dark:text-red-300">
          {errorMessage}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button size="sm" variant="secondary" onClick={() => setOpen(false)}>
          Cancel
        </Button>
        <Button
          size="sm"
          onClick={submit}
          disabled={!relatedId || mutation.isPending}
        >
          {mutation.isPending ? 'Linking…' : 'Link'}
        </Button>
      </div>
    </div>
  )
}
