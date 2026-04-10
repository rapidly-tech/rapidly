import { getServerSideAPI } from '@/utils/client/serverside'
import { getWorkspaceBySlugOrNotFound } from '@/utils/workspace'
import { Metadata } from 'next'
import SettingsPage from './SettingsPage'

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'Settings',
  }
}

/** Workspace settings page for managing general configuration. */
export default async function Page(props: {
  params: Promise<{ workspace: string }>
}) {
  const params = await props.params
  const api = await getServerSideAPI()
  const workspace = await getWorkspaceBySlugOrNotFound(api, params.workspace)

  return <SettingsPage workspace={workspace} />
}
