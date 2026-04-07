import { SettingsItem } from '@/components/Settings/SettingsList'
import { Box } from '@/components/Shared/Box'
import { Text } from '@/components/Shared/Text'
import { useTheme } from '@/design-system/useTheme'
import {
  useCreateNotificationRecipient,
  useDeleteNotificationRecipient,
  useGetNotificationRecipient,
} from '@/hooks/rapidly/notifications'
import { useUpdateWorkspace, useWorkspace } from '@/hooks/rapidly/workspaces'
import { useNotifications } from '@/providers/NotificationsProvider'
import { useToast } from '@/providers/ToastProvider'
import { WorkspaceContext } from '@/providers/WorkspaceProvider'
import { schemas } from '@rapidly-tech/client'
import * as Notifications from 'expo-notifications'
import { getPermissionsAsync } from 'expo-notifications'
import { Stack } from 'expo-router'
import { useCallback, useContext, useEffect, useState } from 'react'
import { RefreshControl, ScrollView, Switch } from 'react-native'

export default function NotificationsPage() {
  const theme = useTheme()

  const { workspace } = useContext(WorkspaceContext)
  const { refetch: refetchWorkspace, isRefetching: isRefetchingWorkspace } =
    useWorkspace()

  const {
    enablePushNotifications,
    disablePushNotifications,
    pushNotificationsEnabled,
  } = usePushNotifications()

  const { mutateAsync: updateWorkspace } = useUpdateWorkspace()

  const createNotificationSettingHandler = useCallback(
    (key: keyof schemas['WorkspaceNotificationSettings']) =>
      async (value: boolean) => {
        if (!workspace?.id) {
          return
        }

        await updateWorkspace({
          workspaceId: workspace?.id,
          update: {
            notification_settings: {
              ...workspace?.notification_settings,
              [key]: value,
            },
          },
        })
      },
    [workspace, updateWorkspace],
  )

  return (
    <>
      <Stack.Screen options={{ title: 'Notifications' }} />
      <ScrollView
        refreshControl={
          <RefreshControl
            refreshing={isRefetchingWorkspace}
            onRefresh={refetchWorkspace}
          />
        }
        contentContainerStyle={{
          padding: theme.spacing['spacing-16'],
        }}
      >
        <SettingsItem title="Push Notifications" variant="static">
          <Switch
            value={pushNotificationsEnabled}
            onValueChange={(value) => {
              if (value) {
                enablePushNotifications()
              } else {
                disablePushNotifications()
              }
            }}
          />
        </SettingsItem>
        <Box height={1} backgroundColor="border" marginVertical="spacing-8" />
        <SettingsItem
          title="New Orders"
          description="Send a notification when new orders are created"
          variant="static"
        >
          <Switch
            value={workspace?.notification_settings.new_payment}
            onValueChange={createNotificationSettingHandler('new_payment')}
          />
        </SettingsItem>
        <Box
          flexDirection="column"
          gap="spacing-4"
          marginVertical="spacing-12"
          padding="spacing-16"
          backgroundColor="card"
          borderRadius="border-radius-12"
        >
          <Text variant="bodySmall" color="subtext">
            These settings will affect both email & push notifications on all
            your devices.
          </Text>
        </Box>
      </ScrollView>
    </>
  )
}

const usePushNotifications = () => {
  const [pushNotificationsEnabled, setPushNotificationsEnabled] =
    useState(false)

  const toast = useToast()
  const { expoPushToken } = useNotifications()
  const { data: notificationRecipient } = useGetNotificationRecipient(
    expoPushToken ?? undefined,
  )
  const { mutateAsync: deleteNotificationRecipient } =
    useDeleteNotificationRecipient()

  const { mutateAsync: createNotificationRecipient } =
    useCreateNotificationRecipient()

  useEffect(() => {
    getPermissionsAsync().then((status) => {
      setPushNotificationsEnabled(status.granted && !!notificationRecipient?.id)
    })
  }, [notificationRecipient])

  const enablePushNotifications = useCallback(async () => {
    const status = await Notifications.requestPermissionsAsync()

    if (status.granted) {
      try {
        const token = await Notifications.getExpoPushTokenAsync()
        if (token.data) {
          await createNotificationRecipient(token.data)
          setPushNotificationsEnabled(true)
          return
        }
      } catch (error: unknown) {
        const err = error as Record<string, any> | undefined
        if (err?.response?.status === 422) {
          setPushNotificationsEnabled(true)
          return
        }
        const status = err?.response?.status
        const message = err?.error?.detail?.[0]?.msg || err?.message
        toast.showError(
          `Failed to enable push notifications${status ? ` (${status})` : ''}${message ? `: ${message}` : ''}`,
        )
      }
    }

    setPushNotificationsEnabled(status.granted)
  }, [createNotificationRecipient, toast])

  const disablePushNotifications = useCallback(async () => {
    if (notificationRecipient?.id) {
      await deleteNotificationRecipient(notificationRecipient.id)
    }

    setPushNotificationsEnabled(false)
  }, [deleteNotificationRecipient, notificationRecipient])

  return {
    enablePushNotifications,
    disablePushNotifications,
    pushNotificationsEnabled,
  }
}
