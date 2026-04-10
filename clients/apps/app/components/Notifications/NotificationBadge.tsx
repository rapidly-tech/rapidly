/**
 * Notifications icon with an unread indicator dot.
 *
 * Links to the notifications list screen. When there are unread
 * notifications a small primary-colored dot appears at the top-right
 * corner of the icon.
 */
import { Box } from '@/components/Shared/Box'
import { useTheme } from '@/design-system/useTheme'
import { useNotificationsBadge } from '@/hooks/notifications'
import { Link } from 'expo-router'
import { Iconify } from 'react-native-iconify'
import { Touchable } from '../Shared/Touchable'

export const NotificationBadge = () => {
  const theme = useTheme()
  const hasUnread = useNotificationsBadge()

  return (
    <Link href="/notifications" asChild>
      <Touchable hitSlop={16} style={{ position: 'relative' }}>
        <Iconify icon="solar:bolt-linear" size={24} color={theme.colors.text} />
        {hasUnread ? (
          <Box
            backgroundColor="primary"
            position="absolute"
            top={0}
            right={0}
            width={4}
            height={4}
            borderRadius="border-radius-2"
          />
        ) : null}
      </Touchable>
    </Link>
  )
}
