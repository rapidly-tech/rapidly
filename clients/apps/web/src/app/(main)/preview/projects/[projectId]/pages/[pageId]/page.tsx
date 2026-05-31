'use client'

import {
  type ProjectPageAccess,
  useProject,
  useProjectPage,
  useUpdateProjectPage,
} from '@/hooks/api/projects'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Input from '@rapidly-tech/ui/components/forms/Input'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'

export default function ProjectPageDetailPage() {
  const params = useParams<{ projectId: string; pageId: string }>()
  const { projectId, pageId } = params

  const projectQuery = useProject(projectId)
  const project = projectQuery.data

  const pageQuery = useProjectPage(pageId)
  const page = pageQuery.data

  if (pageQuery.isLoading || projectQuery.isLoading) {
    return (
      <main className="mx-auto w-full max-w-3xl px-6 py-12">
        <div className="h-32 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      </main>
    )
  }

  if (!page || !project) {
    return (
      <main className="mx-auto w-full max-w-3xl px-6 py-12">
        <p className="text-slate-600 dark:text-slate-300">Page not found.</p>
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
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-2">
        <Link
          href={`/preview/projects/${project.id}`}
          className="text-sm text-slate-500 hover:text-emerald-600 dark:text-slate-400 dark:hover:text-emerald-400"
        >
          ← {project.name}
        </Link>
        <PageHeader pageId={page.id} name={page.name} slug={page.slug} />
        <PageMetadata
          pageId={page.id}
          access={page.access}
          isLocked={page.is_locked}
        />
      </header>

      <PageBody pageId={page.id} initialHtml={page.description_html ?? ''} />
    </main>
  )
}

function PageHeader({
  pageId,
  name,
  slug,
}: {
  pageId: string
  name: string
  slug: string
}) {
  const mutation = useUpdateProjectPage(pageId)
  const [editing, setEditing] = useState(false)
  const [draftName, setDraftName] = useState(name)

  const save = async () => {
    if (!draftName.trim() || draftName === name) {
      setEditing(false)
      return
    }
    await mutation.mutateAsync({ name: draftName.trim() })
    setEditing(false)
  }

  return (
    <div className="flex items-baseline justify-between gap-3">
      {editing ? (
        <Input
          autoFocus
          value={draftName}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            setDraftName(e.target.value)
          }
          onBlur={save}
          onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
            if (e.key === 'Enter') save()
            else if (e.key === 'Escape') {
              setDraftName(name)
              setEditing(false)
            }
          }}
          className="text-3xl font-semibold"
        />
      ) : (
        <h1
          className="text-3xl font-semibold text-slate-900 hover:cursor-text dark:text-slate-100"
          onClick={() => {
            setDraftName(name)
            setEditing(true)
          }}
        >
          {name}
        </h1>
      )}
      <span className="font-mono text-xs text-slate-400 dark:text-slate-500">
        /{slug}
      </span>
    </div>
  )
}

function PageMetadata({
  pageId,
  access,
  isLocked,
}: {
  pageId: string
  access: ProjectPageAccess
  isLocked: boolean
}) {
  const mutation = useUpdateProjectPage(pageId)
  return (
    <div className="flex flex-wrap items-center gap-3 text-sm text-slate-500 dark:text-slate-400">
      <label className="flex items-center gap-2">
        <span>Access</span>
        <select
          value={access}
          onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
            mutation.mutate({ access: e.target.value as ProjectPageAccess })
          }
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        >
          <option value="public">public</option>
          <option value="private">private</option>
        </select>
      </label>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={isLocked}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            mutation.mutate({ is_locked: e.target.checked })
          }
        />
        <span>Locked</span>
      </label>
    </div>
  )
}

function PageBody({
  pageId,
  initialHtml,
}: {
  pageId: string
  initialHtml: string
}) {
  const mutation = useUpdateProjectPage(pageId)
  const [draft, setDraft] = useState(initialHtml)
  const [dirty, setDirty] = useState(false)

  // When the page changes (navigation), reset the draft.
  useEffect(() => {
    setDraft(initialHtml)
    setDirty(false)
  }, [pageId, initialHtml])

  const save = async () => {
    await mutation.mutateAsync({ description_html: draft || null })
    setDirty(false)
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
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium tracking-wider text-slate-500 uppercase dark:text-slate-400">
          Body
        </h2>
        <div className="flex items-center gap-2">
          {dirty && (
            <span className="text-xs text-slate-400 dark:text-slate-500">
              Unsaved changes
            </span>
          )}
          <Button
            size="sm"
            onClick={save}
            disabled={!dirty || mutation.isPending}
          >
            {mutation.isPending ? 'Saving…' : 'Save'}
          </Button>
        </div>
      </div>
      <textarea
        value={draft}
        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => {
          setDraft(e.target.value)
          setDirty(true)
        }}
        rows={20}
        placeholder="Write the page body in plain HTML. Yjs collab editing comes in a future phase."
        className="min-h-[300px] w-full rounded-md border border-slate-300 bg-white p-4 font-mono text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
      />
      {errorMessage && (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-300">
          {errorMessage}
        </p>
      )}
    </section>
  )
}
