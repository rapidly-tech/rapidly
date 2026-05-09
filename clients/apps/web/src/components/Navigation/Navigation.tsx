import Avatar from '@rapidly-tech/ui/components/data/Avatar'
import { twMerge } from 'tailwind-merge'

const BASE_LIST_ITEM_CLASSES =
  'animate-background duration-10 flex items-center gap-2 py-2 px-2 w-full rounded-full transition-colors'

const ACTIVE_CLASSES =
  'bg-slate-100 dark:bg-slate-900 text-slate-700 dark:text-slate-50'

const INACTIVE_CLASSES = 'hover:text-slate-700 dark:hover:text-slate-300'

const resolveListItemClasses = (isCurrent: boolean, extra?: string): string =>
  twMerge(
    BASE_LIST_ITEM_CLASSES,
    isCurrent ? ACTIVE_CLASSES : INACTIVE_CLASSES,
    extra ?? '',
  )

export const ListItem = ({
  children,
  current,
  className,
}: {
  children: React.ReactElement
  current: boolean
  className?: string
}) => <li className={resolveListItemClasses(current, className)}>{children}</li>

export const Profile = ({
  name,
  avatar_url,
}: {
  name: string
  avatar_url: string | null
}) => (
  <>
    <div className="flex w-full min-w-0 shrink grow-0 items-center justify-between text-sm">
      <div className="flex w-full min-w-0 shrink grow-0 items-center">
        <Avatar
          name={name}
          avatar_url={avatar_url}
          className="h-8 w-8 rounded-full"
        />
        <p className="ml-4 truncate">{name}</p>
      </div>
    </div>
  </>
)

const LINK_ITEM_INNER_CLASSES = 'flex flex-row items-center gap-x-2 text-sm'

export const LinkItem = ({
  href,
  icon,
  children,
}: {
  href: string
  icon?: React.ReactElement
  children: React.ReactElement
}) => (
  <a href={href}>
    <ListItem current={false} className="rounded-lg px-4">
      <div className={LINK_ITEM_INNER_CLASSES}>
        {icon && <span className="text-lg">{icon}</span>}
        {children}
      </div>
    </ListItem>
  </a>
)

export const TextItem = ({
  onClick,
  icon,
  children,
}: {
  onClick: () => void
  icon: React.ReactElement
  children: React.ReactElement
}) => (
  <div
    className="flex cursor-pointer items-center text-sm"
    onClick={onClick}
    role="button"
    tabIndex={0}
    onKeyDown={(e) => {
      if (e.key === 'Enter' || e.key === ' ') onClick()
    }}
  >
    <ListItem current={false} className="gap-x-2 px-4 py-0 text-sm">
      <>
        <span className="text-lg">{icon}</span>
        {children}
      </>
    </ListItem>
  </div>
)
