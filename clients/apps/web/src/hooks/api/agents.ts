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

// ══════════════════════════════════════════════
//  Workflow detail (single)
// ══════════════════════════════════════════════

async function fetchWorkflow(id: string): Promise<Workflow> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/workflows/${id}`
  const res = await fetch(url, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`workflow fetch failed: ${res.status}`)
  }
  return (await res.json()) as Workflow
}

export const useWorkflow = (id: string | undefined) =>
  useQuery({
    queryKey: workflowKey('detail', id ?? ''),
    queryFn: () => fetchWorkflow(id!),
    retry: baseRetry,
    enabled: !!id,
  })

// ══════════════════════════════════════════════
//  Runs (per-workflow-version)
// ══════════════════════════════════════════════

export type RunStatus =
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'awaiting_human'

export interface Run {
  id: string
  workflow_version_id: string
  status: RunStatus
  triggered_by_kind: string
  triggered_by_id: string | null
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  created_at: string
}

export interface PaginatedRuns {
  data: Run[]
  meta: {
    total: number
    page: number
    per_page: number
    pages: number
  }
}

const runKey = (...parts: (string | object)[]) => ['agents-runs', ...parts]

async function fetchRuns(
  params: {
    workflow_version_id?: string
    status?: RunStatus
    page?: number
    limit?: number
  } = {},
): Promise<PaginatedRuns> {
  const url = new URL(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/runs/`)
  if (params.workflow_version_id)
    url.searchParams.set('workflow_version_id', params.workflow_version_id)
  if (params.status) url.searchParams.set('status', params.status)
  if (params.page) url.searchParams.set('page', String(params.page))
  if (params.limit) url.searchParams.set('limit', String(params.limit))

  const res = await fetch(url.toString(), {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`runs list failed: ${res.status}`)
  }
  return (await res.json()) as PaginatedRuns
}

export const useRuns = (
  params: {
    workflow_version_id?: string
    status?: RunStatus
    page?: number
    limit?: number
  } = {},
  enabled: boolean = true,
) =>
  useQuery({
    queryKey: runKey('list', params),
    queryFn: () => fetchRuns(params),
    retry: baseRetry,
    enabled,
  })

// ══════════════════════════════════════════════
//  Run detail + node-runs
// ══════════════════════════════════════════════

async function fetchRun(id: string): Promise<RunDetail> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/runs/${id}`
  const res = await fetch(url, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`run fetch failed: ${res.status}`)
  }
  return (await res.json()) as RunDetail
}

export interface RunDetail extends Run {
  // The GET /runs/{id} endpoint returns the same shape as the
  // list endpoint plus input_data / output_data. Listed here so
  // the detail page picks up the typed extras.
  input_data: Record<string, unknown>
  output_data: Record<string, unknown>
}

export const useRun = (id: string | undefined) =>
  useQuery({
    queryKey: runKey('detail', id ?? ''),
    queryFn: () => fetchRun(id!),
    retry: baseRetry,
    enabled: !!id,
  })

// ── Node runs (per-step records under a run) ──

export type NodeRunStatus =
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'skipped'
  | 'awaiting_human'

export interface NodeRun {
  id: string
  run_id: string
  node_id: string
  node_type: string
  status: NodeRunStatus
  started_at: string | null
  completed_at: string | null
  input_data: Record<string, unknown>
  output_data: Record<string, unknown> | null
  error_message: string | null
  created_at: string
}

export interface PaginatedNodeRuns {
  data: NodeRun[]
  meta: {
    total: number
    page: number
    per_page: number
    pages: number
  }
}

const nodeRunKey = (...parts: (string | object)[]) => [
  'agents-node-runs',
  ...parts,
]

async function fetchNodeRuns(runId: string): Promise<PaginatedNodeRuns> {
  const url = new URL(
    `${process.env.NEXT_PUBLIC_API_URL}/api/v1/runs/${runId}/nodes`,
  )
  // The list defaults to 50 items; the engine rarely produces
  // more steps than that. Bigger graphs can scroll once
  // pagination lands on the UI side.
  url.searchParams.set('limit', '100')
  url.searchParams.set('page', '1')

  const res = await fetch(url.toString(), {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`node-runs list failed: ${res.status}`)
  }
  return (await res.json()) as PaginatedNodeRuns
}

export const useNodeRuns = (runId: string | undefined) =>
  useQuery({
    queryKey: nodeRunKey('list', runId ?? ''),
    queryFn: () => fetchNodeRuns(runId!),
    retry: baseRetry,
    enabled: !!runId,
  })
