/**
 * Single notification item rendered in the notifications list.
 *
 * Resolves an icon, title, and description from the notification type
 * and payload, then displays them in a horizontal layout alongside
 * the notification timestamp.
 */
import { Box } from '@/components/Shared/Box'
import { useTheme } from '@/design-system/useTheme'
import { schemas } from '@rapidly-tech/client'
import { useMemo } from 'react'
import { StyleProp, ViewStyle } from 'react-native'
import { Iconify } from 'react-native-iconify'
import { Text } from '../Shared/Text'

type NotificationItem = schemas['NotificationsList']['notifications'][number]

export interface NotificationProps {
  style?: StyleProp<ViewStyle>
  type: NotificationItem['type']
  createdAt: string
  payload: NotificationItem['payload']
}

// Maps notification types to their Solar Linear icon names
const ICON_MAP: Record<string, string> = {
  FileShareDownloadCompletedNotification: 'solar:cloud-download-linear',
  FileShareSessionExpiredNotification: 'solar:clock-circle-linear',
  FileSharePaymentReceivedNotification: 'solar:card-linear',
  MaintainerCreateAccountNotification: 'solar:user-linear',
}

const TITLE_MAP: Record<string, string> = {
  FileShareDownloadCompletedNotification: 'Download Completed',
  FileShareSessionExpiredNotification: 'Session Expired',
  FileSharePaymentReceivedNotification: 'Payment Received',
  MaintainerCreateAccountNotification: 'New Account Created',
}

/** Builds a human-readable description from the notification payload. */
function buildDescription(
  type: string,
  payload: NotificationProps['payload'],
): string {
  switch (type) {
    case 'FileShareDownloadCompletedNotification': {
      const p =
        payload as schemas['FileShareDownloadCompletedNotificationPayload']
      return `Download completed for ${p.file_name}`
    }
    case 'FileShareSessionExpiredNotification': {
      const p = payload as schemas['FileShareSessionExpiredNotificationPayload']
      return `Session expired for ${p.file_name}`
    }
    case 'FileSharePaymentReceivedNotification': {
      const p =
        payload as schemas['FileSharePaymentReceivedNotificationPayload']
      return `Payment of ${p.formatted_amount} received for ${p.file_name}`
    }
    case 'MaintainerCreateAccountNotification': {
      const p = payload as schemas['WorkspaceCreateAccountNotificationPayload']
      return `Account created for ${p.workspace_name}`
    }
    default:
      return 'A new notification has been created'
  }
}

export const Notification = ({
  type,
  payload,
  style,
  createdAt,
}: NotificationProps) => {
  const theme = useTheme()

  const iconName = ICON_MAP[type] ?? 'solar:bell-linear'
  const heading = TITLE_MAP[type] ?? 'New Notification'
  const description = useMemo(
    () => buildDescription(type, payload),
    [type, payload],
  )

  const formattedTime = new Date(createdAt).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: 'numeric',
  })

  return (
    <Box flexDirection="row" gap="spacing-16" style={style}>
      <Box
        backgroundColor="card"
        width={40}
        height={40}
        borderRadius="border-radius-8"
        alignItems="center"
        justifyContent="center"
      >
        <Text>
          <Iconify icon={iconName} size={20} color={theme.colors.text} />
        </Text>
      </Box>
      <Box flex={1} flexDirection="column" gap="spacing-4">
        <Box flexDirection="row" gap="spacing-12">
          <Text>{heading}</Text>
          <Text color="subtext">{formattedTime}</Text>
        </Box>
        <Text color="subtext">{description}</Text>
      </Box>
    </Box>
  )
}
