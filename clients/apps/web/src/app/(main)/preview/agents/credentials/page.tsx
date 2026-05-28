'use client'

import {
  type CredentialAlertRow,
  type CredentialBudgetRow,
  type CredentialCreatePayload,
  type IntegrationCredential,
  useCreateCredential,
  useCredentialAlerts,
  useCredentialBudgets,
  useCredentials,
  useDeleteCredential,
  useSetDefaultCredential,
} from '@/hooks/api/agents'
import { useListWorkspaces } from '@/hooks/api/org'
import { useMemo, useState } from 'react'

const PAGE_SIZE = 20

export default function CredentialsPage() {
  const workspacesQuery = useListWorkspaces({ limit: 50, page: 1 })
  const workspaces = workspacesQuery.data?.data ?? []
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const activeWorkspaceId = workspaceId ?? workspaces[0]?.id ?? null

  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const onSearchChange = (next: string) => {
    setSearch(next)
    setPage(1)
  }
  // Workspace flip should also reset page state — landing on
  // page 4 of a workspace that has 2 pages would be confusing.
  const onWorkspaceChange = (next: string | null) => {
    setWorkspaceId(next)
    setPage(1)
  }

  const credsQuery = useCredentials(
    {
      name: search.trim() || undefined,
      limit: PAGE_SIZE,
      page,
    },
    !!activeWorkspaceId,
  )
  const budgetsQuery = useCredentialBudgets()
  const alertsQuery = useCredentialAlerts()

  // The list endpoint returns rows across all workspaces the
  // caller can read; filter to the active one. With the new
  // page state we can't trust meta.total either — it counts
  // pre-workspace-filter — so we expose the post-filter length
  // to the pagination control.
  const credentials: IntegrationCredential[] = useMemo(
    () =>
      (credsQuery.data?.data ?? []).filter(
        (c) => c.workspace_id === activeWorkspaceId,
      ),
    [credsQuery.data, activeWorkspaceId],
  )
  const meta = credsQuery.data?.meta

  const budgetsById = useMemo(() => {
    const map = new Map<string, CredentialBudgetRow>()
    for (const row of budgetsQuery.data?.rows ?? []) {
      map.set(row.credential_id, row)
    }
    return map
  }, [budgetsQuery.data])

  const alertsById = useMemo(() => {
    const map = new Map<string, CredentialAlertRow>()
    for (const row of alertsQuery.data?.rows ?? []) {
      map.set(row.credential_id, row)
    }
    return map
  }, [alertsQuery.data])

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-16">
      <Header />

      <WorkspaceSwitcher
        workspaces={workspaces.map((w) => ({ id: w.id, name: w.name }))}
        activeId={activeWorkspaceId}
        onChange={onWorkspaceChange}
      />

      {activeWorkspaceId && <CreateForm workspaceId={activeWorkspaceId} />}

      <SearchInput value={search} onChange={onSearchChange} />

      {credsQuery.isLoading ? (
        <Skeleton />
      ) : credsQuery.isError ? (
        <ErrorBanner message={(credsQuery.error as Error).message} />
      ) : credentials.length === 0 ? (
        search.trim() ? (
          <EmptySearch query={search.trim()} />
        ) : (
          <Empty />
        )
      ) : (
        <>
          <CredentialList
            credentials={credentials}
            budgetsById={budgetsById}
            alertsById={alertsById}
          />
          {meta && (
            <Pagination
              page={page}
              pages={meta.pages}
              total={meta.total}
              onPageChange={setPage}
            />
          )}
        </>
      )}
    </main>
  )
}

function SearchInput({
  value,
  onChange,
}: {
  value: string
  onChange: (next: string) => void
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
        Search
      </label>
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Filter credentials by name…"
        className="w-full max-w-md rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
      />
    </div>
  )
}

function EmptySearch({ query }: { query: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
      No credentials match{' '}
      <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono dark:bg-slate-800">
        {query}
      </code>
      .
    </div>
  )
}

function Pagination({
  page,
  pages,
  total,
  onPageChange,
}: {
  page: number
  pages: number
  total: number
  onPageChange: (next: number) => void
}) {
  if (pages <= 1) return null
  return (
    <div className="flex items-center justify-between gap-3 text-xs text-slate-500 dark:text-slate-400">
      <span>
        Page <span className="font-mono">{page}</span> of{' '}
        <span className="font-mono">{pages}</span> ·{' '}
        <span className="font-mono">{total}</span> total
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          ← Prev
        </button>
        <button
          type="button"
          onClick={() => onPageChange(Math.min(pages, page + 1))}
          disabled={page >= pages}
          className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          Next →
        </button>
      </div>
    </div>
  )
}

function Header() {
  return (
    <header className="flex flex-col gap-3">
      <span className="text-xs font-medium tracking-wider text-emerald-600 uppercase dark:text-emerald-400">
        Rapidly · Agents
      </span>
      <h1 className="text-4xl font-semibold text-slate-900 dark:text-slate-100">
        Credentials
      </h1>
      <p className="max-w-2xl text-base leading-relaxed text-slate-600 dark:text-slate-400">
        Per-workspace API keys for outbound LLM + embedding providers. Encrypted
        at rest. The default credential per provider is used by workflows that
        don&apos;t pin a specific one.
      </p>
    </header>
  )
}

function WorkspaceSwitcher({
  workspaces,
  activeId,
  onChange,
}: {
  workspaces: { id: string; name: string }[]
  activeId: string | null
  onChange: (id: string) => void
}) {
  if (workspaces.length <= 1) return null
  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
        Workspace
      </label>
      <select
        value={activeId ?? ''}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
      >
        {workspaces.map((w) => (
          <option key={w.id} value={w.id}>
            {w.name}
          </option>
        ))}
      </select>
    </div>
  )
}

function CreateForm({ workspaceId }: { workspaceId: string }) {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({
    provider: 'openai',
    name: '',
    secret: '',
    base_url: '',
    is_default: false,
    monthly_budget_tokens: '',
    budget_alert_threshold_percent: '',
  })
  const createMutation = useCreateCredential()

  const reset = () =>
    setForm({
      provider: 'openai',
      name: '',
      secret: '',
      base_url: '',
      is_default: false,
      monthly_budget_tokens: '',
      budget_alert_threshold_percent: '',
    })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const body: CredentialCreatePayload = {
      workspace_id: workspaceId,
      provider: form.provider.trim(),
      name: form.name.trim(),
      secret: form.secret,
      is_default: form.is_default,
    }
    if (form.base_url.trim()) body.base_url = form.base_url.trim()
    if (form.monthly_budget_tokens) {
      body.monthly_budget_tokens = parseInt(form.monthly_budget_tokens, 10)
    }
    if (form.budget_alert_threshold_percent) {
      body.budget_alert_threshold_percent = parseInt(
        form.budget_alert_threshold_percent,
        10,
      )
    }
    createMutation.mutate(body, {
      onSuccess: () => {
        reset()
        setOpen(false)
      },
    })
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="self-start rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
      >
        + Add credential
      </button>
    )
  }

  return (
    <form
      onSubmit={submit}
      className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
    >
      <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">
        New credential
      </h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Provider">
          <input
            type="text"
            required
            value={form.provider}
            onChange={(e) =>
              setForm((f) => ({ ...f, provider: e.target.value }))
            }
            className={inputClass}
            placeholder="openai"
          />
        </Field>
        <Field label="Name">
          <input
            type="text"
            required
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            className={inputClass}
            placeholder="production"
          />
        </Field>
      </div>
      <Field label="Secret (API key)">
        <input
          type="password"
          required
          value={form.secret}
          onChange={(e) => setForm((f) => ({ ...f, secret: e.target.value }))}
          className={`${inputClass} font-mono`}
          autoComplete="off"
        />
      </Field>
      <Field label="Base URL (optional)">
        <input
          type="url"
          value={form.base_url}
          onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))}
          className={inputClass}
          placeholder="https://your-ollama-host:11434/v1"
        />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Monthly budget (tokens)">
          <input
            type="number"
            min={1}
            value={form.monthly_budget_tokens}
            onChange={(e) =>
              setForm((f) => ({ ...f, monthly_budget_tokens: e.target.value }))
            }
            className={inputClass}
            placeholder="1000000"
          />
        </Field>
        <Field label="Alert at (% of budget)">
          <input
            type="number"
            min={1}
            max={100}
            value={form.budget_alert_threshold_percent}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                budget_alert_threshold_percent: e.target.value,
              }))
            }
            className={inputClass}
            placeholder="80"
          />
        </Field>
      </div>
      <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
        <input
          type="checkbox"
          checked={form.is_default}
          onChange={(e) =>
            setForm((f) => ({ ...f, is_default: e.target.checked }))
          }
        />
        Mark as default for this provider
      </label>
      {createMutation.isError && (
        <ErrorBanner message={(createMutation.error as Error).message} />
      )}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={createMutation.isPending}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          {createMutation.isPending ? 'Saving…' : 'Create'}
        </button>
        <button
          type="button"
          onClick={() => {
            reset()
            setOpen(false)
          }}
          className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

const inputClass =
  'w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200'

function Field({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
        {label}
      </label>
      {children}
    </div>
  )
}

function CredentialList({
  credentials,
  budgetsById,
  alertsById,
}: {
  credentials: IntegrationCredential[]
  budgetsById: Map<string, CredentialBudgetRow>
  alertsById: Map<string, CredentialAlertRow>
}) {
  return (
    <ul className="flex flex-col gap-3">
      {credentials.map((c) => (
        <CredentialRow
          key={c.id}
          credential={c}
          budget={budgetsById.get(c.id)}
          alert={alertsById.get(c.id)}
        />
      ))}
    </ul>
  )
}

function CredentialRow({
  credential,
  budget,
  alert,
}: {
  credential: IntegrationCredential
  budget?: CredentialBudgetRow
  alert?: CredentialAlertRow
}) {
  const setDefault = useSetDefaultCredential()
  const deleteCred = useDeleteCredential()

  const percent = budget?.percent_used ?? null
  const percentClamped = percent !== null ? Math.min(100, percent * 100) : null

  return (
    <li className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300">
            {credential.provider}
          </span>
          <span className="truncate font-medium text-slate-900 dark:text-slate-100">
            {credential.name}
          </span>
          {credential.is_default && (
            <span className="rounded-md bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
              default
            </span>
          )}
          {alert && (
            <span className="rounded-md bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
              alert · {Math.round(alert.percent_used * 100)}%
            </span>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          {!credential.is_default && (
            <button
              type="button"
              onClick={() => setDefault.mutate(credential.id)}
              disabled={setDefault.isPending}
              className="rounded-md border border-slate-200 px-3 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              Make default
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              if (confirm(`Delete credential "${credential.name}"?`)) {
                deleteCred.mutate(credential.id)
              }
            }}
            disabled={deleteCred.isPending}
            className="rounded-md border border-rose-200 px-3 py-1 text-xs text-rose-600 hover:bg-rose-50 disabled:opacity-50 dark:border-rose-900/50 dark:text-rose-400 dark:hover:bg-rose-900/20"
          >
            Delete
          </button>
        </div>
      </div>
      {credential.base_url && (
        <p className="mt-2 font-mono text-xs text-slate-500 dark:text-slate-400">
          {credential.base_url}
        </p>
      )}
      {budget && credential.monthly_budget_tokens !== null && (
        <BudgetBar
          mtd={budget.month_to_date_tokens}
          cap={credential.monthly_budget_tokens}
          percent={percentClamped}
          overBudget={percent !== null && percent > 1}
        />
      )}
    </li>
  )
}

function BudgetBar({
  mtd,
  cap,
  percent,
  overBudget,
}: {
  mtd: number
  cap: number
  percent: number | null
  overBudget: boolean
}) {
  return (
    <div className="mt-3 flex flex-col gap-1">
      <div className="flex justify-between text-xs text-slate-500 dark:text-slate-400">
        <span>
          {mtd.toLocaleString()} / {cap.toLocaleString()} tokens this month
        </span>
        <span>{percent !== null ? `${Math.round(percent)}%` : '—'}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div
          className={`h-full ${overBudget ? 'bg-rose-500' : 'bg-emerald-500'}`}
          style={{ width: `${percent ?? 0}%` }}
        />
      </div>
    </div>
  )
}

function Skeleton() {
  return (
    <div className="flex flex-col gap-3">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="h-24 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800"
        />
      ))}
    </div>
  )
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">
      {message}
    </div>
  )
}

function Empty() {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-12 text-center dark:border-slate-800 dark:bg-slate-900/50">
      <p className="text-sm text-slate-500 dark:text-slate-400">
        No credentials yet.
      </p>
      <p className="max-w-md text-xs text-slate-400 dark:text-slate-500">
        Add one above. The secret is encrypted at rest; the API never returns
        plaintext after creation.
      </p>
    </div>
  )
}
