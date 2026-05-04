import { FeaturePage } from '@/components/Landing/FeaturePage'
import { CONFIG } from '@/utils/config'
import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Payments',
  description:
    'Accept payments for your file shares with Stripe. Set your price, share a link, get paid instantly.',
  openGraph: {
    siteName: 'Rapidly',
    type: 'website',
    images: [{ url: CONFIG.OG_IMAGE_URL, width: 1200, height: 630 }],
  },
}

const features = [
  {
    icon: 'CreditCard',
    title: 'Stripe-Powered',
    description:
      'Accept credit cards, debit cards, and other payment methods through Stripe. Secure, reliable, and globally trusted.',
  },
  {
    icon: 'Zap',
    title: 'Instant Setup',
    description:
      'Connect your Stripe account and start accepting payments in minutes. No complex integrations required.',
  },
  {
    icon: 'Globe',
    title: 'Global Reach',
    description:
      'Accept payments from customers worldwide with automatic currency conversion and localized payment methods.',
  },
  {
    icon: 'ShieldCheck',
    title: 'Secure Checkout',
    description:
      'Buyers pay through a secure Stripe-hosted checkout. Files are only delivered after successful payment.',
  },
]

export default function PaymentsFeaturePage() {
  return (
    <FeaturePage
      description="Accept payments for your file shares with Stripe. Set your price, share a link, get paid instantly."
      features={features}
      ctaLabel="Start Selling"
      ctaHref="/login"
      docsHref={CONFIG.DOCS_BASE_URL}
    />
  )
}
