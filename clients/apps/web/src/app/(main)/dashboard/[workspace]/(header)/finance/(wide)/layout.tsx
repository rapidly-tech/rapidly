import { DashboardBody } from '@/components/Layout/DashboardLayout'

/** Wide finance layout wrapping financial pages in a full-width dashboard body. */
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <DashboardBody title="Finance" className="gap-y-8 pb-16 md:gap-y-12">
      {children}
    </DashboardBody>
  )
}
