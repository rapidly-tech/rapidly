/** Resolves the currently active navigation route and sub-route. */
import { WorkspaceContext } from '@/providers/workspaceContext'
import { useContext } from 'react'
import { useDashboardRoutes } from '../Dashboard/navigation'

export const useRoute = () => {
  const ctx = useContext(WorkspaceContext)
  const workspace = ctx?.workspace

  const dashboardRoutes = useDashboardRoutes(workspace, true)

  const currentRoute = dashboardRoutes.find((r) => r.isActive)

  const currentSubRoute = currentRoute?.subs?.find(
    (r) => 'isActive' in r && r.isActive,
  )

  return {
    currentRoute,
    currentSubRoute,
  }
}
