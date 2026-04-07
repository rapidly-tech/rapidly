/**
 * Authentication lifecycle hooks for the Rapidly mobile app.
 *
 * useLogout orchestrates a complete sign-out: revokes the OAuth token,
 * unregisters push notifications, clears the query cache, wipes storage,
 * resets widget data, and navigates back to the login screen.
 */
import { useOAuthConfig } from '@/hooks/oauth'
import { useNotifications } from '@/providers/NotificationsProvider'
import { useSession } from '@/providers/SessionProvider'
import { ExtensionStorage } from '@bacons/apple-targets'
import AsyncStorage from '@react-native-async-storage/async-storage'
import { useQueryClient } from '@tanstack/react-query'
import { revokeAsync } from 'expo-auth-session'
import * as Notifications from 'expo-notifications'
import { useRouter } from 'expo-router'
import * as WebBrowser from 'expo-web-browser'
import { useCallback } from 'react'
import {
  useDeleteNotificationRecipient,
  useGetNotificationRecipient,
} from './rapidly/notifications'

const widgetStore = new ExtensionStorage('group.com.rapidly-tech.Rapidly')

export const useLogout = () => {
  const { session, setSession } = useSession()
  const { expoPushToken } = useNotifications()
  const router = useRouter()
  const { CLIENT_ID, discovery } = useOAuthConfig()

  const removeRecipient = useDeleteNotificationRecipient()
  const { data: recipient } = useGetNotificationRecipient(expoPushToken)

  const qc = useQueryClient()

  const signOut = useCallback(async () => {
    try {
      // Clean up push notification recipient on the server
      if (recipient?.id) {
        removeRecipient.mutateAsync(recipient.id).catch(() => {})
      }

      // Revoke the OAuth token (fire-and-forget)
      if (session) {
        revokeAsync(
          { token: session, clientId: CLIENT_ID },
          { revocationEndpoint: discovery.revocationEndpoint },
        ).catch(() => {})
      }

      // Platform cleanup
      Notifications.unregisterForNotificationsAsync().catch(() => {})
      WebBrowser.coolDownAsync().catch(() => {})

      // Reset all cached data
      qc.clear()
      await AsyncStorage.clear()

      // Wipe widget persistence
      widgetStore.set('widget_api_token', '')
      widgetStore.set('widget_workspace_id', '')
      widgetStore.set('widget_workspace_name', '')

      setSession(null)
      router.replace('/')
    } catch (err) {
      console.error('Logout error:', err)
      setSession(null)
      router.replace('/')
    }
  }, [
    session,
    setSession,
    removeRecipient,
    recipient,
    router,
    qc,
    CLIENT_ID,
    discovery,
  ])

  return signOut
}
