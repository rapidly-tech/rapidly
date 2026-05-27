/**
 * Hooks for the Agents chamber surface.
 *
 * Hand-typed against the backend's response shapes for now —
 * the auto-generated `@rapidly-tech/client` doesn't yet carry
 * the agents routes (it's regenerated against a running
 * backend's openapi.json). A follow-up PR will switch this
 * file to the typed client once `pnpm generate` lands the
 * agents endpoints. Until then this is the single source of
 * type truth for the frontend; if a field name changes on
 * the backend, update both.
 *
 * Why hand-typed: shipping the UI before the client regen
 * unblocks operators using the chamber today. The type shapes
 * here mirror the Pydantic schemas in
 * `server/rapidly/agents/<module>/types.py`.
 */

import { useQuery } from '@tanstack/react-query'

import { baseRetry } from './retry'

// ── Cache key builder ─────────────────────────────────────────

const workflowKey = (...parts: (string | object)[]) => [
  'agents-workflows',
  ...parts,
]

// ── Types (mirror the backend Pydantic schemas) ──────────────

export interface Workflow {
  id: string
  workspace_id: string
  project_id: string | null
  name: string
  description: string | null
  current_version_id: string | null
  created_at: string
  updated_at: string
}

export interface PaginatedWorkflows {
  data: Workflow[]
  meta: {
    total: number
    page: number
    per_page: number
    pages: number
  }
}

// ── Fetcher ───────────────────────────────────────────────────

async function fetchWorkflows(
  params: { project_id?: string; page?: number; limit?: number } = {},
): Promise<PaginatedWorkflows> {
  const url = new URL(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/workflows/`)
  if (params.project_id) url.searchParams.set('project_id', params.project_id)
  if (params.page) url.searchParams.set('page', String(params.page))
  if (params.limit) url.searchParams.set('limit', String(params.limit))

  const res = await fetch(url.toString(), {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    // Surface the status code so the query layer can decide
    // whether to retry; the message body shape isn't stable
    // enough to expose verbatim.
    throw new Error(`workflows list failed: ${res.status}`)
  }
  return (await res.json()) as PaginatedWorkflows
}

// ── Hooks ─────────────────────────────────────────────────────

export const useWorkflows = (
  params: { project_id?: string; page?: number; limit?: number } = {},
  enabled: boolean = true,
) =>
  useQuery({
    queryKey: workflowKey('list', params),
    queryFn: () => fetchWorkflows(params),
    retry: baseRetry,
    enabled,
  })
