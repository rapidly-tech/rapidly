'use client'

import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'

// Final CTA strip — the last thing visitors see above the footer.
// Re-states the action with a single confident button, plus a few
// small reinforcement points. Mirrors Grovia's "Start your journey"
// pattern. Keeps the page from ending on the FAQ.

export function FooterCTA() {
  return (
    <section
      aria-label="Start sharing"
      className="relative z-10 mx-auto w-full max-w-4xl px-4 py-20 md:py-28"
    >
      <div className="rounded-3xl border border-(--beige-border)/50 bg-white p-8 text-center shadow-[0_8px_32px_rgba(120,100,80,0.08)] md:p-14 dark:border-white/10 dark:bg-white/5 dark:backdrop-blur-xl">
        <h2 className="rp-text-primary text-3xl font-semibold tracking-tight md:text-4xl">
          Send something. Right now.
        </h2>
        <p className="rp-text-secondary mx-auto mt-3 max-w-xl text-sm md:text-base">
          No account, nothing to install. The drop zone is at the top of this
          page.
        </p>

        <div className="mt-8 flex flex-col items-center justify-center gap-3 md:flex-row md:gap-4">
          <Button
            type="button"
            size="lg"
            className="px-6"
            onClick={() => {
              if (typeof window !== 'undefined') {
                window.scrollTo({ top: 0, behavior: 'smooth' })
              }
            }}
          >
            <Icon icon="solar:upload-linear" className="mr-2 h-4 w-4" />
            Drop a file
          </Button>
          <span className="rp-text-muted text-xs">
            or just start typing a secret anywhere on the page
          </span>
        </div>

        <ul className="rp-text-muted mt-10 grid grid-cols-2 gap-y-2 text-xs md:grid-cols-4">
          <li className="flex items-center justify-center gap-x-1.5">
            <Icon icon="solar:shield-keyhole-linear" className="h-3.5 w-3.5" />
            End-to-end
          </li>
          <li className="flex items-center justify-center gap-x-1.5">
            <Icon
              icon="solar:transfer-horizontal-linear"
              className="h-3.5 w-3.5"
            />
            Peer-to-peer
          </li>
          <li className="flex items-center justify-center gap-x-1.5">
            <Icon icon="solar:user-cross-linear" className="h-3.5 w-3.5" />
            No accounts
          </li>
          <li className="flex items-center justify-center gap-x-1.5">
            <Icon icon="solar:hourglass-line-linear" className="h-3.5 w-3.5" />
            Self-destructing
          </li>
        </ul>
      </div>
    </section>
  )
}
