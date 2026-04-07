'use client'

// ── Imports ──

import type { FileSharingFlowState } from '@/components/FileSharing'
import { FileSharingLanding } from '@/components/FileSharing'
import { useAuth } from '@/hooks/auth'
import { Icon } from '@iconify/react'
import { AnimatePresence, motion } from 'framer-motion'
import { useCallback, useEffect, useState } from 'react'
import { SecretSharingForm, type SecretFormState } from './SecretSharingForm'
import { ShareCounter } from './ShareCounter'

// ── Types ──

type Mode = 'direct' | 'secret'

// ── Constants ──

const directBadges = [
  { icon: 'solar:lock-linear', label: 'AES-256 Encrypted' },
  { icon: 'solar:shield-check-linear', label: 'Zero Knowledge' },
  { icon: 'solar:infinity-linear', label: 'No Size Limits' },
  { icon: 'solar:transfer-horizontal-linear', label: 'Peer-to-Peer' },
]

const secretBadges = [
  { icon: 'solar:lock-linear', label: 'OpenPGP Encrypted' },
  { icon: 'solar:cloud-linear', label: 'Server-Stored' },
  { icon: 'solar:eye-linear', label: 'One-Time View' },
  { icon: 'solar:trash-bin-trash-linear', label: 'Auto-Delete' },
]

const directTitleContent: Record<
  FileSharingFlowState,
  { title: string; subtitle: string }
> = {
  initial: {
    title: 'Share Files Securely',
    subtitle: 'Encrypted peer-to-peer transfers, directly in your browser',
  },
  confirm: {
    title: 'Configure Transfer',
    subtitle: 'Review your files and set sharing options',
  },
  uploading: {
    title: 'Sharing Active',
    subtitle: 'Your files are ready to download',
  },
}

const secretTitleContent: Record<
  SecretFormState,
  { title: string; subtitle: string }
> = {
  input: {
    title: 'Send Secret',
    subtitle: 'Store an encrypted secret or file for one-time viewing',
  },
  result: {
    title: 'Secret Created',
    subtitle: 'Share the link — it self-destructs after one view',
  },
}

// ── Main Component ──

/** Landing page combining direct peer-to-peer file sharing and encrypted secret sharing with mode switching. */
export const FileSharingLandingPage = ({
  showPricing,
  workspaceId: workspaceIdProp,
  onFlowStateChange,
}: {
  showPricing?: boolean
  workspaceId?: string
  onFlowStateChange?: (state: FileSharingFlowState) => void
} = {}) => {
  const { userWorkspaces } = useAuth()
  const workspaceId = workspaceIdProp ?? userWorkspaces?.[0]?.id
  const [mode, setMode] = useState<Mode>('direct')
  const [flowState, setFlowState] = useState<FileSharingFlowState>('initial')
  const [secretFlowState, setSecretFlowState] =
    useState<SecretFormState>('input')
  const [initialChar, setInitialChar] = useState('')

  const handleStateChange = useCallback(
    (state: FileSharingFlowState) => {
      setFlowState(state)
      onFlowStateChange?.(state)
    },
    [onFlowStateChange],
  )

  const handleSecretStateChange = useCallback((state: SecretFormState) => {
    setSecretFlowState(state)
  }, [])

  const handleBackToFiles = useCallback(() => {
    setMode('direct')
    setInitialChar('')
    onFlowStateChange?.('initial')
  }, [onFlowStateChange])

  // Global keydown: typing triggers secret mode
  useEffect(() => {
    if (mode !== 'direct' || flowState !== 'initial') return

    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (e.ctrlKey || e.metaKey || e.altKey) return
      if (e.key.length !== 1) return

      setInitialChar(e.key)
      setMode('secret')
      onFlowStateChange?.('confirm')
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [mode, flowState, onFlowStateChange])

  // Escape key: return to direct mode from secret input
  useEffect(() => {
    if (mode !== 'secret' || secretFlowState !== 'input') return

    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleBackToFiles()
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [mode, secretFlowState, handleBackToFiles])

  const { title, subtitle } =
    mode === 'direct'
      ? directTitleContent[flowState]
      : secretTitleContent[secretFlowState]

  const activeBadges = mode === 'direct' ? directBadges : secretBadges

  return (
    <div className="relative flex flex-1 flex-col items-center px-4 pt-4">
      {/* Title — animate only on mode switch (direct↔secret), stay static within a mode */}
      <AnimatePresence mode="wait">
        <motion.div
          key={mode}
          className="relative z-10 mb-6 text-center"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0, transition: { duration: 0.3 } }}
          exit={{ opacity: 0, y: 8, transition: { duration: 0.15 } }}
        >
          <h1 className="rp-text-primary text-3xl leading-tight! font-semibold tracking-tight md:text-5xl">
            {title}
          </h1>
          <p className="rp-text-secondary mt-4 text-base font-medium tracking-wide">
            {subtitle}
          </p>
        </motion.div>
      </AnimatePresence>

      {/* Content */}
      <div className="relative w-full max-w-2xl">
        {mode === 'direct' ? (
          <div>
            <FileSharingLanding
              onStateChange={handleStateChange}
              workspaceId={workspaceId}
              showPricing={showPricing}
            >
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  setInitialChar('')
                  setMode('secret')
                  onFlowStateChange?.('confirm')
                }}
                className="rp-text-muted hover:rp-text-secondary mt-3 flex items-center gap-x-1.5 text-xs transition-colors"
              >
                <Icon icon="solar:lock-linear" className="h-3.5 w-3.5" />
                or type a secret...
              </button>
            </FileSharingLanding>
          </div>
        ) : (
          <div>
            <SecretSharingForm
              onStateChange={handleSecretStateChange}
              initialValue={initialChar}
              workspaceId={workspaceId}
              showPricing={showPricing}
            />
          </div>
        )}
      </div>

      {/* Live share counter */}
      <div className="relative z-20 flex items-center justify-center py-8">
        <ShareCounter workspaceId={workspaceId} />
      </div>

      {/* Trust badges */}
      <AnimatePresence mode="wait">
        <motion.div
          key={mode}
          className="relative z-10 mx-auto grid grid-cols-2 gap-3 pt-4 pb-4 md:flex md:flex-wrap md:items-center md:justify-center"
          initial={{ opacity: 0, y: 8 }}
          animate={{
            opacity: 1,
            y: 0,
            transition: { duration: 0.3, delay: 0.1 },
          }}
          exit={{ opacity: 0, y: 8, transition: { duration: 0.2 } }}
        >
          {activeBadges.map((badge) => (
            <motion.div
              key={badge.label}
              className="glass-subtle flex items-center justify-center gap-x-2 rounded-full px-4 py-2"
              whileHover={{ scale: 1.06, y: -2 }}
              transition={{ type: 'spring', stiffness: 400, damping: 17 }}
            >
              <Icon
                icon={badge.icon}
                className="h-3.5 w-3.5 text-slate-500 dark:text-slate-400"
              />
              <span className="rp-text-secondary text-xs font-medium">
                {badge.label}
              </span>
            </motion.div>
          ))}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
