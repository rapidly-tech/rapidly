'use client'

import { Icon } from '@iconify/react'

// Feature grid — six cells of value props. Pattern from Grovia's
// "Built for high performance" section, mapped to Rapidly's
// privacy-first positioning. Two columns on tablet, three on
// desktop. Cards mirror the HowItWorks treatment so the page reads
// as one design system.

interface Feature {
  icon: string
  title: string
  body: string
}

const FEATURES: readonly Feature[] = [
  {
    icon: 'solar:shield-keyhole-linear',
    title: 'End-to-end encrypted',
    body: 'AES-256-GCM on your device. We could not read your files even if we wanted to.',
  },
  {
    icon: 'solar:transfer-horizontal-linear',
    title: 'Peer-to-peer',
    body: 'Files stream directly between sender and recipient over WebRTC. No relay server in the middle.',
  },
  {
    icon: 'solar:user-cross-linear',
    title: 'No accounts',
    body: 'No signup, no email capture, no password. Open the page, drop a file, share a link.',
  },
  {
    icon: 'solar:hourglass-line-linear',
    title: 'Self-destructing',
    body: 'Choose how long the link works. After the deadline or first download, it is gone forever.',
  },
  {
    icon: 'solar:download-square-linear',
    title: 'Up to 1 GB',
    body: 'Generous limits without the upload wait — the file lives on your device until the recipient opens it.',
  },
  {
    icon: 'solar:lock-keyhole-minimalistic-linear',
    title: 'Optional password',
    body: 'Add a custom password the recipient must enter. Decryption happens locally; the password never touches our server.',
  },
]

export function Features() {
  return (
    <section
      aria-label="Why Rapidly"
      className="relative z-10 mx-auto w-full max-w-6xl px-4 py-20 md:py-28"
    >
      <div className="mb-12 text-center md:mb-16">
        <h2 className="rp-text-primary text-3xl font-semibold tracking-tight md:text-4xl">
          Built so your files stay yours.
        </h2>
        <p className="rp-text-secondary mx-auto mt-3 max-w-xl text-sm md:text-base">
          Encryption, peer-to-peer transfer, and short-lived links — by default,
          not as a paid upgrade.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:gap-5 lg:grid-cols-3">
        {FEATURES.map((feature) => (
          <div
            key={feature.title}
            className="flex flex-col gap-3 rounded-2xl border border-(--beige-border)/50 bg-white p-6 shadow-[0_2px_16px_rgba(120,100,80,0.06)] transition-shadow duration-200 hover:shadow-[0_8px_28px_rgba(120,100,80,0.10)] dark:border-white/10 dark:bg-white/5 dark:backdrop-blur-xl"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
              <Icon icon={feature.icon} className="h-5 w-5" aria-hidden />
            </div>
            <h3 className="rp-text-primary text-lg font-semibold tracking-tight">
              {feature.title}
            </h3>
            <p className="rp-text-secondary text-sm leading-relaxed">
              {feature.body}
            </p>
          </div>
        ))}
      </div>
    </section>
  )
}
