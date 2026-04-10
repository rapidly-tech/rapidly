'use client'

import { useListNotificationRecipients } from '@/hooks/api/notifications'
import { schemas } from '@rapidly-tech/client'
import ItemGroup from '@rapidly-tech/ui/components/navigation/ItemGroup'

const RecipientDetails = ({
  recipient,
}: {
  recipient: schemas['NotificationRecipientSchema']
}) => (
  <div className="flex flex-col gap-y-2">
    <span className="font-medium">{recipient.platform} Device</span>
    <span className="font-mono text-xs text-slate-500">
      {recipient.expo_push_token}
    </span>
  </div>
)

const EmptyRecipientsMessage = () => (
  <ItemGroup.Item>
    <p className="text-sm text-slate-500">
      You don&apos;t have any active Notification Recipients.
    </p>
  </ItemGroup.Item>
)

export const NotificationRecipientsSettings = () => {
  const { data: notificationRecipients } = useListNotificationRecipients()

  const recipients = notificationRecipients?.data ?? []
  const hasRecipients = recipients.length > 0

  return (
    <ItemGroup>
      {hasRecipients ? (
        recipients.map((recipient) => (
          <ItemGroup.Item key={recipient.id}>
            <RecipientDetails recipient={recipient} />
          </ItemGroup.Item>
        ))
      ) : (
        <EmptyRecipientsMessage />
      )}
    </ItemGroup>
  )
}
