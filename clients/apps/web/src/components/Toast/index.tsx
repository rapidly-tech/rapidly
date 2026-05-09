import { Icon } from '@iconify/react'
import * as Primitives from '@radix-ui/react-toast'
import { cva, VariantProps } from 'class-variance-authority'
import * as React from 'react'

// Re-export the provider directly
const ToastProvider = Primitives.Provider

// ── Viewport ──

const ToastViewport = ({
  ref,
  ...props
}: React.ComponentProps<typeof Primitives.Viewport>) => (
  <Primitives.Viewport
    ref={ref}
    className="fixed top-0 z-100 flex max-h-screen w-full flex-col-reverse p-4 sm:top-auto sm:right-4 sm:bottom-4 sm:flex-col sm:p-0 md:right-10 md:bottom-10 md:max-w-[420px]"
    {...props}
  />
)
ToastViewport.displayName = 'ToastViewport'

// ── Variant styles ──

const VARIANT_BASE =
  'bg-slate-100 dark:bg-slate-950 border border-transparent dark:border-slate-800'

const toastVariants = cva(
  'data-[swipe=move]:transition-none group relative pointer-events-auto flex w-full items-center justify-between space-x-4 overflow-hidden rounded-2xl p-1 shadow-[0_8px_40px_rgba(0,0,0,0.06)] transition-all data-[swipe=move]:translate-x-(--radix-toast-swipe-move-x) data-[swipe=cancel]:translate-x-0 data-[swipe=end]:translate-x-(--radix-toast-swipe-end-x) data-[state=open]:animate-in data-[state=closed]:animate-out data-[swipe=end]:animate-out data-[state=closed]:fade-out-80 data-[state=open]:slide-in-from-top-full data-[state=open]:sm:slide-in-from-bottom-full data-[state=closed]:slide-out-to-bottom-full',
  {
    variants: {
      variant: {
        default: VARIANT_BASE,
        error: VARIANT_BASE,
        success: VARIANT_BASE,
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

// ── Toast root ──

const Toast = ({
  ref,
  variant,
  ...props
}: React.ComponentProps<typeof Primitives.Root> &
  VariantProps<typeof toastVariants>) => (
  <Primitives.Root
    ref={ref}
    className={toastVariants({ variant })}
    {...props}
  />
)
Toast.displayName = 'Toast'

// ── Action button ──

const ToastAction = ({
  ref,
  ...props
}: React.ComponentProps<typeof Primitives.Action>) => (
  <Primitives.Action
    ref={ref}
    className="inline-flex h-8 shrink-0 items-center justify-center rounded-md border border-slate-200 bg-slate-100 px-3 text-sm font-medium transition-colors group-[.error]:border-red-200 group-[.error]:bg-red-100 group-[.success]:border-emerald-200 group-[.success]:bg-emerald-100 hover:bg-slate-200/75 group-[.error]:hover:bg-red-200/50 group-[.success]:hover:bg-emerald-200/50 disabled:pointer-events-none disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:group-[.error]:border-red-800 dark:group-[.error]:bg-red-900/30 dark:group-[.success]:border-emerald-800 dark:group-[.success]:bg-emerald-900/30 dark:hover:bg-slate-700 dark:group-[.error]:hover:bg-red-900/50 dark:group-[.success]:hover:bg-emerald-900/50"
    {...props}
  />
)
ToastAction.displayName = 'ToastAction'

// ── Close button ──

const ToastClose = ({
  ref,
  ...props
}: React.ComponentProps<typeof Primitives.Close>) => (
  <Primitives.Close
    ref={ref}
    className="absolute top-1.5 right-1.5 inline-flex size-7 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-600 dark:text-slate-500 dark:hover:bg-slate-800 dark:hover:text-slate-300"
    toast-close=""
    {...props}
  >
    <Icon icon="solar:close-circle-linear" className="h-4 w-4" />
  </Primitives.Close>
)
ToastClose.displayName = 'ToastClose'

// ── Title ──

const ToastTitle = ({
  ref,
  ...props
}: React.ComponentProps<typeof Primitives.Title>) => (
  <Primitives.Title ref={ref} className="text-sm font-medium" {...props} />
)
ToastTitle.displayName = 'ToastTitle'

// ── Description ──

const ToastDescription = ({
  ref,
  ...props
}: React.ComponentProps<typeof Primitives.Description>) => (
  <Primitives.Description ref={ref} className="text-sm opacity-80" {...props} />
)
ToastDescription.displayName = 'ToastDescription'

// ── Type exports ──

type ToastProps = React.ComponentPropsWithoutRef<typeof Toast>
type ToastActionElement = React.ReactElement<typeof ToastAction>

export {
  Toast,
  ToastAction,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
  type ToastActionElement,
  type ToastProps,
}
