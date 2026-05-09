'use client'

import { workspacePageLink } from '@/utils/nav'
import { schemas } from '@rapidly-tech/client'
import {
  Tabs,
  TabsList,
  TabsTrigger,
} from '@rapidly-tech/ui/components/navigation/Tabs'
import Link from 'next/link'
import { useSelectedLayoutSegment } from 'next/navigation'
import { twMerge } from 'tailwind-merge'

interface WorkspaceStorefrontNavProps {
  className?: string
  workspace: schemas['Workspace']
}

export const StorefrontNav = ({
  workspace,
  className,
}: WorkspaceStorefrontNavProps) => {
  const routeSegment = useSelectedLayoutSegment()
  const currentTab = routeSegment ?? 'shares'

  return (
    <Tabs className="w-full md:w-fit" value={currentTab}>
      <TabsList
        className={twMerge(
          'hidden w-full flex-row overflow-x-auto bg-transparent ring-0 sm:flex dark:bg-transparent dark:ring-0',
          className,
        )}
      >
        <Link href={workspacePageLink(workspace)}>
          <TabsTrigger value="shares">Shares</TabsTrigger>
        </Link>
      </TabsList>
    </Tabs>
  )
}
