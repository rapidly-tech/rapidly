'use client'

import { type Workflow, useWorkflows } from '@/hooks/api/agents'
import Link from 'next/link'

export default function WorkflowsListPage() {
  const query = useWorkflows({ limit: 50, page: 1 })
  const workflows: Workflow[] = query.data?.data ?? []

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-16">
      <Header />

      {query.isLoading ? (
        <LoadingSkeleton />
      ) : query.isError ? (
        <ErrorBanner message={(query.error as Error).message} />
      ) : workflows.length === 0 ? (
        <EmptyState />
      ) : (
        <WorkflowList workflows={workflows} />
      )}
    </main>
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
