'use client'

/**
 * Revolver — 6-chamber radial navigation.
 *
 * The chambers are no longer rendered as separate cards floating on
 * a hexagonal ring. Instead the visualisation IS the navigation:
 * the inner ring is split into six 60° wedges, one per live
 * chamber, and clicking a wedge navigates there. The outer ring
 * carries each chamber's sub-features as a softer, decorative band
 * (hover-tooltip only — those aren't routed).
 *
 * The centre keeps its emerald "Rapidly" disc as the visual anchor.
 */

import { useRouter } from 'next/navigation'
import { useMemo } from 'react'

import type { RingNode } from '@/utils/visualisation/radial-rings'
import { CHAMBERS } from './chambers'
import { RadialRings } from './RadialRings'

interface RevolverProps {
  centre?: React.ReactNode
}

/** Build the ring tree from the chamber registry. Inner ring =
 *  one wedge per chamber (equal-weighted → 60° each). Outer ring =
 *  a fixed-by-id list of sub-features per chamber, each carrying
 *  the chamber's accent tint at progressively lower opacity. */
function buildChamberTree(): RingNode {
  const chamberSubs: Record<
    string,
    { tint: string; subs: Array<{ id: string; label: string }> }
  > = {
    files: {
      tint: '165, 216, 255',
      subs: [
        { id: 'files-p2p', label: 'P2P' },
        { id: 'files-e2ee', label: 'E2EE' },
        { id: 'files-link', label: 'Link' },
      ],
    },
    secret: {
      tint: '224, 169, 240',
      subs: [
        { id: 'secret-vault', label: 'Vault' },
        { id: 'secret-burn', label: 'Burn' },
      ],
    },
    screen: {
      tint: '178, 242, 187',
      subs: [
        { id: 'screen-share', label: 'Share' },
        { id: 'screen-record', label: 'Record' },
        { id: 'screen-cast', label: 'Cast' },
      ],
    },
    watch: {
      tint: '255, 217, 168',
      subs: [
        { id: 'watch-sync', label: 'Sync' },
        { id: 'watch-rooms', label: 'Rooms' },
      ],
    },
    call: {
      tint: '255, 236, 153',
      subs: [
        { id: 'call-voice', label: 'Voice' },
        { id: 'call-video', label: 'Video' },
        { id: 'call-mesh', label: 'Mesh' },
      ],
    },
    collab: {
      tint: '252, 194, 215',
      subs: [
        { id: 'collab-docs', label: 'Docs' },
        { id: 'collab-board', label: 'Board' },
      ],
    },
  }

  return {
    id: 'rapidly',
    color: 'rgba(148, 163, 184, 0.04)',
    children: CHAMBERS.map((chamber) => {
      const meta = chamberSubs[chamber.id]
      return {
        id: chamber.id,
        label: chamber.label,
        color: meta ? `rgba(${meta.tint}, 0.65)` : 'rgba(148,163,184,0.40)',
        children: meta?.subs.map((s) => ({
          id: s.id,
          label: s.label,
          value: 1,
          color: `rgba(${meta.tint}, 0.32)`,
        })),
      }
    }),
  }
}

export function Revolver({ centre }: RevolverProps) {
  const router = useRouter()
  const data = useMemo(() => buildChamberTree(), [])

  const chamberById = useMemo(() => new Map(CHAMBERS.map((c) => [c.id, c])), [])

  return (
    <div className="relative mx-auto flex aspect-square w-full max-w-3xl items-center justify-center">
      {/* Rotated -30° so each 60° wedge centres at a clock position
          (12 / 2 / 4 / 6 / 8 / 10), matching the hexagonal layout
          users expect when reading the ring. */}
      <div
        className="absolute inset-4 z-0 text-slate-500/70 dark:text-slate-200/80"
        style={{ transform: 'rotate(-30deg)' }}
      >
        <RadialRings
          data={data}
          radius={433}
          centerRadius={0.22}
          radiusScaleExponent={0.55}
          excludeRoot
          strokeColor="currentColor"
          strokeWidth={1}
          labelScale={1.6}
          /** Inner-ring wedges are the chamber nav targets. Outer
           *  ring stays decorative + tooltip-only. */
          isInteractive={(arc) => arc.depth === 1 && chamberById.has(arc.id)}
          getAriaLabel={(arc) => {
            const c = chamberById.get(arc.id)
            return c ? `${c.label} — ${c.tagline}` : undefined
          }}
          getTooltip={(arc) => {
            const c = chamberById.get(arc.id)
            if (c) return c.tagline
            return arc.label
          }}
          onArcClick={(id) => {
            const c = chamberById.get(id)
            if (c?.status === 'live') router.push(c.href)
          }}
          className="h-full w-full"
        />
      </div>
      {/* Counter-rotate the labels so they read upright while the
          surrounding wedges sit at -30° offset. The label text lives
          inside the SVG so this CSS rotation doesn't apply — labels
          rotate WITH the wedges by design (a wedge centred at 2
          o'clock has its label angled toward 2 o'clock too). The
          centre disc, however, must stay upright, so we wrap it in
          its own un-rotated layer below. */}
      <div className="relative z-10 flex size-32 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-emerald-700 text-white shadow-xl shadow-emerald-600/30">
        {centre ?? (
          <span className="text-lg font-semibold tracking-tight">Rapidly</span>
        )}
      </div>
    </div>
  )
}
