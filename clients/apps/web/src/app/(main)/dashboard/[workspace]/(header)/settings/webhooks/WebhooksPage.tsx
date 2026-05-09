'use client'

import { DashboardBody } from '@/components/Layout/DashboardLayout'
import WebhookSettings from '@/components/Settings/Webhook/WebhookSettings'
import { schemas } from '@rapidly-tech/client'

export default function ClientPage({
  workspace,
}: {
  workspace: schemas['Workspace']
}) {
  return (
    <DashboardBody wrapperClassName="max-w-(--breakpoint-sm)!" title="Settings">
      <WebhookSettings workspace={workspace} />
    </DashboardBody>
  )
}
