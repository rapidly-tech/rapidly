// ── Imports ──

import { useMetrics } from '@/hooks/api'
import { WorkspaceContext } from '@/providers/workspaceContext'
import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@rapidly-tech/ui/components/primitives/tooltip'
import {
  addMonths,
  endOfMonth,
  isBefore,
  isSameDay,
  isThisMonth,
  startOfMonth,
  subMonths,
} from 'date-fns'
import { useCallback, useContext, useState } from 'react'
import { twMerge } from 'tailwind-merge'
import Spinner from '../Shared/Spinner'

// ── Constants ──

const weekDays = ['M', 'T', 'W', 'T', 'F', 'S', 'S']

// ── Types ──

interface FileShareActivityWidgetProps {
  className?: string
}

// ── Main Component ──

export const FileShareActivityWidget = ({
  className,
}: FileShareActivityWidgetProps) => {
  const [activeMonth, setActiveMonth] = useState(new Date())

  const { workspace } = useContext(WorkspaceContext)

  const startDate = startOfMonth(activeMonth)
  const endDate = endOfMonth(startDate)

  const shareMetrics = useMetrics({
    workspace_id: workspace.id,
    interval: 'day',
    startDate,
    endDate,
    metrics: ['file_share_sessions'],
  })

  // Calculate weekday index for first day (Monday = 0, Sunday = 6)
  const firstDayWeekday = (startDate.getDay() + 6) % 7
  const days = shareMetrics.data?.periods ?? []
  const leadingEmptyCells = Array(firstDayWeekday).fill(null)
  const totalCells = leadingEmptyCells.length + days.length
  const trailingEmptyCells = Array((7 - (totalCells % 7)) % 7).fill(null)
  const calendarDays = [...leadingEmptyCells, ...days, ...trailingEmptyCells]

  const monthName = startDate.toLocaleString('default', {
    month: 'long',
    year: 'numeric',
  })

  const totalShares = shareMetrics.data?.totals?.file_share_sessions ?? 0

  const isToday = useCallback((date: Date) => {
    return isSameDay(date, new Date())
  }, [])

  return (
    <div
      className={twMerge(
        'rp-text-primary flex w-full flex-col rounded-4xl bg-slate-50 p-2 dark:bg-slate-900',
        className,
      )}
    >
      <div className="flex items-center justify-between p-4">
        <h2 className="text-xl">{monthName}</h2>
        <div className="flex items-center gap-x-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setActiveMonth(subMonths(activeMonth, 1))}
          >
            <Icon icon="solar:arrow-left-linear" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            disabled={isThisMonth(activeMonth)}
            onClick={() => {
              const nextMonth = addMonths(activeMonth, 1)
              setActiveMonth(nextMonth)
            }}
          >
            <Icon icon="solar:arrow-right-linear" />
          </Button>
        </div>
      </div>

      <div className="flex items-center justify-between px-4 pb-4">
        <div className="flex items-baseline gap-x-2">
          <h3 className="text-5xl font-light">
            {totalShares.toLocaleString('en-US', {
              style: 'decimal',
              compactDisplay: 'short',
              notation: 'compact',
            })}
          </h3>
          <span className="text-lg">
            {totalShares === 1 ? 'Share' : 'Shares'}
          </span>
        </div>
      </div>
      <div className="flex min-h-[300px] flex-col gap-y-4 rounded-3xl bg-white px-2 py-4 dark:bg-slate-950">
        {shareMetrics.isLoading ? (
          <div className="flex h-full w-full items-center justify-center">
            <Spinner />
          </div>
        ) : (
          <>
            <div className="grid grid-cols-7 justify-items-center">
              {weekDays.map((day, index) => (
                <div
                  key={day + index}
                  className="text-sm text-slate-500 dark:text-slate-700"
                >
                  {day}
                </div>
              ))}
            </div>
            <div className="grid grid-cols-7 justify-items-center gap-y-2">
              {calendarDays.map((day, index) => {
                if (!day) {
                  return (
                    <div
                      key={`empty-${index}`}
                      className="relative flex h-8 w-8 items-center justify-center"
                    />
                  )
                }
                const shares = day.file_share_sessions ?? 0
                const isPreviousDay =
                  isBefore(day.timestamp, new Date()) && !isToday(day.timestamp)

                return (
                  <div key={day.timestamp}>
                    <Tooltip>
                      <TooltipTrigger
                        className={twMerge(
                          'relative flex h-8 w-8 items-center justify-center rounded-full text-sm',
                          shares > 0 &&
                            'bg-slate-300 text-slate-500 dark:bg-slate-800 dark:text-slate-500',
                          isToday(day.timestamp) &&
                            'bg-(--surface-bold) text-(--text-inverted)',
                          isPreviousDay && '',
                        )}
                      >
                        {shares > 0 ? (
                          <span>
                            {shares.toLocaleString('en-US', {
                              style: 'decimal',
                              compactDisplay: 'short',
                              notation: 'compact',
                            })}
                          </span>
                        ) : (
                          <div
                            className={twMerge(
                              'relative flex h-full w-full items-center justify-center overflow-hidden rounded-full border-2 text-sm text-slate-200 dark:text-slate-800',
                              isToday(day.timestamp)
                                ? 'border-(--surface-bold)'
                                : 'border-slate-200 dark:border-slate-800',
                            )}
                          >
                            {shares === 0 && isPreviousDay ? (
                              <span className="h-1 w-1 rounded-full bg-slate-200 dark:bg-slate-800" />
                            ) : isToday(day.timestamp) ? (
                              <span className="text-(--text-inverted)">
                                {shares.toLocaleString('en-US', {
                                  style: 'decimal',
                                  compactDisplay: 'short',
                                  notation: 'compact',
                                })}
                              </span>
                            ) : undefined}
                          </div>
                        )}
                      </TooltipTrigger>
                      <TooltipContent className="flex flex-col gap-1">
                        <span className="text-sm text-slate-500">
                          {new Date(day.timestamp).toLocaleString('default', {
                            day: 'numeric',
                            month: 'short',
                            year: 'numeric',
                          })}
                        </span>
                        <span>
                          {shares.toLocaleString('en-US', {
                            style: 'decimal',
                          })}{' '}
                          {shares === 1 ? 'share' : 'shares'}
                        </span>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                )
              })}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
