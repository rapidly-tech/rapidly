import DashboardLayout, {
  DashboardBody,
} from '@/components/Layout/DashboardLayout'
import { SidebarProvider } from '@rapidly-tech/ui/components/primitives/sidebar'
import { cookies } from 'next/headers'

const BODY_WRAPPER = 'md:gap-y-8 max-w-(--breakpoint-sm)!'

export default async function Layout({
  children,
}: {
  children: React.ReactNode
}) {
  const cookieStore = await cookies()
  const defaultOpen = cookieStore.get('sidebar_state')?.value === 'true'

  return (
    <SidebarProvider defaultOpen={defaultOpen}>
      <DashboardLayout type="account">
        <DashboardBody wrapperClassName={BODY_WRAPPER}>
          <div className="flex flex-col gap-y-12">{children}</div>
        </DashboardBody>
      </DashboardLayout>
    </SidebarProvider>
  )
}
