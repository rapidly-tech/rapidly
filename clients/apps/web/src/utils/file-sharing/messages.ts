import { z } from 'zod'

import { sanitizeFileName } from './filename'

// ── Filename Validation ──

/**
 * Maximum allowed path length for the full filename (including directories).
 * Most filesystems support up to 4096 bytes for full paths.
 */
const MAX_PATH_LENGTH = 4096

/**
 * Maximum allowed length per path component (directory or filename).
 * Most filesystems limit individual components to 255 bytes.
 */
const MAX_COMPONENT_LENGTH = 255

/**
 * Characters that are truly dangerous in filenames (null byte and control chars).
 * Only block security risks; OS-specific incompatibilities (e.g. : ? * on Windows)
 * are sanitized in the transform step so transfers from Linux/macOS aren't rejected.
 */
// eslint-disable-next-line no-control-regex
const DANGEROUS_FILENAME_CHARS = /[\x00-\x1F]/

/**
 * Patterns that could be used for path traversal attacks.
 */
const PATH_TRAVERSAL_PATTERNS = /(?:^|[\\/])\.\.(?:[\\/]|$)/

/**
 * Safe filename schema that prevents path traversal and other attacks.
 *
 * Security protections:
 * - Blocks path traversal sequences (../, ..\, etc.)
 * - Blocks null bytes and control characters
 * - Limits length to prevent buffer overflows
 * - Allows forward slashes for directory structures (but validates each segment)
 * - Sanitizes Windows-incompatible characters (replaced with _) rather than rejecting
 */
export const safeFileName = z
  .string()
  .min(1, 'Filename cannot be empty')
  .max(MAX_PATH_LENGTH, `Path cannot exceed ${MAX_PATH_LENGTH} characters`)
  .refine(
    (name) => !PATH_TRAVERSAL_PATTERNS.test(name),
    'Filename contains path traversal sequences',
  )
  .refine(
    (name) => !DANGEROUS_FILENAME_CHARS.test(name),
    'Filename contains invalid characters',
  )
  .refine(
    (name) => !name.startsWith('/') && !name.startsWith('\\'),
    'Filename cannot start with a path separator',
  )
  .refine(
    (name) =>
      name.split(/[/\\]/).every((seg) => seg.length <= MAX_COMPONENT_LENGTH),
    `Each path component cannot exceed ${MAX_COMPONENT_LENGTH} characters`,
  )
  .transform(sanitizeFileName)

// ── Message Types ──

export enum MessageType {
  RequestInfo = 'RequestInfo',
  Info = 'Info',
  EncryptedInfo = 'EncryptedInfo',
  Start = 'Start',
  Chunk = 'Chunk',
  ChunkAck = 'ChunkAck',
  Pause = 'Pause',
  Done = 'Done',
  Error = 'Error',
  PasswordRequired = 'PasswordRequired',
  UsePassword = 'UsePassword',
  Report = 'Report',
  Ping = 'Ping',
  Pong = 'Pong',
}

// ── Message Schemas ──

export const RequestInfoMessage = z.object({
  type: z.literal(MessageType.RequestInfo),
  browserName: z.string().max(255),
  browserVersion: z.string().max(255),
  osName: z.string().max(255),
  osVersion: z.string().max(255),
  mobileVendor: z.string().max(255),
  mobileModel: z.string().max(255),
})

export const InfoMessage = z.object({
  type: z.literal(MessageType.Info),
  files: z
    .array(
      z.object({
        fileName: safeFileName,
        size: z.number().nonnegative(),
        type: z.string().max(255),
        sha256: z
          .string()
          .length(64)
          .regex(/^[a-f0-9]{64}$/)
          .optional(), // SHA-256 hex digest
        commitment: z
          .string()
          .length(64)
          .regex(/^[a-f0-9]{64}$/)
          .optional(), // HMAC-SHA256 key commitment
      }),
    )
    .min(1, 'At least one file is required')
    .max(65535, 'Too many files'),
  remainingDownloads: z.number().optional(), // null/undefined = unlimited
  encrypted: z.boolean().optional(), // Whether chunks are AES-256-GCM encrypted
})

/** Maximum metadata payload size (16MB). Large folders with many files can exceed 1MB of metadata. */
const MAX_METADATA_PAYLOAD = 16 * 1024 * 1024

export const EncryptedInfoMessage = z.object({
  type: z.literal(MessageType.EncryptedInfo),
  payload: z
    .unknown()
    .refine(
      (val) =>
        (val instanceof ArrayBuffer || ArrayBuffer.isView(val)) &&
        (val instanceof ArrayBuffer
          ? val.byteLength
          : (val as ArrayBufferView).byteLength) <= MAX_METADATA_PAYLOAD,
      'Expected encrypted payload as ArrayBuffer (max 16MB)',
    )
    .transform((val): ArrayBuffer => {
      if (val instanceof ArrayBuffer) return val
      const view = val as ArrayBufferView
      return (view.buffer as ArrayBuffer).slice(
        view.byteOffset,
        view.byteOffset + view.byteLength,
      )
    }),
})

export const StartMessage = z.object({
  type: z.literal(MessageType.Start),
  fileName: safeFileName,
  offset: z.number().nonnegative(),
})

export const ChunkMessage = z.object({
  type: z.literal(MessageType.Chunk),
  fileName: safeFileName,
  fileIndex: z.number().nonnegative().optional(), // Index in files array, used for key derivation
  offset: z.number().nonnegative(),
  bytes: z
    .unknown()
    .refine(
      (val): val is ArrayBuffer | ArrayBufferView =>
        val instanceof ArrayBuffer || ArrayBuffer.isView(val),
      'Expected chunk bytes as ArrayBuffer',
    )
    .transform((val): ArrayBuffer => {
      if (val instanceof ArrayBuffer) return val
      const view = val as ArrayBufferView
      return (view.buffer as ArrayBuffer).slice(
        view.byteOffset,
        view.byteOffset + view.byteLength,
      )
    }),
  final: z.boolean(),
})

export const ChunkAckMessage = z.object({
  type: z.literal(MessageType.ChunkAck),
  fileName: safeFileName,
  offset: z.number().nonnegative(),
  bytesReceived: z.number().nonnegative(),
})

export const DoneMessage = z.object({
  type: z.literal(MessageType.Done),
})

export const ErrorMessage = z.object({
  type: z.literal(MessageType.Error),
  error: z.string().max(1024),
})

export const PasswordRequiredMessage = z.object({
  type: z.literal(MessageType.PasswordRequired),
  errorMessage: z.string().max(1024).optional(),
})

export const UsePasswordMessage = z.object({
  type: z.literal(MessageType.UsePassword),
  // Passwords are always SHA-256 hashed before sending (64 hex chars)
  password: z
    .string()
    .length(64)
    .regex(/^[a-f0-9]{64}$/),
})

export const PauseMessage = z.object({
  type: z.literal(MessageType.Pause),
})

export const ReportMessage = z.object({
  type: z.literal(MessageType.Report),
})

export const PingMessage = z.object({
  type: z.literal(MessageType.Ping),
})

export const PongMessage = z.object({
  type: z.literal(MessageType.Pong),
})

// ── Union Type and Decoder ──

export const Message = z.discriminatedUnion('type', [
  RequestInfoMessage,
  InfoMessage,
  EncryptedInfoMessage,
  StartMessage,
  ChunkMessage,
  ChunkAckMessage,
  DoneMessage,
  ErrorMessage,
  PasswordRequiredMessage,
  UsePasswordMessage,
  PauseMessage,
  ReportMessage,
  PingMessage,
  PongMessage,
])

export type Message = z.infer<typeof Message>

export function decodeMessage(data: unknown): Message {
  return Message.parse(data)
}
