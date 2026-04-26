/**
 * Top-level section wrapper with an optional anchor `id`.
 * Provides consistent vertical spacing between settings blocks.
 */
export const Section = ({
  id,
  children,
}: {
  id?: string
  children: React.ReactNode
}) => (
  <div className="relative flex flex-col gap-4" id={id}>
    {children}
  </div>
)

/**
 * Section header that renders a title and an optional description line.
 */
export const SectionDescription = ({
  title,
  description,
}: {
  title: string
  description?: string
}) => (
  <div className="flex w-full flex-col gap-1">
    <h2 className="text-lg font-medium">{title}</h2>
    {description && (
      <p className="text-balance text-slate-500 dark:text-slate-400">
        {description}
      </p>
    )}
  </div>
)
