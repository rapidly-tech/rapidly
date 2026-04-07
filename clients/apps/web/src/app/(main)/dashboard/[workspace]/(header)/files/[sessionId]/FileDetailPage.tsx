'use client'

import { DashboardBody } from '@/components/Layout/DashboardLayout'
import { useFileShareSession } from '@/hooks/api/fileShareSessions'
import { formatFileSize } from '@/utils/file-sharing/constants'
import { Icon } from '@iconify/react'
import type { components } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { ResponsivePanel } from '@rapidly-tech/ui/components/layout/ElevatedCard'
import { useCallback, useState } from 'react'

// ── Helpers ──

const statusBadgeClass = (status: string): string => {
  switch (status) {
    case 'active':
    case 'completed':
      return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400'
    case 'created':
      return 'bg-slate-200 text-slate-700 dark:bg-slate-900 dark:text-slate-400'
    case 'expired':
      return 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400'
    case 'destroyed':
    case 'reported':
      return 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400'
    default:
      return 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400'
  }
}

// ── Types ──

interface FileDetailPageProps {
  sessionId: string
}

// ── Main Component ──

export default function FileDetailPage({ sessionId }: FileDetailPageProps) {
  const { data, isLoading, error } = useFileShareSession(sessionId)
  const session = data as
    | components['schemas']['FileShareSessionDetailSchema']
    | undefined
  const [copied, setCopied] = useState(false)

  const copyShareLink = useCallback(() => {
    if (!session) return
    const url = `${window.location.origin}/download/${session.short_slug}`
    navigator.clipboard.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [session])

  if (isLoading) {
    return (
      <DashboardBody>
        <div className="flex items-center justify-center py-16">
          <span className="text-sm text-slate-500 dark:text-slate-400">
            Loading file details...
          </span>
        </div>
      </DashboardBody>
    )
  }

  if (error || !session) {
    return (
      <DashboardBody>
        <div className="rounded-xl bg-red-50 p-4 text-red-600 dark:bg-red-900/20 dark:text-red-400">
          File not found or you don&apos;t have access.
        </div>
      </DashboardBody>
    )
  }

  const displayName = session.title || session.file_name || session.short_slug
  const payments = session.payments ?? []
  const downloads = session.downloads ?? []
  const reports = session.reports ?? []

  return (
    <DashboardBody>
      <div className="flex flex-col gap-y-8">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex flex-col gap-y-2">
            <div className="flex items-center gap-3">
              <h1 className="rp-text-primary text-2xl font-medium">
                {displayName}
              </h1>
              <span
                className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${statusBadgeClass(session.status)}`}
              >
                {session.status}
              </span>
            </div>
            {session.file_name && session.title && (
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {session.file_name}
                {session.file_size_bytes != null && (
                  <> &middot; {formatBytes(session.file_size_bytes)}</>
                )}
              </p>
            )}
          </div>
        </div>

        {/* Share link */}
        <ResponsivePanel className="flex items-center justify-between gap-4 p-4">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-slate-500 dark:text-slate-400">
              Share Link
            </span>
            <code className="text-sm dark:text-slate-200">
              {typeof window !== 'undefined'
                ? `${window.location.origin}/download/${session.short_slug}`
                : `/download/${session.short_slug}`}
            </code>
          </div>
          <Button variant="secondary" size="sm" onClick={copyShareLink}>
            <Icon icon="solar:copy-linear" className="mr-1 h-4 w-4" />
            {copied ? 'Copied!' : 'Copy'}
          </Button>
        </ResponsivePanel>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatBox label="Downloads">
            {session.download_count}
            {session.max_downloads > 0 && ` / ${session.max_downloads}`}
          </StatBox>
          <StatBox label="Price">
            {session.price_cents != null && session.price_cents > 0
              ? `$${(session.price_cents / 100).toFixed(2)} ${session.currency.toUpperCase()}`
              : 'Free'}
          </StatBox>
          <StatBox label="Created">
            {new Date(session.created_at).toLocaleDateString()}
          </StatBox>
          <StatBox label="Status">{session.status}</StatBox>
        </div>

        {/* Download progress */}
        {session.max_downloads > 0 && (
          <div className="flex flex-col gap-2">
            <div className="flex justify-between text-sm">
              <span className="text-slate-500 dark:text-slate-400">
                Download Progress
              </span>
              <span>
                {session.download_count} / {session.max_downloads}
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
              <div
                className="h-full rounded-full bg-slate-600 transition-all"
                style={{
                  width: `${Math.min(
                    (session.download_count / session.max_downloads) * 100,
                    100,
                  )}%`,
                }}
              />
            </div>
          </div>
        )}

        {/* Payments */}
        {payments.length > 0 && (
          <div className="flex flex-col gap-4">
            <h2 className="rp-text-primary text-lg font-medium">Payments</h2>
            <div className="glass-elevated overflow-hidden rounded-2xl bg-slate-50 shadow-xs lg:rounded-3xl dark:bg-slate-900">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-900">
                    <th className="px-4 py-3 text-left text-xs font-medium tracking-wider uppercase dark:text-slate-400">
                      Buyer
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium tracking-wider uppercase dark:text-slate-400">
                      Amount
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium tracking-wider uppercase dark:text-slate-400">
                      Status
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium tracking-wider uppercase dark:text-slate-400">
                      Date
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {payments.map((payment) => (
                    <tr
                      key={payment.id}
                      className="border-b border-slate-200 last:border-0 dark:border-slate-800"
                    >
                      <td className="rp-text-primary px-4 py-3 text-sm">
                        {payment.buyer_email || 'Unknown'}
                      </td>
                      <td className="rp-text-primary px-4 py-3 text-sm">
                        ${(payment.amount_cents / 100).toFixed(2)}{' '}
                        {payment.currency.toUpperCase()}
                      </td>
                      <td className="rp-text-primary px-4 py-3 text-sm">
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                            payment.status === 'completed'
                              ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400'
                              : 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400'
                          }`}
                        >
                          {payment.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-500 dark:text-slate-400">
                        {new Date(payment.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Downloads */}
        {downloads.length > 0 && (
          <div className="flex flex-col gap-4">
            <h2 className="rp-text-primary text-lg font-medium">
              Download History
            </h2>
            <div className="glass-elevated overflow-hidden rounded-2xl bg-slate-50 shadow-xs lg:rounded-3xl dark:bg-slate-900">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-900">
                    <th className="px-4 py-3 text-left text-xs font-medium tracking-wider uppercase dark:text-slate-400">
                      #
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium tracking-wider uppercase dark:text-slate-400">
                      Date
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {downloads.map((download) => (
                    <tr
                      key={download.id}
                      className="border-b border-slate-200 last:border-0 dark:border-slate-800"
                    >
                      <td className="rp-text-primary px-4 py-3 text-sm">
                        {download.slot_number}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-500 dark:text-slate-400">
                        {new Date(download.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Reports */}
        {reports.length > 0 && (
          <div className="flex flex-col gap-4">
            <h2 className="rp-text-primary text-lg font-medium">Reports</h2>
            <div className="flex flex-col gap-2">
              {reports.map((report) => (
                <div
                  key={report.id}
                  className="glass-elevated rounded-2xl bg-slate-50 p-4 shadow-xs lg:rounded-3xl dark:bg-slate-900"
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusBadgeClass(report.status)}`}
                    >
                      {report.status}
                    </span>
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                      {new Date(report.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  {report.reason && (
                    <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
                      {report.reason}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Timestamps */}
        <div className="flex flex-col gap-4">
          <h2 className="rp-text-primary text-lg font-medium">Timeline</h2>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <TimestampBox label="Created" value={session.created_at} />
            <TimestampBox label="Activated" value={session.activated_at} />
            <TimestampBox label="Completed" value={session.completed_at} />
            <TimestampBox label="Expires" value={session.expires_at} />
          </div>
        </div>
      </div>
    </DashboardBody>
  )
}

// ── Sub-components ──

function StatBox({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="glass-elevated rounded-2xl bg-slate-50 p-4 shadow-xs lg:rounded-3xl dark:bg-slate-900">
      <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
      <p className="rp-text-primary mt-1 text-lg font-medium">{children}</p>
    </div>
  )
}

function TimestampBox({
  label,
  value,
}: {
  label: string
  value: string | null | undefined
}) {
  return (
    <div className="glass-elevated rounded-2xl bg-slate-50 p-4 shadow-xs lg:rounded-3xl dark:bg-slate-900">
      <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
      <p className="mt-1 text-sm dark:text-slate-200">
        {value ? new Date(value).toLocaleString() : '\u2014'}
      </p>
    </div>
  )
}

// ── Utilities ──

const formatBytes = formatFileSize
