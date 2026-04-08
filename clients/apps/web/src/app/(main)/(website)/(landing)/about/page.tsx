import { FeaturePage } from '@/components/Landing/FeaturePage'
import { CONFIG } from '@/utils/config'
import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'About',
  description:
    'About Rapidly. Secure P2P file sharing, built by an independent developer.',
}

async function getStarCount(): Promise<number> {
  try {
    const res = await fetch(
      'https://api.github.com/repos/rapidly-tech/rapidly',
      { next: { revalidate: 300 } },
    )
    if (!res.ok) return 0
    const data = await res.json()
    return data.stargazers_count ?? 0
  } catch {
    return 0
  }
}

export default async function CompanyPage() {
  const stars = await getStarCount()

  const aboutText = `I am an independent developer who got tired of uploading my files to servers that use it all to train AI.\n\nSo I built something that doesn't scrape your stuff. No servers holding copies. No training data. No terms of service written by lawyers who hate you.\n\nRapidly sends files directly from your browser to theirs. No server in the middle, no uploads, no storage. Just encrypted P2P transfers that work.\n\nNo account needed. No app to install. No file size limits. You open the link and it works. If you want polished, go use Google Drive and let them read your files.\n\nThe whole thing is open source. You can read every line, contribute, or run it yourself. ${stars} stars on GitHub.`

  return (
    <FeaturePage
      description={'"If it doesn\'t take your breath away, it\'s worthless."'}
      features={[
        {
          icon: 'GitHub',
          title: 'Who Am I?',
          description: aboutText,
          href: 'https://github.com/rapidly-tech/rapidly',
        },
      ]}
      ctaLabel="Star on GitHub"
      ctaHref="https://github.com/rapidly-tech/rapidly"
      docsHref={CONFIG.DOCS_BASE_URL}
    />
  )
}
