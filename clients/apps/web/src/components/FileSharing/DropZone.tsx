'use client'

import { extractFileList } from '@/utils/file-sharing/fs'
import { Icon } from '@iconify/react'
import { motion } from 'framer-motion'
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

  // Cursor-reactive parallax was removed alongside the spinning
  // ring SVGs that consumed it — the new flat dropzone card is a
  // single static surface with a scale animation on drag.

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

  // ── Hero card ──
  // Replaced the previous two-circle Venn structure with a single
  // clean dropzone card. The decorative dome + chamber satellites
  // live around it via ``ChambersDome`` at the page level — that's
  // the hero showpiece now, this is just the action surface.
  const cardClass = isDragging
    ? 'border-(--beige-focus) bg-white shadow-[0_16px_56px_rgba(120,100,80,0.18)] dark:border-white/20 dark:bg-white/8'
    : 'border-(--beige-border)/60 bg-white shadow-[0_8px_32px_rgba(120,100,80,0.10)] group-hover:shadow-[0_12px_44px_rgba(120,100,80,0.14)] dark:border-white/10 dark:bg-white/5 dark:backdrop-blur-xl'

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
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            handleClick()
          }
        }}
      >
        {/* Single clean dropzone card — no more Venn circles. The
            decorative dome + chamber satellites live around it via
            ``ChambersDome`` at the page level. */}
        <motion.div
          className={`relative w-full max-w-xl rounded-3xl border px-6 py-12 transition-all duration-300 md:px-10 md:py-16 ${cardClass}`}
          animate={{ scale: isDragging ? 1.015 : 1 }}
          transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
        >
          <div className="flex flex-col items-center justify-center gap-3 text-center">
            <div
              className={`flex h-14 w-14 items-center justify-center rounded-2xl transition-all duration-300 ${
                isDragging
                  ? 'scale-110 bg-slate-200 dark:bg-slate-800/40'
                  : 'bg-slate-100 group-hover:scale-110 group-hover:bg-slate-200 dark:bg-slate-900/40 dark:group-hover:bg-slate-800/40'
              }`}
            >
              <Icon
                icon="solar:upload-linear"
                className={`h-7 w-7 transition-transform duration-300 ${
                  isDragging
                    ? '-translate-y-1 text-slate-700 dark:text-slate-300'
                    : 'text-slate-500 group-hover:-translate-y-0.5 dark:text-slate-400'
                }`}
                aria-hidden="true"
              />
            </div>
            <span
              className={`mt-1 px-4 text-base font-medium transition-colors duration-300 ${
                isDragging
                  ? 'text-slate-800 dark:text-slate-200'
                  : 'text-slate-700 dark:text-slate-300'
              }`}
            >
              {isDragging ? 'Drop files here' : 'Click or drag files here'}
            </span>
            <span className="rp-text-muted text-xs">
              up to 1 GB · encrypted on your device
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
        </motion.div>
      </div>
    </>
  )
}
