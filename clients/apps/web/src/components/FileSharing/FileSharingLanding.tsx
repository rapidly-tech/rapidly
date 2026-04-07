'use client'

// ── Imports ──

import {
  FILE_SHARING_MAX_PRICE_CENTS,
  FILE_SHARING_MIN_PRICE_CENTS,
  PaymentConfigSection,
} from '@/components/FileSharing/PaymentConfigSection'
import { toast } from '@/components/Toast/use-toast'
import { hashPassword } from '@/utils/file-sharing'
import {
  LARGE_FILE_THRESHOLD,
  VERY_LARGE_FILE_THRESHOLD,
} from '@/utils/file-sharing/constants'
import { UploadedFile } from '@/utils/file-sharing/types'
import { Checkbox } from '@rapidly-tech/ui/components/primitives/checkbox'
import { AnimatePresence, motion } from 'framer-motion'
import React, { JSX, useCallback, useEffect, useMemo, useState } from 'react'
import AddFilesButton from './AddFilesButton'
import DropZone from './DropZone'
import Loading from './Loading'
import StartButton from './StartButton'
import Uploader from './Uploader'
import UploadFileList, { formatFileSize } from './UploadFileList'

// ── Types and Constants ──

type AppState =
  | { type: 'initial' }
  | {
      type: 'confirm'
      files: UploadedFile[]
      title: string
      maxDownloads: number
      priceCents: number | null
      currency: string
    }
  | {
      type: 'uploading'
      files: UploadedFile[]
      title: string
      password: string
      maxDownloads: number
      priceCents: number | null
      currency: string
    }

export type FileSharingFlowState = 'initial' | 'confirm' | 'uploading'

const stateTransition = {
  initial: { opacity: 0, y: 12, filter: 'blur(4px)' },
  animate: {
    opacity: 1,
    y: 0,
    filter: 'blur(0px)',
    transition: { duration: 0.4 },
  },
  exit: {
    opacity: 0,
    y: -12,
    filter: 'blur(4px)',
    transition: { duration: 0.25 },
  },
}

const DOWNLOAD_LIMIT_OPTIONS = [
  { value: 1, label: '1 download' },
  { value: 5, label: '5 downloads' },
  { value: 10, label: '10 downloads' },
  { value: 0, label: 'Unlimited' }, // 0 means unlimited
]

// ── Initial State ──

function InitialState({
  onFilesSelected,
  onProcessingChange,
  children,
}: {
  onFilesSelected: (files: UploadedFile[]) => void
  onProcessingChange?: (processing: boolean) => void
  children?: React.ReactNode
}): JSX.Element {
  return (
    <div className="mx-auto w-full max-w-2xl">
      <DropZone
        onDrop={onFilesSelected}
        onProcessingChange={onProcessingChange}
      >
        {children}
      </DropZone>
    </div>
  )
}

// ── Confirm Upload State ──

function ConfirmUploadState({
  files,
  title,
  maxDownloads,
  priceCents,
  currency,
  showPricing,
  workspaceId,
  onTitleChange,
  onMaxDownloadsChange,
  onPriceCentsChange,
  onCurrencyChange,
  onStart,
  onAddFiles,
}: {
  files: UploadedFile[]
  title: string
  maxDownloads: number
  priceCents: number | null
  currency: string
  showPricing?: boolean
  workspaceId?: string
  onTitleChange: (title: string) => void
  onMaxDownloadsChange: (limit: number) => void
  onPriceCentsChange: (cents: number | null) => void
  onCurrencyChange: (currency: string) => void
  onStart: (password: string) => void
  onAddFiles: (files: UploadedFile[]) => void
}): JSX.Element {
  const [usePassword, setUsePassword] = useState(false)
  const [password, setPassword] = useState('')
  const [usePayment, setUsePayment] = useState(priceCents !== null)

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()
      if (!title.trim()) {
        toast({ title: 'Please enter a title', variant: 'error' })
        return
      }
      if (usePassword && !password.trim()) return
      if (
        usePayment &&
        (priceCents === null ||
          priceCents < FILE_SHARING_MIN_PRICE_CENTS ||
          priceCents > FILE_SHARING_MAX_PRICE_CENTS)
      )
        return
      onStart(usePassword ? password : '')
    },
    [onStart, title, usePassword, password, usePayment, priceCents],
  )

  const handlePaymentToggle = useCallback(
    (checked: boolean) => {
      setUsePayment(checked)
      if (!checked) {
        onPriceCentsChange(null)
      }
    },
    [onPriceCentsChange],
  )

  const filesInfo = useMemo(
    () => files.map((f) => ({ fileName: f.name, size: f.size, type: f.type })),
    [files],
  )

  const totalSize = useMemo(
    () => files.reduce((sum, f) => sum + f.size, 0),
    [files],
  )
  const isLargeTransfer = totalSize >= LARGE_FILE_THRESHOLD
  const isVeryLargeTransfer = totalSize >= VERY_LARGE_FILE_THRESHOLD

  return (
    <div className="flex w-full flex-col gap-y-6">
      <form onSubmit={handleSubmit} noValidate>
        <div className="flex w-full flex-col gap-4">
          {/* Title field — on top, always visible and required */}
          <div className="flex flex-col gap-2">
            <label
              htmlFor="file-share-title"
              className="text-sm text-slate-500 dark:text-slate-400"
            >
              Title <span className="text-red-500">*</span>
            </label>
            <input
              id="file-share-title"
              type="text"
              value={title}
              onChange={(e) => onTitleChange(e.target.value)}
              placeholder={
                files.length === 1 ? files[0].name : `${files.length} files`
              }
              maxLength={255}
              className="bg-surface-inset rp-text-primary placeholder:rp-text-muted w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:ring-2 focus:ring-slate-400 focus:outline-none dark:border-slate-800 dark:focus:ring-slate-500"
            />
          </div>

          {/* Total size display */}
          <div className="text-center text-sm text-slate-500 dark:text-slate-400">
            {files.length} {files.length === 1 ? 'file' : 'files'} —{' '}
            {formatFileSize(totalSize)}
          </div>

          {/* Large file warning */}
          {isLargeTransfer && (
            <div className="flex items-start gap-x-2 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:bg-amber-900/20 dark:text-amber-400">
              <div>
                <p className="mb-1 font-medium">
                  {isVeryLargeTransfer
                    ? 'Very large transfer'
                    : 'Large transfer'}
                </p>
                <p className="text-xs">
                  {isVeryLargeTransfer
                    ? 'Transfers over 1 GB may be slow or unreliable over peer-to-peer connections. Consider splitting into smaller files.'
                    : 'Large files work best when both devices are on the same network or have good internet connections.'}
                </p>
              </div>
            </div>
          )}

          {/* Many files warning */}
          {files.length >= 5000 && (
            <div className="flex items-start gap-x-2 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:bg-amber-900/20 dark:text-amber-400">
              <div>
                <p className="mb-1 font-medium">Large number of files</p>
                <p className="text-xs">
                  Folders with over 10,000 files may not transfer completely due
                  to browser limitations. Consider compressing the folder into a
                  zip file first.
                </p>
              </div>
            </div>
          )}

          {/* Download limit selector */}
          <div className="flex flex-col gap-2">
            <span
              id="download-limit-label"
              className="text-sm text-slate-500 dark:text-slate-400"
            >
              Download limit
            </span>
            <div
              className="flex flex-wrap gap-2"
              role="radiogroup"
              aria-labelledby="download-limit-label"
            >
              {DOWNLOAD_LIMIT_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  role="radio"
                  aria-checked={maxDownloads === option.value}
                  onClick={() => onMaxDownloadsChange(option.value)}
                  className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
                    maxDownloads === option.value
                      ? 'border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900'
                      : 'bg-surface-inset border-slate-200 text-slate-600 hover:border-slate-400 dark:border-slate-800 dark:text-slate-400 dark:hover:border-slate-500'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {maxDownloads === 0
                ? 'Anyone with the link can download while you keep this page open'
                : `Link will stop working after ${maxDownloads} successful download${maxDownloads > 1 ? 's' : ''}`}
            </p>
          </div>

          {/* Optional password */}
          <div className="flex flex-col gap-2">
            <label className="flex cursor-pointer items-center gap-2">
              <Checkbox
                checked={usePassword}
                onCheckedChange={(checked) => setUsePassword(checked === true)}
              />
              <span className="text-sm text-slate-500 dark:text-slate-400">
                Password protect
              </span>
            </label>
            {usePassword && (
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter a password"
                autoComplete="off"
                aria-label="Password"
                className="bg-surface-inset rp-text-primary placeholder:rp-text-muted w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:ring-2 focus:ring-slate-400 focus:outline-none dark:border-slate-800 dark:focus:ring-slate-500"
                autoFocus
              />
            )}
          </div>

          {/* Require payment — only shown in dashboard */}
          <PaymentConfigSection
            showPricing={showPricing}
            workspaceId={workspaceId}
            usePayment={usePayment}
            priceCents={priceCents}
            currency={currency}
            onPaymentToggle={handlePaymentToggle}
            onPriceCentsChange={onPriceCentsChange}
            onCurrencyChange={onCurrencyChange}
          />

          <StartButton />

          <div className="flex justify-center">
            <AddFilesButton onAdd={onAddFiles} />
          </div>

          <UploadFileList files={filesInfo} />
        </div>
      </form>
    </div>
  )
}

// ── Uploading State ──

function UploadingState({
  files,
  title,
  password,
  maxDownloads,
  priceCents,
  currency,
  workspaceId,
  onStop,
}: {
  files: UploadedFile[]
  title: string
  password: string
  maxDownloads: number
  priceCents: number | null
  currency: string
  workspaceId?: string
  onStop: () => void
}): JSX.Element {
  return (
    <Uploader
      files={files}
      password={password}
      maxDownloads={maxDownloads}
      title={title || undefined}
      priceCents={priceCents}
      currency={currency}
      workspaceId={workspaceId}
      onStop={onStop}
    />
  )
}

// ── Main Component ──

/** Multi-step file sharing flow managing file selection, upload configuration, and active sharing state. */
export default function FileSharingLanding({
  onStateChange,
  showPricing,
  workspaceId,
  children,
}: {
  onStateChange?: (state: FileSharingFlowState) => void
  showPricing?: boolean
  workspaceId?: string
  children?: React.ReactNode
} = {}): JSX.Element {
  const [state, setState] = useState<AppState>({ type: 'initial' })
  const [isProcessing, setIsProcessing] = useState(false)

  useEffect(() => {
    onStateChange?.(state.type)
  }, [state.type, onStateChange])

  const handleFilesSelected = useCallback((files: UploadedFile[]) => {
    if (files.length > 0) {
      setState({
        type: 'confirm',
        files,
        title: '',
        maxDownloads: 1,
        priceCents: null,
        currency: 'usd',
      })
    }
  }, [])

  const handleAddFiles = useCallback((newFiles: UploadedFile[]) => {
    setState((prev) => {
      if (prev.type === 'confirm') {
        return {
          ...prev,
          files: [...prev.files, ...newFiles],
        }
      }
      return prev
    })
  }, [])

  const handleTitleChange = useCallback((title: string) => {
    setState((prev) => {
      if (prev.type === 'confirm') {
        return { ...prev, title }
      }
      return prev
    })
  }, [])

  const handleMaxDownloadsChange = useCallback((limit: number) => {
    setState((prev) => {
      if (prev.type === 'confirm') {
        return { ...prev, maxDownloads: limit }
      }
      return prev
    })
  }, [])

  const handlePriceCentsChange = useCallback((cents: number | null) => {
    setState((prev) => {
      if (prev.type === 'confirm') {
        return { ...prev, priceCents: cents }
      }
      return prev
    })
  }, [])

  const handleCurrencyChange = useCallback((currency: string) => {
    setState((prev) => {
      if (prev.type === 'confirm') {
        return { ...prev, currency }
      }
      return prev
    })
  }, [])

  const handleStart = useCallback(async (rawPassword: string) => {
    // Hash the password so browser history only shows an opaque 64-char hex string
    // Empty string means no password protection
    const password = rawPassword ? await hashPassword(rawPassword) : ''
    setState((prev) => {
      if (prev.type !== 'confirm') return prev
      return {
        type: 'uploading',
        files: prev.files,
        title: prev.title,
        password,
        maxDownloads: prev.maxDownloads,
        priceCents: prev.priceCents,
        currency: prev.currency,
      }
    })
  }, [])

  const handleStop = useCallback(() => {
    setState({ type: 'initial' })
  }, [])

  return (
    <AnimatePresence mode="wait">
      {state.type === 'initial' && isProcessing && (
        <motion.div key="processing" {...stateTransition}>
          <div className="flex min-h-[300px] items-center justify-center">
            <Loading text="Reading files…" />
          </div>
        </motion.div>
      )}
      {state.type === 'initial' && !isProcessing && (
        <motion.div key="initial" {...stateTransition}>
          <InitialState
            onFilesSelected={handleFilesSelected}
            onProcessingChange={setIsProcessing}
          >
            {children}
          </InitialState>
        </motion.div>
      )}
      {state.type === 'confirm' && (
        <motion.div key="confirm" {...stateTransition}>
          <ConfirmUploadState
            files={state.files}
            title={state.title}
            maxDownloads={state.maxDownloads}
            priceCents={state.priceCents}
            currency={state.currency}
            showPricing={showPricing}
            workspaceId={workspaceId}
            onTitleChange={handleTitleChange}
            onMaxDownloadsChange={handleMaxDownloadsChange}
            onPriceCentsChange={handlePriceCentsChange}
            onCurrencyChange={handleCurrencyChange}
            onStart={handleStart}
            onAddFiles={handleAddFiles}
          />
        </motion.div>
      )}
      {state.type === 'uploading' && (
        <motion.div key="uploading" {...stateTransition}>
          <UploadingState
            files={state.files}
            title={state.title}
            password={state.password}
            maxDownloads={state.maxDownloads}
            priceCents={state.priceCents}
            currency={state.currency}
            workspaceId={workspaceId}
            onStop={handleStop}
          />
        </motion.div>
      )}
    </AnimatePresence>
  )
}
