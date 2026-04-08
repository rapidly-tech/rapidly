// ── Imports ──

import { useNotifications, useNotificationsMarkRead } from '@/hooks/api'
import { useOutsideClick } from '@/utils/useOutsideClick'
import { Icon as IconifyIcon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import RelativeTime from '@rapidly-tech/ui/components/data/RelativeTime'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@rapidly-tech/ui/components/primitives/popover'
import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { twMerge } from 'tailwind-merge'
import Icon from '../Icons/Icon'

// ── Types ──

type NotificationSchema = schemas['NotificationsList']['notifications'][number]

// ── Main Component ──

export const NotificationsPopover = () => {
  const [show, setShow] = useState(false)
  const [showBadge, setShowBadge] = useState(false)

  const notifs = useNotifications()
  const markRead = useNotificationsMarkRead()

  const markLatest = () => {
    if (!notifs || !notifs.data || notifs.data.notifications.length === 0) {
      return
    }
    const first = notifs.data.notifications[0]
    markRead.mutate({ notification_id: first.id })
  }

  // Using onMouseDown to use the same event as "useOutsideClick"
  // That way useOutsideClick can cancel the event before clickBell triggers
  const clickBell = (e: React.MouseEvent) => {
    e.stopPropagation()
    e.preventDefault()

    if (!show && notifs.data) {
      setShow(true)
      markLatest()
    }

    if (show) {
      setShow(false)
    }
  }

  const [inNestedModal, setIsInNestedModal] = useState(false)

  const ref = useRef(null)

  useOutsideClick([ref], () => {
    if (inNestedModal) {
      return
    }
    setShow(false)
  })

  useEffect(() => {
    const haveNotifications =
      notifs.data && notifs.data.notifications.length > 0
    const noReadNotifications =
      haveNotifications && !notifs.data.last_read_notification_id
    const lastNotificationIsUnread =
      haveNotifications &&
      notifs.data.last_read_notification_id !== notifs.data.notifications[0].id

    const showBadge = !!(
      haveNotifications &&
      (noReadNotifications || lastNotificationIsUnread)
    )

    setShowBadge(showBadge)
  }, [notifs.data])

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          className="hover:text-foreground relative flex cursor-pointer flex-row items-center overflow-hidden rounded-lg border border-transparent px-2 text-sm text-slate-500 transition-colors dark:border-transparent dark:hover:text-slate-400"
          onMouseDown={clickBell}
        >
          <IconifyIcon
            icon="solar:bell-linear"
            className="shrink-0 text-[1em]"
            aria-hidden="true"
          />
          <span className="ml-4 truncate font-medium group-data-[collapsible=icon]:hidden">
            Notifications
          </span>
          {showBadge && (
            <div className="absolute top-0 left-3.5 h-1.5 w-1.5 rounded-full bg-(--surface-bold)" />
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent
        sideOffset={12}
        align="end"
        className={twMerge(
          'border-slate-200 bg-white shadow-lg dark:border-slate-800 dark:bg-slate-900',
          notifs.data?.notifications?.length ? 'w-96' : 'w-auto',
        )}
      >
        <List
          notifications={notifs.data?.notifications ?? []}
          setIsInNestedModal={setIsInNestedModal}
        />
      </PopoverContent>
    </Popover>
  )
}

export default Popover

// ── Sub-Components ──

export const List = ({
  notifications,
  setIsInNestedModal,
}: {
  notifications: NotificationSchema[]
  setIsInNestedModal: (_: boolean) => void
}) => {
  return (
    <div className="max-h-[480px] space-y-4 overflow-y-auto">
      {notifications.length === 0 && (
        <div className="flex items-center justify-center text-center text-sm text-slate-500 dark:text-slate-400">
          You don&apos;t have any notifications
        </div>
      )}
      {notifications.map((n) => {
        return (
          <Notification
            n={n}
            key={n.id}
            setIsInNestedModal={setIsInNestedModal}
          />
        )
      })}
    </div>
  )
}

const Item = ({
  children,
  n,
  iconClasses,
}: {
  iconClasses: string
  n: NotificationSchema
  children: { icon: React.ReactElement; text: React.ReactElement }
}) => {
  return (
    <div className="flex space-x-2.5 text-sm transition-colors duration-100">
      <Icon classes={twMerge('mt-1 p-1', iconClasses)} icon={children.icon} />
      <div>
        <div>{children.text}</div>
        <div className="text-slate-500 dark:text-slate-400">
          <RelativeTime date={new Date(n.created_at)} />
        </div>
      </div>
    </div>
  )
}

const MaintainerCreateAccount = ({
  n,
}: {
  n: schemas['WorkspaceCreateAccountNotification']
}) => {
  const { payload } = n
  return (
    <Item
      n={n}
      iconClasses="bg-amber-200 text-amber-500 dark:bg-amber-900/30 dark:text-amber-400"
    >
      {{
        text: (
          <>
            Create a{' '}
            <InternalLink href={payload.url}>
              <>payout account</>
            </InternalLink>{' '}
            now for {payload.workspace_name} to receive funds.
          </>
        ),
        icon: (
          <IconifyIcon icon="solar:info-circle-linear" className="h-4 w-4" />
        ),
      }}
    </Item>
  )
}

const FileShareDownloadCompleted = ({
  n,
}: {
  n: schemas['FileShareDownloadCompletedNotification']
}) => {
  const { payload } = n
  return (
    <Item
      n={n}
      iconClasses="bg-emerald-200 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400"
    >
      {{
        text: <>Someone downloaded your file: {payload.file_name}</>,
        icon: <IconifyIcon icon="solar:download-linear" className="h-4 w-4" />,
      }}
    </Item>
  )
}

const FileShareSessionExpired = ({
  n,
}: {
  n: schemas['FileShareSessionExpiredNotification']
}) => {
  const { payload } = n
  return (
    <Item
      n={n}
      iconClasses="bg-slate-200 text-slate-500 dark:bg-slate-800 dark:text-slate-400"
    >
      {{
        text: <>Your share link has expired: {payload.file_name}</>,
        icon: <IconifyIcon icon="solar:stopwatch-linear" className="h-4 w-4" />,
      }}
    </Item>
  )
}

const FileSharePaymentReceived = ({
  n,
}: {
  n: schemas['FileSharePaymentReceivedNotification']
}) => {
  const { payload } = n
  return (
    <Item
      n={n}
      iconClasses="bg-amber-200 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400"
    >
      {{
        text: (
          <>
            Payment received for {payload.file_name}: {payload.formatted_amount}
          </>
        ),
        icon: (
          <IconifyIcon
            icon="solar:dollar-minimalistic-linear"
            className="h-4 w-4"
          />
        ),
      }}
    </Item>
  )
}

// ── Notification Renderer ──

export const Notification = ({
  n,
}: {
  n: NotificationSchema
  setIsInNestedModal: (_: boolean) => void
}) => {
  switch (n.type) {
    case 'MaintainerCreateAccountNotification':
      return <MaintainerCreateAccount n={n} />
    case 'FileShareDownloadCompletedNotification':
      return <FileShareDownloadCompleted n={n} />
    case 'FileShareSessionExpiredNotification':
      return <FileShareSessionExpired n={n} />
    case 'FileSharePaymentReceivedNotification':
      return <FileSharePaymentReceived n={n} />
  }
}

const InternalLink = (props: {
  href: string
  children: React.ReactElement
}) => {
  return (
    <Link className="font-bold hover:underline" href={props.href}>
      {props.children}
    </Link>
  )
}
