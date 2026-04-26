import { Client, resolveResponse, schemas } from '@rapidly-tech/client'
import { notFound } from 'next/navigation'
import { cache } from 'react'

const _getWorkspaceBySlug = async (
  api: Client,
  slug: string,
): Promise<schemas['Workspace'] | undefined> => {
  const data = await resolveResponse(
    api.GET('/api/workspaces/', {
      params: {
        query: {
          slug,
        },
      },
      next: {
        tags: [`workspaces:${slug}`],
        revalidate: 600,
      },
    }),
  )
  return data.data[0]
}

// Tell React to memoize it for the duration of the request
export const getWorkspaceBySlug = cache(_getWorkspaceBySlug)

export const getWorkspaceBySlugOrNotFound = async (
  api: Client,
  slug: string,
): Promise<schemas['Workspace']> => {
  const workspace = await getWorkspaceBySlug(api, slug)
  if (!workspace) {
    notFound()
  }
  return workspace
}
