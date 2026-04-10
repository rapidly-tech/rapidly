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

  const aboutText = `I actually read the fine print of a popular file transfer service once and yeah that was a bad idea. Turns out they can do whatever they want with your files including feed them to AI.\n\nSo I made rapidly.tech. Send files straight from your browser to whoever you want, nothing gets stored anywhere, no copies floating around on some server.\n\nNo signup, no app to download, no weird limits. It just works.\n\nThe code is all open source because why would you trust some random guy on the internet. ${stars} stars on GitHub.`

  return (
    <FeaturePage
      description={"Hey, I'm VU"}
      features={[
        {
          icon: 'GitHub',
          title: 'Why I Built This',
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
