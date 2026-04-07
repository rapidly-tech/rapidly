'use client'

import {
  SelectContent as SelectContentPrimitive,
  SelectGroup as SelectGroupPrimitive,
  SelectItem as SelectItemPrimitive,
  SelectLabel as SelectLabelPrimitive,
  Select as SelectPrimitive,
  SelectSeparator as SelectSeparatorPrimitive,
  SelectTrigger as SelectTriggerPrimitive,
  SelectValue as SelectValuePrimitive,
} from '@/components/primitives/select'
import { Trigger as SelectTriggerBase } from '@radix-ui/react-select'
import type { ComponentProps } from 'react'
import { twMerge } from 'tailwind-merge'

// Re-export primitives that need no customisation
const Select = SelectPrimitive
const SelectGroup = SelectGroupPrimitive
const SelectValue = SelectValuePrimitive

// Themed trigger with hover transitions
const TRIGGER_STYLES = [
  'flex cursor-pointer flex-row gap-x-2 rounded-2xl border px-3 shadow-sm transition-all duration-200',
  'border-(--beige-border)/30 bg-white hover:bg-white/90 hover:scale-[1.02]',
  'dark:border-white/[0.06] dark:bg-white/[0.03] dark:hover:bg-(--beige-item-hover)',
].join(' ')

const SelectTrigger = ({
  ref,
  className,
  children,
  ...rest
}: ComponentProps<typeof SelectTriggerPrimitive>) => (
  <SelectTriggerPrimitive
    ref={ref}
    className={twMerge(TRIGGER_STYLES, className)}
    {...rest}
  >
    {children}
  </SelectTriggerPrimitive>
)
SelectTrigger.displayName = SelectTriggerPrimitive.displayName

// Dropdown panel
const SelectContent = ({
  ref,
  className,
  children,
  position = 'popper',
  ...rest
}: ComponentProps<typeof SelectContentPrimitive>) => (
  <SelectContentPrimitive
    ref={ref}
    className={twMerge(
      'rounded-2xl border border-(--beige-border)/20 bg-white shadow-xl dark:border-white/[0.08] dark:bg-white/[0.06] dark:backdrop-blur-[60px] dark:backdrop-saturate-[1.6]',
      className,
    )}
    {...rest}
  >
    {children}
  </SelectContentPrimitive>
)
SelectContent.displayName = SelectContentPrimitive.displayName

// Group heading label
const SelectLabel = ({
  ref,
  className,
  ...rest
}: ComponentProps<typeof SelectLabelPrimitive>) => (
  <SelectLabelPrimitive ref={ref} className={className} {...rest} />
)
SelectLabel.displayName = SelectLabelPrimitive.displayName

// Individual option row
const SelectItem = ({
  ref,
  className,
  children,
  ...rest
}: ComponentProps<typeof SelectItemPrimitive>) => (
  <SelectItemPrimitive
    ref={ref}
    className={twMerge('cursor-pointer rounded-lg', className)}
    {...rest}
  >
    {children}
  </SelectItemPrimitive>
)
SelectItem.displayName = SelectItemPrimitive.displayName

// Divider between option groups
const SelectSeparator = ({
  ref,
  className,
  ...rest
}: ComponentProps<typeof SelectSeparatorPrimitive>) => (
  <SelectSeparatorPrimitive
    ref={ref}
    className={twMerge('', className)}
    {...rest}
  />
)
SelectSeparator.displayName = SelectSeparatorPrimitive.displayName

export {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectTriggerBase,
  SelectValue,
}
