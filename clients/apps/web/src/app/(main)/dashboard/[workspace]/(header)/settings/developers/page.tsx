import { DashboardBody } from '@/components/Layout/DashboardLayout'
import OAuthSettings from '@/components/Settings/OAuth/OAuthSettings'
import { Section, SectionDescription } from '@/components/Settings/Section'
import WorkspaceAccessTokensSettings from '@/components/Settings/WorkspaceAccessTokensSettings'
import { getServerSideAPI } from '@/utils/client/serverside'
import { getWorkspaceBySlugOrNotFound } from '@/utils/workspace'
import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Developer Settings',
}

export default async function Page(props: {
  params: Promise<{ workspace: string }>
}) {
  const params = await props.params
  const api = await getServerSideAPI()
  const workspace = await getWorkspaceBySlugOrNotFound(api, params.workspace)

  return (
    <DashboardBody
      title="Settings"
      wrapperClassName="max-w-(--breakpoint-sm)!"
      className="gap-y-8 pb-16 md:gap-y-12"
    >
      <div className="flex flex-col gap-y-12">
        <Section id="workspace-tokens">
          <SectionDescription
            title="Workspace Access Tokens"
            description="Manage access tokens to authenticate with the Rapidly API"
          />
          <WorkspaceAccessTokensSettings workspace={workspace} />
        </Section>

        <Section id="oauth">
          <SectionDescription
            title="OAuth Applications"
            description="Your configured OAuth Applications"
          />
          <OAuthSettings />
        </Section>
      </div>
    </DashboardBody>
  )
}
