/** Skeleton loading state for dashboard routes. */
export default function DashboardLoading() {
  return (
    <div className="flex h-full w-full flex-col gap-6 p-8">
      <div className="h-8 w-48 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="h-32 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800"
          />
        ))}
      </div>
      <div className="h-64 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
    </div>
  )
}
