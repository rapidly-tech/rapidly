import { FeaturePage } from '@/components/Landing/FeaturePage'
import { CONFIG } from '@/utils/config'
import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Finance',
  description:
    'Track your earnings, manage payouts, and get detailed financial reporting — all in one dashboard.',
  openGraph: {
    siteName: 'Rapidly',
    type: 'website',
    images: [{ url: CONFIG.OG_IMAGE_URL, width: 1200, height: 630 }],
  },
}

const features = [
  {
    icon: 'BarChart3',
    title: 'Revenue Dashboard',
    description:
      'See your earnings at a glance with real-time charts, transaction history, and revenue breakdowns by share.',
  },
  {
    icon: 'Banknote',
    title: 'Automatic Payouts',
    description:
      'Funds are automatically transferred to your bank account on a rolling schedule via Stripe Connect.',
  },
  {
    icon: 'TrendingUp',
    title: 'Performance Insights',
    description:
      'Track which shares drive the most revenue, monitor conversion rates, and identify growth opportunities.',
  },
  {
    icon: 'FileText',
    title: 'Export & Reporting',
    description:
      'Download detailed transaction reports in CSV for accounting, tax filing, or business analysis.',
  },
]

export default function FinanceFeaturePage() {
  return (
    <FeaturePage
      description="Track your earnings, manage payouts, and get detailed financial reporting — all in one dashboard."
      features={features}
      ctaLabel="View Dashboard"
      ctaHref="/login"
      docsHref={CONFIG.DOCS_BASE_URL}
    />
  )
}
