import LogoType70 from '@/components/Brand/LogoType70'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Link from 'next/link'

/** Validates that a return_to path is a safe relative URL (no open redirect). */
function getSafeReturnTo(returnTo: string | undefined): string {
  if (!returnTo) return '/'
  // Block protocol-relative URLs (e.g. //evil.com/path)
  if (returnTo.startsWith('//')) return '/'
  try {
    const parsed = new URL(returnTo, 'http://localhost')
    // Only allow relative paths (same-origin) — reject absolute URLs
    if (parsed.origin !== 'http://localhost') return '/'
    return parsed.pathname + parsed.search + parsed.hash
  } catch {
    return '/'
  }
}

/** Error page displaying a user-facing error message with a return link. */
export default async function Page(props: {
  searchParams: Promise<{ message: string; return_to: string }>
}) {
  const searchParams = await props.searchParams

  const { message, return_to } = searchParams
  const safeReturnTo = getSafeReturnTo(return_to)

  return (
    <div className="rp-page-bg flex h-screen w-full grow items-center justify-center">
      <div className="flex w-80 flex-col items-center gap-6 text-center">
        <Link href="/">
          <LogoType70 className="h-10" />
        </Link>
        <h1 className="text-3xl">Oh no!</h1>
        <p>{message}</p>
        <Button asChild>
          <Link href={safeReturnTo}>Go back</Link>
        </Button>
      </div>
    </div>
  )
}
