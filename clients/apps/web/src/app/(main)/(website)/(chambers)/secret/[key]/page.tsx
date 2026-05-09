import { Metadata } from 'next'
import SecretClient from './SecretClient'

interface PageProps {
  params: Promise<{
    key: string
  }>
}

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'View Secret — Rapidly',
    description: 'Someone shared a secret with you via Rapidly secure sharing.',
  }
}

/** Secret viewing page for securely revealing a shared secret by its key. */
export default async function SecretPage({ params }: PageProps) {
  const { key } = await params

  return (
    <div className="flex min-h-[calc(100vh-200px)] items-center justify-center px-4 py-12">
      <SecretClient secretKey={key} />
    </div>
  )
}
