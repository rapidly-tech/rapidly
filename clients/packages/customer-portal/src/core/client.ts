import { initApiClient, type Client } from '@rapidly-tech/client'
import {
  RapidlyCustomerPortalError,
  RateLimitError,
  UnauthorizedError,
} from './errors'

/** Configuration options for initializing a customer portal client. */
export interface PortalClientConfig {
  token: string
  workspaceId: string
  workspaceSlug?: string
  baseUrl?: string
  onUnauthorized?: () => void
}

/** Authenticated customer portal client with a typed request helper. */
export interface PortalClient {
  readonly config: PortalClientConfig
  readonly client: Client
  request: <T>(
    fn: (
      client: Client,
    ) => Promise<{ data?: T; error?: unknown; response: Response }>,
  ) => Promise<T>
}

/** Creates an authenticated customer portal client from the given configuration. */
export function createPortalClient(config: PortalClientConfig): PortalClient {
  const baseUrl = config.baseUrl || 'https://api.rapidly.tech'
  const client = initApiClient(baseUrl, config.token)

  const request = async <T>(
    fn: (
      client: Client,
    ) => Promise<{ data?: T; error?: unknown; response: Response }>,
  ): Promise<T> => {
    const { data, error, response } = await fn(client)

    if (response.status === 401) {
      config.onUnauthorized?.()
      throw new UnauthorizedError()
    }

    if (response.status === 429) {
      throw new RateLimitError()
    }

    if (error) {
      throw RapidlyCustomerPortalError.fromResponse(error, response)
    }

    if (!data) {
      throw new RapidlyCustomerPortalError({
        message: 'No data returned',
        code: 'no_data',
        status: response.status,
      })
    }

    return data
  }

  return {
    config,
    client,
    request,
  }
}
