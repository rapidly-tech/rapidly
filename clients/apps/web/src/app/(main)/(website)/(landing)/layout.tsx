import { PropsWithChildren } from 'react'
import LandingLayout from '../../../../components/Landing/LandingLayout'

export const dynamic = 'force-static'
export const dynamicParams = false

const LandingPageLayout = ({ children }: PropsWithChildren) => (
  <LandingLayout>{children}</LandingLayout>
)

export default LandingPageLayout
