const isServerSide = (): boolean => typeof window === 'undefined'

const getPublicBaseUrl = (): string => process.env.NEXT_PUBLIC_API_URL ?? ''

const getInternalBaseUrl = (): string =>
  process.env.RAPIDLY_API_URL || getPublicBaseUrl()

export const resolveApiUrl = (path: string = ''): string => {
  const base = isServerSide() ? getInternalBaseUrl() : getPublicBaseUrl()
  return `${base}${path}`
}

export const resolvePublicApiUrl = (path: string = ''): string =>
  `${getPublicBaseUrl()}${path}`
