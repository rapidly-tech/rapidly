'use client'

import { schemas } from '@rapidly-tech/client'
import React from 'react'

/** Authenticated user state shared via React context. */
export type AuthContextValue = {
  user?: schemas['UserRead']
  userWorkspaces: schemas['Workspace'][]
  setUser: React.Dispatch<React.SetStateAction<schemas['UserRead']>>
  setWorkspaceMemberships: React.Dispatch<
    React.SetStateAction<schemas['Workspace'][]>
  >
}

const stub = (): never => {
  throw new Error('You forgot to wrap your component in <UserContextProvider>.')
}

export const AuthContext = React.createContext<AuthContextValue>(
  stub as unknown as AuthContextValue,
)

/** Provides user and workspace state to the component tree. */
export const UserContextProvider = ({
  user: _user,
  userWorkspaces: _userWorkspaces,
  children,
}: {
  user: schemas['UserRead'] | undefined
  userWorkspaces: schemas['Workspace'][]
  children: React.ReactNode
}) => {
  const [user, setUser] = React.useState<schemas['UserRead'] | undefined>(_user)
  const [userWorkspaces, setWorkspaceMemberships] =
    React.useState<schemas['Workspace'][]>(_userWorkspaces)

  const contextValue = React.useMemo(
    () => ({
      user,
      setUser: setUser as React.Dispatch<
        React.SetStateAction<schemas['UserRead']>
      >,
      userWorkspaces,
      setWorkspaceMemberships,
    }),
    [user, userWorkspaces, setUser, setWorkspaceMemberships],
  )

  return (
    <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>
  )
}
