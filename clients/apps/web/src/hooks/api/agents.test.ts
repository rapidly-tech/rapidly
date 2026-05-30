/**
 * Tests for the agents.ts ``extractErrorMessage`` helper.
 *
 * Pins the FastAPI error-shape extraction so future
 * regression: the per-row mutation banners (M5.86, M5.87)
 * rely on this surfacing a readable message rather than a
 * raw JSON wrapper.
 */
import { describe, expect, it } from 'vitest'

import { extractErrorMessage } from './agents'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function textResponse(status: number, body: string): Response {
  return new Response(body, { status })
}

describe('extractErrorMessage', () => {
  it('falls back when the body is empty', async () => {
    const res = new Response('', { status: 500 })
    expect(await extractErrorMessage(res, 'thing failed: 500')).toBe(
      'thing failed: 500',
    )
  })

  it('returns the detail string from a FastAPI HTTPException body', async () => {
    // ``raise HTTPException(detail="Run already in terminal status succeeded.")``
    // is the standard server shape; banner should read the detail
    // verbatim, not the JSON wrapper.
    const res = jsonResponse(403, {
      detail: 'Run already in terminal status succeeded.',
    })
    expect(await extractErrorMessage(res, 'fallback')).toBe(
      'Run already in terminal status succeeded.',
    )
  })

  it('joins per-field messages from a Pydantic 422 body', async () => {
    // ``RequestValidationError.errors()`` returns a list of
    // ``{loc, msg, type}`` dicts. Join the msgs with ; so the
    // banner is one readable line instead of dumping the list.
    const res = jsonResponse(422, {
      detail: [
        { loc: ['body', 'name'], msg: 'field required', type: 'missing' },
        {
          loc: ['body', 'secret'],
          msg: 'String should have at least 1 character',
          type: 'string_too_short',
        },
      ],
    })
    expect(await extractErrorMessage(res, 'fallback')).toBe(
      'field required; String should have at least 1 character',
    )
  })

  it('returns the raw text when the body is not JSON', async () => {
    // 502 from an upstream proxy might send HTML; show the
    // operator what the server actually said.
    const res = textResponse(502, '<html>upstream timeout</html>')
    expect(await extractErrorMessage(res, 'fallback')).toBe(
      '<html>upstream timeout</html>',
    )
  })

  it('returns the raw text when JSON has no detail field', async () => {
    // Some endpoints return ``{"error": "..."}`` instead;
    // surface the JSON so the operator can still read it.
    const res = jsonResponse(400, { error: 'bad request' })
    expect(await extractErrorMessage(res, 'fallback')).toBe(
      '{"error":"bad request"}',
    )
  })

  it('falls back when 422 detail list has no msg fields', async () => {
    // Degenerate shape — empty list or list of plain values.
    // Fall back to raw JSON so the operator at least sees something.
    const res = jsonResponse(422, { detail: [] })
    expect(await extractErrorMessage(res, 'fallback')).toBe('{"detail":[]}')
  })
})
