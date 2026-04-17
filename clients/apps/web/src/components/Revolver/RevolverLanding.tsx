/**
 * Full landing section that renders the Revolver with hero copy.
 *
 * Shared between the root landing (gated by
 * ``NEXT_PUBLIC_REVOLVER_LANDING``) and the standalone ``/revolver`` preview
 * route. Keeping the section in one place means the two call sites can't
 * drift.
 */

import { Revolver } from './Revolver'

export function RevolverLanding() {
  return (
    <main className="relative overflow-hidden">
      <div className="mx-auto max-w-5xl px-4 py-24 text-center">
        <h1 className="text-4xl font-semibold tracking-tight text-balance text-slate-900 sm:text-5xl dark:text-white">
          Six chambers. One platform.
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-slate-600 dark:text-slate-400">
          Rapidly is an end-to-end encrypted, peer-to-peer platform for the
          things you share with the people you trust. Pick a chamber.
        </p>
        <div className="mt-16">
          <Revolver />
        </div>
      </div>
    </main>
  )
}
