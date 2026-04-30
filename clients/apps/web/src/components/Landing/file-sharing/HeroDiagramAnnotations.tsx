'use client'

// Annotations layered on top of the existing two-circle Venn hero
// to make the shape READ AS a diagram of peer-to-peer file flow:
//
//   ☁ server (signaling only — never sees the file)
//
//      ╭─── you ───╮       ╭─── recipient ───╮
//      │           │  ⚡   │                 │
//      │  [drop]   │ ━━━>  │                 │
//      ╰───────────╯       ╰─────────────────╯
//
// The animated particle flowing through the eye = the encrypted
// payload moving directly between sender and recipient. The grayed
// server label above tells the privacy story without a separate
// section. Pure SVG + CSS, no extra dependency.

export function HeroDiagramAnnotations() {
  // Absolute-positioned overlay that breaks out of the constrained
  // ``max-w-2xl`` parent — the visible Venn circles are ~866 px wide
  // while the parent is ~672 px, so we need a wider overlay (and
  // z-index high enough to sit above the white circle backgrounds)
  // for the annotations to land on the visible Venn shape.
  return (
    <div
      className="pointer-events-none absolute top-1/2 left-1/2 z-30 hidden h-[600px] w-[900px] -translate-x-1/2 -translate-y-1/2 md:block"
      aria-hidden
    >
      {/* Left circle — ""You"" label */}
      <div className="absolute top-1/2 left-[8%] flex -translate-y-1/2 flex-col items-center gap-1">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white shadow-[0_2px_8px_rgba(120,100,80,0.10)] dark:bg-white/8 dark:backdrop-blur-xl">
          <svg
            viewBox="0 0 24 24"
            className="h-4 w-4 text-slate-600 dark:text-slate-300"
            aria-hidden
          >
            <rect
              x="6"
              y="2"
              width="12"
              height="20"
              rx="3"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            />
            <circle cx="12" cy="19" r="0.8" fill="currentColor" />
          </svg>
        </div>
        <span className="text-[10px] font-medium tracking-wide text-slate-500 dark:text-slate-400">
          you
        </span>
      </div>

      {/* Right circle — ""Recipient"" label */}
      <div className="absolute top-1/2 right-[8%] flex -translate-y-1/2 flex-col items-center gap-1">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white shadow-[0_2px_8px_rgba(120,100,80,0.10)] dark:bg-white/8 dark:backdrop-blur-xl">
          <svg
            viewBox="0 0 24 24"
            className="h-4 w-4 text-slate-600 dark:text-slate-300"
            aria-hidden
          >
            <rect
              x="6"
              y="2"
              width="12"
              height="20"
              rx="3"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            />
            <circle cx="12" cy="19" r="0.8" fill="currentColor" />
          </svg>
        </div>
        <span className="text-[10px] font-medium tracking-wide text-slate-500 dark:text-slate-400">
          recipient
        </span>
      </div>

      {/* Server above the Venn — grayed out, ""never sees the file"" */}
      <div className="absolute top-[2%] left-1/2 flex -translate-x-1/2 flex-col items-center gap-1 opacity-70">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800/40">
          <svg
            viewBox="0 0 24 24"
            className="h-3.5 w-3.5 text-slate-400 dark:text-slate-500"
            aria-hidden
          >
            <path
              d="M 7 16 a 5 5 0 0 1 5 -5 a 6 6 0 0 1 11 0 a 4 4 0 0 1 4 4 a 4 4 0 0 1 -2 7 H 9 a 4 4 0 0 1 -2 -6 z"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              transform="scale(0.7) translate(2 0)"
            />
          </svg>
        </div>
        <span className="text-[9px] tracking-wide text-slate-400 dark:text-slate-500">
          server · never sees the file
        </span>
      </div>

      {/* Animated particle flowing left → right across the Venn.
          Spans the full overlay (900×600) so the path is visible
          across the visible circles. */}
      <svg
        viewBox="0 0 900 600"
        className="absolute inset-0 h-full w-full"
        aria-hidden
        preserveAspectRatio="none"
      >
        <defs>
          <radialGradient id="venn-particle" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#10b981" stopOpacity="1" />
            <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
          </radialGradient>
        </defs>
        <circle
          r="8"
          fill="url(#venn-particle)"
          className="hero-venn-particle"
        />
      </svg>
    </div>
  )
}
