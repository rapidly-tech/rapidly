import ProseWrapper from '@/components/MDX/ProseWrapper'
import { PropsWithChildren } from 'react'

export const dynamic = 'force-static'
export const dynamicParams = false

const WRAPPER_CLASSES = 'flex flex-col items-center md:w-full lg:max-w-6xl!'

const MdxPageLayout = ({ children }: PropsWithChildren) => (
  <div className="flex flex-col items-center md:w-full">
    <ProseWrapper className={WRAPPER_CLASSES}>{children}</ProseWrapper>
  </div>
)

export default MdxPageLayout
