/**
 * URL hash parser for file sharing links.
 *
 * Extracted from SecretViewer.tsx for testability and separation of concerns.
 * Handles all URL formats: file-sharing P2P, secret/file, and pure password.
 */

// ── Types ──

/** File sharing secret/file hash (server-stored encrypted via OpenPGP). */
export interface FileSharingSecretHash {
  mode: 'secret'
  type: 's' | 'f'
  uuid: string
  password?: string
}

/** File sharing P2P download hash (includes encryption key and optionally password). */
export interface FileSharingHash {
  mode: 'file-sharing'
  slug: string
  encryptionKey?: string // Base64url-encoded AES-256 encryption key
  hkdfSalt?: string // Base64url-encoded HKDF salt (16 bytes)
  password?: string // Optional embedded password hash (SHA-256 hex)
}

/** Pure URL password (no server storage - zero-knowledge). */
export interface PasswordHash {
  mode: 'password'
  password: string
}

export type ParsedHash = FileSharingSecretHash | FileSharingHash | PasswordHash

// ── Validation ──

/** Slug must match server-side validation: lowercase alphanumeric, hyphens, forward slashes. */
const SAFE_SLUG = '[a-z0-9][a-z0-9/\\-]{1,255}'

/** Validate slug format without calling the API. */
export function isValidSlugFormat(slug: string): boolean {
  return new RegExp(`^${SAFE_SLUG}$`).test(slug)
}

// ── Hash Parser ──

export function parseHash(hash: string): ParsedHash | null {
  // Match pure password URL: #/p/{base64_password} (zero-knowledge, no server)
  const passwordMatch = hash.match(/^#\/p\/(.+)$/)
  if (passwordMatch && passwordMatch[1].length <= 1024) {
    try {
      const password = atob(passwordMatch[1])
      return {
        mode: 'password',
        password,
      }
    } catch {
      // Invalid base64, ignore
    }
  }

  // Match secret/file with password: #/s/{uuid}/{password} or #/f/{uuid}/{password}
  const secretWithPasswordMatch = hash.match(/^#\/(s|f)\/([^/]+)\/(.+)$/)
  if (secretWithPasswordMatch) {
    return {
      mode: 'secret',
      type: secretWithPasswordMatch[1] as 's' | 'f',
      uuid: secretWithPasswordMatch[2],
      password: secretWithPasswordMatch[3],
    }
  }

  // Match secret/file without password (Short Link): #/s/{uuid} or #/f/{uuid}
  const secretMatch = hash.match(/^#\/(s|f)\/([^/]+)$/)
  if (secretMatch) {
    return {
      mode: 'secret',
      type: secretMatch[1] as 's' | 'f',
      uuid: secretMatch[2],
    }
  }

  // Match file sharing with key + salt + password: #/d/{slug}/k/{key}/s/{salt}/p/{sha256_hex}
  const fileSharingWithKeySaltPasswordMatch = hash.match(
    new RegExp(
      `^#/d/(${SAFE_SLUG})/k/([A-Za-z0-9_-]+)/s/([A-Za-z0-9_-]+)/p/([a-fA-F0-9]{64})$`,
    ),
  )
  if (fileSharingWithKeySaltPasswordMatch) {
    return {
      mode: 'file-sharing',
      slug: fileSharingWithKeySaltPasswordMatch[1],
      encryptionKey: fileSharingWithKeySaltPasswordMatch[2],
      hkdfSalt: fileSharingWithKeySaltPasswordMatch[3],
      password: fileSharingWithKeySaltPasswordMatch[4].toLowerCase(),
    }
  }

  // Match file sharing with key + salt (no password): #/d/{slug}/k/{key}/s/{salt}
  const fileSharingWithKeySaltMatch = hash.match(
    new RegExp(`^#/d/(${SAFE_SLUG})/k/([A-Za-z0-9_-]+)/s/([A-Za-z0-9_-]+)$`),
  )
  if (fileSharingWithKeySaltMatch) {
    return {
      mode: 'file-sharing',
      slug: fileSharingWithKeySaltMatch[1],
      encryptionKey: fileSharingWithKeySaltMatch[2],
      hkdfSalt: fileSharingWithKeySaltMatch[3],
    }
  }

  // Legacy: Match file sharing with encryption key and password (no salt): #/d/{slug}/k/{base64url_key}/p/{sha256_hex}
  const fileSharingWithKeyAndPasswordMatch = hash.match(
    new RegExp(`^#/d/(${SAFE_SLUG})/k/([A-Za-z0-9_-]+)/p/([a-fA-F0-9]{64})$`),
  )
  if (fileSharingWithKeyAndPasswordMatch) {
    return {
      mode: 'file-sharing',
      slug: fileSharingWithKeyAndPasswordMatch[1],
      encryptionKey: fileSharingWithKeyAndPasswordMatch[2],
      password: fileSharingWithKeyAndPasswordMatch[3].toLowerCase(),
    }
  }

  // Legacy: Match file sharing with encryption key only (no salt, no password): #/d/{slug}/k/{base64url_key}
  const fileSharingWithKeyMatch = hash.match(
    new RegExp(`^#/d/(${SAFE_SLUG})/k/([A-Za-z0-9_-]+)$`),
  )
  if (fileSharingWithKeyMatch) {
    return {
      mode: 'file-sharing',
      slug: fileSharingWithKeyMatch[1],
      encryptionKey: fileSharingWithKeyMatch[2],
    }
  }

  // Legacy: Match file sharing with embedded password hash (no key): #/d/{slug}/p/{sha256_hex}
  const fileSharingWithPasswordMatch = hash.match(
    new RegExp(`^#/d/(${SAFE_SLUG})/p/([a-fA-F0-9]{64})$`),
  )
  if (fileSharingWithPasswordMatch) {
    return {
      mode: 'file-sharing',
      slug: fileSharingWithPasswordMatch[1],
      password: fileSharingWithPasswordMatch[2].toLowerCase(),
    }
  }

  // Legacy: Match file sharing without password or key: #/d/{slug}
  const fileSharingMatch = hash.match(new RegExp(`^#/d/(${SAFE_SLUG})$`))
  if (fileSharingMatch) {
    return {
      mode: 'file-sharing',
      slug: fileSharingMatch[1],
    }
  }

  return null
}
