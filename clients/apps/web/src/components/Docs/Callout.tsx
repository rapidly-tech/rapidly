import { PropsWithChildren } from 'react'
import { twMerge } from 'tailwind-merge'

type CalloutIntent = 'note' | 'info' | 'tip' | 'warning'

const INTENT_CLASSES: Record<CalloutIntent, string> = {
  note: 'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300',
  info: 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-900/20 dark:text-emerald-300',
  tip: 'border-teal-200 bg-teal-50 text-teal-800 dark:border-teal-900/50 dark:bg-teal-900/20 dark:text-teal-300',
  warning:
    'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/50 dark:bg-amber-900/20 dark:text-amber-300',
}

const INTENT_LABELS: Record<CalloutIntent, string> = {
  note: 'Note',
  info: 'Info',
  tip: 'Tip',
  warning: 'Warning',
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
