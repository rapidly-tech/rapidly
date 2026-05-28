/**
 * Datetime helpers shared by the Agents chamber pages.
 *
 * Each page used to carry verbatim copies of these four
 * functions; they were drifting into "fix in one place, miss the
 * other three" territory. Extracted into this module so a single
 * locale/formatting tweak doesn't fan out to five files.
 *
 * No date-fns / dayjs — these helpers are small enough that the
 * dependency cost wasn't worth paying.
 */

/**
 * Coarse relative time — ``"5m ago"`` / ``"3h ago"`` / ``"2d ago"``.
 *
 * Used on the runs list rows where exact timestamps would be
 * visual noise; the run/eval-run detail pages render the full
 * timestamp via ``formatTime`` instead. Returns the input
 * verbatim if parsing fails so we surface the bad value
 * instead of "NaN ago".
 */
export function formatRelative(iso: string): string {
  const now = Date.now()
  const then = Date.parse(iso)
  if (Number.isNaN(then)) return iso
  const seconds = Math.max(0, Math.floor((now - then) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

/**
 * Duration string for a (started_at, completed_at) pair.
 *
 * - both null → ``"—"``
 * - started, not completed → ``"running"``
 * - both set, valid → ``"1500ms"`` / ``"5s"`` / ``"2m 30s"``
 * - unparsable → ``"—"``
 *
 * Sub-second runs surface ms so the listing can show meaningful
 * detail on fast workflows; everything ≥ 1s rounds to seconds.
 */
export function formatDuration(
  startedIso: string | null,
  completedIso: string | null,
): string {
  if (!startedIso) return '—'
  if (!completedIso) return 'running'
  const start = Date.parse(startedIso)
  const end = Date.parse(completedIso)
  if (Number.isNaN(start) || Number.isNaN(end)) return '—'
  const ms = end - start
  if (ms < 1000) return `${ms}ms`
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  return `${minutes}m ${seconds % 60}s`
}

/**
 * Wall-clock time formatted for the locale —
 * ``"3:24:05 PM"`` / ``"15:24:05"``.
 *
 * Used on the eval-run + run detail "Started"/"Completed" stats
 * where the operator wants the exact second, not the relative
 * delta. Wrapped in try/catch because Intl can throw on certain
 * invalid date inputs in older runtimes.
 */
export function formatTime(iso: string): string {
  const ms = Date.parse(iso)
  if (Number.isNaN(ms)) return iso
  try {
    return new Date(ms).toLocaleTimeString(undefined, {
      hour: 'numeric',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return iso
  }
}

/**
 * Full locale-formatted timestamp — date + time. Used on the
 * workflow detail's Version history rows where operators want
 * the absolute moment a version was published (so they can
 * correlate with deploys, incidents, etc).
 */
export function formatTimestamp(iso: string): string {
  const ms = Date.parse(iso)
  if (Number.isNaN(ms)) return iso
  return new Date(ms).toLocaleString()
}
