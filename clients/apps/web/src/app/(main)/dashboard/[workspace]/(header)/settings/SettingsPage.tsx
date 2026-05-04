'use client'

import { DashboardBody } from '@/components/Layout/DashboardLayout'
import { Section, SectionDescription } from '@/components/Settings/Section'
import WorkspaceDeleteSettings from '@/components/Settings/WorkspaceDeleteSettings'
import WorkspaceProfileSettings from '@/components/Settings/WorkspaceProfileSettings'
import { schemas } from '@rapidly-tech/client'

export default function ClientPage({
  workspace,
}: {
  workspace: schemas['Workspace']
}) {
  return (
    <DashboardBody
      title="Settings"
      wrapperClassName="max-w-(--breakpoint-sm)!"
      className="gap-y-8 pb-16 md:gap-y-12"
    >
      <div className="flex flex-col gap-y-12">
        <Section id="workspace">
          <SectionDescription title="Profile" />
          <WorkspaceProfileSettings workspace={workspace} />
        </Section>

        <Section id="danger">
          <SectionDescription
            title="Danger Zone"
            description="Irreversible actions for this workspace"
          />
          <WorkspaceDeleteSettings workspace={workspace} />
        </Section>
      </div>
    </DashboardBody>
  )
}
