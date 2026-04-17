import type { Metadata } from 'next'

import { Revolver } from '@/components/Revolver/Revolver'

export const metadata: Metadata = {
  title: 'Rapidly — 6 chambers, one platform',
  description:
    'Files, Secret, Screen, Watch, Call, Collab. Rapidly is a 6-chamber platform for encrypted peer-to-peer collaboration.',
}

export default function RevolverPage() {
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
