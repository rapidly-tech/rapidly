import {
  TabsContent as TabsContentPrimitive,
  TabsList as TabsListPrimitive,
  Tabs as TabsPrimitive,
  TabsTrigger as TabsTriggerPrimitive,
} from '@/components/primitives/tabs'
import type { ComponentProps } from 'react'
import { twMerge } from 'tailwind-merge'

// Root tabs controller -- no styling overrides needed
const Tabs = TabsPrimitive

// Layout presets for the tab strip
const STRIP_BASE =
  'relative flex h-fit w-fit flex-row items-start gap-2 rounded-2xl bg-transparent ring-0 md:flex-row dark:bg-transparent dark:ring-0'
const STRIP_HORIZONTAL = 'md:flex-row md:items-center md:justify-start'
const STRIP_VERTICAL = 'flex-col md:flex-col'

/** Container for tab trigger buttons. Supports vertical layout via the `vertical` prop. */
const TabsList = ({
  ref,
  className,
  vertical,
  ...rest
}: ComponentProps<typeof TabsListPrimitive> & { vertical?: boolean }) => (
  <TabsListPrimitive
    ref={ref}
    className={twMerge(
      STRIP_BASE,
      vertical ? STRIP_VERTICAL : STRIP_HORIZONTAL,
      className,
    )}
    {...rest}
  />
)
TabsList.displayName = TabsListPrimitive.displayName

// Shared trigger token classes
const TRIGGER_BASE = [
  'cursor-pointer px-4 text-slate-400 hover:text-slate-700 transition-all duration-200',
  'data-[state=active]:rounded-2xl data-[state=active]:bg-(--beige-item-hover) data-[state=active]:text-slate-900 data-[state=active]:shadow-md data-[state=active]:border data-[state=active]:border-(--beige-border)/20',
  'dark:text-slate-500 dark:hover:text-slate-300',
  'dark:data-[state=active]:bg-(--beige-item-hover) dark:data-[state=active]:border-(--beige-border)/20 dark:data-[state=active]:text-white',
].join(' ')

const TRIGGER_SIZES: Record<string, string> = {
  default: 'text-sm',
  small: 'text-xs',
}

/** Individual tab button that activates a matching TabsContent panel. */
const TabsTrigger = ({
  ref,
  className,
  size = 'default',
  ...rest
}: ComponentProps<typeof TabsTriggerPrimitive> & {
  size?: 'default' | 'small'
}) => (
  <TabsTriggerPrimitive
    ref={ref}
    className={twMerge(TRIGGER_BASE, TRIGGER_SIZES[size], className)}
    {...rest}
  />
)
TabsTrigger.displayName = TabsTriggerPrimitive.displayName

/** Panel rendered when its associated TabsTrigger is the active tab. */
const TabsContent = ({
  ref,
  className,
  ...rest
}: ComponentProps<typeof TabsContentPrimitive>) => (
  <TabsContentPrimitive ref={ref} className={twMerge(className)} {...rest} />
)
TabsContent.displayName = TabsContentPrimitive.displayName

export { Tabs, TabsContent, TabsList, TabsTrigger }
