import { describe, expect, it, vi } from 'vitest'

import type { SignalingClient } from './signaling'
import { WebSocketRelay } from './ws-relay'

/** Minimal SignalingClient stand-in recording the calls ws-relay makes. */
function makeSignaling(): SignalingClient & {
  _sent: Array<Record<string, unknown>>
  _sentText: Array<{ targetId: string; text: string }>
  _sentBinary: Array<{ targetId: string; data: ArrayBuffer }>
} {
  const sent: Array<Record<string, unknown>> = []
  const sentText: Array<{ targetId: string; text: string }> = []
  const sentBinary: Array<{ targetId: string; data: ArrayBuffer }> = []
  return {
    send: vi.fn((msg: Record<string, unknown>) => {
      sent.push(msg)
      return true
    }),
    sendRelayText: vi.fn((targetId: string, text: string) => {
      sentText.push({ targetId, text })
      return true
    }),
    sendBinary: vi.fn((targetId: string, data: ArrayBuffer) => {
      sentBinary.push({ targetId, data })
      return true
    }),
    rawWs: null,
    _sent: sent,
    _sentText: sentText,
    _sentBinary: sentBinary,
  } as unknown as SignalingClient & {
    _sent: typeof sent
    _sentText: typeof sentText
    _sentBinary: typeof sentBinary
  }
}

const PEER = 'peer-remote'

describe('WebSocketRelay — lifecycle', () => {
  it('start() opens the relay, sends relay:start, and fires onOpen', () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    const onOpen = vi.fn()
    relay.onOpen = onOpen
    expect(relay.open).toBe(false)

    relay.start()

    expect(relay.open).toBe(true)
    expect(sig._sent).toEqual([{ type: 'relay:start', targetId: PEER }])
    expect(onOpen).toHaveBeenCalledTimes(1)
    expect(relay.peer).toBe(PEER)
  })

  it('accept() opens the relay and sends relay:ack', () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    const onOpen = vi.fn()
    relay.onOpen = onOpen

    relay.accept()

    expect(relay.open).toBe(true)
    expect(sig._sent).toEqual([{ type: 'relay:ack', targetId: PEER }])
    expect(onOpen).toHaveBeenCalledTimes(1)
  })

  it('close() fires onClose once and clears all handler refs', () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    const onClose = vi.fn()
    relay.onClose = onClose
    relay.start()

    relay.close()
    expect(relay.open).toBe(false)
    expect(onClose).toHaveBeenCalledTimes(1)

    // Second close is a no-op.
    relay.close()
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('close() before open is a no-op', () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    const onClose = vi.fn()
    relay.onClose = onClose
    relay.close()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('done() sends relay:done when open', () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    relay.start()
    sig._sent.length = 0
    relay.done()
    expect(sig._sent).toEqual([{ type: 'relay:done', targetId: PEER }])
  })

  it('done() is a no-op when not open', () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    relay.done()
    expect(sig._sent).toEqual([])
  })
})

describe('WebSocketRelay — handleRelayData', () => {
  it('drops messages before the relay is open', () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    const onData = vi.fn()
    relay.onData = onData
    relay.handleRelayData(JSON.stringify({ type: 'x' }))
    expect(onData).not.toHaveBeenCalled()
  })

  it('parses JSON text messages to the onData handler', () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    const onData = vi.fn()
    relay.onData = onData
    relay.start()
    relay.handleRelayData(JSON.stringify({ type: 'offer', sdp: 'x' }))
    expect(onData).toHaveBeenCalledWith({ type: 'offer', sdp: 'x' })
  })

  it('silently drops malformed JSON text messages (no throw)', () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    const onData = vi.fn()
    relay.onData = onData
    relay.start()
    expect(() => relay.handleRelayData('not-json')).not.toThrow()
    expect(onData).not.toHaveBeenCalled()
  })

  it('decodes a framed binary payload and reattaches "bytes"', () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    const onData = vi.fn()
    relay.onData = onData
    relay.start()

    // Build a frame: [4-byte header-len][header JSON][payload bytes]
    const header = { type: 'chunk', _hasBinary: 'bytes' }
    const headerBytes = new TextEncoder().encode(JSON.stringify(header))
    const payload = new Uint8Array([1, 2, 3, 4])
    const frame = new ArrayBuffer(4 + headerBytes.byteLength + payload.length)
    const view = new DataView(frame)
    view.setUint32(0, headerBytes.byteLength, false)
    new Uint8Array(frame, 4, headerBytes.byteLength).set(headerBytes)
    new Uint8Array(frame, 4 + headerBytes.byteLength).set(payload)

    relay.handleRelayData(frame)
    expect(onData).toHaveBeenCalledTimes(1)
    const decoded = onData.mock.calls[0][0] as Record<string, unknown>
    expect(decoded.type).toBe('chunk')
    expect(decoded._hasBinary).toBeUndefined() // stripped from output
    expect(decoded.bytes).toBeInstanceOf(ArrayBuffer)
    expect(new Uint8Array(decoded.bytes as ArrayBuffer)).toEqual(payload)
  })

  it('decodes to "payload" field when _hasBinary === "payload"', () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    const onData = vi.fn()
    relay.onData = onData
    relay.start()

    const header = { type: 'chunk', _hasBinary: 'payload' }
    const headerBytes = new TextEncoder().encode(JSON.stringify(header))
    const payload = new Uint8Array([9, 8, 7])
    const frame = new ArrayBuffer(4 + headerBytes.byteLength + payload.length)
    const view = new DataView(frame)
    view.setUint32(0, headerBytes.byteLength, false)
    new Uint8Array(frame, 4, headerBytes.byteLength).set(headerBytes)
    new Uint8Array(frame, 4 + headerBytes.byteLength).set(payload)

    relay.handleRelayData(frame)
    const decoded = onData.mock.calls[0][0] as Record<string, unknown>
    expect(decoded.bytes).toBeUndefined()
    expect(decoded.payload).toBeInstanceOf(ArrayBuffer)
    expect(new Uint8Array(decoded.payload as ArrayBuffer)).toEqual(payload)
  })

  it('fires onError when binary frame has invalid header length', () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    const onError = vi.fn()
    relay.onError = onError
    relay.start()

    // Frame claims header length > actual frame bytes.
    const frame = new ArrayBuffer(8)
    new DataView(frame).setUint32(0, 9999, false) // header length 9999 in an 8-byte frame
    relay.handleRelayData(frame)
    expect(onError).toHaveBeenCalledTimes(1)
    expect(onError.mock.calls[0][0].message).toMatch(/malformed/)
  })

  it('fires onError when binary frame is too small (< 4 bytes)', () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    const onError = vi.fn()
    relay.onError = onError
    relay.start()

    const frame = new ArrayBuffer(2)
    relay.handleRelayData(frame)
    expect(onError).toHaveBeenCalledTimes(1)
  })
})

describe('WebSocketRelay — send', () => {
  it('throws when the relay is not open', async () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    await expect(relay.send({ type: 'x' })).rejects.toThrow(/not open/)
  })

  it('JSON-only payload goes via sendRelayText', async () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    relay.start()
    await relay.send({ type: 'offer', sdp: 'abc' })
    expect(sig._sentText).toHaveLength(1)
    expect(sig._sentText[0].targetId).toBe(PEER)
    expect(JSON.parse(sig._sentText[0].text)).toEqual({
      type: 'offer',
      sdp: 'abc',
    })
    expect(sig._sentBinary).toHaveLength(0)
  })

  it('binary "bytes" field produces a framed ArrayBuffer via sendBinary', async () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    relay.start()

    const payload = new Uint8Array([10, 20, 30]).buffer
    await relay.send({ type: 'chunk', seq: 1, bytes: payload })

    expect(sig._sentBinary).toHaveLength(1)
    const frame = sig._sentBinary[0].data
    const view = new DataView(frame)
    const headerLen = view.getUint32(0, false)
    const headerBytes = new Uint8Array(frame, 4, headerLen)
    const header = JSON.parse(new TextDecoder().decode(headerBytes))
    expect(header).toEqual({ type: 'chunk', seq: 1, _hasBinary: 'bytes' })

    const payloadOut = new Uint8Array(frame, 4 + headerLen)
    expect(Array.from(payloadOut)).toEqual([10, 20, 30])
    expect(sig._sentText).toHaveLength(0)
  })

  it('binary "payload" field sets _hasBinary: "payload"', async () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    relay.start()

    const payload = new Uint8Array([1, 2, 3]).buffer
    await relay.send({ type: 'chunk', payload })

    const frame = sig._sentBinary[0].data
    const view = new DataView(frame)
    const headerLen = view.getUint32(0, false)
    const header = JSON.parse(
      new TextDecoder().decode(new Uint8Array(frame, 4, headerLen)),
    )
    expect(header._hasBinary).toBe('payload')
    expect(header.payload).toBeUndefined()
  })

  it('accepts a TypedArray (Uint8Array) for the binary field', async () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    relay.start()

    const payload = new Uint8Array([7, 8, 9])
    await relay.send({ type: 'chunk', bytes: payload })

    expect(sig._sentBinary).toHaveLength(1)
    const frame = sig._sentBinary[0].data
    const view = new DataView(frame)
    const headerLen = view.getUint32(0, false)
    const out = new Uint8Array(frame, 4 + headerLen)
    expect(Array.from(out)).toEqual([7, 8, 9])
  })

  it('rejects a DataView binary field (only raw ArrayBuffer / Uint8Array etc. supported)', async () => {
    const sig = makeSignaling()
    const relay = new WebSocketRelay(sig, PEER)
    relay.start()

    // DataView is excluded explicitly — it falls through to the
    // JSON-only path, which won't carry the binary bytes. Test that
    // this path uses sendRelayText rather than throwing.
    const payload = new DataView(new ArrayBuffer(4))
    await relay.send({ type: 'chunk', bytes: payload })
    expect(sig._sentText).toHaveLength(1)
    expect(sig._sentBinary).toHaveLength(0)
  })
})

describe('WebSocketRelay — roundtrip', () => {
  it('encoded binary send → decoded handleRelayData preserves bytes + header', async () => {
    const sig = makeSignaling()
    const a = new WebSocketRelay(sig, PEER)
    a.start()
    const payload = new Uint8Array([42, 43, 44, 45, 46]).buffer
    await a.send({ type: 'chunk', seq: 7, bytes: payload })

    // Feed the captured frame back into a second relay's decoder.
    const b = new WebSocketRelay(sig, PEER)
    b.start()
    const received: unknown[] = []
    b.onData = (m) => received.push(m)
    b.handleRelayData(sig._sentBinary[0].data)

    expect(received).toHaveLength(1)
    const msg = received[0] as Record<string, unknown>
    expect(msg.type).toBe('chunk')
    expect(msg.seq).toBe(7)
    expect(msg._hasBinary).toBeUndefined()
    expect(new Uint8Array(msg.bytes as ArrayBuffer)).toEqual(
      new Uint8Array(payload),
    )
  })
})
