import { useMetrics } from '@/hooks/api'
import { WorkspaceContext } from '@/providers/workspaceContext'
import {
  Card,
  CardFooter,
  CardHeader,
} from '@rapidly-tech/ui/components/layout/Card'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@rapidly-tech/ui/components/primitives/tooltip'
import Link from 'next/link'
import { useContext, useMemo } from 'react'
import { twMerge } from 'tailwind-merge'

export interface FilesWidgetProps {
  className?: string
}

export const FilesWidget = ({ className }: FilesWidgetProps) => {
  const { workspace } = useContext(WorkspaceContext)

  const [startDate, endDate] = useMemo(() => {
    const end = new Date()
    const start = new Date()
    start.setFullYear(start.getFullYear() - 1)
    return [start, end] as const
  }, [])

  const shareMetrics = useMetrics({
    workspace_id: workspace.id,
    interval: 'month',
    startDate,
    endDate,
    metrics: ['file_share_sessions', 'file_share_downloads'],
  })

  const latestPeriod =
    shareMetrics.data?.periods[shareMetrics.data.periods.length - 1]
  const totalSessions = latestPeriod?.file_share_sessions ?? 0
  const totalDownloads =
    shareMetrics.data?.periods.reduce(
      (acc, curr) => acc + (curr.file_share_downloads ?? 0),
      0,
    ) ?? 0

  const maxPeriod =
    shareMetrics.data?.periods.reduce(
      (acc, curr) =>
        (curr.file_share_sessions ?? 0) > acc
          ? (curr.file_share_sessions ?? 0)
          : acc,
      0,
    ) ?? 0

  return (
    <Card
      className={twMerge(
        'flex h-80 flex-col justify-between bg-slate-50',
        className,
      )}
    >
      <CardHeader className="flex flex-col gap-y-2 pb-2">
        <div className="flex flex-row items-center justify-between">
          <span className="text-lg">Files Shared</span>
          <Link
            href={`/dashboard/${workspace.slug}/files`}
            className="text-sm text-slate-500 hover:underline dark:text-slate-400"
          >
            View All
          </Link>
        </div>
        <div className="flex flex-row items-baseline gap-x-6">
          <div>
            <h2 className="text-5xl font-light">{totalSessions}</h2>
            <span className="text-sm text-slate-400 dark:text-slate-500">
              this month
            </span>
          </div>
          <div>
            <h3 className="text-2xl font-light">{totalDownloads}</h3>
            <span className="text-sm text-slate-400 dark:text-slate-500">
              downloads (year)
            </span>
          </div>
        </div>
      </CardHeader>
      <TooltipProvider>
        <CardFooter className="m-2 flex h-full flex-row items-end justify-between gap-x-1 rounded-3xl bg-white p-4 dark:bg-slate-950">
          {shareMetrics.data?.periods.map((period, i) => {
            const sessions = period.file_share_sessions ?? 0
            const activeClass =
              i === (shareMetrics.data?.periods.length ?? 0) - 1
                ? 'bg-(--surface-bold)'
                : 'hover:bg-slate-200 dark:hover:bg-slate-800'

            const tooltipContent = `${sessions} files in ${period.timestamp.toLocaleDateString(
              'en-US',
              {
                month: 'long',
                year: 'numeric',
              },
            )}`

            return (
              <Tooltip key={i} delayDuration={0}>
                <TooltipTrigger
                  style={{
                    height: `${Math.max(
                      maxPeriod > 0 ? (sessions / maxPeriod) * 100 : 0,
                      8,
                    )}%`,
                  }}
                  className={twMerge(
                    'w-3 shrink rounded-full bg-slate-300 dark:bg-slate-800',
                    activeClass,
                  )}
                />
                <TooltipContent className="text-sm">
                  {tooltipContent}
                </TooltipContent>
              </Tooltip>
            )
          })}
        </CardFooter>
      </TooltipProvider>
    </Card>
  )
}
