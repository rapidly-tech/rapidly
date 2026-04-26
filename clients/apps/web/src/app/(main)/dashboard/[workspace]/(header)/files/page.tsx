import { getServerSideAPI } from '@/utils/client/serverside'
import { DataTableSearchParams, parseSearchParams } from '@/utils/datatable'
import { getWorkspaceBySlugOrNotFound } from '@/utils/workspace'
import { Metadata } from 'next'
import FileShareInsightsPage from '../customers/FileShareInsightsPage'

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'My Files',
  }
}

/** Files listing page showing file share insights with pagination and search. */
export default async function Page(props: {
  params: Promise<{ workspace: string }>
  searchParams: Promise<DataTableSearchParams & { query?: string }>
}) {
  const searchParams = await props.searchParams
  const params = await props.params
  const api = await getServerSideAPI()
  const workspace = await getWorkspaceBySlugOrNotFound(api, params.workspace)
  const { pagination, sorting } = parseSearchParams(
    searchParams,
    [{ id: 'created_at', desc: true }],
    20,
  )

  return (
    <FileShareInsightsPage
      workspace={workspace}
      pagination={pagination}
      sorting={sorting}
      query={searchParams.query}
    />
  )
}
