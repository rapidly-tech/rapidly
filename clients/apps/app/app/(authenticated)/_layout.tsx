import { ErrorFallback } from '@/components/Errors/Fallback'
import { useTheme } from '@/design-system/useTheme'
import { useAppOpenTracking } from '@/hooks/useAppOpenTracking'
import DeepLinkProvider from '@/providers/DeepLinkProvider'
import NotificationsProvider from '@/providers/NotificationsProvider'
import { QueryProvider } from '@/providers/QueryProvider'
import { RapidlyClientProvider } from '@/providers/RapidlyClientProvider'
import { useSession } from '@/providers/SessionProvider'
import { ToastProvider } from '@/providers/ToastProvider'
import { UserProvider } from '@/providers/UserProvider'
import { RapidlyWorkspaceProvider } from '@/providers/WorkspaceProvider'
import { DarkTheme, ThemeProvider } from '@react-navigation/native'
import { useQueryClient } from '@tanstack/react-query'
import { Redirect, Stack, useRouter } from 'expo-router'
import React from 'react'
import { ErrorBoundary as ErrorBoundaryComponent } from 'react-error-boundary'
import { StatusBar } from 'react-native'

const RootLayout = () => {
  const theme = useTheme()
  const { session } = useSession()
  const queryClient = useQueryClient()
  const router = useRouter()

  useAppOpenTracking()

  if (!session) {
    return <Redirect href="/" />
  }

  return (
    <ErrorBoundaryComponent
      onReset={() => {
        queryClient.clear()
        router.replace('/')
      }}
      fallbackRender={({ error, resetErrorBoundary }) => (
        <ErrorFallback error={error} resetErrorBoundary={resetErrorBoundary} />
      )}
    >
      <>
        <StatusBar barStyle="light-content" />
        <Stack
          screenOptions={{
            headerStyle: {
              backgroundColor: theme.colors.background,
            },
            headerTitleStyle: {
              color: theme.colors.text,
              fontSize: 18,
            },
            contentStyle: { backgroundColor: theme.colors.background },
            headerShadowVisible: false,
          }}
        />
      </>
    </ErrorBoundaryComponent>
  )
}

export default function Providers() {
  return (
    <ThemeProvider value={DarkTheme}>
      <RapidlyClientProvider>
        <QueryProvider>
          <UserProvider>
            <DeepLinkProvider>
              <NotificationsProvider>
                <RapidlyWorkspaceProvider>
                  <ToastProvider>
                    <RootLayout />
                  </ToastProvider>
                </RapidlyWorkspaceProvider>
              </NotificationsProvider>
            </DeepLinkProvider>
          </UserProvider>
        </QueryProvider>
      </RapidlyClientProvider>
    </ThemeProvider>
  )
}
