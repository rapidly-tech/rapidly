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

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

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
  archived_at: string | null
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
  params: {
    workspace_id?: string
    project_id?: string
    name?: string
    has_version?: boolean
    is_archived?: boolean | null
    page?: number
    limit?: number
  } = {},
): Promise<PaginatedWorkflows> {
  const url = new URL(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/workflows/`)
  if (params.workspace_id)
    url.searchParams.set('workspace_id', params.workspace_id)
  if (params.project_id) url.searchParams.set('project_id', params.project_id)
  if (params.name) url.searchParams.set('name', params.name)
  if (params.has_version !== undefined)
    url.searchParams.set('has_version', String(params.has_version))
  // ``is_archived`` is tri-state. ``undefined`` / ``null`` →
  // omit the param entirely (server returns both archived and
  // active). ``true`` / ``false`` → narrow.
  if (params.is_archived === true || params.is_archived === false) {
    url.searchParams.set('is_archived', String(params.is_archived))
  }
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
  params: {
    workspace_id?: string
    project_id?: string
    name?: string
    has_version?: boolean
    is_archived?: boolean | null
    page?: number
    limit?: number
  } = {},
  enabled: boolean = true,
) =>
  useQuery({
    queryKey: workflowKey('list', params),
    queryFn: () => fetchWorkflows(params),
    retry: baseRetry,
    enabled,
  })

export interface WorkflowCreatePayload {
  workspace_id: string
  name: string
  description?: string | null
  project_id?: string | null
}

async function createWorkflow(body: WorkflowCreatePayload): Promise<Workflow> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/workflows/`
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `workflow create failed: ${res.status}`)
  }
  return (await res.json()) as Workflow
}

export const useCreateWorkflow = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createWorkflow,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: workflowKey() })
    },
  })
}

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

export type TriggeredByKind =
  | 'user'
  | 'webhook'
  | 'schedule'
  | 'sub_workflow'
  | 'eval'

export interface Run {
  id: string
  workflow_version_id: string
  status: RunStatus
  triggered_by_kind: TriggeredByKind
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
    triggered_by_kind?: TriggeredByKind
    page?: number
    limit?: number
  } = {},
): Promise<PaginatedRuns> {
  const url = new URL(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/runs/`)
  if (params.workflow_version_id)
    url.searchParams.set('workflow_version_id', params.workflow_version_id)
  if (params.status) url.searchParams.set('status', params.status)
  if (params.triggered_by_kind)
    url.searchParams.set('triggered_by_kind', params.triggered_by_kind)
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
    triggered_by_kind?: TriggeredByKind
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

const TERMINAL_RUN_STATUSES: RunStatus[] = ['succeeded', 'failed', 'cancelled']

export const useRun = (id: string | undefined) =>
  useQuery({
    queryKey: runKey('detail', id ?? ''),
    queryFn: () => fetchRun(id!),
    retry: baseRetry,
    enabled: !!id,
    // Poll every 2s while the run is non-terminal. Once it
    // lands in succeeded / failed / cancelled, ``refetchInterval``
    // returns false and the cache stops moving. This is the
    // same shape M5.5's eval-cases hook uses; the two together
    // give a near-live UI without any websocket plumbing.
    refetchInterval: (q) => {
      const data = q.state.data as RunDetail | undefined
      if (!data) return 2000
      return TERMINAL_RUN_STATUSES.includes(data.status) ? false : 2000
    },
  })

export interface TriggerRunPayload {
  input_data: Record<string, unknown>
}

async function triggerRun(args: {
  workflowId: string
  body: TriggerRunPayload
}): Promise<Run> {
  const { workflowId, body } = args
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/workflows/${workflowId}/runs`
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `run trigger failed: ${res.status}`)
  }
  return (await res.json()) as Run
}

export const useTriggerRun = (workflowId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: TriggerRunPayload) => triggerRun({ workflowId, body }),
    onSuccess: () => {
      // Invalidate all run-list queries so the workflow detail
      // page picks up the new row immediately.
      qc.invalidateQueries({ queryKey: runKey() })
    },
  })
}

// ── Workflow version publishing (M4.1 graph_json upload) ───

export interface WorkflowVersion {
  id: string
  workflow_id: string
  version_number: number
  graph_json: Record<string, unknown>
  created_by_id: string
  created_at: string
}

export interface PublishVersionPayload {
  graph_json: { nodes: unknown[]; edges: unknown[] }
}

async function publishVersion(args: {
  workflowId: string
  body: PublishVersionPayload
}): Promise<WorkflowVersion> {
  const { workflowId, body } = args
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/workflows/${workflowId}/versions`
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `version publish failed: ${res.status}`)
  }
  return (await res.json()) as WorkflowVersion
}

async function setCurrentVersion(args: {
  workflowId: string
  versionId: string
}): Promise<Workflow> {
  const { workflowId, versionId } = args
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/workflows/${workflowId}`
  const res = await fetch(url, {
    method: 'PATCH',
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ current_version_id: versionId }),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `set-current-version failed: ${res.status}`)
  }
  return (await res.json()) as Workflow
}

export const usePublishVersion = (workflowId: string) => {
  const qc = useQueryClient()
  return useMutation({
    // Two-step: POST the version, then PATCH the workflow to
    // make it the active one. Workflow authors who publish
    // overwhelmingly want the new version to be the live one;
    // if they wanted a non-active snapshot they'd POST the
    // version via API and skip the PATCH. v1 collapses the
    // common case into one click.
    mutationFn: async (body: PublishVersionPayload) => {
      const version = await publishVersion({ workflowId, body })
      await setCurrentVersion({ workflowId, versionId: version.id })
      return version
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: workflowKey() })
      qc.invalidateQueries({ queryKey: workflowKey(workflowId, 'versions') })
    },
  })
}

// ── Workflow version listing + rollback ────────────────────────

export interface PaginatedWorkflowVersions {
  data: WorkflowVersion[]
  meta: {
    total: number
    page: number
    per_page: number
    pages: number
  }
}

async function fetchWorkflowVersions(args: {
  workflowId: string
  page?: number
  limit?: number
}): Promise<PaginatedWorkflowVersions> {
  const { workflowId, page = 1, limit = 25 } = args
  const url = new URL(
    `${process.env.NEXT_PUBLIC_API_URL}/api/v1/workflows/${workflowId}/versions`,
  )
  url.searchParams.set('page', String(page))
  url.searchParams.set('limit', String(limit))
  const res = await fetch(url.toString(), {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`versions list failed: ${res.status}`)
  }
  return (await res.json()) as PaginatedWorkflowVersions
}

export const useWorkflowVersions = (
  workflowId: string,
  params: { page?: number; limit?: number } = {},
  enabled: boolean = true,
) =>
  useQuery({
    queryKey: workflowKey(workflowId, 'versions', params),
    queryFn: () => fetchWorkflowVersions({ workflowId, ...params }),
    retry: baseRetry,
    enabled,
  })

export const useSetCurrentVersion = (workflowId: string) => {
  const qc = useQueryClient()
  return useMutation({
    // Plain PATCH — same fetcher publish uses, but without the
    // POST /versions step. Used by the version-history section
    // to roll back to a past version.
    mutationFn: (versionId: string) =>
      setCurrentVersion({ workflowId, versionId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: workflowKey() })
    },
  })
}

// ── Workflow rename + delete ───────────────────────────────────

export interface WorkflowUpdatePayload {
  name?: string
  description?: string | null
  project_id?: string | null
}

async function updateWorkflow(args: {
  workflowId: string
  body: WorkflowUpdatePayload
}): Promise<Workflow> {
  const { workflowId, body } = args
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/workflows/${workflowId}`
  const res = await fetch(url, {
    method: 'PATCH',
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `workflow update failed: ${res.status}`)
  }
  return (await res.json()) as Workflow
}

export const useUpdateWorkflow = (workflowId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: WorkflowUpdatePayload) =>
      updateWorkflow({ workflowId, body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: workflowKey() })
    },
  })
}

async function deleteWorkflow(workflowId: string): Promise<void> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/workflows/${workflowId}`
  const res = await fetch(url, {
    method: 'DELETE',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `workflow delete failed: ${res.status}`)
  }
}

export const useDeleteWorkflow = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteWorkflow,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: workflowKey() })
    },
  })
}

async function archiveWorkflow(id: string): Promise<Workflow> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/workflows/${id}/archive`
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `workflow archive failed: ${res.status}`)
  }
  return (await res.json()) as Workflow
}

async function unarchiveWorkflow(id: string): Promise<Workflow> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/workflows/${id}/unarchive`
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `workflow unarchive failed: ${res.status}`)
  }
  return (await res.json()) as Workflow
}

export const useArchiveWorkflow = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: archiveWorkflow,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: workflowKey() })
    },
  })
}

export const useUnarchiveWorkflow = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: unarchiveWorkflow,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: workflowKey() })
    },
  })
}

async function cancelRun(id: string): Promise<RunDetail> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/runs/${id}/cancel`
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`run cancel failed: ${res.status}`)
  }
  return (await res.json()) as RunDetail
}

export const useCancelRun = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: cancelRun,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: runKey() })
    },
  })
}

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

export const useNodeRuns = (
  runId: string | undefined,
  options: { isRunActive?: boolean } = {},
) =>
  useQuery({
    queryKey: nodeRunKey('list', runId ?? ''),
    queryFn: () => fetchNodeRuns(runId!),
    retry: baseRetry,
    enabled: !!runId,
    // Poll only while the parent Run is non-terminal. The
    // caller passes ``isRunActive`` based on the Run's
    // status; once it goes false the cache stops moving.
    refetchInterval: options.isRunActive ? 2000 : false,
  })

// ══════════════════════════════════════════════
//  Datasets + cases (eval fixtures, M4.8a)
// ══════════════════════════════════════════════

export interface Dataset {
  id: string
  workspace_id: string
  name: string
  description: string | null
  archived_at: string | null
  created_at: string
  modified_at: string | null
}

export interface PaginatedDatasets {
  data: Dataset[]
  meta: {
    total: number
    page: number
    per_page: number
    pages: number
  }
}

export interface DatasetCase {
  id: string
  dataset_id: string
  name: string
  input_data: Record<string, unknown>
  expected_output: Record<string, unknown> | null
  order_index: number
  created_at: string
  modified_at: string | null
}

const datasetKey = (...parts: (string | object)[]) => [
  'agents-datasets',
  ...parts,
]

async function fetchDatasets(
  params: {
    workspace_id?: string
    name?: string
    is_archived?: boolean | null
    page?: number
    limit?: number
  } = {},
): Promise<PaginatedDatasets> {
  const url = new URL(
    `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/datasets/`,
  )
  if (params.workspace_id)
    url.searchParams.set('workspace_id', params.workspace_id)
  if (params.name) url.searchParams.set('name', params.name)
  if (params.is_archived === true || params.is_archived === false) {
    url.searchParams.set('is_archived', String(params.is_archived))
  }
  if (params.page) url.searchParams.set('page', String(params.page))
  if (params.limit) url.searchParams.set('limit', String(params.limit))

  const res = await fetch(url.toString(), {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) throw new Error(`datasets list failed: ${res.status}`)
  return (await res.json()) as PaginatedDatasets
}

export const useDatasets = (
  params: {
    workspace_id?: string
    name?: string
    is_archived?: boolean | null
    page?: number
    limit?: number
  } = {},
  enabled: boolean = true,
) =>
  useQuery({
    queryKey: datasetKey('list', params),
    queryFn: () => fetchDatasets(params),
    retry: baseRetry,
    enabled,
  })

async function fetchDataset(id: string): Promise<Dataset> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/datasets/${id}`
  const res = await fetch(url, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) throw new Error(`dataset fetch failed: ${res.status}`)
  return (await res.json()) as Dataset
}

export const useDataset = (id: string | undefined) =>
  useQuery({
    queryKey: datasetKey('detail', id ?? ''),
    queryFn: () => fetchDataset(id!),
    retry: baseRetry,
    enabled: !!id,
  })

export interface DatasetCreatePayload {
  workspace_id: string
  name: string
  description?: string | null
}

async function createDataset(body: DatasetCreatePayload): Promise<Dataset> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/datasets/`
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `dataset create failed: ${res.status}`)
  }
  return (await res.json()) as Dataset
}

export const useCreateDataset = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createDataset,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: datasetKey() })
    },
  })
}

async function fetchDatasetCases(datasetId: string): Promise<DatasetCase[]> {
  // The cases list endpoint returns a bare array (no pagination
  // envelope) — see ``server/rapidly/agents/dataset/api.py``;
  // operators rarely have >>100 cases in a dataset, so the
  // unpaginated shape was a deliberate v1 simplification.
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/datasets/${datasetId}/cases`
  const res = await fetch(url, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) throw new Error(`dataset cases failed: ${res.status}`)
  return (await res.json()) as DatasetCase[]
}

export const useDatasetCases = (datasetId: string | undefined) =>
  useQuery({
    queryKey: datasetKey('cases', datasetId ?? ''),
    queryFn: () => fetchDatasetCases(datasetId!),
    retry: baseRetry,
    enabled: !!datasetId,
  })

export interface DatasetCaseCreatePayload {
  name: string
  input_data: Record<string, unknown>
  expected_output?: Record<string, unknown> | null
  order_index?: number
}

async function createDatasetCase(args: {
  datasetId: string
  body: DatasetCaseCreatePayload
}): Promise<DatasetCase> {
  const { datasetId, body } = args
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/datasets/${datasetId}/cases`
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `case create failed: ${res.status}`)
  }
  return (await res.json()) as DatasetCase
}

export const useCreateDatasetCase = (datasetId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: DatasetCaseCreatePayload) =>
      createDatasetCase({ datasetId, body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: datasetKey('cases', datasetId) })
    },
  })
}

// Exposed so the bulk-import flow can call it directly while
// managing its own per-row progress state. We can't use
// useMutation for the bulk case because the caller wants
// in-flight per-row counters, not an opaque "is pending".
export { createDatasetCase as postDatasetCase }

// ── Dataset rename + delete + case delete ──────────────────────

export interface DatasetUpdatePayload {
  name?: string
  description?: string | null
}

async function updateDataset(args: {
  datasetId: string
  body: DatasetUpdatePayload
}): Promise<Dataset> {
  const { datasetId, body } = args
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/datasets/${datasetId}`
  const res = await fetch(url, {
    method: 'PATCH',
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `dataset update failed: ${res.status}`)
  }
  return (await res.json()) as Dataset
}

export const useUpdateDataset = (datasetId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: DatasetUpdatePayload) =>
      updateDataset({ datasetId, body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: datasetKey() })
    },
  })
}

async function deleteDataset(datasetId: string): Promise<void> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/datasets/${datasetId}`
  const res = await fetch(url, {
    method: 'DELETE',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `dataset delete failed: ${res.status}`)
  }
}

export const useDeleteDataset = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteDataset,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: datasetKey() })
    },
  })
}

async function archiveDataset(id: string): Promise<Dataset> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/datasets/${id}/archive`
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `dataset archive failed: ${res.status}`)
  }
  return (await res.json()) as Dataset
}

async function unarchiveDataset(id: string): Promise<Dataset> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/datasets/${id}/unarchive`
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `dataset unarchive failed: ${res.status}`)
  }
  return (await res.json()) as Dataset
}

export const useArchiveDataset = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: archiveDataset,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: datasetKey() })
    },
  })
}

export const useUnarchiveDataset = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: unarchiveDataset,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: datasetKey() })
    },
  })
}

async function deleteDatasetCase(args: {
  datasetId: string
  caseId: string
}): Promise<void> {
  const { datasetId, caseId } = args
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/datasets/${datasetId}/cases/${caseId}`
  const res = await fetch(url, {
    method: 'DELETE',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `case delete failed: ${res.status}`)
  }
}

export const useDeleteDatasetCase = (datasetId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (caseId: string) => deleteDatasetCase({ datasetId, caseId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: datasetKey('cases', datasetId) })
    },
  })
}

// ══════════════════════════════════════════════
//  Eval runs (M4.8b–e)
// ══════════════════════════════════════════════

export type EvalRunStatus =
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled'

export type AssertionStrategy = 'exact_match' | 'json_schema' | 'llm_judge'

export interface EvalRun {
  id: string
  workspace_id: string
  dataset_id: string
  workflow_version_id: string
  status: EvalRunStatus
  assertion_strategy: AssertionStrategy
  judge_model_id: string | null
  case_count: number
  pass_count: number
  fail_count: number
  error_count: number
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  created_at: string
}

export interface PaginatedEvalRuns {
  data: EvalRun[]
  meta: {
    total: number
    page: number
    per_page: number
    pages: number
  }
}

export interface EvalRunCase {
  id: string
  eval_run_id: string
  case_id: string | null
  run_id: string | null
  case_name: string
  case_input_data: Record<string, unknown>
  case_expected_output: Record<string, unknown> | null
  actual_output: Record<string, unknown> | null
  passed: boolean | null
  error_message: string | null
  judge_reason: string | null
  duration_ms: number | null
  created_at: string
}

const evalRunKey = (...parts: (string | object)[]) => [
  'agents-eval-runs',
  ...parts,
]

async function fetchEvalRuns(
  params: {
    workspace_id?: string
    dataset_id?: string
    workflow_version_id?: string
    status?: EvalRunStatus
    assertion_strategy?: AssertionStrategy
    page?: number
    limit?: number
  } = {},
): Promise<PaginatedEvalRuns> {
  const url = new URL(
    `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/eval-runs/`,
  )
  if (params.workspace_id)
    url.searchParams.set('workspace_id', params.workspace_id)
  if (params.dataset_id) url.searchParams.set('dataset_id', params.dataset_id)
  if (params.workflow_version_id)
    url.searchParams.set('workflow_version_id', params.workflow_version_id)
  if (params.status) url.searchParams.set('status', params.status)
  if (params.assertion_strategy)
    url.searchParams.set('assertion_strategy', params.assertion_strategy)
  if (params.page) url.searchParams.set('page', String(params.page))
  if (params.limit) url.searchParams.set('limit', String(params.limit))

  const res = await fetch(url.toString(), {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) throw new Error(`eval-runs list failed: ${res.status}`)
  return (await res.json()) as PaginatedEvalRuns
}

export const useEvalRuns = (
  params: {
    workspace_id?: string
    dataset_id?: string
    workflow_version_id?: string
    status?: EvalRunStatus
    assertion_strategy?: AssertionStrategy
    page?: number
    limit?: number
  } = {},
  enabled: boolean = true,
) =>
  useQuery({
    queryKey: evalRunKey('list', params),
    queryFn: () => fetchEvalRuns(params),
    retry: baseRetry,
    enabled,
  })

async function fetchEvalRun(id: string): Promise<EvalRun> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/eval-runs/${id}`
  const res = await fetch(url, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) throw new Error(`eval-run fetch failed: ${res.status}`)
  return (await res.json()) as EvalRun
}

const TERMINAL_EVAL_STATUSES: EvalRunStatus[] = [
  'succeeded',
  'failed',
  'cancelled',
]

export const useEvalRun = (id: string | undefined) =>
  useQuery({
    queryKey: evalRunKey('detail', id ?? ''),
    queryFn: () => fetchEvalRun(id!),
    retry: baseRetry,
    enabled: !!id,
    // Poll while the eval is non-terminal so the header
    // case_count + pass/fail counters tick live as the
    // runner increments them. Same shape as useRun (M5.9).
    // The cases endpoint already polls (M5.5); pairing
    // the two means the whole eval-run detail page feels
    // live without a websocket.
    refetchInterval: (q) => {
      const data = q.state.data as EvalRun | undefined
      if (!data) return 2500
      return TERMINAL_EVAL_STATUSES.includes(data.status) ? false : 2500
    },
  })

async function fetchEvalRunCases(id: string): Promise<EvalRunCase[]> {
  // Bare array — mirrors the dataset cases endpoint's choice
  // not to paginate (eval runs against curated datasets rarely
  // exceed 100 cases).
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/eval-runs/${id}/cases`
  const res = await fetch(url, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) throw new Error(`eval-run cases failed: ${res.status}`)
  return (await res.json()) as EvalRunCase[]
}

export interface TriggerEvalPayload {
  workflow_version_id: string
  dataset_id: string
  assertion_strategy: AssertionStrategy
  judge_model_id?: string | null
}

async function triggerEval(body: TriggerEvalPayload): Promise<EvalRun> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/eval-runs/`
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `eval-run trigger failed: ${res.status}`)
  }
  return (await res.json()) as EvalRun
}

export const useTriggerEval = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: triggerEval,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: evalRunKey() })
    },
  })
}

async function cancelEvalRun(id: string): Promise<EvalRun> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/eval-runs/${id}/cancel`
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `eval-run cancel failed: ${res.status}`)
  }
  return (await res.json()) as EvalRun
}

export const useCancelEvalRun = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: cancelEvalRun,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: evalRunKey() })
    },
  })
}

export const useEvalRunCases = (
  id: string | undefined,
  options: { isEvalActive?: boolean } = {},
) =>
  useQuery({
    queryKey: evalRunKey('cases', id ?? ''),
    queryFn: () => fetchEvalRunCases(id!),
    retry: baseRetry,
    enabled: !!id,
    // Poll only while the parent eval is non-terminal —
    // mirrors the pattern useNodeRuns uses for run-detail
    // polling. The page passes ``isEvalActive`` based on
    // the eval's status; once it goes false the cache stops
    // moving and the polling effectively idles.
    refetchInterval: options.isEvalActive ? 3000 : false,
  })

// ══════════════════════════════════════════════
//  IntegrationCredentials (M4.7a-h)
// ══════════════════════════════════════════════

export interface IntegrationCredential {
  id: string
  workspace_id: string
  provider: string
  name: string
  base_url: string | null
  is_default: boolean
  monthly_budget_tokens: number | null
  budget_alert_threshold_percent: number | null
  budget_alert_triggered_at: string | null
  created_at: string
  modified_at: string | null
}

export interface PaginatedCredentials {
  data: IntegrationCredential[]
  meta: {
    total: number
    page: number
    per_page: number
    pages: number
  }
}

export interface CredentialBudgetRow {
  credential_id: string
  workspace_id: string
  provider: string
  name: string
  monthly_budget_tokens: number | null
  month_to_date_tokens: number
  percent_used: number | null
}

export interface CredentialAlertRow {
  credential_id: string
  workspace_id: string
  provider: string
  name: string
  monthly_budget_tokens: number
  threshold_percent: number
  month_to_date_tokens: number
  percent_used: number
  triggered_at: string
}

export interface CredentialCreatePayload {
  workspace_id: string
  provider: string
  name: string
  secret: string
  base_url?: string | null
  is_default?: boolean
  monthly_budget_tokens?: number | null
  budget_alert_threshold_percent?: number | null
}

const credentialKey = (...parts: (string | object)[]) => [
  'agents-credentials',
  ...parts,
]

async function fetchCredentials(
  params: {
    provider?: string
    name?: string
    page?: number
    limit?: number
  } = {},
): Promise<PaginatedCredentials> {
  const url = new URL(
    `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/integration-credentials/`,
  )
  if (params.provider) url.searchParams.set('provider', params.provider)
  if (params.name) url.searchParams.set('name', params.name)
  if (params.page) url.searchParams.set('page', String(params.page))
  if (params.limit) url.searchParams.set('limit', String(params.limit))
  const res = await fetch(url.toString(), {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) throw new Error(`credentials list failed: ${res.status}`)
  return (await res.json()) as PaginatedCredentials
}

export const useCredentials = (
  params: {
    provider?: string
    name?: string
    page?: number
    limit?: number
  } = {},
  enabled: boolean = true,
) =>
  useQuery({
    queryKey: credentialKey('list', params),
    queryFn: () => fetchCredentials(params),
    retry: baseRetry,
    enabled,
  })

async function fetchCredentialBudgets(): Promise<{
  month_start: string
  rows: CredentialBudgetRow[]
}> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/llm-usage/budgets`
  const res = await fetch(url, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) throw new Error(`budgets fetch failed: ${res.status}`)
  return (await res.json()) as {
    month_start: string
    rows: CredentialBudgetRow[]
  }
}

export const useCredentialBudgets = () =>
  useQuery({
    queryKey: credentialKey('budgets'),
    queryFn: fetchCredentialBudgets,
    retry: baseRetry,
  })

async function fetchCredentialAlerts(): Promise<{
  rows: CredentialAlertRow[]
}> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/llm-usage/alerts`
  const res = await fetch(url, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) throw new Error(`alerts fetch failed: ${res.status}`)
  return (await res.json()) as { rows: CredentialAlertRow[] }
}

export const useCredentialAlerts = () =>
  useQuery({
    queryKey: credentialKey('alerts'),
    queryFn: fetchCredentialAlerts,
    retry: baseRetry,
  })

// ── LLM usage rollup (M4.7f) ─────────────────────────────────

export interface UsageRollupRow {
  workspace_id: string
  credential_id: string | null
  provider: string
  model: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  call_count: number
}

export interface UsageRollupResponse {
  window_start: string
  window_end: string
  rows: UsageRollupRow[]
}

async function fetchUsageRollup(
  params: {
    window_start?: string
    window_end?: string
    credential_id?: string
    provider?: string
  } = {},
): Promise<UsageRollupResponse> {
  const url = new URL(
    `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/llm-usage/rollup`,
  )
  if (params.window_start)
    url.searchParams.set('window_start', params.window_start)
  if (params.window_end) url.searchParams.set('window_end', params.window_end)
  if (params.credential_id)
    url.searchParams.set('credential_id', params.credential_id)
  if (params.provider) url.searchParams.set('provider', params.provider)

  const res = await fetch(url.toString(), {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) throw new Error(`usage rollup failed: ${res.status}`)
  return (await res.json()) as UsageRollupResponse
}

const usageKey = (...parts: (string | object)[]) => ['agents-usage', ...parts]

export const useUsageRollup = (
  params: {
    window_start?: string
    window_end?: string
    credential_id?: string
    provider?: string
  } = {},
) =>
  useQuery({
    queryKey: usageKey('rollup', params),
    queryFn: () => fetchUsageRollup(params),
    retry: baseRetry,
  })

// ══════════════════════════════════════════════
//  Vector collections (M4.6c — RAG corpus root)
// ══════════════════════════════════════════════

export interface VectorCollection {
  id: string
  workspace_id: string
  project_id: string | null
  name: string
  embedding_model: string
  dimensions: number
  created_at: string
  modified_at: string | null
}

export interface PaginatedVectorCollections {
  data: VectorCollection[]
  meta: {
    total: number
    page: number
    per_page: number
    pages: number
  }
}

export interface VectorCollectionCreatePayload {
  workspace_id: string
  name: string
  embedding_model: string
  dimensions: number
  project_id?: string | null
}

const vectorCollectionKey = (...parts: (string | object)[]) => [
  'agents-vector-collections',
  ...parts,
]

async function fetchVectorCollections(
  params: {
    workspace_id?: string
    page?: number
    limit?: number
    project_id?: string
    name?: string
  } = {},
): Promise<PaginatedVectorCollections> {
  const url = new URL(
    `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/vector-collections/`,
  )
  if (params.workspace_id)
    url.searchParams.set('workspace_id', params.workspace_id)
  if (params.page) url.searchParams.set('page', String(params.page))
  if (params.limit) url.searchParams.set('limit', String(params.limit))
  if (params.project_id) url.searchParams.set('project_id', params.project_id)
  if (params.name) url.searchParams.set('name', params.name)

  const res = await fetch(url.toString(), {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`vector collections list failed: ${res.status}`)
  }
  return (await res.json()) as PaginatedVectorCollections
}

export const useVectorCollections = (
  params: {
    workspace_id?: string
    page?: number
    limit?: number
    project_id?: string
    name?: string
  } = {},
) =>
  useQuery({
    queryKey: vectorCollectionKey('list', params),
    queryFn: () => fetchVectorCollections(params),
    retry: baseRetry,
  })

async function createVectorCollection(
  body: VectorCollectionCreatePayload,
): Promise<VectorCollection> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/vector-collections/`
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `vector collection create failed: ${res.status}`)
  }
  return (await res.json()) as VectorCollection
}

export const useCreateVectorCollection = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createVectorCollection,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: vectorCollectionKey() })
    },
  })
}

async function deleteVectorCollection(id: string): Promise<void> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/vector-collections/${id}`
  const res = await fetch(url, {
    method: 'DELETE',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok && res.status !== 204) {
    throw new Error(`vector collection delete failed: ${res.status}`)
  }
}

export const useDeleteVectorCollection = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteVectorCollection,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: vectorCollectionKey() })
    },
  })
}

export interface VectorCollectionUpdatePayload {
  name?: string
  project_id?: string | null
}

async function updateVectorCollection(args: {
  collectionId: string
  body: VectorCollectionUpdatePayload
}): Promise<VectorCollection> {
  const { collectionId, body } = args
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/vector-collections/${collectionId}`
  const res = await fetch(url, {
    method: 'PATCH',
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `vector collection update failed: ${res.status}`)
  }
  return (await res.json()) as VectorCollection
}

export const useUpdateVectorCollection = (collectionId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: VectorCollectionUpdatePayload) =>
      updateVectorCollection({ collectionId, body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: vectorCollectionKey() })
    },
  })
}

// ── Mutations ─────────────────────────────────────────────────

async function createCredential(
  body: CredentialCreatePayload,
): Promise<IntegrationCredential> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/integration-credentials/`
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    // Surface the response body when 422 — Pydantic validation
    // errors carry per-field detail the UI can flag inline.
    const text = await res.text().catch(() => '')
    throw new Error(text || `credential create failed: ${res.status}`)
  }
  return (await res.json()) as IntegrationCredential
}

export const useCreateCredential = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createCredential,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: credentialKey() })
    },
  })
}

async function deleteCredential(id: string): Promise<void> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/integration-credentials/${id}`
  const res = await fetch(url, {
    method: 'DELETE',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok && res.status !== 204) {
    throw new Error(`credential delete failed: ${res.status}`)
  }
}

export const useDeleteCredential = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteCredential,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: credentialKey() })
    },
  })
}

async function setDefaultCredential(
  id: string,
): Promise<IntegrationCredential> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/integration-credentials/${id}/default`
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`credential set-default failed: ${res.status}`)
  }
  return (await res.json()) as IntegrationCredential
}

export const useSetDefaultCredential = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: setDefaultCredential,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: credentialKey() })
    },
  })
}
