import ImpersonationBanner from '@/components/Impersonation/ImpersonationBanner'
import DashboardLayout from '@/components/Layout/DashboardLayout'
import { SidebarProvider } from '@rapidly-tech/ui/components/primitives/sidebar'
import { cookies, headers } from 'next/headers'

/** Workspace dashboard header layout with sidebar navigation and impersonation banner. */
export default async function Layout({
  children,
}: {
  children: React.ReactNode
}) {
  const cookieStore = await cookies()
  const defaultOpen = cookieStore.get('sidebar_state')?.value === 'true'
  const headersList = await headers()
  const isImpersonating = headersList.get('x-rapidly-impersonating') === '1'

  return (
    <>
      <ImpersonationBanner />
      <SidebarProvider defaultOpen={defaultOpen}>
        <DashboardLayout isImpersonating={isImpersonating}>
          {children}
        </DashboardLayout>
      </SidebarProvider>
    </>
  )
}
