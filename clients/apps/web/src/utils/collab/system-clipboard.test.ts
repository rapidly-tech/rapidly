/**
 * System-clipboard bridge — pinned behaviour:
 *
 * - ``payloadToText`` round-trips through ``parseClipboardText``.
 * - ``parseClipboardText`` returns null for empty / malformed / wrong-
 *   magic / wrong-shape payloads (caller falls through cleanly).
 * - ``writeSystemClipboard`` returns false when navigator.clipboard
 *   is missing or writeText throws (in-app buffer remains the truth).
 * - ``readSystemClipboardPayload`` likewise returns null on any
 *   failure mode.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { CLIPBOARD_MAGIC, type ClipboardPayload } from './clipboard'
import {
  parseClipboardText,
  payloadToText,
  readSystemClipboardPayload,
  writeSystemClipboard,
} from './system-clipboard'

const samplePayload: ClipboardPayload = {
  magic: CLIPBOARD_MAGIC,
  elements: [
    {
      id: 'a',
      type: 'rect',
      x: 0,
      y: 0,
      width: 10,
      height: 10,
      angle: 0,
      zIndex: 0,
      groupIds: [],
      strokeColor: '#000',
      fillColor: 'transparent',
      fillStyle: 'solid',
      strokeWidth: 1,
      strokeStyle: 'solid',
      roughness: 0,
      opacity: 1,
      seed: 1,
      version: 1,
      locked: false,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any,
  ],
}

describe('payloadToText / parseClipboardText', () => {
  it('round-trips a payload', () => {
    const text = payloadToText(samplePayload)
    const parsed = parseClipboardText(text)
    expect(parsed).not.toBeNull()
    expect(parsed?.elements).toHaveLength(1)
    expect(parsed?.elements[0].id).toBe('a')
  })

  it('rejects empty input', () => {
    expect(parseClipboardText('')).toBeNull()
  })

  it('rejects malformed JSON', () => {
    expect(parseClipboardText('{not json')).toBeNull()
  })

  it('rejects non-object payloads', () => {
    expect(parseClipboardText('null')).toBeNull()
    expect(parseClipboardText('"hello"')).toBeNull()
    expect(parseClipboardText('42')).toBeNull()
  })

  it('rejects wrong magic', () => {
    expect(
      parseClipboardText(JSON.stringify({ magic: 'figma', elements: [] })),
    ).toBeNull()
  })

  it('rejects missing or non-array elements', () => {
    expect(
      parseClipboardText(
        JSON.stringify({ magic: CLIPBOARD_MAGIC, elements: 'oops' }),
      ),
    ).toBeNull()
  })
})

describe('writeSystemClipboard', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns false when navigator.clipboard is unavailable', async () => {
    vi.stubGlobal('navigator', {})
    expect(await writeSystemClipboard(samplePayload)).toBe(false)
  })

  it('returns true on success and writes the JSON envelope', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    expect(await writeSystemClipboard(samplePayload)).toBe(true)
    expect(writeText).toHaveBeenCalledTimes(1)
    const written = writeText.mock.calls[0][0] as string
    expect(parseClipboardText(written)).not.toBeNull()
  })

  it('swallows writeText rejections and returns false', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('denied'))
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    expect(await writeSystemClipboard(samplePayload)).toBe(false)
  })
})

describe('readSystemClipboardPayload', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns null when navigator.clipboard is unavailable', async () => {
    vi.stubGlobal('navigator', {})
    expect(await readSystemClipboardPayload()).toBeNull()
  })

  it('returns null when readText rejects', async () => {
    vi.stubGlobal('navigator', {
      clipboard: { readText: vi.fn().mockRejectedValue(new Error('denied')) },
    })
    expect(await readSystemClipboardPayload()).toBeNull()
  })

  it('returns the parsed payload when the clipboard holds our JSON', async () => {
    const text = payloadToText(samplePayload)
    vi.stubGlobal('navigator', {
      clipboard: { readText: vi.fn().mockResolvedValue(text) },
    })
    const result = await readSystemClipboardPayload()
    expect(result?.elements[0].id).toBe('a')
  })

  it('returns null when the clipboard text is not our payload', async () => {
    vi.stubGlobal('navigator', {
      clipboard: { readText: vi.fn().mockResolvedValue('plain text') },
    })
    expect(await readSystemClipboardPayload()).toBeNull()
  })
})
