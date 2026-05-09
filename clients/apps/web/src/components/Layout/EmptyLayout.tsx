import { PropsWithChildren } from 'react'

/** Renders a minimal full-height layout wrapper with no navigation or chrome. */
const EmptyLayout = ({ children }: PropsWithChildren) => {
  return <div className="flex h-full min-h-screen flex-col">{children}</div>
}

export default EmptyLayout
