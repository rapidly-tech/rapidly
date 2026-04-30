'use client'

import { Icon } from '@iconify/react'

// Three-step explainer. Numbered (01, 02, 03) per Grovia's section
// pattern. Each step is product-true: Drop / Share / Receive maps
// directly to what the dropzone, link card, and recipient page do.

interface Step {
  number: string
  icon: string
  title: string
  body: string
}

const STEPS: readonly Step[] = [
  {
    number: '01',
    icon: 'solar:upload-linear',
    title: 'Drop',
    body: 'Pick a file or paste a secret. It is encrypted on your device before it goes anywhere.',
  },
  {
    number: '02',
    icon: 'solar:link-circle-linear',
    title: 'Share',
    body: 'Copy the link. Send it however you like — email, chat, QR — only the recipient can open it.',
  },
  {
    number: '03',
    icon: 'solar:shield-keyhole-linear',
    title: 'Receive',
    body: 'They open the link. The payload streams peer-to-peer, end to end. Our server never sees it.',
  },
]

export function HowItWorks() {
  return (
    <section
      aria-label="How Rapidly works"
      className="relative z-10 mx-auto w-full max-w-5xl px-4 py-20 md:py-28"
    >
      <div className="mb-12 text-center md:mb-16">
        <h2 className="rp-text-primary text-3xl font-semibold tracking-tight md:text-4xl">
          Three steps. Nothing in the middle.
        </h2>
        <p className="rp-text-secondary mx-auto mt-3 max-w-xl text-sm md:text-base">
          From drop to receive, the payload moves directly between sender and
          recipient. No accounts, no uploads to our server.
        </p>
      </div>

      <ol className="grid grid-cols-1 gap-4 md:grid-cols-3 md:gap-6">
        {STEPS.map((step) => (
          <li
            key={step.number}
            className="flex flex-col gap-4 rounded-2xl border border-(--beige-border)/50 bg-white p-7 shadow-[0_2px_16px_rgba(120,100,80,0.06)] transition-shadow duration-200 hover:shadow-[0_8px_28px_rgba(120,100,80,0.10)] dark:border-white/10 dark:bg-white/5 dark:backdrop-blur-xl"
          >
            <div className="flex items-center justify-between">
              <span className="rp-text-muted font-mono text-sm tracking-wider">
                {step.number}
              </span>
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
                <Icon icon={step.icon} className="h-5 w-5" aria-hidden />
              </div>
            </div>
            <h3 className="rp-text-primary text-xl font-semibold tracking-tight">
              {step.title}
            </h3>
            <p className="rp-text-secondary text-sm leading-relaxed">
              {step.body}
            </p>
          </li>
        ))}
      </ol>
    </section>
  )
}
