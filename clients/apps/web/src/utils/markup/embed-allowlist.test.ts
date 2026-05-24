/**
 * Embed allowlist + URL canonicalisation — pinned behaviour:
 *
 * - Only YouTube / Loom / Figma / Vimeo + their aliases pass.
 * - http: / https: only — file:, data:, javascript: are rejected.
 * - YouTube watch URLs convert to /embed/ID.
 * - youtu.be short links convert to /embed/ID.
 * - Loom share URLs convert to /embed/ID.
 * - Vimeo bare URLs convert to player.vimeo.com.
 * - Unparseable input returns null.
 */

import { describe, expect, it } from 'vitest'

import {
  EMBED_ALLOWLIST,
  EMBED_SANDBOX,
  embedUrlFor,
  isEmbeddableUrl,
  matchEmbedHost,
} from './embed-allowlist'

describe('matchEmbedHost', () => {
  it('accepts each allowlisted host + its aliases', () => {
    for (const entry of EMBED_ALLOWLIST) {
      expect(matchEmbedHost(`https://${entry.primary}/x`)).toBe(entry.primary)
      for (const alias of entry.aliases) {
        expect(matchEmbedHost(`https://${alias}/x`)).toBe(entry.primary)
      }
    }
  })

  it('rejects unrelated hosts', () => {
    expect(matchEmbedHost('https://example.com/')).toBeNull()
    expect(matchEmbedHost('https://evil.youtube.com.attacker.com/')).toBeNull()
  })

  it('rejects non-http(s) schemes', () => {
    expect(matchEmbedHost('javascript:alert(1)')).toBeNull()
    expect(matchEmbedHost('data:text/html,foo')).toBeNull()
    expect(matchEmbedHost('file:///etc/passwd')).toBeNull()
  })

  it('returns null on unparseable input', () => {
    expect(matchEmbedHost('not a url')).toBeNull()
    expect(matchEmbedHost('')).toBeNull()
  })
})

describe('isEmbeddableUrl', () => {
  it('mirrors matchEmbedHost', () => {
    expect(isEmbeddableUrl('https://www.youtube.com/watch?v=abc')).toBe(true)
    expect(isEmbeddableUrl('https://example.com/')).toBe(false)
  })
})

describe('embedUrlFor', () => {
  it('converts a YouTube watch URL to the embed URL', () => {
    expect(embedUrlFor('https://www.youtube.com/watch?v=dQw4w9WgXcQ')).toBe(
      'https://www.youtube.com/embed/dQw4w9WgXcQ',
    )
  })

  it('converts a youtu.be short link to the embed URL', () => {
    expect(embedUrlFor('https://youtu.be/dQw4w9WgXcQ')).toBe(
      'https://www.youtube.com/embed/dQw4w9WgXcQ',
    )
  })

  it('passes a YouTube /embed/ URL through unchanged', () => {
    expect(embedUrlFor('https://www.youtube.com/embed/dQw4w9WgXcQ')).toBe(
      'https://www.youtube.com/embed/dQw4w9WgXcQ',
    )
  })

  it('converts a Loom share URL to the embed URL', () => {
    expect(embedUrlFor('https://www.loom.com/share/abc123')).toBe(
      'https://www.loom.com/embed/abc123',
    )
  })

  it('converts a Vimeo bare URL to player.vimeo.com', () => {
    expect(embedUrlFor('https://vimeo.com/123456789')).toBe(
      'https://player.vimeo.com/video/123456789',
    )
  })

  it('passes a player.vimeo.com URL through unchanged', () => {
    expect(embedUrlFor('https://player.vimeo.com/video/123456789')).toBe(
      'https://player.vimeo.com/video/123456789',
    )
  })

  it('wraps a Figma URL in the embed query', () => {
    const out = embedUrlFor('https://www.figma.com/file/xyz/Project')
    expect(out).toContain('https://www.figma.com/embed')
    expect(out).toContain('url=')
  })

  it('returns null for non-allowed hosts', () => {
    expect(embedUrlFor('https://example.com/x')).toBeNull()
  })
})

describe('EMBED_SANDBOX', () => {
  it('omits allow-same-origin so iframes cannot read our cookies', () => {
    expect(EMBED_SANDBOX).not.toContain('allow-same-origin')
  })

  it('includes allow-scripts so embedded players run', () => {
    expect(EMBED_SANDBOX).toContain('allow-scripts')
  })
})
