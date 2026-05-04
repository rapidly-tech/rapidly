import { useMetrics } from '@/hooks/api'
import { WorkspaceContext } from '@/providers/workspaceContext'
import { Icon } from '@iconify/react'
import { formatCurrency } from '@rapidly-tech/currency'
import { Card } from '@rapidly-tech/ui/components/layout/Card'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@rapidly-tech/ui/components/primitives/tooltip'
import { endOfMonth, format, startOfMonth, subMonths } from 'date-fns'
import { useContext } from 'react'
import { twMerge } from 'tailwind-merge'
import Spinner from '../Shared/Spinner'

interface FileShareRevenueWidgetProps {
  className?: string
}

const FileShareRevenueWidget = ({ className }: FileShareRevenueWidgetProps) => {
  const { workspace } = useContext(WorkspaceContext)

  const revenueMetrics = useMetrics({
    startDate: startOfMonth(subMonths(new Date(), 5)),
    endDate: endOfMonth(new Date()),
    workspace_id: workspace.id,
    interval: 'month',
    metrics: ['file_share_revenue'],
  })

  const maxRevenue =
    Math.max(
      0,
      ...(revenueMetrics.data?.periods.map(
        (period) => period.file_share_revenue ?? 0,
      ) ?? []),
    ) || 1 // Avoid division by zero when all values are 0

  return (
    <Card
      className={twMerge(
        'flex h-full w-full flex-col gap-y-8 bg-slate-50 p-6 dark:bg-slate-900',
        className,
      )}
    >
      <div className="flex flex-col gap-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg text-slate-500">Last 6 Months</h2>
        </div>

        <h3 className="text-4xl font-light">File Share Revenue</h3>
      </div>

      <div className="grid h-full grid-cols-3 gap-4 lg:grid-cols-6 lg:gap-6">
        {revenueMetrics.data?.periods.map((period, index, array) => {
          const currentPeriodValue = period.file_share_revenue ?? 0
          const previousPeriodValue = array[index - 1]?.file_share_revenue ?? 0

          const percentageChangeComparedToPreviousPeriod =
            previousPeriodValue === 0
              ? currentPeriodValue === 0
                ? 0
                : 100
              : ((currentPeriodValue - previousPeriodValue) /
                  Math.abs(previousPeriodValue)) *
                100

          const isTrendFlat = percentageChangeComparedToPreviousPeriod === 0
          const isTrendingUp = percentageChangeComparedToPreviousPeriod > 0

          return (
            <div
              key={period.timestamp}
              className="flex h-full flex-col gap-y-2"
            >
              <Tooltip>
                <TooltipTrigger className="relative h-full min-h-48 overflow-hidden rounded-2xl bg-[repeating-linear-gradient(-45deg,rgba(0,0,0,0.05),rgba(0,0,0,0.05)_2px,transparent_2px,transparent_8px)] dark:bg-[repeating-linear-gradient(45deg,rgba(255,255,255,0.03),rgba(255,255,255,0.03)_2px,transparent_2px,transparent_8px)]">
                  {revenueMetrics.isLoading ? (
                    <div className="flex h-full w-full items-center justify-center rounded-2xl bg-slate-200 dark:bg-slate-800">
                      <Spinner />
                    </div>
                  ) : (
                    <div
                      className={twMerge(
                        'absolute bottom-0 w-full rounded-2xl',
                        index === array.length - 1
                          ? 'bg-teal-300 dark:bg-teal-500'
                          : 'bg-slate-300 dark:bg-slate-700',
                      )}
                      style={{
                        height: `${((period.file_share_revenue ?? 0) / maxRevenue) * 100}%`,
                      }}
                    />
                  )}
                </TooltipTrigger>
                <TooltipContent>
                  <span>
                    {formatCurrency(
                      period.file_share_revenue ?? 0,
                      workspace.default_presentment_currency ?? 'usd',
                      0,
                    )}{' '}
                    in {format(period.timestamp, 'MMMM')}
                  </span>
                </TooltipContent>
              </Tooltip>
              <div className="flex flex-col text-left">
                <span className="text-sm lg:text-base">
                  {format(period.timestamp, 'MMMM')}
                </span>
                <div className="flex flex-row items-center justify-between gap-x-2">
                  <span className="text-sm text-slate-500">
                    {formatCurrency(
                      period.file_share_revenue ?? 0,
                      workspace.default_presentment_currency ?? 'usd',
                      0,
                    )}
                  </span>
                  {!isTrendFlat ? (
                    <Tooltip>
                      <TooltipTrigger
                        className={twMerge(
                          'flex flex-row items-center gap-x-1 rounded-xs p-0.5 text-xs',
                          isTrendingUp
                            ? 'bg-emerald-100 text-emerald-500 dark:bg-emerald-950'
                            : 'bg-red-100 text-red-500 dark:bg-red-950',
                        )}
                      >
                        {isTrendingUp ? (
                          <Icon
                            icon="solar:alt-arrow-up-linear"
                            className="text-[1em]"
                          />
                        ) : (
                          <Icon
                            icon="solar:alt-arrow-down-linear"
                            className="text-[1em]"
                          />
                        )}
                      </TooltipTrigger>
                      <TooltipContent>
                        <span className="text-xs">
                          {percentageChangeComparedToPreviousPeriod.toFixed(0) +
                            '%'}
                        </span>
                      </TooltipContent>
                    </Tooltip>
                  ) : null}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}

export default FileShareRevenueWidget
