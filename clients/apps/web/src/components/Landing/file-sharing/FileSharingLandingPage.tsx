'use client'

// ── Imports ──

import type { FileSharingFlowState } from '@/components/FileSharing'
import { FileSharingLanding } from '@/components/FileSharing'
import { useAuth } from '@/hooks/auth'
import { Icon } from '@iconify/react'
import { AnimatePresence, motion } from 'framer-motion'
import { useCallback, useEffect, useRef, useState } from 'react'
import { ChamberStrip } from './ChamberStrip'
import { SecretSharingForm, type SecretFormState } from './SecretSharingForm'
import { ShareCounter } from './ShareCounter'
import { StairSection } from './StairSection'

// ── Types ──

type Mode = 'direct' | 'secret'

// ── Constants ──

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
  entranceAnimation = true,
}: {
  showPricing?: boolean
  workspaceId?: string
  onFlowStateChange?: (state: FileSharingFlowState) => void
  entranceAnimation?: boolean
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

  // Track whether the user has switched modes at least once.
  // On first render: CSS fade-in (no JS wait = fast LCP).
  // On mode switches: framer-motion handles the enter/exit animation.
  const isFirstRender = useRef(true)
  const shouldAnimate = !isFirstRender.current
  if (isFirstRender.current && mode !== 'direct') {
    // First switch happened — future renders use framer-motion
    isFirstRender.current = false
  }

  // Mark first render complete after initial mount
  useEffect(() => {
    isFirstRender.current = false
  }, [])

  return (
    <div className="relative flex flex-1 flex-col items-center px-4 pt-4">
      {/* Title — CSS fade-in on first paint, framer-motion on mode switches */}
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={mode}
          className={`relative z-10 mb-6 text-center ${!shouldAnimate && entranceAnimation ? 'animate-fade-in-up' : ''}`}
          initial={shouldAnimate ? { opacity: 0, y: -8 } : false}
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
              entranceAnimation={entranceAnimation}
            >
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  setInitialChar('')
                  setMode('secret')
                  onFlowStateChange?.('confirm')
                }}
                className="rp-text-muted hover:rp-text-secondary mt-3 flex min-h-[44px] items-center gap-x-1.5 text-xs transition-colors"
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

      {/* Chamber badges — Secret is omitted because the card above
          already surfaces the secret entry point via "or type a secret...". */}
      <ChamberStrip excludeIds={['secret']} />

      {/* R3F frosted-glass stair scene — adapted from Paul Henschel's
          raycast cycling stair demo. Only on the initial direct
          landing so the heavy WebGL canvas isn't loading during
          mid-task flows. */}
      {mode === 'direct' && flowState === 'initial' && <StairSection />}
    </div>
  )
}
