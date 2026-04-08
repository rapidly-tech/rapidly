import { Client, resolveResponse } from '@rapidly-tech/client'
import { useMutation, useQuery } from '@tanstack/react-query'
import { baseRetry } from './retry'

// ── Session authentication ──

/** Requests a login code for customer portal session authentication. */
export const useCustomerPortalSessionRequest = (
  api: Client,
  workspaceId: string,
) =>
  useMutation({
    mutationFn: async ({
      email,
      customer_id,
    }: {
      email: string
      customer_id?: string
    }) =>
      api.POST('/api/customer-portal/customer-session/request', {
        body: {
          email,
          workspace_id: workspaceId,
          ...(customer_id && { customer_id }),
        },
      }),
  })

/** Authenticates a customer portal session using a verification code. */
export const useCustomerPortalSessionAuthenticate = (api: Client) =>
  useMutation({
    mutationFn: ({ code }: { code: string }) =>
      api
        .POST('/api/customer-portal/customer-session/authenticate', {
          body: { code },
        })
        .then((res) => {
          if (res.response.status === 429) {
            return {
              data: undefined,
              error: {
                detail: 'Too many attempts. Please try again in 15 minutes.',
              },
              response: res.response,
            }
          }

          return res
        }),
  })

/** Introspects the current customer portal session. */
export const useCustomerPortalSession = (api: Client) =>
  useQuery({
    queryKey: ['customer_portal_session'],
    queryFn: () =>
      resolveResponse(
        api.GET('/api/customer-portal/customer-session/introspect'),
      ),
    retry: baseRetry,
  })

/** Fetches the currently authenticated customer's profile. */
export const useAuthenticatedCustomer = (api: Client) =>
  useQuery({
    queryKey: ['customer'],
    queryFn: () =>
      resolveResponse(api.GET('/api/customer-portal/customers/me')),
    retry: baseRetry,
  })

/** Fetches the user record linked to the current customer portal session. */
export const usePortalAuthenticatedUser = (api: Client) =>
  useQuery({
    queryKey: ['portal_authenticated_user'],
    queryFn: () =>
      resolveResponse(api.GET('/api/customer-portal/customer-session/user')),
    retry: baseRetry,
  })
