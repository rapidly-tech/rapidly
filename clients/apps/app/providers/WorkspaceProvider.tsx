/**
 * Workspace context provider for the Rapidly mobile app.
 *
 * Loads the user's workspaces, persists the selected workspace ID,
 * synchronises the Apple Extension Storage for widget consumption,
 * and redirects to onboarding when no workspaces exist.
 */
import { Box } from '@/components/Shared/Box'
import { useWorkspaces } from '@/hooks/rapidly/workspaces'
import { useStorageState } from '@/hooks/storage'
import { ExtensionStorage } from '@bacons/apple-targets'
import { schemas } from '@rapidly-tech/client'
import AsyncStorage from '@react-native-async-storage/async-storage'
import { Redirect, usePathname } from 'expo-router'
import { createContext, PropsWithChildren, useEffect, useMemo } from 'react'
import { ActivityIndicator } from 'react-native'
import { useSession } from './SessionProvider'

const widgetStorage = new ExtensionStorage('group.com.rapidly-tech.Rapidly')

export interface WorkspaceContextValue {
  isLoading: boolean
  workspace: schemas['Workspace'] | undefined
  workspaces: schemas['Workspace'][]
  setWorkspace: (workspace: schemas['Workspace']) => void
}

const throwNotWrapped = (): never => {
  throw new Error(
    'You forgot to wrap your component in <RapidlyWorkspaceProvider>.',
  )
}

export const WorkspaceContext =
  // @ts-ignore
  createContext<WorkspaceContextValue>(throwNotWrapped)

export function RapidlyWorkspaceProvider({ children }: PropsWithChildren) {
  const [[storageLoading, storedId], setStoredId] =
    useStorageState('workspaceId')
  const { session } = useSession()
  const pathname = usePathname()

  const { data: wsData, isLoading: loadingWs } = useWorkspaces({
    enabled: !!session,
  })

  // Hydrate from AsyncStorage for cross-session persistence
  useEffect(() => {
    AsyncStorage.getItem('workspaceId').then((id) => {
      setStoredId(id ?? null)
    })
  }, [setStoredId])

  // Auto-select the first workspace when none is stored or the stored one
  // no longer exists (e.g. after switching accounts)
  useEffect(() => {
    if (!wsData || wsData.data.length === 0) return

    const stillValid = wsData.data.some((ws) => ws.id === storedId)
    if (!storedId || !stillValid) {
      setStoredId(wsData.data[0].id ?? null)
    }
  }, [wsData, storedId, setStoredId])

  const activeWorkspace = useMemo(
    () => wsData?.data.find((ws) => ws.id === storedId),
    [wsData, storedId],
  )

  // Push workspace identity to the widget extension
  useEffect(() => {
    if (activeWorkspace) {
      widgetStorage.set('widget_workspace_id', activeWorkspace.id)
      widgetStorage.set('widget_workspace_name', activeWorkspace.name)
    }
  }, [activeWorkspace])

  const loading = storageLoading || loadingWs
  const allWorkspaces = wsData?.data ?? []

  if (loading) {
    return (
      <Box flex={1} justifyContent="center" alignItems="center">
        <ActivityIndicator size="large" />
      </Box>
    )
  }

  if (allWorkspaces.length === 0 && pathname !== '/onboarding') {
    return <Redirect href="/onboarding" />
  }

  const selectWorkspace = (ws: schemas['Workspace']) => {
    setStoredId(ws.id)
    AsyncStorage.setItem('workspaceId', ws.id)
  }

  return (
    <WorkspaceContext.Provider
      value={{
        isLoading: loading,
        workspace: activeWorkspace,
        workspaces: allWorkspaces,
        setWorkspace: selectWorkspace,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  )
}
