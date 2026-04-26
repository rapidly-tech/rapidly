import { Client, schemas } from '@rapidly-tech/client'
import { notFound } from 'next/navigation'
import { cache } from 'react'

/** Re-export the generated storefront file-share type for convenience. */
export type StorefrontFileShare = schemas['FileShareStorefront']

/** Storefront secret type — temporary local definition until backend adds the schema. */
export type StorefrontSecret = {
  id: string
  created_at: string
  uuid: string
  title?: string | null
  price_cents?: number | null
  currency: string
  expires_at?: string | null
}

/** Storefront response type used by helpers below. */
type StorefrontData = schemas['Storefront'] & {
  secrets?: StorefrontSecret[]
}

const _getStorefront = async (
  api: Client,
  slug: string,
): Promise<StorefrontData | undefined> => {
  const { data, error, response } = await api.GET('/api/storefronts/{slug}', {
    params: {
      path: {
        slug,
      },
    },
    next: {
      revalidate: 600,
      tags: [`storefront:${slug}`],
    },
  })

  if (response.status === 404) {
    return undefined
  }

  if (error) {
    throw error
  }

  return data
}

// Tell React to memoize it for the duration of the request
export const getStorefront = cache(_getStorefront)

export const getStorefrontOrNotFound = async (
  api: Client,
  slug: string,
): Promise<StorefrontData> => {
  const storefront = await getStorefront(api, slug)
  if (!storefront) {
    notFound()
  }
  return storefront
}
