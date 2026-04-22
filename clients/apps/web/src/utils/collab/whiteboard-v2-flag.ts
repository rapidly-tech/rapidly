/**
 * Feature flag for the Phase 3-27 whiteboard replacing the stopgap
 * ``CollabCanvas``.
 *
 * Controlled by the env var ``NEXT_PUBLIC_COLLAB_WHITEBOARD_V2``:
 *
 *   - ``'true'`` / ``'1'`` / ``'on'`` → v2 mounted for the ``canvas``
 *     kind. Host + guest both need the flag set; different doc roots
 *     (``Y.Map<elements>`` vs. ``Y.Array<strokes>``) mean mixed-
 *     version peers see empty canvases on the other side.
 *   - **anything else / absent** → stopgap ``CollabCanvas`` as today.
 *
 * Per-deploy rollout: staging flips first, production follows once
 * the feature lands in a release. No runtime UI toggle — a flag that
 * could flip mid-session would swap data shapes under live peers.
 */

/** Read the env var and map it to a boolean. Pure — tests pass the
 *  raw string in, production reads ``process.env``. */
export function isWhiteboardV2EnabledFromEnv(
  raw: string | undefined = process.env.NEXT_PUBLIC_COLLAB_WHITEBOARD_V2,
): boolean {
  if (typeof raw !== 'string') return false
  const normalised = raw.trim().toLowerCase()
  return normalised === 'true' || normalised === '1' || normalised === 'on'
}
