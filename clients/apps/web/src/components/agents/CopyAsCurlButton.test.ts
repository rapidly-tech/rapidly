import { describe, expect, it } from 'vitest'

import { bashSingleQuoteEscape } from './CopyAsCurlButton'

describe('bashSingleQuoteEscape', () => {
  it('returns the input unchanged when there are no single quotes', () => {
    expect(bashSingleQuoteEscape('hello world')).toBe('hello world')
    expect(bashSingleQuoteEscape('')).toBe('')
    expect(bashSingleQuoteEscape('{"x":1}')).toBe('{"x":1}')
  })

  it('escapes a single quote using the bash close-escape-open idiom', () => {
    // Bash single-quoted strings can't contain a single quote
    // directly; the canonical workaround is close the quote,
    // emit ``\'``, and reopen — so ``'`` → ``'\''``.
    expect(bashSingleQuoteEscape("don't")).toBe(`don'\\''t`)
  })

  it('escapes every single quote in a multi-quote string', () => {
    expect(bashSingleQuoteEscape("'a' 'b'")).toBe(`'\\''a'\\'' '\\''b'\\''`)
  })

  it('does not touch double quotes', () => {
    // The component wraps the payload in single quotes for -d,
    // so double quotes inside JSON do not need escaping. Only
    // single quotes do.
    expect(bashSingleQuoteEscape('{"x":"y"}')).toBe('{"x":"y"}')
  })

  it('handles a realistic JSON payload with an embedded single quote', () => {
    const json = JSON.stringify({ text: "don't worry" })
    const out = bashSingleQuoteEscape(json)
    // Wrap with -d '...' would produce
    //   -d '{"text":"don'\''t worry"}'
    // which bash reads as the literal {"text":"don't worry"}.
    expect(out).toBe(`{"text":"don'\\''t worry"}`)
  })
})
