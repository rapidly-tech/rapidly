import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Projects — Rapidly',
  description: 'Project management workspace inside Rapidly.',
}

export default function PreviewIndexPage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-16">
      <header className="flex flex-col gap-3">
        <span className="text-xs font-medium tracking-wider text-emerald-600 uppercase dark:text-emerald-400">
          Rapidly · Preview
        </span>
        <h1 className="text-4xl font-semibold text-slate-900 dark:text-slate-100">
          Projects
        </h1>
        <p className="max-w-2xl text-base leading-relaxed text-slate-600 dark:text-slate-400">
          A workspace for tracking work items, cycles, modules, and pages.
          Currently under construction — the API surface lives under{' '}
          <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-sm text-slate-800 dark:bg-slate-800 dark:text-slate-200">
            /api/projects
          </code>{' '}
          and related routes.
        </p>
      </header>

      <section className="grid gap-4 sm:grid-cols-2">
        <Card title="Projects" href="/preview/projects" />
        <Card title="States" href="/preview/states" />
        <Card title="Labels" href="/preview/labels" />
        <Card title="Estimates" href="/preview/estimates" />
      </section>
    </main>
  )
}

function Card({ title, href }: { title: string; href: string }) {
  return (
    <a
      href={href}
      className="group flex flex-col gap-2 rounded-lg border border-slate-200 bg-white p-5 transition hover:border-emerald-400 hover:shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:hover:border-emerald-600"
    >
      <span className="text-lg font-medium text-slate-900 dark:text-slate-100">
        {title}
      </span>
      <span className="text-sm text-slate-500 group-hover:text-emerald-600 dark:text-slate-400 dark:group-hover:text-emerald-400">
        Open →
      </span>
    </a>
  )
}
