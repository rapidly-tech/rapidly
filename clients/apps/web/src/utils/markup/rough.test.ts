/**
 * Rough-path determinism tests.
 *
 * The jitter module is deliberately seed-reproducible: every peer
 * paints a given element with the exact same wobble. We can't
 * pixel-diff inside vitest (no canvas backend), but the PRNG output
 * is directly observable, and we can call our rough functions
 * against a minimal Path2D stub and count the commands they emit.
 */

import { describe, expect, it } from 'vitest'

import {
  clampRoughness,
  makeRng,
  roughEllipse,
  roughLine,
  roughRect,
} from './rough'

/** Path2D stand-in for tests — logs every command so assertions can
 *  inspect what was drawn. The real Path2D isn't polyfilled in
 *  jsdom and we don't need it here. */
class SpyPath {
  readonly ops: string[] = []
  moveTo(x: number, y: number): void {
    this.ops.push(`M ${x.toFixed(4)} ${y.toFixed(4)}`)
  }
  lineTo(x: number, y: number): void {
    this.ops.push(`L ${x.toFixed(4)} ${y.toFixed(4)}`)
  }
  bezierCurveTo(
    c1x: number,
    c1y: number,
    c2x: number,
    c2y: number,
    x: number,
    y: number,
  ): void {
    this.ops.push(
      `B ${c1x.toFixed(4)} ${c1y.toFixed(4)} ${c2x.toFixed(4)} ${c2y.toFixed(4)} ${x.toFixed(4)} ${y.toFixed(4)}`,
    )
  }
  quadraticCurveTo(cx: number, cy: number, x: number, y: number): void {
    this.ops.push(
      `Q ${cx.toFixed(4)} ${cy.toFixed(4)} ${x.toFixed(4)} ${y.toFixed(4)}`,
    )
  }
  closePath(): void {
    this.ops.push('Z')
  }
}

describe('makeRng', () => {
  it('same seed → same sequence', () => {
    const a = makeRng(42)
    const b = makeRng(42)
    for (let i = 0; i < 10; i++) {
      expect(a()).toBe(b())
    }
  })

  it('different seeds → different sequences', () => {
    const a = makeRng(1)
    const b = makeRng(2)
    const diffs = [a() !== b(), a() !== b(), a() !== b()].filter(Boolean).length
    expect(diffs).toBeGreaterThan(0)
  })

  it('output is bounded in [0, 1)', () => {
    const r = makeRng(123)
    for (let i = 0; i < 100; i++) {
      const v = r()
      expect(v).toBeGreaterThanOrEqual(0)
      expect(v).toBeLessThan(1)
    }
  })
})

describe('roughLine', () => {
  it('emits a bezier per stroke and doubles at roughness > 0', () => {
    const p1 = new SpyPath() as unknown as Path2D
    const spy = p1 as unknown as SpyPath
    roughLine(p1, 0, 0, 100, 0, makeRng(1), { roughness: 1 })
    // One rough line with roughness > 0 draws twice: 2× (move + bezier).
    expect(spy.ops.filter((o) => o.startsWith('M')).length).toBe(2)
    expect(spy.ops.filter((o) => o.startsWith('B')).length).toBe(2)
  })

  it('single-stroke when doubleStroke is false', () => {
    const p = new SpyPath() as unknown as Path2D
    const spy = p as unknown as SpyPath
    roughLine(p, 0, 0, 100, 0, makeRng(1), {
      roughness: 1,
      doubleStroke: false,
    })
    expect(spy.ops.filter((o) => o.startsWith('M')).length).toBe(1)
  })

  it('same seed → same commands (determinism for CRDT parity)', () => {
    const p1 = new SpyPath() as unknown as Path2D
    const p2 = new SpyPath() as unknown as Path2D
    roughLine(p1, 10, 20, 200, 50, makeRng(99), { roughness: 2 })
    roughLine(p2, 10, 20, 200, 50, makeRng(99), { roughness: 2 })
    expect((p1 as unknown as SpyPath).ops).toEqual(
      (p2 as unknown as SpyPath).ops,
    )
  })

  it('different seeds → different commands', () => {
    const p1 = new SpyPath() as unknown as Path2D
    const p2 = new SpyPath() as unknown as Path2D
    roughLine(p1, 0, 0, 100, 0, makeRng(1), { roughness: 2 })
    roughLine(p2, 0, 0, 100, 0, makeRng(99), { roughness: 2 })
    expect((p1 as unknown as SpyPath).ops).not.toEqual(
      (p2 as unknown as SpyPath).ops,
    )
  })
})

describe('roughRect', () => {
  it('draws 4 sides', () => {
    const p = new SpyPath() as unknown as Path2D
    const spy = p as unknown as SpyPath
    roughRect(p, 0, 0, 100, 50, makeRng(1), { roughness: 1 })
    // Four rough lines × two passes each = 8 moveTos.
    expect(spy.ops.filter((o) => o.startsWith('M')).length).toBe(8)
  })

  it('same seed → same rect commands', () => {
    const p1 = new SpyPath() as unknown as Path2D
    const p2 = new SpyPath() as unknown as Path2D
    roughRect(p1, 0, 0, 100, 50, makeRng(7), { roughness: 2 })
    roughRect(p2, 0, 0, 100, 50, makeRng(7), { roughness: 2 })
    expect((p1 as unknown as SpyPath).ops).toEqual(
      (p2 as unknown as SpyPath).ops,
    )
  })
})

describe('roughEllipse', () => {
  it('emits a closed loop of quadratic curves', () => {
    const p = new SpyPath() as unknown as Path2D
    const spy = p as unknown as SpyPath
    roughEllipse(p, 50, 25, 50, 25, makeRng(1), { roughness: 1 })
    expect(spy.ops.filter((o) => o === 'Z').length).toBe(2) // double-stroke closes twice
    expect(spy.ops.filter((o) => o.startsWith('Q')).length).toBeGreaterThan(0)
  })

  it('same seed → same ellipse commands', () => {
    const p1 = new SpyPath() as unknown as Path2D
    const p2 = new SpyPath() as unknown as Path2D
    roughEllipse(p1, 0, 0, 40, 20, makeRng(3), { roughness: 2 })
    roughEllipse(p2, 0, 0, 40, 20, makeRng(3), { roughness: 2 })
    expect((p1 as unknown as SpyPath).ops).toEqual(
      (p2 as unknown as SpyPath).ops,
    )
  })
})

describe('clampRoughness', () => {
  it('maps values to 0/1/2', () => {
    expect(clampRoughness(-5)).toBe(0)
    expect(clampRoughness(0)).toBe(0)
    expect(clampRoughness(1)).toBe(1)
    expect(clampRoughness(1.5)).toBe(1)
    expect(clampRoughness(2)).toBe(2)
    expect(clampRoughness(10)).toBe(2)
  })
})
