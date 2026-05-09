import { describe, expect, it } from 'vitest'

import { CONFIG } from './config'
import { workspacePageLink } from './nav'

describe('workspacePageLink', () => {
  const base = CONFIG.FRONTEND_BASE_URL

  it('builds /{slug}/ when no path is supplied', () => {
    const org = { slug: 'acme' } as Parameters<typeof workspacePageLink>[0]
    expect(workspacePageLink(org)).toBe(`${base}/acme/`)
  })

  it('appends the path after the slug', () => {
    const org = { slug: 'acme' } as Parameters<typeof workspacePageLink>[0]
    expect(workspacePageLink(org, 'settings')).toBe(`${base}/acme/settings`)
  })

  it('treats an explicit empty path the same as undefined', () => {
    const org = { slug: 'acme' } as Parameters<typeof workspacePageLink>[0]
    expect(workspacePageLink(org, '')).toBe(`${base}/acme/`)
  })

  it('does not URL-encode the slug or path (caller pre-encodes)', () => {
    const org = { slug: 'a b' } as Parameters<typeof workspacePageLink>[0]
    expect(workspacePageLink(org, 'some/path?q=1')).toBe(
      `${base}/a b/some/path?q=1`,
    )
  })
})
