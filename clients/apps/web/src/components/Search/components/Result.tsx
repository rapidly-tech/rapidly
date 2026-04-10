import { Icon } from '@iconify/react'
import { useMemo } from 'react'

interface Props {
  icon?: React.ReactNode
  title: string
  description?: string
}

const ICON_CLASSES =
  'dark:text-slate-400 flex h-5 w-5 items-center justify-center text-slate-500'

const ENTER_HINT_CLASSES =
  "dark:bg-slate-800 -mr-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-white px-1.5 py-0.5 opacity-0 group-data-[selected='true']:opacity-100"

const ResultIcon = ({ icon }: { icon: React.ReactNode }) => (
  <span className={ICON_CLASSES}>{icon}</span>
)

const ResultDescription = ({ text }: { text: string }) => (
  <div className="text-sm text-slate-500 dark:text-slate-400">{text}</div>
)

const EnterKeyHint = () => (
  <div className={ENTER_HINT_CLASSES}>
    <Icon
      icon="solar:undo-left-round-linear"
      className="text-[1em] text-slate-500"
    />
  </div>
)

export const Result = ({ icon, title, description }: Props) => {
  const hasIcon = Boolean(icon)
  const hasDescription = Boolean(description)

  const titleRow = useMemo(
    () => (
      <div className="flex flex-row items-center gap-2">
        {hasIcon && <ResultIcon icon={icon} />}
        <div className="rp-text-primary font-medium">{title}</div>
      </div>
    ),
    [hasIcon, icon, title],
  )

  return (
    <div className="flex w-full flex-row items-center justify-between gap-3 px-2">
      <div className="flex w-full flex-col gap-0.5">
        {titleRow}
        {hasDescription && description && (
          <ResultDescription text={description} />
        )}
      </div>
      <EnterKeyHint />
    </div>
  )
}
