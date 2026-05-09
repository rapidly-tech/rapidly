/** Skeleton loading state for the analytics section. */
export default function AnalyticsLoading() {
  return (
    <div className="flex h-full w-full flex-col gap-6 p-8">
      <div className="flex items-center justify-between">
        <div className="h-8 w-40 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
        <div className="h-9 w-28 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      </div>
      <div className="h-64 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      <div className="h-48 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
    </div>
  )
}
