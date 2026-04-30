'use client'

// Side-by-side comparison diagram: ""other services"" (file lives on
// their server) vs Rapidly (peer-to-peer, server only signals).
// Pure SVG — no React Flow / canvas — because the diagrams are
// static layouts with one animated dot each. ~50 KB cheaper than
// pulling in @xyflow/react for two displays that never need pan,
// zoom, drag, or interactive editing.
//
// Visual language:
// - Left panel uses warning/red accents on the server (it sees your
//   file) and a dot that pauses at the server during transit.
// - Right panel uses emerald accents on the direct edge and grays
//   the server out (signaling only).
// - Both panels share the same icon vocabulary (device + cloud) so
//   the comparison is apples-to-apples.

interface DiagramPanelProps {
  title: string
  caption: string
  variant: 'server' | 'p2p'
}

function DiagramPanel({ title, caption, variant }: DiagramPanelProps) {
  const isServer = variant === 'server'

  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-(--beige-border)/50 bg-white p-6 shadow-[0_2px_16px_rgba(120,100,80,0.06)] md:p-8 dark:border-white/10 dark:bg-white/5 dark:backdrop-blur-xl">
      <div>
        <h3 className="rp-text-primary text-lg font-semibold tracking-tight">
          {title}
        </h3>
        <p className="rp-text-secondary mt-1 text-sm leading-relaxed">
          {caption}
        </p>
      </div>

      <svg
        viewBox="0 0 400 220"
        className="h-auto w-full"
        role="img"
        aria-label={
          isServer
            ? 'File flows from sender through a server that stores it, then to recipient'
            : 'File flows directly from sender to recipient; the server only helps them find each other'
        }
      >
        <defs>
          {/* Particle gradient — borrowed from Liam's
              RelationshipEdgeParticleMarker idea (radial fade so the
              dot reads as a glowing point, not a hard circle). */}
          <radialGradient id={`particle-${variant}`} cx="50%" cy="50%" r="50%">
            <stop
              offset="0%"
              stopColor={isServer ? '#ef4444' : '#10b981'}
              stopOpacity="1"
            />
            <stop
              offset="100%"
              stopColor={isServer ? '#ef4444' : '#10b981'}
              stopOpacity="0"
            />
          </radialGradient>
        </defs>

        {/* Edges — drawn first so nodes sit on top */}
        {isServer ? (
          <>
            {/* Sender → Server */}
            <path
              d="M 60 110 Q 130 50 200 80"
              className="stroke-slate-300 dark:stroke-slate-600"
              strokeWidth="1.5"
              strokeDasharray="4 4"
              fill="none"
            />
            {/* Server → Recipient */}
            <path
              d="M 200 80 Q 270 50 340 110"
              className="stroke-slate-300 dark:stroke-slate-600"
              strokeWidth="1.5"
              strokeDasharray="4 4"
              fill="none"
            />
          </>
        ) : (
          <>
            {/* Direct: Sender → Recipient (emerald, solid) */}
            <path
              d="M 60 110 Q 200 80 340 110"
              className="stroke-emerald-500/70 dark:stroke-emerald-400/70"
              strokeWidth="2"
              fill="none"
            />
            {/* Faint dotted lines to the (grayed-out) signaling server */}
            <path
              d="M 60 110 L 200 70"
              className="stroke-slate-300/50 dark:stroke-slate-600/50"
              strokeWidth="1"
              strokeDasharray="2 4"
              fill="none"
            />
            <path
              d="M 200 70 L 340 110"
              className="stroke-slate-300/50 dark:stroke-slate-600/50"
              strokeWidth="1"
              strokeDasharray="2 4"
              fill="none"
            />
          </>
        )}

        {/* Sender — phone icon */}
        <g transform="translate(40 90)">
          <rect
            x="0"
            y="0"
            width="40"
            height="50"
            rx="6"
            className="fill-white stroke-slate-400 dark:fill-slate-800 dark:stroke-slate-500"
            strokeWidth="1.5"
          />
          <line
            x1="0"
            y1="42"
            x2="40"
            y2="42"
            className="stroke-slate-300 dark:stroke-slate-600"
            strokeWidth="1"
          />
          <circle
            cx="20"
            cy="46"
            r="1.5"
            className="fill-slate-400 dark:fill-slate-500"
          />
        </g>
        <text
          x="60"
          y="160"
          textAnchor="middle"
          className="fill-slate-600 text-[11px] font-medium dark:fill-slate-400"
        >
          You
        </text>

        {/* Server — cloud icon at top centre */}
        <g
          transform={isServer ? 'translate(180 50)' : 'translate(180 40)'}
          className={isServer ? '' : 'opacity-50'}
        >
          {/* Stylised cloud */}
          <path
            d="M 8 20 a 7 7 0 0 1 7 -7 a 9 9 0 0 1 16 0 a 6 6 0 0 1 6 6 a 5 5 0 0 1 -3 9 H 11 a 5 5 0 0 1 -3 -8 z"
            className={
              isServer
                ? 'fill-red-50 stroke-red-400 dark:fill-red-950/40 dark:stroke-red-700'
                : 'fill-slate-100 stroke-slate-400 dark:fill-slate-800/40 dark:stroke-slate-600'
            }
            strokeWidth="1.5"
          />
          {/* File icon inside / next to the cloud — only shown on the server-stored panel */}
          {isServer && (
            <g transform="translate(28 4)">
              <rect
                x="0"
                y="0"
                width="14"
                height="18"
                rx="2"
                className="fill-red-500 stroke-red-600"
                strokeWidth="1"
              />
              <line
                x1="3"
                y1="6"
                x2="11"
                y2="6"
                className="stroke-white/80"
                strokeWidth="1"
              />
              <line
                x1="3"
                y1="9"
                x2="11"
                y2="9"
                className="stroke-white/80"
                strokeWidth="1"
              />
              <line
                x1="3"
                y1="12"
                x2="9"
                y2="12"
                className="stroke-white/80"
                strokeWidth="1"
              />
            </g>
          )}
        </g>
        <text
          x="200"
          y={isServer ? 30 : 22}
          textAnchor="middle"
          className={
            isServer
              ? 'fill-red-600 text-[11px] font-semibold dark:fill-red-400'
              : 'fill-slate-500 text-[10px] dark:fill-slate-500'
          }
        >
          {isServer ? 'their server (sees your file)' : 'signaling only'}
        </text>

        {/* Recipient — phone icon */}
        <g transform="translate(320 90)">
          <rect
            x="0"
            y="0"
            width="40"
            height="50"
            rx="6"
            className="fill-white stroke-slate-400 dark:fill-slate-800 dark:stroke-slate-500"
            strokeWidth="1.5"
          />
          <line
            x1="0"
            y1="42"
            x2="40"
            y2="42"
            className="stroke-slate-300 dark:stroke-slate-600"
            strokeWidth="1"
          />
          <circle
            cx="20"
            cy="46"
            r="1.5"
            className="fill-slate-400 dark:fill-slate-500"
          />
        </g>
        <text
          x="340"
          y="160"
          textAnchor="middle"
          className="fill-slate-600 text-[11px] font-medium dark:fill-slate-400"
        >
          Recipient
        </text>

        {/* Animated particle on the edge — different path per
            variant. Stops when the user has prefers-reduced-motion. */}
        <circle
          r="6"
          fill={`url(#particle-${variant})`}
          className={isServer ? 'flow-particle-server' : 'flow-particle-direct'}
        />
      </svg>

      {/* Bottom badge — privacy claim */}
      <div className="flex items-center gap-2">
        <span
          className={
            isServer
              ? 'inline-flex items-center gap-1.5 rounded-full bg-red-50 px-3 py-1 text-xs font-medium text-red-700 dark:bg-red-950/30 dark:text-red-400'
              : 'inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400'
          }
        >
          <span
            className={
              isServer
                ? 'h-1.5 w-1.5 rounded-full bg-red-500'
                : 'h-1.5 w-1.5 rounded-full bg-emerald-500'
            }
          />
          {isServer
            ? 'Server can read your file'
            : 'Server never sees your file'}
        </span>
      </div>
    </div>
  )
}

export function HowItDiffers() {
  return (
    <section
      aria-label="How Rapidly differs"
      className="relative z-10 mx-auto w-full max-w-6xl px-4 py-20 md:py-28"
    >
      <div className="mb-12 text-center md:mb-16">
        <h2 className="rp-text-primary text-3xl font-semibold tracking-tight md:text-4xl">
          The same arrow, but the file goes through us. Or doesn&apos;t.
        </h2>
        <p className="rp-text-secondary mx-auto mt-3 max-w-2xl text-sm md:text-base">
          Most file-sharing services upload your file to their server, then hand
          the recipient a link to download it. Rapidly skips the middle.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 md:gap-6">
        <DiagramPanel
          title="Other services"
          caption="Sender uploads → server stores the file → recipient downloads. The server has the bytes."
          variant="server"
        />
        <DiagramPanel
          title="Rapidly"
          caption="Sender's browser streams directly to the recipient's. The server only helps them find each other."
          variant="p2p"
        />
      </div>
    </section>
  )
}
