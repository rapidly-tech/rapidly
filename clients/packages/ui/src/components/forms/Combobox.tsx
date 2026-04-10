'use client'

import { Icon } from '@iconify/react'
import * as React from 'react'

import { Button } from '@/components/primitives/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/primitives/command'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/primitives/popover'
import { cn } from '@/lib/utils'

/** Props for the generic Combobox component. */
export interface ComboboxProps<T> {
  // Data
  items: T[]
  value: string | null
  selectedItem: T | null

  // Callbacks
  onChange: (value: string | null) => void
  onQueryChange: (query: string) => void
  getItemValue: (item: T) => string
  getItemLabel: (item: T) => string

  // Optional customization
  renderItem?: (item: T) => React.ReactNode
  isLoading?: boolean

  // Text customization
  placeholder?: string
  searchPlaceholder?: string
  emptyLabel?: string

  // Styling
  className?: string
}

/** Searchable dropdown that combines a text input with a selectable list of items. */
export function Combobox<T>({
  items,
  value,
  selectedItem,
  onChange,
  onQueryChange,
  getItemValue,
  getItemLabel,
  renderItem,
  isLoading = false,
  placeholder = 'Select a value',
  searchPlaceholder = 'Search…',
  emptyLabel = 'No results found',
  className,
}: ComboboxProps<T>) {
  const [open, setOpen] = React.useState(false)
  const [query, setQuery] = React.useState('')

  const handleQueryChange = React.useCallback(
    (newQuery: string) => {
      setQuery(newQuery)
      onQueryChange(newQuery)
    },
    [onQueryChange],
  )

  const handleSelect = React.useCallback(
    (itemValue: string) => {
      const newValue = itemValue === value ? null : itemValue
      onChange(newValue)
      setOpen(false)
    },
    [onChange, value],
  )

  const selectedLabel = React.useMemo(() => {
    if (!value || !selectedItem) return null
    return getItemLabel(selectedItem)
  }, [value, selectedItem, getItemLabel])

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn(
            'flex w-full flex-row justify-between gap-x-2 rounded-2xl border border-(--beige-border)/30 bg-white px-3 font-normal shadow-sm transition-all duration-200 hover:scale-[1.02] hover:bg-white/90 dark:border-white/[0.06] dark:bg-white/[0.03] dark:backdrop-blur-2xl dark:backdrop-saturate-150 dark:hover:bg-(--beige-item-hover)',
            selectedItem
              ? 'text-foreground hover:text-foreground'
              : 'text-foreground/50 hover:text-foreground/50',
            className,
          )}
        >
          {selectedLabel ?? placeholder}
          <Icon icon="solar:sort-vertical-linear" className="opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-(--radix-popover-trigger-width) rounded-xl p-0">
        <Command shouldFilter={false} className="rounded-xl">
          <CommandInput
            placeholder={searchPlaceholder}
            className="h-9 border-0 focus:ring-0 focus:outline-0"
            value={query}
            onValueChange={handleQueryChange}
          />
          <CommandList>
            {isLoading ? (
              <div className="flex items-center justify-center py-6">
                <Icon
                  icon="solar:refresh-circle-linear"
                  className="h-4 w-4 animate-spin opacity-50"
                />
              </div>
            ) : items.length === 0 ? (
              <CommandEmpty>{emptyLabel}</CommandEmpty>
            ) : (
              <CommandGroup>
                {items.map((item) => {
                  const itemValue = getItemValue(item)
                  const itemLabel = getItemLabel(item)
                  const isSelected = value === itemValue

                  return (
                    <CommandItem
                      key={itemValue}
                      value={itemValue}
                      onSelect={handleSelect}
                      className="rounded-md"
                    >
                      {renderItem ? renderItem(item) : itemLabel}
                      <Icon
                        icon="solar:check-read-linear"
                        className={cn(
                          'ml-auto',
                          isSelected ? 'opacity-100' : 'opacity-0',
                        )}
                      />
                    </CommandItem>
                  )
                })}
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
