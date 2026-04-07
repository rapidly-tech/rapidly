import { getQueryClient } from '@/utils/api/query'
import { api } from '@/utils/client'
import { operations, resolveResponse, schemas } from '@rapidly-tech/client'
import { useMutation, useQuery } from '@tanstack/react-query'
import { baseRetry } from './retry'

// Cache key constants keep invalidation logic DRY.
const DELIVERIES_LIST = ['webhookDeliveries', 'list'] as const
const ENDPOINTS_LIST = ['webhookEndpoints', 'list'] as const
const endpointById = (id: string) => ['webhookEndpoint', 'id', id] as const

// Helper to flush all webhook-related caches after a destructive change.
function invalidateWebhookCaches(endpointId: string) {
  const qc = getQueryClient()
  qc.invalidateQueries({ queryKey: [...ENDPOINTS_LIST] })
  qc.invalidateQueries({ queryKey: endpointById(endpointId) })
  qc.invalidateQueries({ queryKey: [...DELIVERIES_LIST] })
}

// ── Read hooks ──

export const useListWebhooksDeliveries = (
  parameters: NonNullable<
    operations['webhooks:list_webhook_deliveries']['parameters']['query']
  >,
) =>
  useQuery({
    queryKey: [...DELIVERIES_LIST, { parameters }],
    queryFn: () =>
      resolveResponse(
        api.GET('/api/webhooks/deliveries', {
          params: { query: parameters },
        }),
      ),
    retry: baseRetry,
  })

export const useListWebhooksEndpoints = (variables: {
  workspaceId: string
  limit: number
  page: number
}) =>
  useQuery({
    queryKey: [...ENDPOINTS_LIST, { ...variables }],
    queryFn: () =>
      resolveResponse(
        api.GET('/api/webhooks/endpoints', {
          params: {
            query: {
              workspace_id: variables.workspaceId,
              limit: variables.limit,
              page: variables.page,
            },
          },
        }),
      ),
    retry: baseRetry,
  })

export const useWebhookEndpoint = (id?: string) =>
  useQuery({
    queryKey: endpointById(id ?? ''),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/webhooks/endpoints/{id}', {
          params: { path: { id: id as string } },
        }),
      ),
    retry: baseRetry,
    enabled: Boolean(id),
  })

// ── Write hooks ──

export const useRedeliverWebhookEvent = () =>
  useMutation({
    mutationFn: ({ id }: { id: string }) =>
      api.POST('/api/webhooks/events/{id}/redeliver', {
        params: { path: { id } },
      }),
    onSuccess: (result) => {
      if (result.error) return
      getQueryClient().invalidateQueries({ queryKey: [...DELIVERIES_LIST] })
    },
  })

export const useCreateWebhookEndpoint = () =>
  useMutation({
    mutationFn: (body: schemas['WebhookEndpointCreate']) =>
      api.POST('/api/webhooks/endpoints', { body }),
    onSuccess: (result) => {
      if (result.error) return
      getQueryClient().invalidateQueries({ queryKey: [...ENDPOINTS_LIST] })
    },
  })

export const useEditWebhookEndpoint = () =>
  useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string
      body: schemas['WebhookEndpointUpdate']
    }) =>
      api.PATCH('/api/webhooks/endpoints/{id}', {
        params: { path: { id } },
        body,
      }),
    onSuccess: (result, { id }) => {
      if (result.error) return
      const qc = getQueryClient()
      qc.invalidateQueries({ queryKey: [...ENDPOINTS_LIST] })
      qc.invalidateQueries({ queryKey: endpointById(id) })
    },
  })

export const useResetSecretWebhookEndpoint = () =>
  useMutation({
    mutationFn: ({ id }: { id: string }) =>
      api.PATCH('/api/webhooks/endpoints/{id}/secret', {
        params: { path: { id } },
      }),
    onSuccess: (_result, { id }) => invalidateWebhookCaches(id),
  })

export const useDeleteWebhookEndpoint = () =>
  useMutation({
    mutationFn: ({ id }: { id: string }) =>
      api.DELETE('/api/webhooks/endpoints/{id}', {
        params: { path: { id } },
      }),
    onSuccess: (_result, { id }) => invalidateWebhookCaches(id),
  })
