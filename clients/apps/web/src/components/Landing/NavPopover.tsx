'use client'

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@rapidly-tech/ui/components/primitives/popover'
import Link from 'next/link'
import { ReactNode, useCallback, useRef, useState } from 'react'
import { twMerge } from 'tailwind-merge'

export interface NavPopoverSection {
  title?: string
  items: NavPopoverItem[]
}

export interface NavPopoverItem {
  href: string
  label: string
  subtitle?: string
  target?: '_blank'
}

interface NavPopoverProps {
  trigger: ReactNode
  sections: NavPopoverSection[]
  isActive?: boolean
  layout?: 'grid' | 'flex'
}

const CLOSE_DELAY_MS = 150

const TRIGGER_BASE =
  'rp-text-secondary -m-1 flex cursor-pointer items-center gap-x-2 p-1 transition-colors hover:text-(--text-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400'

const TRIGGER_ACTIVE = 'text-(--text-primary)'

const LINK_CLASSES =
  'flex flex-col rounded-md px-4 py-2 text-sm transition-colors hover:bg-(--beige-item-hover)'

const hasSubtitles = (items: NavPopoverItem[]): boolean =>
  items.some((item) => Boolean(item.subtitle))

const resolveContentLayout = (
  layout: 'grid' | 'flex',
  sectionCount: number,
): string => {
  if (layout === 'flex') return 'flex flex-row'
  const gridColsMap: Record<number, string> = {
    1: 'grid grid-cols-1',
    2: 'grid grid-cols-2',
    3: 'grid grid-cols-3',
    4: 'grid grid-cols-4',
  }
  return gridColsMap[sectionCount] ?? 'grid grid-cols-1'
}

const NavLink = ({ item }: { item: NavPopoverItem }) => (
  <Link
    key={item.href + item.label}
    href={item.href}
    prefetch
    target={item.target}
    className={LINK_CLASSES}
  >
    <span className="font-medium">{item.label}</span>
    {item.subtitle && (
      <span className="rp-text-secondary">{item.subtitle}</span>
    )}
  </Link>
)

const SectionBlock = ({ section }: { section: NavPopoverSection }) => {
  const wideSection = hasSubtitles(section.items)

  return (
    <div
      className={twMerge('flex flex-col p-2', wideSection ? 'col-span-2' : '')}
    >
      {section.title && (
        <h3 className="rp-text-secondary px-4 py-2 text-sm">{section.title}</h3>
      )}
      <div className={twMerge(wideSection ? 'grid grid-cols-2' : '')}>
        {section.items.map((item) => (
          <NavLink key={item.href + item.label} item={item} />
        ))}
      </div>
    </div>
  )
}

export const NavPopover = ({
  trigger,
  sections,
  isActive,
  layout = 'grid',
}: NavPopoverProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const closeTimeoutRef = useRef<ReturnType<typeof setTimeout>>(null)

  const open = useCallback(() => {
    if (closeTimeoutRef.current) clearTimeout(closeTimeoutRef.current)
    setIsOpen(true)
  }, [])

  const closeWithDelay = useCallback(() => {
    closeTimeoutRef.current = setTimeout(() => setIsOpen(false), CLOSE_DELAY_MS)
  }, [])

  const handleOpenChange = useCallback(
    (next: boolean) => {
      if (next) {
        open()
      } else {
        if (closeTimeoutRef.current) clearTimeout(closeTimeoutRef.current)
        setIsOpen(false)
      }
    },
    [open],
  )

  const triggerClasses = twMerge(
    TRIGGER_BASE,
    (isOpen || isActive) && TRIGGER_ACTIVE,
  )

  const contentClasses = twMerge(
    'w-fit divide-x p-0',
    resolveContentLayout(layout, sections.length),
  )

  return (
    <Popover open={isOpen} onOpenChange={handleOpenChange}>
      <PopoverTrigger
        className={triggerClasses}
        onMouseEnter={open}
        onMouseLeave={closeWithDelay}
      >
        {trigger}
      </PopoverTrigger>
      <PopoverContent
        className={contentClasses}
        sideOffset={0}
        onMouseEnter={open}
        onMouseLeave={closeWithDelay}
        onCloseAutoFocus={(e) => e.preventDefault()}
        onInteractOutside={(e) => e.preventDefault()}
      >
        {sections.map((section, idx) => (
          <SectionBlock key={idx} section={section} />
        ))}
      </PopoverContent>
    </Popover>
  )
}
