import { getServerSideAPI } from '@/utils/client/serverside'
import { DataTableSearchParams, parseSearchParams } from '@/utils/datatable'
import { getWorkspaceBySlugOrNotFound } from '@/utils/workspace'
import EndpointsPage from './EndpointsPage'

/** Webhook endpoint detail page showing delivery history for a specific endpoint. */
export default async function Page(props: {
  params: Promise<{ workspace: string; id: string }>
  searchParams: Promise<DataTableSearchParams>
}) {
  const searchParams = await props.searchParams
  const params = await props.params
  const api = await getServerSideAPI()
  const workspace = await getWorkspaceBySlugOrNotFound(api, params.workspace)

  const { pagination, sorting } = parseSearchParams(searchParams, [
    { id: 'created_at', desc: true },
  ])

  return (
    <EndpointsPage
      workspace={workspace}
      pagination={pagination}
      sorting={sorting}
    />
  )
}
