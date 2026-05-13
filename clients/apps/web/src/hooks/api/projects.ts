import { getQueryClient } from '@/utils/api/query'
import { api } from '@/utils/client'
import { operations, resolveResponse, schemas } from '@rapidly-tech/client'
import { useMutation, useQuery } from '@tanstack/react-query'
import { baseRetry } from './retry'

// ── Cache key builders ──

const projectKey = (...parts: (string | object)[]) => ['projects', ...parts]
const workItemKey = (...parts: (string | object)[]) => ['work_items', ...parts]

// ══════════════════════════════════════════════
//  Projects
// ══════════════════════════════════════════════

export type Project = schemas['Project']
export type ProjectCreate = schemas['ProjectCreate']
export type ProjectUpdate = schemas['ProjectUpdate']

export const useProjects = (
  params: operations['projects:list']['parameters']['query'],
  enabled: boolean = true,
) =>
  useQuery({
    queryKey: projectKey('list', params ?? {}),
    queryFn: () =>
      resolveResponse(api.GET('/api/projects/', { params: { query: params } })),
    retry: baseRetry,
    enabled,
  })

export const useProject = (id: string | undefined) =>
  useQuery({
    queryKey: projectKey('detail', id ?? ''),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/projects/{id}', { params: { path: { id: id! } } }),
      ),
    retry: baseRetry,
    enabled: !!id,
  })

export const useCreateProject = () =>
  useMutation({
    mutationFn: (body: ProjectCreate) =>
      resolveResponse(api.POST('/api/projects/', { body })),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['projects'] })
    },
  })

export const useUpdateProject = (id: string) =>
  useMutation({
    mutationFn: (body: ProjectUpdate) =>
      resolveResponse(
        api.PATCH('/api/projects/{id}', {
          params: { path: { id } },
          body,
        }),
      ),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['projects'] })
    },
  })

export const useArchiveProject = (id: string) =>
  useMutation({
    mutationFn: () =>
      resolveResponse(
        api.POST('/api/projects/{id}/archive', { params: { path: { id } } }),
      ),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['projects'] })
    },
  })

export const useDeleteProject = (id: string) =>
  useMutation({
    mutationFn: () =>
      api.DELETE('/api/projects/{id}', { params: { path: { id } } }),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['projects'] })
    },
  })

// ══════════════════════════════════════════════
//  Work items
// ══════════════════════════════════════════════

export type WorkItem = schemas['WorkItem']
export type WorkItemCreate = schemas['WorkItemCreate']
export type WorkItemUpdate = schemas['WorkItemUpdate']

export const useWorkItems = (
  params: operations['work-items:list_items']['parameters']['query'],
  enabled: boolean = true,
) =>
  useQuery({
    queryKey: workItemKey('list', params ?? {}),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/work-items/', { params: { query: params } }),
      ),
    retry: baseRetry,
    enabled,
  })

export const useWorkItem = (id: string | undefined) =>
  useQuery({
    queryKey: workItemKey('detail', id ?? ''),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/work-items/{id}', { params: { path: { id: id! } } }),
      ),
    retry: baseRetry,
    enabled: !!id,
  })

export const useCreateWorkItem = () =>
  useMutation({
    mutationFn: (body: WorkItemCreate) =>
      resolveResponse(api.POST('/api/work-items/', { body })),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['work_items'] })
    },
  })

export const useUpdateWorkItem = (id: string) =>
  useMutation({
    mutationFn: (body: WorkItemUpdate) =>
      resolveResponse(
        api.PATCH('/api/work-items/{id}', {
          params: { path: { id } },
          body,
        }),
      ),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['work_items'] })
    },
  })

// Variant whose ``mutationFn`` takes the work-item id alongside the patch
// body, useful when one component drives many different items (e.g. a
// kanban board reassigning items between columns).
export const useReassignWorkItem = () =>
  useMutation({
    mutationFn: ({ id, body }: { id: string; body: WorkItemUpdate }) =>
      resolveResponse(
        api.PATCH('/api/work-items/{id}', {
          params: { path: { id } },
          body,
        }),
      ),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['work_items'] })
    },
  })

export const useDeleteWorkItem = (id: string) =>
  useMutation({
    mutationFn: () =>
      api.DELETE('/api/work-items/{id}', { params: { path: { id } } }),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['work_items'] })
    },
  })

// ══════════════════════════════════════════════
//  Project states
// ══════════════════════════════════════════════

export type ProjectState = schemas['ProjectState']
export type ProjectStateCreate = schemas['ProjectStateCreate']

const stateKey = (...parts: (string | object)[]) => ['project_states', ...parts]

export const useProjectStates = (
  params: operations['project-states:list']['parameters']['query'],
  enabled: boolean = true,
) =>
  useQuery({
    queryKey: stateKey('list', params ?? {}),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/project-states/', { params: { query: params } }),
      ),
    retry: baseRetry,
    enabled,
  })

export const useCreateProjectState = () =>
  useMutation({
    mutationFn: (body: ProjectStateCreate) =>
      resolveResponse(api.POST('/api/project-states/', { body })),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['project_states'] })
    },
  })

// ══════════════════════════════════════════════
//  Project labels
// ══════════════════════════════════════════════

export type ProjectLabel = schemas['ProjectLabel']
export type ProjectLabelCreate = schemas['ProjectLabelCreate']

const labelKey = (...parts: (string | object)[]) => ['project_labels', ...parts]

export const useProjectLabels = (
  params: operations['project-labels:list']['parameters']['query'],
  enabled: boolean = true,
) =>
  useQuery({
    queryKey: labelKey('list', params ?? {}),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/project-labels/', { params: { query: params } }),
      ),
    retry: baseRetry,
    enabled,
  })

export const useCreateProjectLabel = () =>
  useMutation({
    mutationFn: (body: ProjectLabelCreate) =>
      resolveResponse(api.POST('/api/project-labels/', { body })),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['project_labels'] })
    },
  })

// ══════════════════════════════════════════════
//  Work-item comments
// ══════════════════════════════════════════════

export type WorkItemComment = schemas['WorkItemComment']
export type WorkItemCommentCreate = schemas['WorkItemCommentCreate']

const commentKey = (...parts: (string | object)[]) => [
  'work_item_comments',
  ...parts,
]

export const useWorkItemComments = (
  params: operations['work-item-comments:list']['parameters']['query'],
  enabled: boolean = true,
) =>
  useQuery({
    queryKey: commentKey('list', params ?? {}),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/work-item-comments/', { params: { query: params } }),
      ),
    retry: baseRetry,
    enabled,
  })

export const useCreateWorkItemComment = () =>
  useMutation({
    mutationFn: (body: WorkItemCommentCreate) =>
      resolveResponse(api.POST('/api/work-item-comments/', { body })),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['work_item_comments'] })
    },
  })

export const useDeleteWorkItemComment = (id: string) =>
  useMutation({
    mutationFn: () =>
      api.DELETE('/api/work-item-comments/{id}', {
        params: { path: { id } },
      }),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['work_item_comments'] })
    },
  })

// ══════════════════════════════════════════════
//  Work-item relations
// ══════════════════════════════════════════════

export type WorkItemRelation = schemas['WorkItemRelation']
export type WorkItemRelationCreate = schemas['WorkItemRelationCreate']
export type WorkItemRelationType = schemas['WorkItemRelationType']

const relationKey = (...parts: (string | object)[]) => [
  'work_item_relations',
  ...parts,
]

export const useWorkItemRelations = (
  params: operations['work-item-relations:list']['parameters']['query'],
  enabled: boolean = true,
) =>
  useQuery({
    queryKey: relationKey('list', params ?? {}),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/work-item-relations/', { params: { query: params } }),
      ),
    retry: baseRetry,
    enabled,
  })

export const useCreateWorkItemRelation = () =>
  useMutation({
    mutationFn: (body: WorkItemRelationCreate) =>
      resolveResponse(api.POST('/api/work-item-relations/', { body })),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['work_item_relations'] })
    },
  })

export const useDeleteWorkItemRelation = (id: string) =>
  useMutation({
    mutationFn: () =>
      api.DELETE('/api/work-item-relations/{id}', {
        params: { path: { id } },
      }),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['work_item_relations'] })
    },
  })

// ══════════════════════════════════════════════
//  Project cycles
// ══════════════════════════════════════════════

export type ProjectCycle = schemas['ProjectCycle']
export type ProjectCycleCreate = schemas['ProjectCycleCreate']
export type ProjectCycleUpdate = schemas['ProjectCycleUpdate']

const cycleKey = (...parts: (string | object)[]) => ['project_cycles', ...parts]

export const useProjectCycles = (
  params: operations['project-cycles:list']['parameters']['query'],
  enabled: boolean = true,
) =>
  useQuery({
    queryKey: cycleKey('list', params ?? {}),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/project-cycles/', { params: { query: params } }),
      ),
    retry: baseRetry,
    enabled,
  })

export const useProjectCycle = (id: string | undefined) =>
  useQuery({
    queryKey: cycleKey('detail', id ?? ''),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/project-cycles/{id}', {
          params: { path: { id: id! } },
        }),
      ),
    retry: baseRetry,
    enabled: !!id,
  })

export const useCycleWorkItemIds = (cycleId: string | undefined) =>
  useQuery({
    queryKey: cycleKey('work_item_ids', cycleId ?? ''),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/project-cycles/{id}/work-items', {
          params: { path: { id: cycleId! } },
        }),
      ),
    retry: baseRetry,
    enabled: !!cycleId,
  })

export const useCreateProjectCycle = () =>
  useMutation({
    mutationFn: (body: ProjectCycleCreate) =>
      resolveResponse(api.POST('/api/project-cycles/', { body })),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['project_cycles'] })
    },
  })

export const useUpdateProjectCycle = (id: string) =>
  useMutation({
    mutationFn: (body: ProjectCycleUpdate) =>
      resolveResponse(
        api.PATCH('/api/project-cycles/{id}', {
          params: { path: { id } },
          body,
        }),
      ),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['project_cycles'] })
    },
  })

export const useArchiveProjectCycle = (id: string) =>
  useMutation({
    mutationFn: () =>
      resolveResponse(
        api.POST('/api/project-cycles/{id}/archive', {
          params: { path: { id } },
        }),
      ),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['project_cycles'] })
    },
  })

export const useAddCycleWorkItems = (cycleId: string) =>
  useMutation({
    mutationFn: (workItemIds: string[]) =>
      api.POST('/api/project-cycles/{id}/work-items', {
        params: { path: { id: cycleId } },
        body: { work_item_ids: workItemIds },
      }),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['project_cycles'] })
    },
  })

export const useRemoveCycleWorkItems = (cycleId: string) =>
  useMutation({
    mutationFn: (workItemIds: string[]) =>
      api.DELETE('/api/project-cycles/{id}/work-items', {
        params: { path: { id: cycleId } },
        body: { work_item_ids: workItemIds },
      }),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['project_cycles'] })
    },
  })

// ══════════════════════════════════════════════
//  Project modules
// ══════════════════════════════════════════════

export type ProjectModule = schemas['ProjectModule']
export type ProjectModuleCreate = schemas['ProjectModuleCreate']
export type ProjectModuleUpdate = schemas['ProjectModuleUpdate']
export type ModuleStatus = schemas['ModuleStatus']

const moduleKey = (...parts: (string | object)[]) => [
  'project_modules',
  ...parts,
]

export const useProjectModules = (
  params: operations['project-modules:list']['parameters']['query'],
  enabled: boolean = true,
) =>
  useQuery({
    queryKey: moduleKey('list', params ?? {}),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/project-modules/', { params: { query: params } }),
      ),
    retry: baseRetry,
    enabled,
  })

export const useProjectModule = (id: string | undefined) =>
  useQuery({
    queryKey: moduleKey('detail', id ?? ''),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/project-modules/{id}', {
          params: { path: { id: id! } },
        }),
      ),
    retry: baseRetry,
    enabled: !!id,
  })

export const useCreateProjectModule = () =>
  useMutation({
    mutationFn: (body: ProjectModuleCreate) =>
      resolveResponse(api.POST('/api/project-modules/', { body })),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['project_modules'] })
    },
  })

export const useUpdateProjectModule = (id: string) =>
  useMutation({
    mutationFn: (body: ProjectModuleUpdate) =>
      resolveResponse(
        api.PATCH('/api/project-modules/{id}', {
          params: { path: { id } },
          body,
        }),
      ),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['project_modules'] })
    },
  })

export const useArchiveProjectModule = (id: string) =>
  useMutation({
    mutationFn: () =>
      resolveResponse(
        api.POST('/api/project-modules/{id}/archive', {
          params: { path: { id } },
        }),
      ),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['project_modules'] })
    },
  })

export const useModuleWorkItemIds = (moduleId: string | undefined) =>
  useQuery({
    queryKey: moduleKey('work_item_ids', moduleId ?? ''),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/project-modules/{id}/work-items', {
          params: { path: { id: moduleId! } },
        }),
      ),
    retry: baseRetry,
    enabled: !!moduleId,
  })

export const useAddModuleWorkItems = (moduleId: string) =>
  useMutation({
    mutationFn: (workItemIds: string[]) =>
      api.POST('/api/project-modules/{id}/work-items', {
        params: { path: { id: moduleId } },
        body: { work_item_ids: workItemIds },
      }),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['project_modules'] })
    },
  })

export const useRemoveModuleWorkItems = (moduleId: string) =>
  useMutation({
    mutationFn: (workItemIds: string[]) =>
      api.DELETE('/api/project-modules/{id}/work-items', {
        params: { path: { id: moduleId } },
        body: { work_item_ids: workItemIds },
      }),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['project_modules'] })
    },
  })

// ══════════════════════════════════════════════
//  Work-item activity (read-only)
// ══════════════════════════════════════════════

export type WorkItemActivity = schemas['WorkItemActivity']
export type WorkItemActivityVerb = schemas['WorkItemActivityVerb']

const activityKey = (...parts: (string | object)[]) => [
  'work_item_activities',
  ...parts,
]

export const useWorkItemActivities = (
  params: operations['work-item-activities:list']['parameters']['query'],
  enabled: boolean = true,
) =>
  useQuery({
    queryKey: activityKey('list', params ?? {}),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/work-item-activities/', {
          params: { query: params },
        }),
      ),
    retry: baseRetry,
    enabled,
  })

// ══════════════════════════════════════════════
//  Project pages
// ══════════════════════════════════════════════

export type ProjectPage = schemas['ProjectPage']
export type ProjectPageCreate = schemas['ProjectPageCreate']
export type ProjectPageUpdate = schemas['ProjectPageUpdate']
export type ProjectPageAccess = schemas['ProjectPageAccess']

const pageKey = (...parts: (string | object)[]) => ['project_pages', ...parts]

export const useProjectPages = (
  params: operations['project-pages:list']['parameters']['query'],
  enabled: boolean = true,
) =>
  useQuery({
    queryKey: pageKey('list', params ?? {}),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/project-pages/', { params: { query: params } }),
      ),
    retry: baseRetry,
    enabled,
  })

export const useProjectPage = (id: string | undefined) =>
  useQuery({
    queryKey: pageKey('detail', id ?? ''),
    queryFn: () =>
      resolveResponse(
        api.GET('/api/project-pages/{id}', {
          params: { path: { id: id! } },
        }),
      ),
    retry: baseRetry,
    enabled: !!id,
  })

export const useCreateProjectPage = () =>
  useMutation({
    mutationFn: (body: ProjectPageCreate) =>
      resolveResponse(api.POST('/api/project-pages/', { body })),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['project_pages'] })
    },
  })

export const useUpdateProjectPage = (id: string) =>
  useMutation({
    mutationFn: (body: ProjectPageUpdate) =>
      resolveResponse(
        api.PATCH('/api/project-pages/{id}', {
          params: { path: { id } },
          body,
        }),
      ),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['project_pages'] })
    },
  })

export const useDeleteProjectPage = (id: string) =>
  useMutation({
    mutationFn: () =>
      api.DELETE('/api/project-pages/{id}', { params: { path: { id } } }),
    onSuccess: () => {
      getQueryClient().invalidateQueries({ queryKey: ['project_pages'] })
    },
  })
