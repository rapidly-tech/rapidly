'use client'

import {
  type UsageRollupRow,
  useCredentials,
  useUsageRollup,
} from '@/hooks/api/agents'
import { useMemo, useState } from 'react'

const WINDOWS: { label: string; hours: number }[] = [
  { label: 'Last 24h', hours: 24 },
  { label: 'Last 7 days', hours: 24 * 7 },
  { label: 'Last 30 days', hours: 24 * 30 },
]

export default function UsagePage() {
  const [windowHours, setWindowHours] = useState(24)

  // Compute window_start client-side so the operator's
  // selected window stays stable across refetches; the
  // backend's default-window logic would pick a slightly
  // different start each time.
  const windowStart = useMemo(
    () => new Date(Date.now() - windowHours * 3600_000).toISOString(),
    [windowHours],
  )

  const rollupQuery = useUsageRollup({ window_start: windowStart })
  const credsQuery = useCredentials({ limit: 100, page: 1 })

  // Build a credential_id → name map so the per-row credential
  // column reads as "production" not a 36-char UUID.
  const credentialNames = useMemo(() => {
    const map = new Map<string, string>()
    for (const c of credsQuery.data?.data ?? []) {
      map.set(c.id, c.name)
    }
    return map
  }, [credsQuery.data])

  const rows = rollupQuery.data?.rows ?? []
  const total = rows.reduce(
    (acc, r) => {
      acc.input += r.input_tokens
      acc.output += r.output_tokens
      acc.calls += r.call_count
      return acc
    },
    { input: 0, output: 0, calls: 0 },
  )

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-16">
      <Header />

      <WindowSwitcher value={windowHours} onChange={setWindowHours} />

      {rollupQuery.isLoading ? (
        <Skeleton />
      ) : rollupQuery.isError ? (
        <ErrorBanner message={(rollupQuery.error as Error).message} />
      ) : rows.length === 0 ? (
        <Empty />
      ) : (
        <>
          <SummaryRow total={total} />
          <RollupTable rows={rows} credentialNames={credentialNames} />
        </>
      )}
    </main>
  )
}

function Header() {
  return (
    <header className="flex flex-col gap-3">
      <span className="text-xs font-medium tracking-wider text-emerald-600 uppercase dark:text-emerald-400">
        Rapidly · Agents
      </span>
      <h1 className="text-4xl font-semibold text-slate-900 dark:text-slate-100">
        LLM usage
      </h1>
      <p className="max-w-2xl text-base leading-relaxed text-slate-600 dark:text-slate-400">
        Tokens spent across all workflows + evals, grouped by credential,
        provider, and model. Same rollup the credential budgets endpoint powers
        — surfaced here without per-credential drilling.
      </p>
    </header>
  )
}

function WindowSwitcher({
  value,
  onChange,
}: {
  value: number
  onChange: (hours: number) => void
}) {
  return (
    <div className="flex gap-1">
      {WINDOWS.map((w) => (
        <button
          key={w.hours}
          type="button"
          onClick={() => onChange(w.hours)}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
            value === w.hours
              ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
              : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
          }`}
        >
          {w.label}
        </button>
      ))}
    </div>
  )
}

function SummaryRow({
  total,
}: {
  total: { input: number; output: number; calls: number }
}) {
  return (
    <dl className="grid grid-cols-3 gap-4">
      <Stat label="Calls" value={total.calls.toLocaleString()} />
      <Stat label="Input tokens" value={total.input.toLocaleString()} />
      <Stat label="Output tokens" value={total.output.toLocaleString()} />
    </dl>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <dt className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
        {label}
      </dt>
      <dd className="text-2xl font-semibold text-slate-700 dark:text-slate-200">
        {value}
      </dd>
    </div>
  )
}

function RollupTable({
  rows,
  credentialNames,
}: {
  rows: UsageRollupRow[]
  credentialNames: Map<string, string>
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
      <table className="w-full text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-xs tracking-wide text-slate-500 uppercase dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
          <tr>
            <th className="px-4 py-3 text-left font-medium">Provider</th>
            <th className="px-4 py-3 text-left font-medium">Model</th>
            <th className="px-4 py-3 text-left font-medium">Credential</th>
            <th className="px-4 py-3 text-right font-medium">Input</th>
            <th className="px-4 py-3 text-right font-medium">Output</th>
            <th className="px-4 py-3 text-right font-medium">Calls</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={i}
              className="border-b border-slate-100 last:border-0 dark:border-slate-800/50"
            >
              <td className="px-4 py-3 text-slate-700 dark:text-slate-300">
                {r.provider}
              </td>
              <td className="px-4 py-3 font-mono text-xs text-slate-700 dark:text-slate-300">
                {r.model}
              </td>
              <td className="px-4 py-3 text-slate-600 dark:text-slate-400">
                {r.credential_id ? (
                  (credentialNames.get(r.credential_id) ??
                  `${r.credential_id.slice(0, 8)}…`)
                ) : (
                  <span className="text-slate-400 italic dark:text-slate-500">
                    env / explicit
                  </span>
                )}
              </td>
              <td className="px-4 py-3 text-right font-mono text-slate-700 dark:text-slate-300">
                {r.input_tokens.toLocaleString()}
              </td>
              <td className="px-4 py-3 text-right font-mono text-slate-700 dark:text-slate-300">
                {r.output_tokens.toLocaleString()}
              </td>
              <td className="px-4 py-3 text-right font-mono text-slate-700 dark:text-slate-300">
                {r.call_count}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Skeleton() {
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-3 gap-4">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-20 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800"
          />
        ))}
      </div>
      <div className="h-64 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
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
        No usage in this window.
      </p>
      <p className="max-w-md text-xs text-slate-400 dark:text-slate-500">
        Trigger a workflow run or an eval to see tokens recorded here.
      </p>
    </div>
  )
}
