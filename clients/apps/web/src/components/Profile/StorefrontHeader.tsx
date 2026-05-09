'use client'

import { schemas } from '@rapidly-tech/client'
import Avatar from '@rapidly-tech/ui/components/data/Avatar'
import Link from 'next/link'
import { useEffect, useMemo } from 'react'
import { Gradient } from './GradientMesh'
import { computeComplementaryColor } from './utils'

interface StorefrontHeaderProps {
  workspace: schemas['Workspace']
}

/** Renders the storefront header with animated gradient background and workspace avatar. */
export const StorefrontHeader = ({ workspace }: StorefrontHeaderProps) => {
  const gradient = useMemo(
    () => (typeof window !== 'undefined' ? new Gradient() : undefined),
    [],
  )

  useEffect(() => {
    if (!gradient) {
      return
    }

    const root = document.documentElement

    const [a, b, c, d] = computeComplementaryColor('#121316')

    root.style.setProperty('--gradient-color-1', `#${a.toHex()}`)
    root.style.setProperty('--gradient-color-2', `#${b.toHex()}`)
    root.style.setProperty('--gradient-color-3', `#${c.toHex()}`)
    root.style.setProperty('--gradient-color-4', `#${d.toHex()}`)

    /* @ts-expect-error — Gradient class lacks type definitions */
    gradient.initGradient('#gradient-canvas')

    return () => {
      root.style.removeProperty('--gradient-color-1')
      root.style.removeProperty('--gradient-color-2')
      root.style.removeProperty('--gradient-color-3')
      root.style.removeProperty('--gradient-color-4')
    }
  }, [gradient, workspace])

  return (
    <div className="flex w-full grow flex-col items-center gap-y-6">
      <div className="relative aspect-3/1 w-full rounded-2xl bg-slate-100 md:aspect-4/1 md:rounded-4xl dark:bg-black">
        <canvas
          id="gradient-canvas"
          className="absolute top-0 right-0 bottom-0 left-0 h-full w-full rounded-2xl md:rounded-4xl"
        />
        <Avatar
          className="absolute -bottom-16 left-1/2 h-32 w-32 -translate-x-1/2 border-8 border-white text-lg md:text-5xl dark:border-slate-950"
          name={workspace.name}
          avatar_url={workspace.avatar_url}
        />
      </div>
      <div className="mt-16 flex grow flex-col items-center">
        <div className="flex flex-col items-center md:gap-y-1">
          <h1 className="text-xl md:text-3xl">{workspace.name}</h1>
          <Link
            className="text-slate-500 dark:text-slate-400"
            href={`/${workspace.slug}`}
            tabIndex={-1}
          >
            @{workspace.slug}
          </Link>
        </div>
      </div>
      <div className="flex w-full grow flex-col items-center">
        <div className="flex w-full grow flex-col items-center gap-y-6"></div>
      </div>
    </div>
  )
}
