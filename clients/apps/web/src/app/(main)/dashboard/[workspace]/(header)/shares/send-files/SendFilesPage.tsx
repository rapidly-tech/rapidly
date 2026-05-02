'use client'

import type { FileSharingFlowState } from '@/components/FileSharing'
import { FileSharingLandingPage } from '@/components/Landing/file-sharing/FileSharingLandingPage'
import { DashboardBody } from '@/components/Layout/DashboardLayout'
import { schemas } from '@rapidly-tech/client'
import { useCallback, useState } from 'react'

export default function SendFilesPage({
  workspace,
}: {
  workspace: schemas['Workspace']
}) {
  const [flowState, setFlowState] = useState<FileSharingFlowState>('initial')
  const [resetKey, setResetKey] = useState(0)

  const handleFlowStateChange = useCallback((state: FileSharingFlowState) => {
    setFlowState(state)
  }, [])

  const handleTitleClick = useCallback(() => {
    setResetKey((k) => k + 1)
    setFlowState('initial')
  }, [])

  return (
    <DashboardBody
      title={
        <button
          type="button"
          onClick={handleTitleClick}
          className="cursor-pointer"
        >
          <h4 className="rp-text-primary text-2xl font-medium whitespace-nowrap transition-opacity hover:opacity-70">
            Share Files
          </h4>
        </button>
      }
      className="flex-1"
      wrapperClassName={
        flowState === 'initial' ? 'overflow-x-clip' : undefined
      }
    >
      <FileSharingLandingPage
        key={resetKey}
        showPricing={true}
        workspaceId={workspace.id}
        onFlowStateChange={handleFlowStateChange}
        entranceAnimation={false}
      />
    </DashboardBody>
  )
}
