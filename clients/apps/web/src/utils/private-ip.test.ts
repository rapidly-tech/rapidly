import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  BLOCKED_HOSTNAMES,
  isPrivateIP,
  resolveAndValidateHostname,
} from './private-ip'

/** ``isPrivateIP`` + ``resolveAndValidateHostname`` are the SSRF gate
 *  for the ``validate-website`` route. A regression here would let a
 *  user-supplied URL reach an internal-only address (metadata server,
 *  private VPC IP, localhost). Every blocking branch is pinned. */

describe('isPrivateIP — IPv4 loopback + zero', () => {
  it.each(['127.0.0.1', '127.1.2.3', '127.255.255.255', '0.0.0.0'])(
    'blocks %s',
    (ip) => {
      expect(isPrivateIP(ip)).toBe(true)
    },
  )
})

describe('isPrivateIP — IPv4 RFC1918 private ranges', () => {
  it.each([
    '10.0.0.1',
    '10.255.255.254',
    '192.168.0.1',
    '192.168.1.100',
    '172.16.0.1',
    '172.20.0.1',
    '172.31.255.254',
  ])('blocks %s', (ip) => {
    expect(isPrivateIP(ip)).toBe(true)
  })

  it.each(['172.15.0.1', '172.32.0.1', '172.100.0.1'])(
    'does NOT block %s (outside 172.16/12)',
    (ip) => {
      expect(isPrivateIP(ip)).toBe(false)
    },
  )
})

describe('isPrivateIP — link-local', () => {
  it('blocks 169.254/16 (AWS metadata + link-local)', () => {
    expect(isPrivateIP('169.254.169.254')).toBe(true)
    expect(isPrivateIP('169.254.0.1')).toBe(true)
  })
})

describe('isPrivateIP — IPv6 loopback + private', () => {
  it('blocks ::1 and ::', () => {
    expect(isPrivateIP('::1')).toBe(true)
    expect(isPrivateIP('::')).toBe(true)
  })

  it('blocks fe80::/10 link-local', () => {
    expect(isPrivateIP('fe80::1')).toBe(true)
    expect(isPrivateIP('fe80:dead::')).toBe(true)
  })

  it('blocks fc00::/7 unique local (both fc00 and fd00 prefixes)', () => {
    expect(isPrivateIP('fc00::1')).toBe(true)
    expect(isPrivateIP('fd00::1')).toBe(true)
  })
})

describe('isPrivateIP — public IPs are allowed', () => {
  it.each([
    '8.8.8.8',
    '1.1.1.1',
    '100.64.0.1', // carrier-grade NAT; NOT in the blocklist per current rules
    '2001:4860:4860::8888', // Google public DNS
  ])('allows %s', (ip) => {
    expect(isPrivateIP(ip)).toBe(false)
  })
})

describe('BLOCKED_HOSTNAMES', () => {
  it('includes localhost + metadata endpoints', () => {
    expect(BLOCKED_HOSTNAMES).toContain('localhost')
    expect(BLOCKED_HOSTNAMES).toContain('metadata.google.internal')
    expect(BLOCKED_HOSTNAMES).toContain('metadata.google')
    expect(BLOCKED_HOSTNAMES).toContain('169.254.169.254')
  })
})

// ── resolveAndValidateHostname ──

// Mock ``dns.promises.lookup`` via vi.mock so we don't actually hit
// DNS in CI. Each test seeds the resolver's response.

vi.mock('node:dns', () => ({
  default: {
    promises: {
      lookup: vi.fn(),
    },
  },
  promises: {
    lookup: vi.fn(),
  },
}))

import dns from 'node:dns'

function stubLookup(address: string): void {
  ;(dns.promises.lookup as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    address,
    family: address.includes(':') ? 6 : 4,
  })
}

function stubLookupError(): void {
  ;(dns.promises.lookup as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
    new Error('ENOTFOUND'),
  )
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('resolveAndValidateHostname', () => {
  it('blocks exact-match hostnames from BLOCKED_HOSTNAMES', async () => {
    const result = await resolveAndValidateHostname('localhost')
    expect(result).toEqual({ address: 'localhost', blocked: true })
  })

  it('case-insensitive hostname match for the blocklist', async () => {
    const result = await resolveAndValidateHostname('LOCALHOST')
    expect(result.blocked).toBe(true)
    expect(result.address).toBe('localhost')
  })

  it('blocks an IP literal hostname in the private range', async () => {
    const result = await resolveAndValidateHostname('10.0.0.1')
    expect(result).toEqual({ address: '10.0.0.1', blocked: true })
  })

  it('blocks when DNS resolves to a private IP', async () => {
    stubLookup('192.168.1.5')
    const result = await resolveAndValidateHostname('mysite.example')
    expect(result).toEqual({ address: '192.168.1.5', blocked: true })
  })

  it('allows a hostname that resolves to a public IP', async () => {
    stubLookup('8.8.8.8')
    const result = await resolveAndValidateHostname('public.example')
    expect(result).toEqual({ address: '8.8.8.8', blocked: false })
  })

  it('lets DNS failures fall through unblocked (fetch will fail later)', async () => {
    stubLookupError()
    const result = await resolveAndValidateHostname('nonexistent.invalid')
    expect(result).toEqual({
      address: 'nonexistent.invalid',
      blocked: false,
    })
  })

  it('blocks the AWS metadata IP even when given as a raw hostname', async () => {
    const result = await resolveAndValidateHostname('169.254.169.254')
    // Exact-match blocklist entry catches this before IP-literal check.
    expect(result.blocked).toBe(true)
  })

  it('short-circuits without a DNS call for blocklisted hostnames', async () => {
    await resolveAndValidateHostname('localhost')
    expect(dns.promises.lookup).not.toHaveBeenCalled()
  })

  it('short-circuits without a DNS call for IP literals', async () => {
    await resolveAndValidateHostname('127.0.0.1')
    expect(dns.promises.lookup).not.toHaveBeenCalled()
  })

  it('calls DNS for public hostnames', async () => {
    stubLookup('8.8.8.8')
    await resolveAndValidateHostname('example.com')
    expect(dns.promises.lookup).toHaveBeenCalledWith('example.com')
  })
})
