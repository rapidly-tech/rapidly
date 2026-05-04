import { Metadata } from 'next'
import FileDetailPage from './FileDetailPage'

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'File Details',
  }
}

/** File detail page showing metadata and activity for a specific file session. */
export default async function Page(props: {
  params: Promise<{ workspace: string; sessionId: string }>
}) {
  const params = await props.params
  return <FileDetailPage sessionId={params.sessionId} />
}
