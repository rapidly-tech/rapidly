/** Onboarding layout providing a dark background wrapper for the onboarding flow. */
export default async function Layout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex h-full flex-col dark:bg-slate-950">{children}</div>
  )
}
