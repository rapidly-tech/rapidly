'use client'

import { CHAMBERS } from '@/components/Revolver/chambers'
import Link from 'next/link'

// Inline Solar SVG paths — copy of the ChamberStrip ones, sharing
// rationale: the @iconify/react runtime fetch is unreliable in
// production (CSP blocks api.iconify.design) so chamber icons
// rendered as empty boxes. Hardcoding the 24×24 SVGs from
// @iconify-json/solar makes them ship on first paint.
const SVGS: Record<string, React.ReactNode> = {
  files: (
    <g fill="none">
      <path
        fill="currentColor"
        d="m15.393 4.054l-.502.557zm3.959 3.563l-.502.557zm2.302 2.537l-.685.305zM3.172 20.828l.53-.53zm17.656 0l-.53-.53zM14 21.25h-4v1.5h4zM2.75 14v-4h-1.5v4zm18.5-.437V14h1.5v-.437zM14.891 4.61l3.959 3.563l1.003-1.115l-3.958-3.563zm7.859 8.952c0-1.689.015-2.758-.41-3.714l-1.371.61c.266.598.281 1.283.281 3.104zm-3.9-5.389c1.353 1.218 1.853 1.688 2.119 2.285l1.37-.61c-.426-.957-1.23-1.66-2.486-2.79zM10.03 2.75c1.582 0 2.179.012 2.71.216l.538-1.4c-.852-.328-1.78-.316-3.248-.316zm5.865.746c-1.086-.977-1.765-1.604-2.617-1.93l-.537 1.4c.532.204.98.592 2.15 1.645zM10 21.25c-1.907 0-3.261-.002-4.29-.14c-1.005-.135-1.585-.389-2.008-.812l-1.06 1.06c.748.75 1.697 1.081 2.869 1.239c1.15.155 2.625.153 4.489.153zM1.25 14c0 1.864-.002 3.338.153 4.489c.158 1.172.49 2.121 1.238 2.87l1.06-1.06c-.422-.424-.676-1.004-.811-2.01c-.138-1.027-.14-2.382-.14-4.289zM14 22.75c1.864 0 3.338.002 4.489-.153c1.172-.158 2.121-.49 2.87-1.238l-1.06-1.06c-.424.422-1.004.676-2.01.811c-1.027.138-2.382.14-4.289.14zM21.25 14c0 1.907-.002 3.262-.14 4.29c-.135 1.005-.389 1.585-.812 2.008l1.06 1.06c.75-.748 1.081-1.697 1.239-2.869c.155-1.15.153-2.625.153-4.489zm-18.5-4c0-1.907.002-3.261.14-4.29c.135-1.005.389-1.585.812-2.008l-1.06-1.06c-.75.748-1.081 1.697-1.239 2.869C1.248 6.661 1.25 8.136 1.25 10zm7.28-8.75c-1.875 0-3.356-.002-4.511.153c-1.177.158-2.129.49-2.878 1.238l1.06 1.06c.424-.422 1.005-.676 2.017-.811c1.033-.138 2.395-.14 4.312-.14z"
      />
      <path
        stroke="currentColor"
        strokeWidth="1.5"
        d="M13 2.5V5c0 2.357 0 3.536.732 4.268S15.643 10 18 10h4"
      />
    </g>
  ),
  secret: (
    <g fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M2 16c0-2.828 0-4.243.879-5.121C3.757 10 5.172 10 8 10h8c2.828 0 4.243 0 5.121.879C22 11.757 22 13.172 22 16s0 4.243-.879 5.121C20.243 22 18.828 22 16 22H8c-2.828 0-4.243 0-5.121-.879C2 20.243 2 18.828 2 16Z" />
      <path strokeLinecap="round" d="M6 10V8a6 6 0 1 1 12 0v2" />
    </g>
  ),
  screen: (
    <g fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M2 10c0-3.771 0-5.657 1.172-6.828S6.229 2 10 2h4c3.771 0 5.657 0 6.828 1.172S22 6.229 22 10v1c0 2.828 0 4.243-.879 5.121C20.243 17 18.828 17 16 17H8c-2.828 0-4.243 0-5.121-.879C2 15.243 2 13.828 2 11z" />
      <path strokeLinecap="round" d="M16 22H8m4-5v5m10-9H2" />
    </g>
  ),
  watch: (
    <path
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      d="M20.409 9.353a2.998 2.998 0 0 1 0 5.294L7.597 21.614C5.534 22.737 3 21.277 3 18.968V5.033c0-2.31 2.534-3.769 4.597-2.648z"
    />
  ),
  call: (
    <path
      fill="currentColor"
      d="m16.1 13.359l-.528-.532zm.456-.453l.529.532zm2.417-.317l-.358.66zm1.91 1.039l-.358.659zm.539 3.255l.529.532zm-1.42 1.412l-.53-.531zm-1.326.67l.07.747zm-9.86-4.238l.528-.532zM4.002 5.746l-.749.042zm6.474 1.451l.53.532zm.157-2.654l.6-.449zM9.374 2.86l-.601.45zM6.26 2.575l.53.532zm-1.57 1.56l-.528-.531zm7.372 7.362l.529-.532zm4.567 2.394l.455-.453l-1.058-1.064l-.455.453zm1.985-.643l1.91 1.039l.716-1.318l-1.91-1.038zm2.278 3.103l-1.42 1.413l1.057 1.063l1.42-1.412zm-2.286 1.867c-1.45.136-5.201.015-9.263-4.023l-1.057 1.063c4.432 4.407 8.65 4.623 10.459 4.454zm-9.263-4.023c-3.871-3.85-4.512-7.087-4.592-8.492l-1.498.085c.1 1.768.895 5.356 5.033 9.47zm1.376-6.18l.286-.286L9.95 6.666l-.287.285zm.515-3.921L9.974 2.41l-1.201.899l1.26 1.684zM5.733 2.043l-1.57 1.56l1.058 1.064l1.57-1.56zm4.458 5.44c-.53-.532-.53-.532-.53-.53h-.002l-.003.004a1 1 0 0 0-.127.157c-.054.08-.113.185-.163.318a2.1 2.1 0 0 0-.088 1.071c.134.865.73 2.008 2.256 3.526l1.058-1.064c-1.429-1.42-1.769-2.284-1.832-2.692c-.03-.194.001-.29.01-.312q.009-.02 0-.006a.3.3 0 0 1-.03.039l-.01.01l-.01.009zm1.343 4.546c1.527 1.518 2.676 2.11 3.542 2.242c.443.068.8.014 1.071-.087a1.5 1.5 0 0 0 .42-.236l.05-.045l.007-.006l.003-.003l.001-.002s.002-.001-.527-.533c-.53-.532-.528-.533-.528-.533l.002-.002l.002-.002l.006-.005l.01-.01l.038-.03q.014-.009-.007.002c-.025.009-.123.04-.32.01c-.414-.064-1.284-.404-2.712-1.824zm-1.56-9.62C8.954 1.049 6.95.834 5.733 2.044L6.79 3.107c.532-.529 1.476-.475 1.983.202zM4.752 5.704c-.02-.346.139-.708.469-1.036L4.163 3.604c-.537.534-.96 1.29-.909 2.184zm14.72 12.06c-.274.274-.57.428-.865.455l.139 1.494c.735-.069 1.336-.44 1.784-.885zM11.006 7.73c.985-.979 1.058-2.527.229-3.635l-1.201.899c.403.539.343 1.246-.085 1.673zm9.52 6.558c.817.444.944 1.49.367 2.064l1.058 1.064c1.34-1.333.927-3.557-.71-4.446zm-3.441-.849c.384-.382 1.002-.476 1.53-.19l.716-1.317c-1.084-.59-2.428-.427-3.304.443z"
    />
  ),
  collab: (
    <g fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="9" cy="6" r="4" />
      <path strokeLinecap="round" d="M15 9a3 3 0 1 0 0-6" />
      <ellipse cx="9" cy="17" rx="7" ry="4" />
      <path
        strokeLinecap="round"
        d="M18 14c1.754.385 3 1.359 3 2.5c0 1.03-1.014 1.923-2.5 2.37"
      />
    </g>
  ),
}

// Dome / arc section — adapted from the ""Powerful Integrations,
// Effortless Setup"" pattern (Lenora, Grovia and many other modern
// templates use this). Six chambers = our parallel to the brand
// integrations those templates show. Each chamber gets a floating
// rounded-square card sitting on a soft pale-gradient semi-circle.
//
// Layout: an SVG arc draws the curve; cards are absolute-positioned
// along it via trig (angle → x/y). Hidden on mobile because the
// dome footprint needs horizontal room — small screens fall back to
// the original ``ChamberStrip`` pill list.

// Small per-chamber accent for the icon — keeps each card visually
// distinct without saturating any of them.
const CHAMBER_TINT: Record<string, string> = {
  files: 'text-orange-500',
  secret: 'text-emerald-500',
  screen: 'text-sky-500',
  watch: 'text-amber-500',
  call: 'text-rose-500',
  collab: 'text-violet-500',
}

// Position the six cards along a half-circle. ``arcPositions`` are
// in (x, y) percentages relative to the dome container (0,0 = top-
// left, 100,100 = bottom-right). Centre card highest, edges lower —
// matches the Lenora reference where logos sit higher in the middle.
const ARC_POSITIONS = [
  { x: 8, y: 62 }, // far-left
  { x: 22, y: 28 }, // mid-left, high
  { x: 40, y: 8 }, // centre-left, highest
  { x: 60, y: 8 }, // centre-right, highest
  { x: 78, y: 28 }, // mid-right, high
  { x: 92, y: 62 }, // far-right
]

// Renders the dome arc + chamber cards as a self-contained block.
// Title / pill label live in the parent so the dome can sit
// around the dropzone without competing copy stacked on top.
export function ChambersDome() {
  return (
    <div className="relative w-full">
      {/* Dome with floating chamber cards. The arc itself is an SVG
          path (semi-ellipse) filled with a soft pale gradient; cards
          sit on top via absolute positioning. */}
      <div className="relative mx-auto hidden aspect-[16/7] w-full max-w-4xl md:block">
        {/* Pale gradient dome shape */}
        <svg
          viewBox="0 0 100 44"
          className="absolute inset-0 h-full w-full"
          aria-hidden
          preserveAspectRatio="none"
        >
          <defs>
            {/* Cream/beige gradient — matches the original two-circle
                Venn aesthetic, not the cool pale blue I had before. */}
            <linearGradient id="dome-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(245, 240, 234, 0)" />
              <stop offset="50%" stopColor="rgba(245, 240, 234, 0.7)" />
              <stop offset="100%" stopColor="rgba(239, 233, 225, 0.5)" />
            </linearGradient>
            <linearGradient id="dome-grad-dark" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(60, 50, 40, 0)" />
              <stop offset="50%" stopColor="rgba(60, 50, 40, 0.5)" />
              <stop offset="100%" stopColor="rgba(50, 42, 35, 0.3)" />
            </linearGradient>
          </defs>
          {/* Half-ellipse: M start, A rx ry rot 0 0 to-x to-y, Z */}
          <path
            d="M 5 44 A 50 44 0 0 1 95 44 Z"
            className="fill-[url(#dome-grad)] dark:fill-[url(#dome-grad-dark)]"
          />
        </svg>

        {/* Floating chamber cards */}
        {CHAMBERS.slice(0, 6).map((chamber, i) => {
          const pos = ARC_POSITIONS[i]
          const tint = CHAMBER_TINT[chamber.id] ?? 'text-slate-500'
          // Subtle alternating rotation for the casually-placed feel
          // matching Lenora's reference.
          const rotate = i % 2 === 0 ? -6 : 6
          return (
            <Link
              key={chamber.id}
              href={chamber.href}
              aria-label={`${chamber.label} — ${chamber.tagline}`}
              className="group absolute focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
              style={{
                left: `${pos.x}%`,
                top: `${pos.y}%`,
                transform: `translate(-50%, -50%) rotate(${rotate}deg)`,
              }}
            >
              <div
                className={`flex h-16 w-16 items-center justify-center rounded-2xl border border-(--beige-border)/60 bg-white shadow-[0_8px_24px_rgba(120,100,80,0.10)] transition-transform duration-300 group-hover:scale-110 group-hover:shadow-[0_12px_32px_rgba(120,100,80,0.16)] dark:border-white/10 dark:bg-white/8 dark:backdrop-blur-xl ${tint}`}
              >
                <svg viewBox="0 0 24 24" className="h-7 w-7" aria-hidden>
                  {SVGS[chamber.id]}
                </svg>
              </div>
              <span className="rp-text-secondary mt-2 block text-center text-xs font-medium">
                {chamber.label}
              </span>
            </Link>
          )
        })}
      </div>

      {/* Mobile fallback — stacked grid since the arc doesn't have
          horizontal room on a phone. */}
      <div className="grid grid-cols-3 gap-4 md:hidden">
        {CHAMBERS.slice(0, 6).map((chamber) => {
          const tint = CHAMBER_TINT[chamber.id] ?? 'text-slate-500'
          return (
            <Link
              key={chamber.id}
              href={chamber.href}
              aria-label={`${chamber.label} — ${chamber.tagline}`}
              className="flex flex-col items-center gap-2 focus-visible:outline-none"
            >
              <div
                className={`flex h-14 w-14 items-center justify-center rounded-2xl border border-(--beige-border)/60 bg-white shadow-[0_4px_12px_rgba(120,100,80,0.08)] dark:border-white/10 dark:bg-white/8 dark:backdrop-blur-xl ${tint}`}
              >
                <svg viewBox="0 0 24 24" className="h-6 w-6" aria-hidden>
                  {SVGS[chamber.id]}
                </svg>
              </div>
              <span className="rp-text-secondary text-xs font-medium">
                {chamber.label}
              </span>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
