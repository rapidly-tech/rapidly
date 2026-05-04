import { AnimatePresence, motion } from 'framer-motion'
import React, { type FunctionComponent, type JSX } from 'react'
import ReactDOM from 'react-dom'
import FocusLock from 'react-focus-lock'
import { twMerge } from 'tailwind-merge'

export interface InlineModalProps {
  isShown: boolean
  hide: () => void
  modalContent: JSX.Element
  className?: string
}

// Spring config for the slide-in panel
const SLIDE_SPRING = { type: 'spring', stiffness: 300, damping: 30 } as const

function useEscapeDismiss(
  containerRef: React.RefObject<HTMLDivElement | null>,
  active: boolean,
  onDismiss: () => void,
) {
  const handler = React.useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key !== 'Escape' || !active) return
      if (!containerRef.current?.contains(e.target as Node)) return
      onDismiss()
    },
    [active, containerRef, onDismiss],
  )
  return handler
}

function useBodyScrollLock(locked: boolean) {
  React.useEffect(() => {
    if (!locked) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [locked])
}

export const InlineModal: FunctionComponent<InlineModalProps> = ({
  isShown,
  hide,
  modalContent,
  className,
}) => {
  const containerRef = React.useRef<HTMLDivElement>(null)
  const handleKeyDown = useEscapeDismiss(containerRef, isShown, hide)
  useBodyScrollLock(isShown)

  const stopInnerPropagation = (e: React.MouseEvent) => e.stopPropagation()

  const content = (
    <FocusLock>
      <div
        ref={containerRef}
        className="fixed inset-0 z-50 overflow-hidden focus-within:outline-none"
        aria-modal
        tabIndex={-1}
        role="dialog"
        onKeyDown={handleKeyDown}
      >
        <motion.div
          initial={{ backgroundColor: 'rgba(0, 0, 0, 0)' }}
          animate={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
          exit={{ backgroundColor: 'rgba(0, 0, 0, 0)' }}
          className="relative flex h-screen flex-col items-center md:w-full md:flex-row"
          onMouseDown={(e) => {
            e.preventDefault()
            e.stopPropagation()
            hide()
          }}
        >
          <motion.div
            initial={{ x: '100%', opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: '100%', opacity: 0 }}
            transition={SLIDE_SPRING}
            className={twMerge(
              'rp-text-primary relative z-10 flex h-full max-h-full w-full flex-col overflow-y-auto bg-white shadow-sm md:fixed md:top-0 md:right-0 md:bottom-0 md:h-auto md:w-[540px] dark:bg-slate-950',
              className,
            )}
            onMouseDown={stopInnerPropagation}
          >
            {modalContent}
          </motion.div>
        </motion.div>
      </div>
    </FocusLock>
  )

  if (typeof document === 'undefined') return null

  return ReactDOM.createPortal(
    <AnimatePresence>{isShown && content}</AnimatePresence>,
    document.body,
  )
}

// ── Subcomponents ──

const DismissIcon = () => (
  <svg
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M6 18L18 6M6 6L18 18"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

export const CloseButton = ({
  className,
  hide,
}: {
  className?: string
  hide: () => void
}) => (
  <button
    type="button"
    className={twMerge(
      'text-foreground hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-500',
      className,
    )}
    onClick={hide}
    tabIndex={-1}
    aria-label="Close"
  >
    <DismissIcon />
  </button>
)

export const InlineModalHeader = ({
  children,
  className,
  hide,
}: {
  children: React.ReactElement<unknown>
  className?: string
  hide: () => void
}) => (
  <div
    className={twMerge(
      'flex w-full items-center justify-between px-8 py-6',
      className,
    )}
  >
    <div className="text-lg">{children}</div>
    <CloseButton hide={hide} />
  </div>
)
