import { ApiOperation, Operation } from '@/components/Docs/ApiReference'
import apiReference from '@/generated/api-reference.json'
import { notFound } from 'next/navigation'

interface ApiGroup {
  slug: string
  title: string
  operations: ApiOperation[]
}

const groups = apiReference.groups as ApiGroup[]

export const dynamicParams = false

export function generateStaticParams() {
  return groups.map((g) => ({ group: g.slug }))
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ group: string }>
}) {
  const { group } = await params
  const g = groups.find((x) => x.slug === group)
  return {
    title: `${g?.title ?? 'API'} API | Rapidly Docs`,
    description: `REST API reference for ${g?.title ?? 'Rapidly'} — endpoints, parameters, and responses.`,
  }
}

export default async function ApiGroupPage({
  params,
}: {
  params: Promise<{ group: string }>
}) {
  const { group } = await params
  const g = groups.find((x) => x.slug === group)
  if (!g) notFound()

  return (
    <>
      <h1>{g.title} API</h1>
      <p className="docs-lead">
        {g.operations.length} endpoint{g.operations.length === 1 ? '' : 's'} —
        authenticate with a workspace access token via{' '}
        <code>Authorization: Bearer</code>. See the{' '}
        <a href="/docs/api-reference/introduction">API introduction</a> for base
        URLs, pagination, and rate limits.
      </p>
      {g.operations.map((op) => (
        <Operation key={`${op.method}-${op.path}`} op={op} />
      ))}
    </>
  )
}
