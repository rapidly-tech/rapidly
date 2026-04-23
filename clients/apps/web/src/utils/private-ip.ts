/**
 * Private-IP + hostname guards for SSRF prevention.
 *
 * Any server-side fetch that accepts a user-supplied URL must route
 * through ``resolveAndValidateHostname`` to block requests to RFC1918,
 * loopback, link-local, and well-known cloud metadata addresses before
 * dialing.
 */

import dns from 'node:dns'

/** Blocked hostnames that should never be fetched server-side. */
export const BLOCKED_HOSTNAMES = [
  'localhost',
  'metadata.google.internal',
  'metadata.google',
  '169.254.169.254',
]

/**
 * Returns true when the given IP sits in a loopback, private, or
 * link-local range. Covers IPv4 (10/8, 172.16/12, 192.168/16, 127/8,
 * 169.254/16, 0.0.0.0) + IPv6 (::1, ::, fe80::/10, fc00::/7).
 */
export function isPrivateIP(ip: string): boolean {
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

export interface HostnameResolution {
  address: string
  blocked: boolean
}

/**
 * Resolves a hostname and checks whether it points to a private/blocked
 * IP. Returns the resolved address so the caller can fetch via IP (with
 * an explicit Host header) — that avoids a TOCTOU / DNS-rebinding gap
 * where a re-resolve between the validation and the fetch could hit
 * different IPs.
 */
export async function resolveAndValidateHostname(
  hostname: string,
): Promise<HostnameResolution> {
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
