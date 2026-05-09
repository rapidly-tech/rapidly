'use client'

import { Icon } from '@iconify/react'
import { enums } from '@rapidly-tech/client'
import { Checkbox } from '@rapidly-tech/ui/components/primitives/checkbox'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@rapidly-tech/ui/components/primitives/popover'
import { useCallback, useMemo, useState } from 'react'

interface WebhookEventTypeSelectProps {
  selectedEventTypes: string[]
  onSelectEventTypes: (eventTypes: string[]) => void
  className?: string
}

const TRIGGER_CLASSES =
  'dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 flex h-10 items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-xs hover:bg-slate-50'

const SEARCH_INPUT_CLASSES =
  'dark:bg-slate-800 dark:text-slate-200 dark:placeholder:text-slate-500 w-full rounded-md border-0 bg-slate-50 px-3 py-2 text-sm outline-none placeholder:text-slate-400'

const ITEM_LABEL_CLASSES =
  'dark:hover:bg-slate-700 flex cursor-pointer items-center gap-3 rounded-md px-2 py-2 hover:bg-slate-50'

const formatLabel = (selected: string[]): string => {
  if (selected.length === 0) return 'All Event Types'
  if (selected.length === 1) return selected[0]
  return `${selected.length} event types`
}

const isSelected = (selected: string[], eventType: string): boolean =>
  selected.includes(eventType)

const StatusBar = ({
  count,
  onClear,
}: {
  count: number
  onClear: () => void
}) => (
  <div className="flex items-center justify-between border-b px-3 py-2 dark:border-slate-700">
    <span className="text-xs text-slate-500 dark:text-slate-400">
      {count === 0 ? 'All events' : `${count} selected`}
    </span>
    {count > 0 && (
      <button
        type="button"
        onClick={onClear}
        className="text-xs text-slate-600 hover:text-slate-500 dark:text-slate-400 dark:hover:text-slate-300"
      >
        Clear
      </button>
    )}
  </div>
)

const EmptyResults = () => (
  <div className="py-4 text-center text-sm text-slate-500">
    No event types found
  </div>
)

export const WebhookEventTypeSelect = ({
  selectedEventTypes,
  onSelectEventTypes,
  className,
}: WebhookEventTypeSelectProps) => {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')

  const allEventTypes = useMemo(
    () => Object.values(enums.webhookEventTypeValues),
    [],
  )

  const filteredEventTypes = useMemo(() => {
    if (!search) return allEventTypes
    const term = search.toLowerCase()
    return allEventTypes.filter((t) => t.toLowerCase().includes(term))
  }, [search, allEventTypes])

  const toggleEventType = useCallback(
    (eventType: string) => {
      const next = isSelected(selectedEventTypes, eventType)
        ? selectedEventTypes.filter((t) => t !== eventType)
        : [...selectedEventTypes, eventType]
      onSelectEventTypes(next)
    },
    [selectedEventTypes, onSelectEventTypes],
  )

  const clearAll = useCallback(
    () => onSelectEventTypes([]),
    [onSelectEventTypes],
  )

  const label = useMemo(
    () => formatLabel(selectedEventTypes),
    [selectedEventTypes],
  )

  const hasResults = filteredEventTypes.length > 0

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={`${TRIGGER_CLASSES} ${className ?? ''}`}
        >
          <span className="truncate">{label}</span>
          <Icon
            icon="solar:alt-arrow-down-linear"
            className="h-4 w-4 opacity-50"
          />
        </button>
      </PopoverTrigger>
      <PopoverContent
        className="w-72 p-0"
        align="start"
        onOpenAutoFocus={(e: Event) => e.preventDefault()}
      >
        <div className="border-b p-2">
          <input
            type="text"
            placeholder="Search event types..."
            aria-label="Search event types"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={SEARCH_INPUT_CLASSES}
          />
        </div>
        <StatusBar count={selectedEventTypes.length} onClear={clearAll} />
        <div className="max-h-64 overflow-y-auto p-1">
          {hasResults ? (
            filteredEventTypes.map((eventType) => (
              <label key={eventType} className={ITEM_LABEL_CLASSES}>
                <Checkbox
                  checked={isSelected(selectedEventTypes, eventType)}
                  onCheckedChange={() => toggleEventType(eventType)}
                />
                <span className="text-sm">{eventType}</span>
              </label>
            ))
          ) : (
            <EmptyResults />
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}

export default WebhookEventTypeSelect
