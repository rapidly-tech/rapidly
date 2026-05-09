import { nanoid } from 'nanoid'
import { cookies, headers } from 'next/headers'

const DISTINCT_ID_COOKIE = 'rapidly_distinct_id'
const DISTINCT_ID_HEADER = 'x-rapidly-distinct-id'
const generateFallbackId = (): string => `anon_fallback_${nanoid()}`

const readFromHeaders = async (): Promise<string | undefined> => {
  const headerStore = await headers()
  return headerStore.get(DISTINCT_ID_HEADER) ?? undefined
}

const readFromCookies = async (): Promise<string | undefined> => {
  const cookieStore = await cookies()
  return cookieStore.get(DISTINCT_ID_COOKIE)?.value
}

export async function getDistinctId(): Promise<string> {
  const fromHeader = await readFromHeaders()
  if (fromHeader) return fromHeader

  const fromCookie = await readFromCookies()
  if (fromCookie) return fromCookie

  return generateFallbackId()
}
