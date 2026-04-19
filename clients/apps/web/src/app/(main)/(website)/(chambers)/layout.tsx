import { PropsWithChildren } from 'react'

import LandingLayout from '@/components/Landing/LandingLayout'

// Wraps every chamber page (Files dashboard lives on its own; this
// layout is for Secret, Screen, Watch, Call, Collab + their per-slug
// guest views) in the landing chrome: RapidlyLogotype in the topbar,
// features nav, docs nav, footer. Without this, chamber hosts render
// on a bare beige page with just the action card — no branding, no
// way to navigate elsewhere on the site.
//
// Intentionally does NOT use ``export const dynamic = 'force-static'``
// the way ``(landing)/layout.tsx`` does — chamber sessions use
// per-request dynamic segments (``/chamber/[slug]``) and runtime
// config, which force-static would break.
const ChambersLayout = ({ children }: PropsWithChildren) => (
  <LandingLayout>{children}</LandingLayout>
)

export default ChambersLayout
