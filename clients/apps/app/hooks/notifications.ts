/**
 * Hook that tracks whether the notification badge should be visible.
 *
 * The badge shows when there are notifications and the most recent one
 * hasn't been marked as read yet.
 */
import { useEffect, useState } from 'react'
import { useListNotifications } from './rapidly/notifications'

export const useNotificationsBadge = (): boolean => {
  const [visible, setVisible] = useState(false)
  const { data: feed } = useListNotifications()

  useEffect(() => {
    if (!feed || feed.notifications.length === 0) {
      setVisible(false)
      return
    }

    const neverRead = !feed.last_read_notification_id
    const latestUnread =
      feed.last_read_notification_id !== feed.notifications[0].id

    setVisible(neverRead || latestUnread)
  }, [feed])

  return visible
}
