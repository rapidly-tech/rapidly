/** Skeleton loading state for portal routes. */
export default function PortalLoading() {
  return (
    <div className="flex h-full w-full flex-col gap-6 p-8">
      <div className="h-6 w-32 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      <div className="h-48 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
    </div>
  )
}
