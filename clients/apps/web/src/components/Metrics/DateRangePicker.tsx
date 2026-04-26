'use client'

/**
 * DateRangePicker - calendar + preset interval selector for the
 * Rapidly analytics dashboard. Shows a popover calendar for custom
 * ranges and a list of quick-pick presets (Today, This Month, etc.).
 */

import {
  endOfDay,
  endOfMonth,
  endOfToday,
  endOfWeek,
  endOfYear,
  endOfYesterday,
  format,
  startOfDay,
  startOfMonth,
  startOfToday,
  startOfWeek,
  startOfYear,
  startOfYesterday,
  subMonths,
  subYears,
} from 'date-fns'
import * as React from 'react'
import { useContext } from 'react'

import { WorkspaceContext } from '@/providers/workspaceContext'
import { Icon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import FormattedInterval from '@rapidly-tech/ui/components/data/FormattedInterval'
import { Calendar } from '@rapidly-tech/ui/components/primitives/calendar'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@rapidly-tech/ui/components/primitives/popover'
import { twMerge } from 'tailwind-merge'

// ── Types ──

export type DateRange = {
  from: Date
  to: Date
}

type PresetSlug =
  | 'today'
  | 'yesterday'
  | 'thisWeek'
  | 'lastWeek'
  | 'thisMonth'
  | 'lastMonth'
  | 'last3Months'
  | 'thisYear'
  | 'lastYear'
  | 'allTime'

interface QuickRange {
  slug: PresetSlug
  label: string
  value: [Date, Date]
}

// ── Preset Definitions ──

/** Build workspace-aware preset ranges (the "All Time" preset needs the workspace creation date). */
function buildPresets(ws: schemas['Workspace']): QuickRange[] {
  const now = new Date()
  return [
    { slug: 'today', label: 'Today', value: [startOfToday(), endOfToday()] },
    {
      slug: 'yesterday',
      label: 'Yesterday',
      value: [startOfYesterday(), endOfYesterday()],
    },
    {
      slug: 'thisWeek',
      label: 'This Week',
      value: [startOfWeek(now), endOfWeek(now)],
    },
    {
      slug: 'thisMonth',
      label: 'This Month',
      value: [startOfMonth(now), endOfMonth(now)],
    },
    {
      slug: 'lastMonth',
      label: 'Last Month',
      value: [startOfMonth(subMonths(now, 1)), endOfMonth(subMonths(now, 1))],
    },
    {
      slug: 'last3Months',
      label: 'Last 3 Months',
      value: [subMonths(startOfToday(), 3), endOfToday()],
    },
    {
      slug: 'thisYear',
      label: 'This Year',
      value: [startOfYear(now), endOfYear(now)],
    },
    {
      slug: 'lastYear',
      label: 'Last Year',
      value: [startOfYear(subYears(now, 1)), endOfYear(subYears(now, 1))],
    },
    {
      slug: 'allTime',
      label: 'All Time',
      value: [startOfDay(new Date(ws.created_at)), endOfToday()],
    },
  ]
}

/** Match a date range to a preset by comparing date-only strings. */
function matchPreset(
  range: DateRange,
  ws: schemas['Workspace'],
): QuickRange | undefined {
  const fromStr = format(range.from, 'yyyy-MM-dd')
  const toStr = format(range.to, 'yyyy-MM-dd')

  return buildPresets(ws).find((preset) => {
    const presetFrom = format(preset.value[0], 'yyyy-MM-dd')
    const presetTo = format(preset.value[1], 'yyyy-MM-dd')
    return fromStr === presetFrom && toStr === presetTo
  })
}

// ── Props ──

interface DateRangePickerProps extends React.HTMLAttributes<HTMLDivElement> {
  date: DateRange | undefined
  onDateChange: (v: DateRange) => void
  minDate?: Date
}

// ── Preset List Sub-Component ──

interface PresetListProps {
  activeSlug: PresetSlug | undefined
  onSelect: (preset: QuickRange) => void
}

const PresetList = ({ activeSlug, onSelect }: PresetListProps) => {
  const { workspace } = useContext(WorkspaceContext)

  return (
    <div className="flex w-full flex-col gap-1">
      {buildPresets(workspace).map((preset) => {
        const selected = activeSlug === preset.slug
        return (
          <div
            key={preset.slug}
            role="button"
            onClick={() => onSelect(preset)}
            className={twMerge(
              'flex w-full items-center justify-between rounded-sm border border-transparent px-3 py-2 text-sm text-slate-500 select-none hover:bg-slate-100 dark:text-slate-500 dark:hover:bg-slate-900',
              selected &&
                'rp-text-primary bg-slate-100 dark:border-slate-800 dark:bg-slate-900',
            )}
          >
            {preset.label}
          </div>
        )
      })}
    </div>
  )
}

// ── Main Component ──

const DateRangePicker: React.FC<DateRangePickerProps> = ({
  className,
  date,
  onDateChange,
  minDate,
}) => {
  const { workspace } = useContext(WorkspaceContext)
  const matchedPreset = date ? matchPreset(date, workspace) : undefined

  // Determine what label to show in the trigger
  const triggerLabel = (() => {
    if (matchedPreset) return matchedPreset.label
    if (!date?.from) return <span>Pick a date</span>
    if (!date.to) return format(date.from, 'LLL dd, yy')
    return <FormattedInterval startDatetime={date.from} endDatetime={date.to} />
  })()

  return (
    <div
      className={twMerge(
        'flex h-10 w-52 flex-row divide-x divide-slate-200 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xs dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900',
        className,
      )}
    >
      {/* Calendar popover */}
      <Popover>
        <PopoverTrigger className="flex cursor-pointer items-center justify-center px-4 py-3 duration-150 hover:bg-slate-100 dark:hover:bg-slate-800">
          <Icon icon="solar:calendar-linear" className="text-[1em]" />
        </PopoverTrigger>
        <PopoverContent>
          <Calendar
            autoFocus
            mode="range"
            defaultMonth={date?.to}
            selected={date}
            disabled={minDate ? { before: minDate } : undefined}
            onSelect={(selection) => {
              onDateChange({
                from: startOfDay(selection?.from ?? new Date()),
                to: endOfDay(selection?.to ?? new Date()),
              })
            }}
          />
        </PopoverContent>
      </Popover>

      {/* Preset selector popover */}
      <Popover>
        <PopoverTrigger className="flex-1 cursor-pointer truncate px-4 text-sm duration-150 hover:bg-slate-100 dark:hover:bg-slate-800">
          {triggerLabel}
        </PopoverTrigger>
        <PopoverContent className="p-2">
          <PresetList
            activeSlug={matchedPreset?.slug}
            onSelect={(preset) => {
              onDateChange({ from: preset.value[0], to: preset.value[1] })
            }}
          />
        </PopoverContent>
      </Popover>
    </div>
  )
}

export default DateRangePicker
