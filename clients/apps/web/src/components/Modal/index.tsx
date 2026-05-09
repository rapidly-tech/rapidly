import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { motion } from 'framer-motion'
import React, { type FunctionComponent, type JSX } from 'react'
import ReactDOM from 'react-dom'
import FocusLock from 'react-focus-lock'
import { twMerge } from 'tailwind-merge'

export interface ModalProps {
  title: string
  isShown: boolean
  hide: () => void
  modalContent: JSX.Element
  className?: string
}

// Shared entrance animation preset
const ENTRANCE_ANIM = {
  initial: { opacity: 0, scale: 0.99 },
  animate: { opacity: 1, scale: 1 },
  transition: { duration: 0.1, ease: 'easeInOut' },
} as const

// Dismiss icon used by CloseButton and ModalHeader
const CrossIcon = () => (
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

export const CloseButton = ({ hide }: { hide: () => void }) => (
  <Button variant="ghost" size="icon" onClick={hide}>
    <CrossIcon />
  </Button>
)

function useScrollLockAndEscape(
  ref: React.RefObject<HTMLDivElement | null>,
  visible: boolean,
  onClose: () => void,
) {
  React.useEffect(() => {
    if (!visible) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [visible])

  return React.useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key !== 'Escape' || !visible) return
      if (!ref.current?.contains(e.target as Node)) return
      onClose()
    },
    [onClose, visible, ref],
  )
}

export const Modal: FunctionComponent<ModalProps> = ({
  title,
  isShown,
  hide,
  modalContent,
  className,
}) => {
  const dialogRef = React.useRef<HTMLDivElement>(null)
  const handleKeyDown = useScrollLockAndEscape(dialogRef, isShown, hide)

  if (!isShown) return null

  const dialog = (
    <FocusLock>
      <div
        ref={dialogRef}
        className="rp-text-primary fixed top-0 right-0 bottom-0 left-0 z-50 overflow-hidden focus-within:outline-none"
        aria-modal
        tabIndex={-1}
        role="dialog"
        onKeyDown={handleKeyDown}
      >
        <div
          className="flex h-full flex-col items-center bg-black/70 p-2 md:w-full"
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()
            hide()
          }}
        >
          <div className="block h-20 w-2 lg:max-h-[10%] lg:grow-2" />

          <motion.div
            className={twMerge(
              'relative z-10 flex max-h-full w-full flex-col gap-y-1 overflow-x-hidden overflow-y-auto rounded-3xl bg-slate-100 p-1 shadow-sm lg:w-[800px] lg:max-w-full dark:border dark:border-slate-900 dark:bg-slate-950',
              className,
            )}
            {...ENTRANCE_ANIM}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Title bar */}
            <div className="flex flex-row items-center justify-between pt-1 pr-1 pb-0 pl-4 text-sm">
              <span className="text-slate-500">{title}</span>
              <Button
                variant="ghost"
                size="sm"
                className="size-8 rounded-full text-slate-500 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-400"
                onClick={hide}
                aria-label="Close"
              >
                <Icon icon="solar:close-circle-linear" className="text-[1em]" />
              </Button>
            </div>

            {/* Content area */}
            <div className="flex flex-col overflow-y-auto rounded-[20px] bg-white dark:bg-slate-950">
              {modalContent}
            </div>
          </motion.div>
        </div>
      </div>
    </FocusLock>
  )

  return ReactDOM.createPortal(dialog, document.body)
}

export const ModalHeader = ({
  children,
  className,
  hide,
}: {
  children: React.ReactNode
  className?: string
  hide: () => void
}) => (
  <div
    className={twMerge(
      'flex w-full items-center justify-between border-b px-5 py-3 dark:bg-slate-900 dark:text-slate-400',
      className,
    )}
  >
    <div>{children}</div>
    <CloseButton hide={hide} />
  </div>
)

export const ModalBox = ({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) => (
  <div
    className={twMerge(
      'z-0 flex h-full w-full flex-col space-y-2 overflow-hidden rounded-2xl bg-slate-50 p-5 shadow-2xl dark:bg-slate-800',
      className,
    )}
  >
    {children}
  </div>
)
