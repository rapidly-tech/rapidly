import { PropsWithChildren } from 'react'
import { twMerge } from 'tailwind-merge'

type CalloutIntent = 'note' | 'info' | 'tip' | 'warning' | 'danger'

const INTENT_CLASSES: Record<CalloutIntent, string> = {
  note: 'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300',
  info: 'border-slate-300 bg-slate-900/5 text-slate-800 dark:border-slate-700 dark:bg-white/5 dark:text-slate-200',
  tip: 'border-slate-300 bg-slate-900/5 text-slate-800 dark:border-slate-700 dark:bg-white/5 dark:text-slate-200',
  warning:
    'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/50 dark:bg-amber-900/20 dark:text-amber-300',
  danger:
    'border-red-200 bg-red-50 text-red-800 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300',
}

const INTENT_LABELS: Record<CalloutIntent, string> = {
  note: 'Note',
  info: 'Info',
  tip: 'Tip',
  warning: 'Warning',
  danger: 'Danger',
}

const Callout = ({
  intent,
  children,
}: PropsWithChildren<{ intent: CalloutIntent }>) => (
  <div
    className={twMerge(
      'docs-callout my-4 rounded-lg border px-4 py-3 text-sm',
      INTENT_CLASSES[intent],
    )}
  >
    <span className="font-medium">{INTENT_LABELS[intent]}: </span>
    {children}
  </div>
)

export const Note = ({ children }: PropsWithChildren) => (
  <Callout intent="note">{children}</Callout>
)

export const Info = ({ children }: PropsWithChildren) => (
  <Callout intent="info">{children}</Callout>
)

export const Tip = ({ children }: PropsWithChildren) => (
  <Callout intent="tip">{children}</Callout>
)

export const Warning = ({ children }: PropsWithChildren) => (
  <Callout intent="warning">{children}</Callout>
)

export const Danger = ({ children }: PropsWithChildren) => (
  <Callout intent="danger">{children}</Callout>
)
