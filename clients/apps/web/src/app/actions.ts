'use server'

import { revalidateTag } from 'next/cache'

type TagParam = Parameters<typeof revalidateTag>[0]
type CacheProfile = Parameters<typeof revalidateTag>[1]

export default async function revalidate(
  tag: TagParam,
  cacheProfile: CacheProfile = 'default',
): Promise<void> {
  revalidateTag(tag, cacheProfile)
}
