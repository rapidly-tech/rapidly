import { api } from '@/utils/client'
import { operations, resolveResponse } from '@rapidly-tech/client'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { baseRetry } from './retry'

// ── List query ──

/** Fetches a list of file share sessions with optional polling. */
export const useFileShareSessions = (
  parameters?: NonNullable<
    operations['file-sharing:list_sessions']['parameters']['query']
  >,
  refetchInterval?: number | false,
) =>
  useQuery({
    queryKey: ['file_share_sessions', { ...(parameters || {}) }],
    queryFn: () =>
      resolveResponse(
        api.GET('/api/file-sharing/sessions', {
          params: {
            query: parameters || {},
          },
        }),
      ),
    retry: baseRetry,
    staleTime: 0,
    refetchOnMount: 'always',
    refetchInterval: refetchInterval ?? false,
    placeholderData: keepPreviousData,
  })

// ── Detail query ──

/** Fetches detailed information for a single file share session by ID. */
export const useFileShareSession = (sessionId: string) =>
  useQuery({
    queryKey: ['file_share_session', sessionId],
    queryFn: () =>
      resolveResponse(
        api.GET('/api/file-sharing/sessions/{session_id}', {
          params: {
            path: { session_id: sessionId },
          },
        }),
      ),
    retry: baseRetry,
    enabled: !!sessionId,
  })
