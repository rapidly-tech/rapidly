import React, { PropsWithChildren } from 'react'
import { twMerge } from 'tailwind-merge'

/** Props for the List container component. */
export interface ListProps extends PropsWithChildren {
  className?: string
  size?: 'small' | 'default'
}

/** Bordered vertical list container with dividers between items. */
export const List = ({ children, className, size = 'default' }: ListProps) => {
  return children ? (
    <div
      className={twMerge(
        'flex flex-col divide-y divide-white/[0.06] overflow-hidden border border-white/[0.08] bg-white/[0.04] backdrop-blur-2xl backdrop-saturate-150 dark:divide-white/[0.04] dark:border-white/[0.06] dark:bg-white/[0.03]',
        size === 'default' ? 'rounded-4xl' : 'rounded-2xl',
        className,
      )}
    >
      {children}
    </div>
  ) : null
}

/** Props for an individual row within a List. */
export interface ListItemProps extends PropsWithChildren {
  className?: string
  inactiveClassName?: string
  selectedClassName?: string
  children: React.ReactNode
  selected?: boolean
  onSelect?: (e: React.MouseEvent) => void
  size?: 'small' | 'default'
}

/** Selectable row within a List, with hover and active state styling. */
export const ListItem = ({
  className,
  inactiveClassName,
  selectedClassName,
  children,
  selected,
  onSelect,
  size = 'default',
}: ListItemProps) => {
  return (
    <div
      className={twMerge(
        'flex flex-row items-center justify-between',
        selected
          ? 'bg-white/[0.08] backdrop-blur-xl dark:bg-white/[0.06]'
          : 'hover:bg-white/[0.06] dark:hover:bg-(--beige-item-hover)',
        selected ? selectedClassName : inactiveClassName,
        onSelect && 'cursor-pointer',
        size === 'default' ? 'px-6 py-4' : 'px-4 py-2',
        className,
      )}
      onClick={onSelect}
    >
      {children}
    </div>
  )
}
