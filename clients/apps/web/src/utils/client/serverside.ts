import { Client } from '@rapidly-tech/client'
import { cookies, headers } from 'next/headers'
import { cache } from 'react'
import { buildServerAPI } from '.'

/**
 * Builds a server-side API client using the incoming request's headers
 * and cookies. The result is memoised with `React.cache` so that
 * multiple server components rendered in the same request share a
 * single client instance.
 */
async function createCachedAPI(token?: string): Promise<Client> {
  const [reqHeaders, reqCookies] = await Promise.all([headers(), cookies()])
  return buildServerAPI(reqHeaders, reqCookies, token)
}

export const getServerSideAPI = cache(createCachedAPI)
