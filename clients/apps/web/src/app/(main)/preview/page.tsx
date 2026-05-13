'use client'

import {
  type UserFavorite,
  type UserFavoriteEntityType,
  useDeleteUserFavorite,
  useUserFavorites,
} from '@/hooks/api/projects'
import Link from 'next/link'

export default function PreviewIndexPage() {
  const favoritesQuery = useUserFavorites({ limit: 50, page: 1 })
  const favorites: UserFavorite[] = favoritesQuery.data?.data ?? []

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

      <FavoritesRail
        favorites={favorites}
        isLoading={favoritesQuery.isLoading}
      />

      <section className="grid gap-4 sm:grid-cols-2">
        <Card title="All projects" href="/preview/projects" />
      </section>
    </main>
  )
}

function FavoritesRail({
  favorites,
  isLoading,
}: {
  favorites: UserFavorite[]
  isLoading: boolean
}) {
  const removeFavorite = useDeleteUserFavorite()

  if (isLoading) {
    return (
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
          Favorites
        </h2>
        <div className="h-20 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      </section>
    )
  }

  if (favorites.length === 0) {
    return (
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
          Favorites
        </h2>
        <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
          Star a project, page, or work item to pin it here.
        </p>
      </section>
    )
  }

  const grouped = favorites.reduce(
    (acc, fav) => {
      ;(acc[fav.entity_type] ??= []).push(fav)
      return acc
    },
    {} as Record<UserFavoriteEntityType, UserFavorite[]>,
  )

  const order: UserFavoriteEntityType[] = [
    'project',
    'work_item',
    'page',
    'cycle',
    'module',
  ]

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
        Favorites
      </h2>
      <div className="flex flex-col gap-4">
        {order
          .filter((t) => grouped[t]?.length)
          .map((entityType) => (
            <div key={entityType} className="flex flex-col gap-2">
              <span className="text-xs font-medium tracking-wider text-slate-500 uppercase dark:text-slate-400">
                {LABELS[entityType]}
              </span>
              <ul className="grid gap-2 sm:grid-cols-2">
                {grouped[entityType].map((fav) => (
                  <li
                    key={fav.id}
                    className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-800 dark:bg-slate-900"
                  >
                    <Link
                      href={hrefFor(fav)}
                      className="truncate text-sm text-slate-900 hover:text-emerald-600 dark:text-slate-100 dark:hover:text-emerald-400"
                    >
                      {fav.entity_id}
                    </Link>
                    <button
                      type="button"
                      onClick={() => removeFavorite.mutate(fav.id)}
                      disabled={removeFavorite.isPending}
                      className="text-xs text-slate-400 hover:text-rose-500 disabled:opacity-50 dark:text-slate-500 dark:hover:text-rose-400"
                      aria-label="Remove from favorites"
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
      </div>
    </section>
  )
}

const LABELS: Record<UserFavoriteEntityType, string> = {
  project: 'Projects',
  work_item: 'Work items',
  page: 'Pages',
  cycle: 'Cycles',
  module: 'Modules',
}

function hrefFor(fav: UserFavorite): string {
  // We only have entity_id, not the parent project id, so the resolved
  // page is responsible for fetching the entity and 404-ing if it's
  // gone.  This keeps the favorites rail decoupled from the per-type
  // detail layout.
  switch (fav.entity_type) {
    case 'project':
      return `/preview/projects/${fav.entity_id}`
    case 'work_item':
      return `/preview/projects?work_item=${fav.entity_id}`
    case 'page':
      return `/preview/projects?page=${fav.entity_id}`
    case 'cycle':
      return `/preview/projects?cycle=${fav.entity_id}`
    case 'module':
      return `/preview/projects?module=${fav.entity_id}`
  }
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
