import { describe, expect, it } from 'vitest'

import { parseZenUml, zenUmlToElements } from './mermaid-zenuml'

describe('parseZenUml', () => {
  it('returns null when the source is not zenuml', () => {
    expect(parseZenUml('flowchart TD\nA --> B')).toBeNull()
    expect(parseZenUml('')).toBeNull()
  })

  it('captures the title', () => {
    const d = parseZenUml('zenuml\ntitle Order Flow')!
    expect(d.title).toBe('Order Flow')
  })

  it('parses typed participant declarations', () => {
    const d = parseZenUml(`zenuml
      @Actor Alice
      @Database DB
      @Boundary API
      @Control Ctrl
      @Entity Order`)!
    const ids = d.participants.map((p) => p.id)
    const kinds = new Map(d.participants.map((p) => [p.id, p.kind]))
    expect(ids).toEqual(['Alice', 'DB', 'API', 'Ctrl', 'Order'])
    expect(kinds.get('Alice')).toBe('Actor')
    expect(kinds.get('DB')).toBe('Database')
    expect(kinds.get('API')).toBe('Boundary')
    expect(kinds.get('Ctrl')).toBe('Control')
    expect(kinds.get('Order')).toBe('Entity')
  })

  it('infers untyped participants from messages as Object', () => {
    const d = parseZenUml('zenuml\nAlice->Bob.method()')!
    const bob = d.participants.find((p) => p.id === 'Bob')!
    expect(bob.kind).toBe('Object')
  })

  it('parses sync messages as solid arrows', () => {
    const d = parseZenUml('zenuml\nAlice->Bob.placeOrder()')!
    expect(d.messages).toHaveLength(1)
    expect(d.messages[0]).toEqual({
      from: 'Alice',
      to: 'Bob',
      label: 'placeOrder()',
      dashed: false,
      isReturn: false,
    })
  })

  it('marks ->> messages as dashed (async)', () => {
    const d = parseZenUml('zenuml\nAlice->>Bob.notify()')!
    expect(d.messages[0].dashed).toBe(true)
  })

  it('emits a return arrow back to the caller from inside a block', () => {
    const d = parseZenUml(`zenuml
      Alice->Bob.run() {
        return done
      }`)!
    expect(d.messages).toHaveLength(2)
    const ret = d.messages[1]
    expect(ret.from).toBe('Bob')
    expect(ret.to).toBe('Alice')
    expect(ret.label).toBe('done')
    expect(ret.isReturn).toBe(true)
    expect(ret.dashed).toBe(true)
  })

  it('resolves a bare nested call against the enclosing block', () => {
    const d = parseZenUml(`zenuml
      Alice->Bob.run() {
        Charlie.helper()
      }`)!
    // Bob (top of stack inside the block) calls Charlie.
    const nested = d.messages.find((m) => m.to === 'Charlie')!
    expect(nested.from).toBe('Bob')
    expect(nested.label).toBe('helper()')
  })

  it('parses messages inside an if(...) fragment without dropping them', () => {
    const d = parseZenUml(`zenuml
      Alice->Bob.run() {
        if (x > 0) {
          Bob->DB.query()
        }
      }`)!
    expect(d.messages.find((m) => m.to === 'DB')).toBeDefined()
  })

  it('skips comments + tolerates trailing comments', () => {
    const d = parseZenUml(`zenuml
      %% intro
      Alice->Bob.x() %% trailing`)!
    expect(d.messages).toHaveLength(1)
  })

  it('ignores garbled lines without aborting', () => {
    const d = parseZenUml(`zenuml
      Alice->Bob.a()
      garbled+++
      Bob->Charlie.b()`)!
    expect(d.messages).toHaveLength(2)
  })
})

describe('zenUmlToElements', () => {
  it('emits one rect + label + lifeline per participant', () => {
    const d = parseZenUml(`zenuml
      Alice->Bob.x()`)!
    const els = zenUmlToElements(d)
    // 2 participant heads + 2 lifelines + 1 message arrow + 1 message label.
    expect(els.filter((e) => e.type === 'rect')).toHaveLength(2)
    expect(els.filter((e) => e.type === 'line')).toHaveLength(2)
    expect(els.filter((e) => e.type === 'arrow')).toHaveLength(1)
  })

  it('renders the title text when set', () => {
    const d = parseZenUml('zenuml\ntitle Hello\nA->B.x()')!
    const els = zenUmlToElements(d)
    const titles = els.filter(
      (e) =>
        e.type === 'text' &&
        (e as unknown as { text: string }).text === 'Hello',
    )
    expect(titles).toHaveLength(1)
  })

  it('async messages render with a dashed stroke', () => {
    const d = parseZenUml('zenuml\nA->>B.x()')!
    const els = zenUmlToElements(d)
    const arrow = els.find((e) => e.type === 'arrow') as unknown as {
      strokeStyle: string
    }
    expect(arrow.strokeStyle).toBe('dashed')
  })

  it('places later participants to the right of earlier ones', () => {
    const d = parseZenUml('zenuml\nA->B.x()\nB->C.y()')!
    const els = zenUmlToElements(d)
    // Pull the participant header rects (one per participant), ordered.
    const heads = els
      .filter((e) => e.type === 'rect')
      .map((e) => (e as unknown as { x: number }).x)
    expect(heads.length).toBeGreaterThanOrEqual(3)
    expect(heads[0]).toBeLessThan(heads[1])
    expect(heads[1]).toBeLessThan(heads[2])
  })

  it('places later messages below earlier ones', () => {
    const d = parseZenUml('zenuml\nA->B.first()\nA->B.second()')!
    const els = zenUmlToElements(d)
    const arrows = els.filter((e) => e.type === 'arrow') as Array<{
      y: number
    }>
    expect(arrows[0].y).toBeLessThan(arrows[1].y)
  })

  it('respects originX / originY', () => {
    const d = parseZenUml('zenuml\nA->B.x()')!
    const els = zenUmlToElements(d, { originX: 500, originY: 300 })
    const rect = els.find((e) => e.type === 'rect') as { x: number; y: number }
    expect(rect.x).toBeGreaterThanOrEqual(500)
    expect(rect.y).toBeGreaterThanOrEqual(300)
  })

  it('produces deterministic output for a given input', () => {
    const a = zenUmlToElements(parseZenUml('zenuml\nA->B.x()\nB->C.y()')!)
    const b = zenUmlToElements(parseZenUml('zenuml\nA->B.x()\nB->C.y()')!)
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })

  it('renders nothing meaningful for an empty diagram', () => {
    const d = parseZenUml('zenuml\n%% no content')!
    expect(zenUmlToElements(d)).toEqual([])
  })
})
