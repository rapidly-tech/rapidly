import { describe, expect, it } from 'vitest'

import type { SignalingMessage } from '@/utils/p2p/signaling'
import { parseIceCandidate } from './signaling-helpers'

function msg(overrides: Partial<SignalingMessage>): SignalingMessage {
  return { type: 'candidate', ...overrides } as SignalingMessage
}

describe('parseIceCandidate', () => {
  it('extracts a candidate init from a well-formed message', () => {
    const parsed = parseIceCandidate(
      msg({
        candidate: 'candidate:1 1 UDP 1234 127.0.0.1 5000 typ host',
        sdpMid: '0',
        sdpMLineIndex: 0,
        usernameFragment: 'frag',
      }),
    )
    expect(parsed).toEqual({
      candidate: 'candidate:1 1 UDP 1234 127.0.0.1 5000 typ host',
      sdpMid: '0',
      sdpMLineIndex: 0,
      usernameFragment: 'frag',
    })
  })

  it('returns null for an empty candidate string (end-of-candidates)', () => {
    // Per the WebRTC spec an empty candidate signals EOC; we drop it
    // so ICE gathering isn't closed inadvertently.
    expect(parseIceCandidate(msg({ candidate: '' }))).toBeNull()
  })

  it('returns null when candidate is missing', () => {
    expect(parseIceCandidate(msg({}))).toBeNull()
  })

  it('returns null when candidate is not a string', () => {
    expect(
      parseIceCandidate(msg({ candidate: 42 as unknown as string })),
    ).toBeNull()
    expect(
      parseIceCandidate(msg({ candidate: null as unknown as string })),
    ).toBeNull()
  })

  it('defaults sdpMid to null when missing or wrong-typed', () => {
    const parsed = parseIceCandidate(
      msg({
        candidate: 'candidate:2 1 UDP 3000 127.0.0.1 9000 typ host',
        sdpMLineIndex: 1,
      }),
    )
    expect(parsed?.sdpMid).toBeNull()
    expect(parsed?.sdpMLineIndex).toBe(1)
  })

  it('defaults sdpMLineIndex to null when missing or wrong-typed', () => {
    const parsed = parseIceCandidate(
      msg({
        candidate: 'candidate:3 1 UDP 3000 127.0.0.1 9000 typ host',
        sdpMid: 'audio',
        sdpMLineIndex: 'oops' as unknown as number,
      }),
    )
    expect(parsed?.sdpMLineIndex).toBeNull()
    expect(parsed?.sdpMid).toBe('audio')
  })

  it('leaves usernameFragment undefined when missing', () => {
    const parsed = parseIceCandidate(
      msg({
        candidate: 'candidate:4 1 UDP 3000 127.0.0.1 9000 typ host',
        sdpMid: '0',
        sdpMLineIndex: 0,
      }),
    )
    expect(parsed?.usernameFragment).toBeUndefined()
  })
})
