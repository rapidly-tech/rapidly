'use client'

/**
 * Small horizontal strip showing who's in the room. The self-pill is
 * always rendered; remote peers come from the awareness map exposed by
 * ``useCollabRoom``. Colour is derived from ``clientID`` so a returning
 * peer keeps a stable hue across reconnects.
 */

interface PresenceStripProps {
  peers: ReadonlyArray<{ clientID: number; state: Record<string, unknown> }>
  selfLabel: string
}

function hueFor(clientID: number): number {
  // 137.5° is the golden-angle hue step — hashing by it spreads colours
  // maximally around the wheel for small peer counts.
  return (clientID * 137.508) % 360
}

export function PresenceStrip({ peers, selfLabel }: PresenceStripProps) {
  return (
    <div className="glass-elevated flex flex-wrap items-center gap-2 rounded-2xl bg-slate-50 p-3 text-sm shadow-xs dark:bg-slate-900">
      <span className="rp-text-muted text-xs">In this doc:</span>

      <span
        className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200"
        aria-label="You"
      >
        <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden />
        {selfLabel}
      </span>

      {peers.length === 0 && (
        <span className="rp-text-muted text-xs">
          No one else yet — share the invite link to bring someone in.
        </span>
      )}

      {peers.map(({ clientID, state }) => {
        const name =
          typeof state.name === 'string' && state.name.length > 0
            ? state.name
            : `Peer ${clientID.toString().slice(-4)}`
        const hue = hueFor(clientID)
        return (
          <span
            key={clientID}
            className="rp-text-primary inline-flex items-center gap-1.5 rounded-full bg-white px-2.5 py-1 text-xs font-medium dark:bg-white/5"
          >
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: `hsl(${hue} 70% 50%)` }}
              aria-hidden
            />
            {name}
          </span>
        )
      })}
    </div>
  )
}
