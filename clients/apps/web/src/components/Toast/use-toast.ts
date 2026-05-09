import * as React from 'react'

import { ToastActionElement, type ToastProps } from '.'

// Display at most one toast at a time; dismissed toasts linger for cleanup
const MAX_VISIBLE = 1
const REMOVAL_GRACE_MS = 10_000

type ToasterToast = ToastProps & {
  id: string
  title?: React.ReactNode
  description?: React.ReactNode
  action?: ToastActionElement
}

// Monotonic counter for generating unique toast IDs
let nextId = 0
const createToastId = (): string => {
  nextId = (nextId + 1) % Number.MAX_VALUE
  return String(nextId)
}

// ── Action definitions ──

type ToastAction =
  | { kind: 'push'; toast: ToasterToast }
  | { kind: 'patch'; toast: Partial<ToasterToast> }
  | { kind: 'dismiss'; targetId?: string }
  | { kind: 'drop'; targetId?: string }

interface ToastStoreState {
  toasts: ToasterToast[]
}

// ── Deferred removal scheduling ──

const pendingRemovals = new Map<string, ReturnType<typeof setTimeout>>()

function scheduleRemoval(id: string) {
  if (pendingRemovals.has(id)) return

  const timer = setTimeout(() => {
    pendingRemovals.delete(id)
    emit({ kind: 'drop', targetId: id })
  }, REMOVAL_GRACE_MS)

  pendingRemovals.set(id, timer)
}

// ── State management (external store pattern) ──

export const reducer = (
  prev: ToastStoreState,
  action: ToastAction,
): ToastStoreState => {
  switch (action.kind) {
    case 'push':
      return {
        ...prev,
        toasts: [action.toast, ...prev.toasts].slice(0, MAX_VISIBLE),
      }

    case 'patch':
      return {
        ...prev,
        toasts: prev.toasts.map((t) =>
          t.id === action.toast.id ? { ...t, ...action.toast } : t,
        ),
      }

    case 'dismiss': {
      const id = action.targetId
      if (id) {
        scheduleRemoval(id)
      } else {
        prev.toasts.forEach((t) => scheduleRemoval(t.id))
      }
      return {
        ...prev,
        toasts: prev.toasts.map((t) =>
          t.id === id || id === undefined ? { ...t, open: false } : t,
        ),
      }
    }

    case 'drop':
      return action.targetId === undefined
        ? { ...prev, toasts: [] }
        : {
            ...prev,
            toasts: prev.toasts.filter((t) => t.id !== action.targetId),
          }
  }
}

const subscribers: Array<(s: ToastStoreState) => void> = []
let store: ToastStoreState = { toasts: [] }

function emit(action: ToastAction) {
  store = reducer(store, action)
  for (const fn of subscribers) fn(store)
}

// ── Public API ──

interface ToastInput extends Omit<ToasterToast, 'id'> {}

function toast(props: ToastInput) {
  const id = createToastId()

  const dismiss = () => emit({ kind: 'dismiss', targetId: id })
  const update = (next: ToasterToast) =>
    emit({ kind: 'patch', toast: { ...next, id } })

  emit({
    kind: 'push',
    toast: {
      ...props,
      id,
      open: true,
      onOpenChange: (open: boolean) => {
        if (!open) dismiss()
      },
    },
  })

  return { id, dismiss, update }
}

function useToast() {
  const [snapshot, setSnapshot] = React.useState<ToastStoreState>(store)

  React.useEffect(() => {
    subscribers.push(setSnapshot)
    return () => {
      const idx = subscribers.indexOf(setSnapshot)
      if (idx !== -1) subscribers.splice(idx, 1)
    }
  }, [])

  return {
    ...snapshot,
    toast,
    dismiss: (id?: string) => emit({ kind: 'dismiss', targetId: id }),
  }
}

export { toast, useToast }
