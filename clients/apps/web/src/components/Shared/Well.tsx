import { twMerge } from 'tailwind-merge'

// Shared props pattern for Well and its sub-sections
interface SectionProps {
  className?: string
  children: React.ReactNode
}

// Reusable inner wrapper (header, content, and footer share layout)
const WellSection = ({ children, className }: SectionProps) => (
  <div className={twMerge('flex flex-col gap-y-2', className)}>{children}</div>
)

// ── Exports ──

export type WellProps = SectionProps

export const Well = ({ children, className }: WellProps) => (
  <div
    className={twMerge(
      'flex flex-col gap-y-4 rounded-3xl bg-slate-100 p-8 dark:bg-slate-900',
      className,
    )}
  >
    {children}
  </div>
)

export type WellHeaderProps = SectionProps
export const WellHeader = WellSection

export type WellContentProps = SectionProps
export const WellContent = WellSection

export type WellFooterProps = SectionProps
export const WellFooter = WellSection
