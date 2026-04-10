import revalidate from '@/app/actions'
import { getQueryClient } from '@/utils/api/query'
import { api } from '@/utils/client'
import { operations, resolveResponse, schemas } from '@rapidly-tech/client'
import { useMutation, useQuery } from '@tanstack/react-query'
import { baseRetry } from './retry'

// ── Cache key builders ──

const wsKey = (...parts: string[]) => ['workspaces', ...parts]
const memberKey = (id: string) => ['workspaceMembers', id]
const tokenKey = (wsId: string, extra?: Record<string, unknown>) => [
  'workspace_access_tokens',
  { workspace_id: wsId, ...(extra ?? {}) },
]

// ══════════════════════════════════════════════
//  Members
// ══════════════════════════════════════════════

export const useListWorkspaceMembers = (id: string) =>
  useQuery({
    queryKey: memberKey(id),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/workspaces/{id}/members', { params: { path: { id } } }),
      ),
    retry: baseRetry,
  })

export const useInviteWorkspaceMember = (id: string) =>
  useMutation({
    mutationFn: (email: string) =>
      api.POST('/api/workspaces/{id}/members/invite', {
        params: { path: { id } },
        body: { email },
      }),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: memberKey(id) })
    },
  })

export const useLeaveWorkspace = (id: string) =>
  useMutation({
    mutationFn: () =>
      api.DELETE('/api/workspaces/{id}/members/leave', {
        params: { path: { id } },
      }),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['workspaces'] })
    },
  })

export const useRemoveWorkspaceMember = (workspaceId: string) =>
  useMutation({
    mutationFn: (userId: string) =>
      api.DELETE('/api/workspaces/{id}/members/{user_id}', {
        params: { path: { id: workspaceId, user_id: userId } },
      }),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: memberKey(workspaceId) })
    },
  })

// ══════════════════════════════════════════════
//  Workspace CRUD
// ══════════════════════════════════════════════

export const useListWorkspaces = (
  params: operations['workspaces:list']['parameters']['query'],
  enabled: boolean = true,
) =>
  useQuery({
    queryKey: ['workspaces', params],
    queryFn: () =>
      resolveResponse(
        api.GET('/api/workspaces/', { params: { query: params } }),
      ),
    retry: baseRetry,
    enabled,
  })

export const useCreateWorkspace = () =>
  useMutation({
    mutationFn: (body: schemas['WorkspaceCreate']) =>
      api.POST('/api/workspaces/', { body }),
    onSuccess: async ({ data, error }) => {
      if (error || !data) return
      getQueryClient().invalidateQueries({ queryKey: wsKey(data.id) })
      await Promise.all([
        revalidate(`workspaces:${data.id}`),
        revalidate(`workspaces:${data.slug}`),
        revalidate(`storefront:${data.slug}`),
      ])
    },
  })

export const useUpdateWorkspace = () =>
  useMutation({
    mutationFn: (variables: {
      id: string
      body: schemas['WorkspaceUpdate']
      userId?: string
    }) =>
      api.PATCH('/api/workspaces/{id}', {
        params: { path: { id: variables.id } },
        body: variables.body,
      }),
    onSuccess: async ({ data, error }, variables) => {
      if (error || !data) return

      getQueryClient().invalidateQueries({ queryKey: wsKey(data.id) })
      await revalidate(`workspaces:${data.id}`)
      await revalidate(`workspaces:${data.slug}`)

      if (variables.userId) {
        await revalidate(`users:${variables.userId}:workspaces`, { expire: 0 })
      }
    },
  })

export const useWorkspaceAccount = (id?: string) =>
  useQuery({
    queryKey: ['workspaces', 'account', id],
    queryFn: () =>
      resolveResponse(
        api.GET('/api/workspaces/{id}/account', {
          params: { path: { id: id ?? '' } },
        }),
      ),
    retry: baseRetry,
    enabled: Boolean(id),
  })

// ══════════════════════════════════════════════
//  Access tokens
// ══════════════════════════════════════════════

export const useWorkspaceAccessTokens = (
  workspace_id: string,
  params?: Omit<
    NonNullable<
      operations['workspace_access_tokens:list']['parameters']['query']
    >,
    'workspace_id'
  >,
) =>
  useQuery({
    queryKey: tokenKey(workspace_id, params as Record<string, unknown>),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/workspace-access-tokens/', {
          params: { query: { workspace_id, ...(params ?? {}) } },
        }),
      ),
    retry: baseRetry,
  })

export const useCreateWorkspaceAccessToken = (workspace_id: string) =>
  useMutation({
    mutationFn: (
      body: Omit<schemas['WorkspaceAccessTokenCreate'], 'workspace_id'>,
    ) =>
      api.POST('/api/workspace-access-tokens/', {
        body: { ...body, workspace_id },
      }),
    onSuccess: ({ error }) => {
      if (error) return
      getQueryClient().invalidateQueries({
        queryKey: tokenKey(workspace_id),
      })
    },
  })

export const useUpdateWorkspaceAccessToken = (id: string) =>
  useMutation({
    mutationFn: (body: schemas['WorkspaceAccessTokenUpdate']) =>
      api.PATCH('/api/workspace-access-tokens/{id}', {
        params: { path: { id } },
        body,
      }),
    onSuccess: ({ data, error }) => {
      if (error || !data) return
      getQueryClient().invalidateQueries({
        queryKey: tokenKey(data.workspace_id),
      })
    },
  })

export const useDeleteWorkspaceAccessToken = () =>
  useMutation({
    mutationFn: (token: schemas['WorkspaceAccessToken']) =>
      api.DELETE('/api/workspace-access-tokens/{id}', {
        params: { path: { id: token.id } },
      }),
    onSuccess: ({ error }, token) => {
      if (error) return
      getQueryClient().invalidateQueries({
        queryKey: tokenKey(token.workspace_id),
      })
    },
  })

// ══════════════════════════════════════════════
//  Payment & review status
// ══════════════════════════════════════════════

export const useWorkspacePaymentStatus = (
  id: string,
  enabled: boolean = true,
  accountVerificationOnly: boolean = false,
) =>
  useQuery({
    queryKey: ['workspaces', 'payment-status', id, accountVerificationOnly],
    queryFn: () =>
      resolveResponse(
        api.GET('/api/workspaces/{id}/payment-status', {
          params: {
            path: { id },
            query: accountVerificationOnly
              ? { account_verification_only: true }
              : {},
          },
        }),
      ),
    retry: baseRetry,
    enabled: enabled && Boolean(id),
  })

export const useDeleteWorkspace = () =>
  useMutation({
    mutationFn: ({ id }: { id: string }) =>
      api.DELETE('/api/workspaces/{id}', {
        params: { path: { id } },
      }),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['workspaces'] })
    },
  })
