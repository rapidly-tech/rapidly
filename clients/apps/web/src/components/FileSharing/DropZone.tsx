'use client'

import { extractFileList } from '@/utils/file-sharing/fs'
import { Icon } from '@iconify/react'
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion'
import React, { JSX, useCallback, useEffect, useRef, useState } from 'react'
import TermsAcceptance from './TermsAcceptance'

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

  // Parallax offsets — top and bottom rings shift in opposite directions for depth
  const topRingX = useTransform(smoothX, [-1, 1], [-5, 5])
  const topRingY = useTransform(smoothY, [-1, 1], [-5, 5])
  const bottomRingX = useTransform(smoothX, [-1, 1], [6, -6])
  const bottomRingY = useTransform(smoothY, [-1, 1], [6, -6])

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
  // Dark fill uses a warm RGB tint (matches the dashboard cards'
  // brown undertone) instead of pure white-alpha, which read as
  // cold gray on the new warm-dark background.
  const circleClass =
    'border border-white/50 bg-white/70 backdrop-blur-xl shadow-[0_4px_60px_rgba(120,100,80,0.06)] dark:border-[rgb(180,160,135)]/12 dark:bg-[rgb(180,160,135)]/6 dark:backdrop-blur-xl dark:shadow-[0_4px_60px_rgba(0,0,0,0.2)]'

  // Inner ring — always visible, strong
  const ringColor = isDragging
    ? 'text-slate-400/60 dark:text-slate-400/50'
    : 'text-slate-400/35 group-hover:text-slate-400/65 dark:text-slate-400/20 dark:group-hover:text-slate-400/50'

  // Middle ring — always visible at half tone
  const ringColorMiddle = isDragging
    ? 'text-slate-400/45 dark:text-slate-400/35'
    : 'text-slate-400/15 group-hover:text-slate-400/45 dark:text-slate-400/8 dark:group-hover:text-slate-400/35'

  // Outer ring — always visible at quarter tone
  const ringColorOuter = isDragging
    ? 'text-slate-400/30 dark:text-slate-400/25'
    : 'text-slate-400/5 group-hover:text-slate-400/30 dark:text-slate-400/3 dark:group-hover:text-slate-400/23'

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
        {/* Container — circles extend freely beyond, no clipping */}
        <div className="relative flex items-center justify-center">
          {/* ===== Top white circle — only bottom curve visible ===== */}
          <div
            className={`pointer-events-none absolute left-1/2 h-[866px] w-[866px] -translate-x-1/2 -translate-y-[36%] rounded-full transition-all duration-500 ${circleClass}`}
          />

          {/* ===== Bottom white circle — only top curve visible ===== */}
          <div
            className={`pointer-events-none absolute left-1/2 h-[866px] w-[866px] -translate-x-1/2 translate-y-[36%] rounded-full transition-all duration-500 ${circleClass}`}
          />

          {/* ===== Top circle — spinning rings with parallax ===== */}
          <motion.div
            className="pointer-events-none absolute left-1/2 z-1 h-[866px] w-[866px] -translate-x-1/2 -translate-y-[36%]"
            style={{ x: topRingX, y: topRingY }}
            animate={{ scale: isDragging ? 1.02 : 1 }}
            transition={{ duration: 0.7, ease: [0.4, 0, 0.2, 1] }}
          >
            <svg
              className="absolute inset-0 overflow-visible"
              viewBox="0 0 866 866"
              fill="none"
              aria-hidden="true"
            >
              <g
                style={{
                  animation: 'ring-spin 200s linear infinite',
                  transformOrigin: '433px 433px',
                }}
              >
                <circle
                  cx="433"
                  cy="433"
                  r="441"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  fill="none"
                  className={`transition-colors duration-500 ${ringColor}`}
                />
              </g>
              <g
                style={{
                  animation: 'ring-spin 260s linear infinite reverse',
                  transformOrigin: '433px 433px',
                }}
              >
                <circle
                  cx="433"
                  cy="433"
                  r="450"
                  stroke="currentColor"
                  strokeWidth="1"
                  fill="none"
                  className={`transition-colors duration-500 ${ringColorMiddle}`}
                />
              </g>
              <g
                style={{
                  animation: 'ring-spin 320s linear infinite',
                  transformOrigin: '433px 433px',
                }}
              >
                <circle
                  cx="433"
                  cy="433"
                  r="457"
                  stroke="currentColor"
                  strokeWidth="0.5"
                  fill="none"
                  className={`transition-colors duration-500 ${ringColorOuter}`}
                />
              </g>
            </svg>
          </motion.div>

          {/* ===== Bottom circle — spinning rings with parallax ===== */}
          <motion.div
            className="pointer-events-none absolute left-1/2 z-1 h-[866px] w-[866px] -translate-x-1/2 translate-y-[36%]"
            style={{ x: bottomRingX, y: bottomRingY }}
            animate={{ scale: isDragging ? 1.02 : 1 }}
            transition={{ duration: 0.7, ease: [0.4, 0, 0.2, 1] }}
          >
            <svg
              className="absolute inset-0 overflow-visible"
              viewBox="0 0 866 866"
              fill="none"
              aria-hidden="true"
            >
              <g
                style={{
                  animation: 'ring-spin 220s linear infinite reverse',
                  transformOrigin: '433px 433px',
                }}
              >
                <circle
                  cx="433"
                  cy="433"
                  r="441"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  fill="none"
                  className={`transition-colors duration-500 ${ringColor}`}
                />
              </g>
              <g
                style={{
                  animation: 'ring-spin 280s linear infinite',
                  transformOrigin: '433px 433px',
                }}
              >
                <circle
                  cx="433"
                  cy="433"
                  r="450"
                  stroke="currentColor"
                  strokeWidth="1"
                  fill="none"
                  className={`transition-colors duration-500 ${ringColorMiddle}`}
                />
              </g>
              <g
                style={{
                  animation: 'ring-spin 340s linear infinite reverse',
                  transformOrigin: '433px 433px',
                }}
              >
                <circle
                  cx="433"
                  cy="433"
                  r="457"
                  stroke="currentColor"
                  strokeWidth="0.5"
                  fill="none"
                  className={`transition-colors duration-500 ${ringColorOuter}`}
                />
              </g>
            </svg>
          </motion.div>

          {/* Ambient glow at the eye center */}
          <div
            className={`pointer-events-none absolute h-[200px] w-[350px] rounded-full blur-[60px] transition-all duration-500 ${
              isDragging
                ? 'scale-115 bg-slate-300/20 dark:bg-white/5'
                : 'bg-slate-200/15 group-hover:scale-110 group-hover:bg-slate-300/20 dark:bg-white/3 dark:group-hover:bg-white/5'
            }`}
          />

          {/* ===== Content — centered in the eye opening, slight
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
