import { useFileShareSessions } from '@/hooks/api/fileShareSessions'
import { WorkspaceContext } from '@/providers/workspaceContext'
import { Icon } from '@iconify/react'
import { Status } from '@rapidly-tech/ui/components/feedback/Status'
import Button from '@rapidly-tech/ui/components/forms/Button'
import {
  Card,
  CardContent,
  CardHeader,
} from '@rapidly-tech/ui/components/layout/Card'
import Link from 'next/link'
import { useContext } from 'react'
import { twMerge } from 'tailwind-merge'

interface RecentFilesWidgetProps {
  className?: string
}

export const RecentFilesWidget = ({ className }: RecentFilesWidgetProps) => {
  const { workspace } = useContext(WorkspaceContext)

  const sessions = useFileShareSessions({
    workspace_id: workspace.id,
    limit: 10,
    sorting: ['-created_at'],
  })

  const items = sessions.data?.data ?? []

  return (
    <div
      className={twMerge(
        'relative h-full min-h-80 rounded-4xl bg-slate-50 md:min-h-fit dark:bg-slate-900',
        className,
      )}
    >
      {items.length > 0 ? (
        <div className="absolute inset-2 flex flex-col">
          <div className="flex items-center justify-between p-4">
            <h3 className="text-lg">Recent Files</h3>
            <Link href={`/dashboard/${workspace.slug}/files`}>
              <Button
                variant="secondary"
                size="sm"
                className="rounded-full border-none"
              >
                View All
              </Button>
            </Link>
          </div>
          <div className="flex h-full flex-col gap-y-2 overflow-y-auto rounded-t-2xl rounded-b-4xl pb-4">
            {items.map((session) => {
              const createdAt = new Date(session.created_at)
              const displayDate = createdAt.toLocaleDateString('en-US', {
                month: 'long',
                day: 'numeric',
                hour12: false,
                hour: 'numeric',
                minute: 'numeric',
              })

              return (
                <Link
                  key={session.id}
                  href={`/dashboard/${workspace.slug}/files/${session.id}`}
                >
                  <Card className="flex flex-col gap-y-1 rounded-2xl border-none bg-white transition-opacity hover:opacity-60 dark:bg-slate-800">
                    <CardHeader className="flex flex-row items-baseline justify-between bg-transparent p-4 pt-2 pb-0 text-sm text-slate-400 dark:text-slate-500">
                      <span>{displayDate}</span>
                      <Status
                        className={twMerge(
                          'px-1.5 py-0.5 text-xs capitalize',
                          session.status === 'active'
                            ? 'bg-emerald-50 text-emerald-500 dark:bg-emerald-950'
                            : session.status === 'expired'
                              ? 'bg-amber-50 text-amber-500 dark:bg-amber-950'
                              : 'bg-slate-50 text-slate-500 dark:bg-slate-950',
                        )}
                        status={session.status ?? 'active'}
                      />
                    </CardHeader>
                    <CardContent className="flex flex-row justify-between gap-x-4 p-4 pt-0 pb-3">
                      <h3 className="min-w-0 truncate">
                        {session.title || session.short_slug || 'Untitled File'}
                      </h3>
                      <span className="text-sm text-slate-500">
                        {session.download_count ?? 0} downloads
                      </span>
                    </CardContent>
                  </Card>
                </Link>
              )
            })}
          </div>
        </div>
      ) : (
        <Card className="flex h-full flex-col items-center justify-center gap-y-6 bg-slate-50 p-6 text-slate-400 dark:text-slate-500">
          <Icon
            icon="solar:share-linear"
            className="h-6 w-6 text-slate-300 dark:text-slate-700"
          />
          <h3>No files yet</h3>
        </Card>
      )}
    </div>
  )
}
