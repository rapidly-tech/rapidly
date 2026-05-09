import { FILE_SHARING_API } from '@/utils/file-sharing/constants'
import { useMutation } from '@tanstack/react-query'

export interface CreateSecretRequest {
  message: string
  expiration: number
  workspace_id?: string
  price_cents?: number
  currency?: string
  title?: string
}

interface CreateSecretResponse {
  message: string // UUID
}

export interface FetchSecretResponse {
  message: string // Encrypted content (empty string if payment_required)
  payment_required?: boolean
  price_cents?: number | null
  currency?: string | null
  title?: string | null
}

interface SecretCheckoutResponse {
  checkout_url: string
  session_id: string
}

/**
 * Safely parse a response as JSON, falling back to a message object
 * if the response body is not valid JSON (e.g. HTML error pages).
 * Maps FastAPI's `detail` field to `message` for error responses.
 */
async function safeJson<T extends { message: string }>(
  response: Response,
): Promise<T> {
  try {
    const json = await response.json()
    if (!response.ok && typeof json.detail === 'string' && !json.message) {
      json.message = json.detail
    }
    return json as T
  } catch {
    return { message: `Request failed (${response.status})` } as T
  }
}

async function postResource<T extends { message: string }>(
  path: string,
  request: CreateSecretRequest,
): Promise<{ data: T; status: number }> {
  try {
    const response = await fetch(`${FILE_SHARING_API}/${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      credentials: 'include',
    })
    return { data: await safeJson<T>(response), status: response.status }
  } catch (error) {
    return { data: { message: String(error) } as T, status: 500 }
  }
}

async function fetchResource<T extends { message: string }>(
  path: string,
  id: string,
): Promise<{ data: T; status: number }> {
  try {
    const response = await fetch(`${FILE_SHARING_API}/${path}/${id}`, {
      credentials: 'include',
    })
    return { data: await safeJson<T>(response), status: response.status }
  } catch (error) {
    return { data: { message: String(error) } as T, status: 500 }
  }
}

// Bare functions kept for imperative crypto flows (encrypt → post → navigate)
// where TanStack Query's declarative pattern does not fit.

export function postSecret(request: CreateSecretRequest) {
  return postResource<CreateSecretResponse>('secret', request)
}

export function fetchSecret(secretId: string) {
  return fetchResource<FetchSecretResponse>('secret', secretId)
}

export interface SecretMetadataResponse {
  title: string | null
  payment_required: boolean
  price_cents: number | null
  currency: string | null
}

export async function fetchSecretMetadata(
  secretId: string,
): Promise<{ data: SecretMetadataResponse | null; status: number }> {
  try {
    const response = await fetch(
      `${FILE_SHARING_API}/secret/${secretId}/metadata`,
      { credentials: 'include' },
    )
    if (!response.ok) {
      return { data: null, status: response.status }
    }
    const data = await response.json()
    return { data, status: response.status }
  } catch {
    return { data: null, status: 500 }
  }
}

export function fetchFile(fileId: string) {
  return fetchResource<FetchSecretResponse>('file', fileId)
}

export async function createSecretCheckout(
  secretId: string,
): Promise<{ data: SecretCheckoutResponse; status: number }> {
  try {
    const response = await fetch(
      `${FILE_SHARING_API}/secrets/${secretId}/checkout`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
      },
    )
    const data = await response.json()
    return { data, status: response.status }
  } catch {
    return {
      data: { checkout_url: '', session_id: '' },
      status: 500,
    }
  }
}

export async function claimSecretPaymentToken(
  secretId: string,
  checkoutSessionId: string,
): Promise<{ data: { success: boolean }; status: number }> {
  try {
    const response = await fetch(
      `${FILE_SHARING_API}/secrets/${secretId}/claim-payment-token`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ checkout_session_id: checkoutSessionId }),
        credentials: 'include',
      },
    )
    const data = await response.json()
    return { data, status: response.status }
  } catch {
    return {
      data: { success: false },
      status: 500,
    }
  }
}

// TanStack Query mutation wrapper for use in simpler components.

export function useReportViolation() {
  return useMutation({
    mutationFn: async ({
      slug,
      readerToken,
    }: {
      slug: string
      readerToken?: string
    }) => {
      const response = await fetch(
        `${FILE_SHARING_API}/channels/${slug}/report`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token: readerToken ?? '' }),
        },
      )
      if (!response.ok) {
        throw new Error(
          'Unable to submit report. The share link may have expired.',
        )
      }
    },
  })
}
