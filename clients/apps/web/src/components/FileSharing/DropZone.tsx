'use client'

import { RadialRings } from '@/components/Revolver/RadialRings'
import { extractFileList } from '@/utils/file-sharing/fs'
import type { RingNode } from '@/utils/visualisation/radial-rings'
import { Icon } from '@iconify/react'
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion'
import React, { JSX, useCallback, useEffect, useRef, useState } from 'react'
import TermsAcceptance from './TermsAcceptance'

// ── Decorative ring data ──
//
// Six chambers as the inner ring + a few sub-features per chamber as
// the outer ring. Equal-weighted so the inner ring divides cleanly
// into 60° wedges and the outer ring stays balanced. Colours are the
// muted slate / chamber-tint palette already used elsewhere in the
// product so the rings feel like decoration, not a chart.
const RING_DATA: RingNode = {
  id: 'rapidly',
  color: 'rgba(148, 163, 184, 0.04)',
  children: [
    {
      id: 'files',
      color: 'rgba(165, 216, 255, 0.18)',
      children: [
        { id: 'files-p2p', value: 1, color: 'rgba(165, 216, 255, 0.32)' },
        { id: 'files-e2ee', value: 1, color: 'rgba(165, 216, 255, 0.22)' },
        { id: 'files-link', value: 1, color: 'rgba(165, 216, 255, 0.14)' },
      ],
    },
    {
      id: 'secret',
      color: 'rgba(224, 169, 240, 0.18)',
      children: [
        { id: 'secret-vault', value: 1, color: 'rgba(224, 169, 240, 0.28)' },
        { id: 'secret-burn', value: 1, color: 'rgba(224, 169, 240, 0.18)' },
      ],
    },
    {
      id: 'screen',
      color: 'rgba(178, 242, 187, 0.18)',
      children: [
        { id: 'screen-share', value: 1, color: 'rgba(178, 242, 187, 0.30)' },
        { id: 'screen-record', value: 1, color: 'rgba(178, 242, 187, 0.20)' },
        { id: 'screen-cast', value: 1, color: 'rgba(178, 242, 187, 0.14)' },
      ],
    },
    {
      id: 'watch',
      color: 'rgba(255, 217, 168, 0.18)',
      children: [
        { id: 'watch-sync', value: 1, color: 'rgba(255, 217, 168, 0.30)' },
        { id: 'watch-rooms', value: 1, color: 'rgba(255, 217, 168, 0.18)' },
      ],
    },
    {
      id: 'call',
      color: 'rgba(255, 236, 153, 0.18)',
      children: [
        { id: 'call-voice', value: 1, color: 'rgba(255, 236, 153, 0.30)' },
        { id: 'call-video', value: 1, color: 'rgba(255, 236, 153, 0.20)' },
        { id: 'call-mesh', value: 1, color: 'rgba(255, 236, 153, 0.14)' },
      ],
    },
    {
      id: 'collab',
      color: 'rgba(252, 194, 215, 0.18)',
      children: [
        { id: 'collab-docs', value: 1, color: 'rgba(252, 194, 215, 0.30)' },
        { id: 'collab-board', value: 1, color: 'rgba(252, 194, 215, 0.20)' },
      ],
    },
  ],
}

// ── Main Component ──

/** Full-page drag-and-drop zone with animated ring visuals for selecting files to share. */
export default function DropZone({
  onDrop,
  onProcessingChange,
  children,
}: {
  onDrop: (files: File[]) => void
  onProcessingChange?: (processing: boolean) => void
  children?: React.ReactNode
}): JSX.Element {
  // ── State ──
  const [isDragging, setIsDragging] = useState(false)
  const dragCounterRef = useRef(0)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // ── Cursor-reactive effects ──
  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)
  const springCfg = { stiffness: 120, damping: 25, mass: 0.5 }
  const smoothX = useSpring(mouseX, springCfg)
  const smoothY = useSpring(mouseY, springCfg)

  // Parallax offset — single visualisation shifts subtly toward the
  // cursor for depth.
  const topRingX = useTransform(smoothX, [-1, 1], [-5, 5])
  const topRingY = useTransform(smoothY, [-1, 1], [-5, 5])

  // ── Drag & Drop Handlers ──
  const handleDragEnter = useCallback((e: DragEvent) => {
    e.preventDefault()
    dragCounterRef.current++
    if (dragCounterRef.current === 1) {
      setIsDragging(true)
    }
  }, [])

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault()
    dragCounterRef.current--
    if (dragCounterRef.current === 0) {
      setIsDragging(false)
    }
  }, [])

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault()
    if (e.dataTransfer) {
      e.dataTransfer.dropEffect = 'copy'
    }
  }, [])

  const handleDrop = useCallback(
    async (e: DragEvent) => {
      e.preventDefault()
      dragCounterRef.current = 0
      setIsDragging(false)

      if (e.dataTransfer) {
        onProcessingChange?.(true)
        try {
          const files = await extractFileList(e)
          onDrop(files)
        } finally {
          onProcessingChange?.(false)
        }
      }
    },
    [onDrop, onProcessingChange],
  )

  const handleClick = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  const handleFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        const files = Array.from(e.target.files)
        onDrop(files)
      }
    },
    [onDrop],
  )

  // ── Cursor tracking ──
  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      const el = containerRef.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      const cx = rect.left + rect.width / 2
      const cy = rect.top + rect.height / 2
      mouseX.set(Math.max(-1, Math.min(1, (e.clientX - cx) / (rect.width / 2))))
      mouseY.set(
        Math.max(-1, Math.min(1, (e.clientY - cy) / (rect.height / 2))),
      )
    },
    [mouseX, mouseY],
  )

  const handleMouseLeave = useCallback(() => {
    mouseX.set(0)
    mouseY.set(0)
  }, [mouseX, mouseY])

  // ── Event Listener Setup ──
  useEffect(() => {
    const buf = window.__rapidlyDrop
    if (buf) {
      buf.ready = true

      // Process any files dropped before React hydration completed
      if (buf.files) {
        const earlyFiles = buf.files
        buf.files = null
        onDrop(earlyFiles)
      }
    }

    window.addEventListener('dragenter', handleDragEnter)
    window.addEventListener('dragleave', handleDragLeave)
    window.addEventListener('dragover', handleDragOver)
    window.addEventListener('drop', handleDrop)

    return () => {
      if (buf) buf.ready = false
      window.removeEventListener('dragenter', handleDragEnter)
      window.removeEventListener('dragleave', handleDragLeave)
      window.removeEventListener('dragover', handleDragOver)
      window.removeEventListener('drop', handleDrop)
    }
  }, [handleDragEnter, handleDragLeave, handleDragOver, handleDrop, onDrop])

  // ── Ring Styles ──
  // Dark fill uses --surface (a warm tone slightly lighter than bg)
  // instead of --card (which is rgb(20,20,20)/0.5 — dark gray that
  // composites nearly invisible over the warm-dark bg). Light mode
  // unchanged.
  const circleClass =
    'border border-white/50 bg-white/70 backdrop-blur-xl shadow-[0_4px_60px_rgba(120,100,80,0.06)] dark:border-(--border) dark:bg-(--surface) dark:backdrop-blur-xl dark:shadow-[0_4px_60px_rgba(0,0,0,0.2)]'

  // Stroke colour for the radial-rings outline. Lifts on hover so
  // the visualisation reads as alive without distracting at rest.
  const ringColor = isDragging
    ? 'text-slate-400/60 dark:text-slate-400/50'
    : 'text-slate-400/35 group-hover:text-slate-400/65 dark:text-slate-400/20 dark:group-hover:text-slate-400/50'

  // ── Render ──
  return (
    <>
      <span className="sr-only" aria-live="assertive" role="status">
        {isDragging ? 'Drop zone active. Release to upload files.' : ''}
      </span>
      <input
        type="file"
        ref={fileInputRef}
        className="hidden"
        onChange={handleFileInputChange}
        multiple
      />
      <div
        ref={containerRef}
        id="drop-zone-button"
        role="button"
        tabIndex={0}
        aria-label="Select files to share"
        className="group relative mx-auto flex cursor-pointer flex-col items-center focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 focus-visible:outline-none"
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            handleClick()
          }
        }}
      >
        {/* Container — visualisation extends freely beyond, no clipping */}
        <div className="relative flex items-center justify-center">
          {/* Soft backdrop disc behind the rings — keeps the centre
               legible against busy page backgrounds. The ``circleClass``
               glass treatment is preserved here so the visual identity
               of the previous half-circle pair carries over. */}
          <div
            className={`pointer-events-none absolute left-1/2 h-[866px] w-[866px] -translate-x-1/2 rounded-full transition-all duration-500 ${circleClass}`}
          />

          {/* ===== Radial multi-ring visualisation — chamber tree
               laid out as concentric segmented rings. Replaces the
               static dual-circle Venn so the surface reads as a
               product map rather than two flat half-circles. ===== */}
          <motion.div
            className="pointer-events-none absolute left-1/2 z-1 h-[866px] w-[866px] -translate-x-1/2"
            style={{ x: topRingX, y: topRingY }}
            animate={{ scale: isDragging ? 1.02 : 1 }}
            transition={{ duration: 0.7, ease: [0.4, 0, 0.2, 1] }}
          >
            <div
              className={`absolute inset-0 transition-colors duration-500 ${ringColor}`}
              style={{
                animation: 'ring-spin 240s linear infinite',
                transformOrigin: 'center',
              }}
            >
              <RadialRings
                data={RING_DATA}
                radius={433}
                centerRadius={0.18}
                radiusScaleExponent={0.5}
                excludeRoot
                strokeColor="currentColor"
                strokeWidth={0.5}
                className="h-full w-full overflow-visible"
              />
            </div>
          </motion.div>
          {/* ===== Content — centered in the rings, slight
               nudge up so the stack doesn't crowd the bottom half. ===== */}
          <div className="relative z-10 flex h-64 w-64 -translate-y-1 flex-col items-center justify-center pt-2 md:h-80 md:w-80">
            {/* Upload icon container */}
            <div
              className={`flex h-12 w-12 items-center justify-center rounded-xl transition-all duration-300 ${
                isDragging
                  ? 'scale-110 bg-slate-200 dark:bg-slate-800/40'
                  : 'bg-slate-100 group-hover:scale-110 group-hover:bg-slate-200 dark:bg-slate-900/40 dark:group-hover:bg-slate-800/40'
              }`}
            >
              <Icon
                icon="solar:upload-linear"
                className={`h-6 w-6 transition-transform duration-300 ${
                  isDragging
                    ? '-translate-y-1 text-slate-600 dark:text-slate-400'
                    : 'text-slate-500 group-hover:-translate-y-0.5 dark:text-slate-400'
                }`}
                aria-hidden="true"
              />
            </div>
            <span
              className={`mt-3 px-6 text-center text-sm font-medium transition-colors duration-300 ${
                isDragging
                  ? 'text-slate-700 dark:text-slate-300'
                  : 'text-slate-500 dark:text-slate-400'
              }`}
            >
              {isDragging ? 'Drop files here' : 'Click or drag files here'}
            </span>
            {!isDragging && children}
            {!isDragging && (
              <div
                className="mt-2"
                role="presentation"
                onClick={(e) => e.stopPropagation()}
              >
                <TermsAcceptance />
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
