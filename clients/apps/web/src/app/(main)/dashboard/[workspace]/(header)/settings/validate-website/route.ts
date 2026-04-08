import { getAuthenticatedUser } from '@/utils/user'
import { NextResponse } from 'next/server'
import dns from 'node:dns'

interface ValidateURLRequest {
  url: string
}

interface ValidateURLResponse {
  reachable: boolean
  status?: number
  error?: string
}

/** Returns true if the IP address is in a private, loopback, or link-local range. */
function isPrivateIP(ip: string): boolean {
  // IPv4 patterns
  if (
    ip === '127.0.0.1' ||
    ip.startsWith('127.') ||
    ip === '0.0.0.0' ||
    ip.startsWith('10.') ||
    ip.startsWith('192.168.') ||
    ip.startsWith('169.254.') ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(ip)
  ) {
    return true
  }

  // IPv6 loopback and link-local
  if (
    ip === '::1' ||
    ip === '::' ||
    ip.startsWith('fe80:') ||
    ip.startsWith('fc00:') ||
    ip.startsWith('fd00:')
  ) {
    return true
  }

  return false
}

/** Blocked hostnames that should never be fetched server-side. */
const BLOCKED_HOSTNAMES = [
  'localhost',
  'metadata.google.internal',
  'metadata.google',
  '169.254.169.254',
]

/**
 * Resolves a hostname and checks whether it points to a private/blocked IP.
 * Returns the resolved address if safe, or null if blocked.
 *
 * By returning the resolved IP we avoid a TOCTOU / DNS-rebinding gap:
 * the caller must fetch using this IP (with the Host header set) instead
 * of re-resolving the hostname.
 */
async function resolveAndValidateHostname(
  hostname: string,
): Promise<
  { address: string; blocked: true } | { address: string; blocked: false }
> {
  const lower = hostname.toLowerCase()

  if (BLOCKED_HOSTNAMES.includes(lower)) {
    return { address: lower, blocked: true }
  }

  // Check if the hostname is already an IP literal
  if (isPrivateIP(lower)) {
    return { address: lower, blocked: true }
  }

  // Resolve hostname and check the resulting IP
  try {
    const { address } = await dns.promises.lookup(lower)
    if (isPrivateIP(address)) {
      return { address, blocked: true }
    }
    return { address, blocked: false }
  } catch {
    // DNS resolution failed — will be caught later during fetch
    return { address: lower, blocked: false }
  }
}

export async function POST(request: Request): Promise<NextResponse> {
  const user = await getAuthenticatedUser()
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  try {
    const body = (await request.json()) as ValidateURLRequest
    const { url } = body

    if (!url) {
      return NextResponse.json(
        {
          reachable: false,
          error: 'URL is required',
        } satisfies ValidateURLResponse,
        { status: 400 },
      )
    }

    // Validate URL format
    let parsedURL: URL
    try {
      parsedURL = new URL(url)
      if (!['http:', 'https:'].includes(parsedURL.protocol)) {
        return NextResponse.json(
          {
            reachable: false,
            error: 'Invalid URL protocol',
          } satisfies ValidateURLResponse,
          { status: 400 },
        )
      }
    } catch {
      return NextResponse.json(
        {
          reachable: false,
          error: 'Invalid URL format',
        } satisfies ValidateURLResponse,
        { status: 400 },
      )
    }

    // Resolve DNS once and validate the IP to prevent DNS rebinding (TOCTOU)
    const resolved = await resolveAndValidateHostname(parsedURL.hostname)
    if (resolved.blocked) {
      return NextResponse.json(
        {
          reachable: false,
          error: 'URL points to a private or internal address',
        } satisfies ValidateURLResponse,
        { status: 422 },
      )
    }

    // Build a URL that uses the resolved IP to avoid re-resolution
    const fetchURL = new URL(url)
    fetchURL.hostname = resolved.address

    // Perform HEAD request with timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 5000)

    try {
      const response = await fetch(fetchURL.toString(), {
        method: 'HEAD',
        signal: controller.signal,
        redirect: 'manual',
        headers: {
          'User-Agent': 'Rapidly URL Validator/1.0',
          Host: parsedURL.host,
        },
      })

      clearTimeout(timeoutId)

      const isReachable = response.status >= 200 && response.status < 400

      return NextResponse.json({
        reachable: isReachable,
        status: response.status,
      } satisfies ValidateURLResponse)
    } catch (fetchError) {
      clearTimeout(timeoutId)

      if (fetchError instanceof Error && fetchError.name === 'AbortError') {
        return NextResponse.json({
          reachable: false,
          error: 'Request timed out',
        } satisfies ValidateURLResponse)
      }

      return NextResponse.json({
        reachable: false,
        error: 'Unable to reach URL',
      } satisfies ValidateURLResponse)
    }
  } catch (error) {
    return NextResponse.json(
      {
        reachable: false,
        error: (error as Error).message,
      } satisfies ValidateURLResponse,
      { status: 500 },
    )
  }
}
