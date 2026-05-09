import {
  INITIAL_RETRY_DELAY_MS,
  MAX_RETRY_DELAY_MS,
} from '@/utils/constants/timings'
import { Client, schemas } from '@rapidly-tech/client'
import * as Sentry from '@sentry/nextjs'
import { headers } from 'next/headers'
import { cache } from 'react'

const USER_HEADER = 'x-rapidly-user'
const WORKSPACES_ENDPOINT = '/api/workspaces/' as const
const MAX_WORKSPACES = 100
const CACHE_TTL = 600

interface ApiResult<T> {
  data?: T
  error?: unknown
}

async function retryWithBackoff<T>(
  fn: () => Promise<ApiResult<T>>,
  maxRetries = 3,
): Promise<ApiResult<T>> {
  let delay = INITIAL_RETRY_DELAY_MS
  let lastResult: ApiResult<T> | undefined

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      lastResult = await fn()
      if (!lastResult.error) return lastResult
    } catch (error) {
      lastResult = { error }
    }

    if (attempt < maxRetries) {
      await new Promise((resolve) => setTimeout(resolve, delay))
      delay = Math.min(delay * 2, MAX_RETRY_DELAY_MS)
    }
  }

  return lastResult!
}

const parseUserFromHeader = (
  headerValue: string | null,
): schemas['UserRead'] | undefined => {
  if (!headerValue) return undefined
  return JSON.parse(headerValue)
}

const _getAuthenticatedUser = async (): Promise<
  schemas['UserRead'] | undefined
> => {
  const userData = (await headers()).get(USER_HEADER)
  return parseUserFromHeader(userData)
}

export const getAuthenticatedUser = cache(_getAuthenticatedUser)

const buildRequestOptions = (
  userId: string,
  bypassCache: boolean,
): Record<string, unknown> => {
  const opts: Record<string, unknown> = {
    params: {
      query: {
        limit: MAX_WORKSPACES,
        sorting: ['name'],
      },
    },
  }

  if (bypassCache) {
    opts.cache = 'no-cache'
  } else {
    opts.next = {
      tags: [`users:${userId}:workspaces`],
      revalidate: CACHE_TTL,
    }
  }

  return opts
}

const reportFetchFailure = (
  user: schemas['UserRead'],
  error: unknown,
): void => {
  Sentry.captureException(
    new Error('Failed to fetch workspaces after retries'),
    {
      user: { id: user.id },
      extra: { originalError: error },
    },
  )
}

const _getWorkspaceMemberships = async (
  api: Client,
  bypassCache: boolean = false,
): Promise<schemas['Workspace'][]> => {
  const user = await getAuthenticatedUser()
  if (!user) return []

  const requestOptions = buildRequestOptions(user.id, bypassCache)

  const { data, error } = await retryWithBackoff(() =>
    api.GET(WORKSPACES_ENDPOINT, requestOptions),
  )

  if (error || !data) {
    reportFetchFailure(user, error)
    return []
  }

  return data.data
}

const _getWorkspaceMembershipsCached = (api: Client) =>
  _getWorkspaceMemberships(api, false)

export const getWorkspaceMemberships = (
  api: Client,
  bypassCache: boolean = false,
) => {
  if (bypassCache) {
    return _getWorkspaceMemberships(api, true)
  }
  return cache(_getWorkspaceMembershipsCached)(api)
}
