import createOpenAPIFetchClient, {
  type FetchResponse,
  type HeadersOptions,
  type ParseAsResponse,
} from 'openapi-fetch'
import type {
  ResponseObjectMap,
  SuccessResponse,
} from 'openapi-typescript-helpers'
import type { components, paths } from './v1'

/** Initializes an OpenAPI fetch client with optional bearer token authentication. */
export const initApiClient = (
  baseUrl: string,
  token?: string,
  headers?: HeadersOptions,
) =>
  createOpenAPIFetchClient<paths>({
    baseUrl,
    credentials: 'include',
    headers: {
      ...(headers ? headers : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })

/** Base error class for non-successful API responses. */
export class ApiResponseError extends Error {
  error: any
  response: Response

  constructor(error: any, response: Response) {
    super(error.message)
    this.name = 'ApiResponseError'
    this.error = error
    this.response = response
  }
}

/** Error thrown when the API returns a 401 Unauthorized response. */
export class AuthenticationError extends ApiResponseError {
  constructor(error: any, response: Response) {
    super(error, response)
    this.name = 'AuthenticationError'
  }
}

/** Error thrown when the API returns a 404 Not Found response. */
export class ResourceNotFoundError extends ApiResponseError {
  constructor(error: any, response: Response) {
    super(error, response)
    this.name = 'ResourceNotFoundError'
  }
}

/** Error thrown when the API returns a 429 Too Many Requests response. */
export class RateLimitError extends ApiResponseError {
  constructor(error: any, response: Response) {
    super(error, response)
    this.name = 'RateLimitError'
  }
}

/** Unwraps an API fetch response, throwing typed errors for failure status codes. */
export const resolveResponse = async <
  T extends Record<string | number, any>,
  Options,
  Media extends `${string}/${string}`,
>(
  p: Promise<FetchResponse<T, Options, Media>>,
  handlers?: {
    [status: number]: (response: Response) => never
  },
): Promise<
  ParseAsResponse<SuccessResponse<ResponseObjectMap<T>, Media>, Options>
> => {
  const { data, error, response } = await p
  if (handlers) {
    const handler = handlers[response.status]
    if (handler) {
      return handler(response)
    }
  }

  if (response.status === 429) {
    throw new RateLimitError({ message: 'Too Many Requests' }, response)
  }

  if (error) {
    if (response.status === 401) {
      throw new AuthenticationError(error, response)
    } else if (response.status === 404) {
      throw new ResourceNotFoundError(error, response)
    }

    throw new ApiResponseError(error, response)
  }

  if (!data) {
    throw new Error('No data returned')
  }
  return data
}

/** Type guard that checks whether an error detail is a validation error array. */
export const isValidationError = (
  detail: any,
): detail is {
  loc: (string | number)[]
  msg: string
  type: string
}[] => {
  return detail && Array.isArray(detail) && detail.length > 0 && detail[0].loc
}

export type { Middleware } from 'openapi-fetch'
export * as enums from './enums'
export type { components, operations, paths } from './v1'
/** Shorthand type alias for all API schema definitions. */
export type schemas = components['schemas']
/** Type alias for an initialized API client instance. */
export type Client = ReturnType<typeof initApiClient>
