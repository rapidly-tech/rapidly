/**
 * Global toast notification provider for the Rapidly mobile app.
 *
 * Exposes showInfo / showSuccess / showError / showWarning helpers via
 * the useToast hook. Non-persistent toasts auto-dismiss after 2 seconds.
 */
import { Toast, ToastType } from '@/components/Shared/Toast'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react'

const DISMISS_DELAY_MS = 2000
const TOAST_BOTTOM_OFFSET = 30

interface DisplayOptions {
  persistent?: boolean
}

interface ToastEntry {
  id: number
  message: string
  type: ToastType
  persistent: boolean
}

interface ToastAPI {
  showInfo: (message: string, opts?: DisplayOptions) => void
  showSuccess: (message: string, opts?: DisplayOptions) => void
  showError: (message: string, opts?: DisplayOptions) => void
  showWarning: (message: string, opts?: DisplayOptions) => void
  dismiss: () => void
}

const ToastCtx = createContext<ToastAPI | null>(null)

export const useToast = (): ToastAPI => {
  const ctx = useContext(ToastCtx)
  if (!ctx) throw new Error('useToast must be used within a ToastProvider')
  return ctx
}

export const ToastProvider = ({ children }: { children: React.ReactNode }) => {
  const [entry, setEntry] = useState<ToastEntry | null>(null)
  const [shown, setShown] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const nextId = useRef(0)

  const cancelTimer = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current)
      timer.current = null
    }
  }, [])

  const dismiss = useCallback(() => {
    cancelTimer()
    setShown(false)
    setTimeout(() => setEntry(null), 200)
  }, [cancelTimer])

  const present = useCallback(
    (message: string, type: ToastType, opts?: DisplayOptions) => {
      cancelTimer()

      const persistent = opts?.persistent ?? false
      const id = ++nextId.current

      setEntry({ id, message, type, persistent })
      setShown(true)

      if (!persistent) {
        timer.current = setTimeout(dismiss, DISMISS_DELAY_MS)
      }
    },
    [cancelTimer, dismiss],
  )

  const showInfo = useCallback(
    (msg: string, opts?: DisplayOptions) => present(msg, 'info', opts),
    [present],
  )
  const showSuccess = useCallback(
    (msg: string, opts?: DisplayOptions) => present(msg, 'success', opts),
    [present],
  )
  const showError = useCallback(
    (msg: string, opts?: DisplayOptions) => present(msg, 'error', opts),
    [present],
  )
  const showWarning = useCallback(
    (msg: string, opts?: DisplayOptions) => present(msg, 'warning', opts),
    [present],
  )

  useEffect(() => () => cancelTimer(), [cancelTimer])

  const api: ToastAPI = {
    showInfo,
    showSuccess,
    showError,
    showWarning,
    dismiss,
  }

  return (
    <ToastCtx.Provider value={api}>
      {children}
      {entry ? (
        <Toast
          key={entry.id}
          message={entry.message}
          type={entry.type}
          persistent={entry.persistent}
          visible={shown}
          onDismiss={dismiss}
          bottomOffset={TOAST_BOTTOM_OFFSET}
        />
      ) : null}
    </ToastCtx.Provider>
  )
}
