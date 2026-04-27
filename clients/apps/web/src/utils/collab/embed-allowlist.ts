/**
 * Embed-host allowlist for the Collab v2 whiteboard.
 *
 * Phase 19 of the plan calls for embeds via sandboxed iframes against
 * a curated allowlist (YouTube / Loom / Figma / Vimeo). This module
 * owns the host check + a normaliser that turns user-pasted URLs (a
 * Loom share link, a YouTube watch URL, …) into the matching embed
 * URL the iframe should load.
 *
 * Pure module — no DOM, no canvas. The palette command consults
 * ``isEmbeddableUrl`` before minting an ``EmbedElement``; the future
 * iframe overlay reads ``embedUrlFor`` to know what src to load.
 */

/** Hosts we accept iframes for. Each entry maps a primary host to
 *  optional aliases the user might paste (``www.youtube.com`` vs
 *  ``youtube.com``, ``youtu.be`` short links, etc.).
 *
 *  Adding a host means accepting that its sandboxed content can run
 *  inside our origin's iframe context — review carefully before
 *  expanding. The current four are documented in §2 of the plan. */
export const EMBED_ALLOWLIST: ReadonlyArray<{
  primary: string
  aliases: ReadonlyArray<string>
}> = [
  { primary: 'youtube.com', aliases: ['www.youtube.com', 'youtu.be'] },
  { primary: 'loom.com', aliases: ['www.loom.com'] },
  { primary: 'figma.com', aliases: ['www.figma.com'] },
  { primary: 'vimeo.com', aliases: ['www.vimeo.com', 'player.vimeo.com'] },
]

/** Sandbox attribute applied to every embed iframe. We deliberately
 *  do **not** include ``allow-same-origin`` so the iframe can't read
 *  cookies / localStorage from our domain. ``allow-scripts`` is
 *  required for YouTube / Vimeo players to function. */
export const EMBED_SANDBOX = 'allow-scripts allow-presentation'

/** Hostname check — returns the matching primary host (so callers can
 *  branch on ``youtube.com`` vs ``vimeo.com`` without re-parsing) or
 *  null when the URL isn't in the allowlist or fails to parse. */
export function matchEmbedHost(url: string): string | null {
  let parsed: URL
  try {
    parsed = new URL(url)
  } catch {
    return null
  }
  if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') {
    return null
  }
  const host = parsed.hostname.toLowerCase()
  for (const entry of EMBED_ALLOWLIST) {
    if (host === entry.primary) return entry.primary
    if (entry.aliases.includes(host)) return entry.primary
  }
  return null
}

export function isEmbeddableUrl(url: string): boolean {
  return matchEmbedHost(url) !== null
}

/** Convert a user-pasted URL to the canonical embed URL for its host.
 *  Returns ``null`` when the URL isn't on the allowlist.
 *
 *  The transforms are minimal — we don't parse paths beyond what we
 *  need to swap a watch URL for an embed URL. Anything we can't
 *  recognise but is on an allowed host is returned as-is so the user
 *  can fall back on whatever the host's default behaviour is for
 *  bare URLs. */
export function embedUrlFor(url: string): string | null {
  const host = matchEmbedHost(url)
  if (!host) return null
  let parsed: URL
  try {
    parsed = new URL(url)
  } catch {
    return null
  }

  // YouTube — watch?v=ID and youtu.be/ID both → embed/ID.
  if (host === 'youtube.com') {
    if (parsed.hostname === 'youtu.be') {
      const id = parsed.pathname.replace(/^\//, '')
      if (id) return `https://www.youtube.com/embed/${id}`
    }
    if (parsed.pathname === '/watch') {
      const id = parsed.searchParams.get('v')
      if (id) return `https://www.youtube.com/embed/${id}`
    }
    if (parsed.pathname.startsWith('/embed/')) return parsed.toString()
    return parsed.toString()
  }

  // Loom — share/ID → embed/ID.
  if (host === 'loom.com') {
    const m = parsed.pathname.match(/^\/share\/([^/]+)/)
    if (m) return `https://www.loom.com/embed/${m[1]}`
    return parsed.toString()
  }

  // Vimeo — vimeo.com/ID → player.vimeo.com/video/ID.
  if (host === 'vimeo.com') {
    if (parsed.hostname === 'player.vimeo.com') return parsed.toString()
    const m = parsed.pathname.match(/^\/(\d+)/)
    if (m) return `https://player.vimeo.com/video/${m[1]}`
    return parsed.toString()
  }

  // Figma — file/proto URLs accept ``embed=true`` but the public embed
  // URL pattern works directly with the file URL too.
  if (host === 'figma.com') {
    if (parsed.pathname.startsWith('/embed')) return parsed.toString()
    return `https://www.figma.com/embed?embed_host=rapidly&url=${encodeURIComponent(parsed.toString())}`
  }

  return parsed.toString()
}
