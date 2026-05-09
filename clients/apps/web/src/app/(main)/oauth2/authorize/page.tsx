import { resolveApiUrl } from '@/utils/api'
import { cookies, headers } from 'next/headers'
import { redirect } from 'next/navigation'
import AuthorizeErrorPage from './AuthorizeErrorPage'
import AuthorizePage from './AuthorizePage'
import WorkspaceSelectionPage from './WorkspaceSelectionPage'
import { AuthorizeResponse } from './types'

const buildAuthorizeUrl = (params: Record<string, string>): string => {
  const qs = new URLSearchParams(params).toString()
  return `${resolveApiUrl()}/api/oauth2/authorize?${qs}`
}

const fetchAuthorizeResponse = async (
  searchParams: Record<string, string>,
): Promise<Response> => {
  const cookieStore = await cookies()
  return fetch(buildAuthorizeUrl(searchParams), {
    method: 'GET',
    credentials: 'include',
    redirect: 'manual',
    headers: { Cookie: cookieStore.toString() },
  })
}

const buildLoginRedirect = (searchParams: Record<string, string>): string => {
  const updatedParams = new URLSearchParams({
    ...searchParams,
    prompt: searchParams.prompt === 'login' ? 'consent' : searchParams.prompt,
  }).toString()

  const returnTo = `/oauth2/authorize?${updatedParams}`
  const locationParams = new URLSearchParams({ return_to: returnTo })

  if (searchParams.do_not_track) {
    locationParams.set('do_not_track', searchParams.do_not_track)
  }

  return `/login?${locationParams.toString()}`
}

const isRedirectStatus = (status: number): boolean =>
  status >= 300 && status < 400

/** Server-side safe redirect check: only allows same-origin redirects. */
function isSafeRedirectUrl(url: string, appOrigin: string): boolean {
  try {
    const parsed = new URL(url, appOrigin)
    return parsed.origin === appOrigin
  } catch {
    return false
  }
}

const requiresWorkspaceSelection = (
  data: AuthorizeResponse,
  searchParams: Record<string, string>,
): boolean => data.sub_type === 'workspace' && !searchParams['sub']

export default async function Page(props: {
  searchParams: Promise<Record<string, string>>
}) {
  const searchParams = await props.searchParams
  const response = await fetchAuthorizeResponse(searchParams)

  if (isRedirectStatus(response.status)) {
    const location = response.headers.get('Location') ?? '/'
    const headersList = await headers()
    const host = headersList.get('host') ?? 'localhost:3000'
    const proto = headersList.get('x-forwarded-proto') ?? 'https'
    const appOrigin = `${proto}://${host}`

    if (!isSafeRedirectUrl(location, appOrigin)) {
      redirect('/')
    }
    redirect(location)
  }

  if (response.status === 401) {
    redirect(buildLoginRedirect(searchParams))
  }

  const data = await response.json()

  if (response.status === 400) {
    return (
      <AuthorizeErrorPage
        error={data.error}
        error_description={data.error_description}
        error_uri={data.error_uri}
      />
    )
  }

  if (response.ok) {
    const authorizeData = data as AuthorizeResponse

    if (requiresWorkspaceSelection(authorizeData, searchParams)) {
      return (
        <WorkspaceSelectionPage
          authorizeResponse={data}
          searchParams={searchParams}
        />
      )
    }

    return (
      <AuthorizePage authorizeResponse={data} searchParams={searchParams} />
    )
  }
}
