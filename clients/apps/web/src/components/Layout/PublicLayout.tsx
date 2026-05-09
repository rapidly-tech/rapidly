import { PropsWithChildren } from 'react'
import { twMerge } from 'tailwind-merge'
import Footer from '../Workspace/Footer'
import EmptyLayout from './EmptyLayout'

/** Renders the public-facing page layout with centered content, optional wide mode, and footer. */
const PublicLayout = ({
  children,
  wide,
  className,
  footer = true,
}: PropsWithChildren<{
  wide?: boolean
  className?: string
  footer?: boolean
}>) => {
  return (
    <EmptyLayout>
      <div
        className={twMerge(
          'mx-auto mb-16 flex w-full flex-col space-y-8 px-4 md:mt-12 md:mb-24 md:space-y-12',
          wide ? 'max-w-7xl' : 'max-w-[970px]',
          className,
        )}
      >
        {children}
      </div>
      {footer && <Footer />}
    </EmptyLayout>
  )
}

export default PublicLayout
