import { twMerge } from 'tailwind-merge'

const GROUP_CONTAINER =
  'glass-elevated dark:bg-slate-900 dark:divide-slate-700 w-full flex-col divide-y divide-slate-200/50 overflow-hidden rounded-2xl bg-slate-50 shadow-xs lg:rounded-3xl'

export const SettingsGroup: React.FC<React.PropsWithChildren> = ({
  children,
}) => <div className={GROUP_CONTAINER}>{children}</div>

export interface SettingsGroupItemProps {
  title: string
  description?: string
  vertical?: boolean
}

const resolveItemLayout = (vertical?: boolean): string =>
  vertical
    ? 'flex-col'
    : 'flex-col md:flex-row md:items-start md:justify-between'

const resolveChildrenAlignment = (vertical?: boolean): string =>
  twMerge(
    'flex w-full flex-row gap-y-2 md:w-full',
    vertical ? '' : 'md:justify-end',
  )

const ItemHeader = ({
  title,
  description,
}: {
  title: string
  description?: string
}) => (
  <div className="flex w-full flex-col md:max-w-1/2">
    <h3 className="text-sm font-medium">{title}</h3>
    {description && (
      <p className="text-xs text-slate-500 dark:text-slate-400">
        {description}
      </p>
    )}
  </div>
)

export const SettingsGroupItem: React.FC<
  React.PropsWithChildren<SettingsGroupItemProps>
> = ({ children, title, description, vertical }) => (
  <div
    className={twMerge(
      'flex gap-x-12 gap-y-4 p-4',
      resolveItemLayout(vertical),
    )}
  >
    <ItemHeader title={title} description={description} />
    {children && (
      <div className={resolveChildrenAlignment(vertical)}>{children}</div>
    )}
  </div>
)

export const SettingsGroupActions: React.FC<React.PropsWithChildren> = ({
  children,
}) => (
  <div className="flex flex-col gap-4 p-4 md:flex-row md:items-center">
    {children}
  </div>
)
