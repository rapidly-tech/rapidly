'use client'

import { schemas } from '@rapidly-tech/client'
import React from 'react'

const stub = (): never => {
  throw new Error(
    'You forgot to wrap your component in <WorkspaceContextProvider>.',
  )
}

interface WorkspaceContextType {
  workspace: schemas['Workspace']
  workspaces: schemas['Workspace'][]
}

export const WorkspaceContext = React.createContext<WorkspaceContextType>(
  stub as unknown as WorkspaceContextType,
)

/** Scopes child components to a specific workspace and its siblings. */
export const WorkspaceContextProvider = ({
  workspace,
  workspaces,
  children,
}: {
  workspace: schemas['Workspace']
  workspaces: schemas['Workspace'][]
  children: React.ReactNode
}) => {
  return (
    <WorkspaceContext.Provider
      value={{
        workspace,
        workspaces,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  )
}
