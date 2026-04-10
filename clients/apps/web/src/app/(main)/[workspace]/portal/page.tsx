import { getServerSideAPI } from '@/utils/client/serverside'
import { getWorkspaceOrNotFound } from '@/utils/customerPortal'
import { redirect } from 'next/navigation'

/** Customer portal entry point that redirects to the portal overview page. */
export default async function Page(props: {
  params: Promise<{ workspace: string }>
  searchParams: Promise<{ [key: string]: string }>
}) {
  const searchParams = await props.searchParams
  const params = await props.params
  const api = await getServerSideAPI()
  await getWorkspaceOrNotFound(api, params.workspace, searchParams)

  redirect(
    `/${params.workspace}/portal/overview?${new URLSearchParams(searchParams)}`,
  )
}
