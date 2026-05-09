import { describe, expect, it, vi } from 'vitest'

import { createVideoController } from './video-controller'

/** Minimal HTMLVideoElement stand-in. EventTarget-based so our adapter's
 *  addEventListener / removeEventListener calls land naturally and we
 *  can ``dispatchEvent`` to simulate browser events. */
function makeVideoStub() {
  const target = new EventTarget()
  const stub = {
    paused: true,
    currentTime: 0,
    playbackRate: 1,
    play: vi.fn(async () => {
      stub.paused = false
    }),
    pause: vi.fn(() => {
      stub.paused = true
    }),
    addEventListener: target.addEventListener.bind(target),
    removeEventListener: target.removeEventListener.bind(target),
    dispatchEvent: target.dispatchEvent.bind(target),
  }
  return stub as unknown as HTMLVideoElement & typeof stub
}

describe('createVideoController', () => {
  it('reports playing=false when the video is paused', () => {
    const video = makeVideoStub()
    video.paused = true
    const ctrl = createVideoController(video)
    expect(ctrl.playing).toBe(false)
    ctrl.dispose()
  })

  it('reports playing=true when paused is false', () => {
    const video = makeVideoStub()
    video.paused = false
    const ctrl = createVideoController(video)
    expect(ctrl.playing).toBe(true)
    ctrl.dispose()
  })

  it('exposes the video currentTime', () => {
    const video = makeVideoStub()
    video.currentTime = 42
    const ctrl = createVideoController(video)
    expect(ctrl.currentTime).toBe(42)
    ctrl.dispose()
  })

  it('forwards play / pause to the video element', async () => {
    const video = makeVideoStub()
    const ctrl = createVideoController(video)
    await ctrl.play()
    expect(video.play).toHaveBeenCalledTimes(1)
    ctrl.pause()
    expect(video.pause).toHaveBeenCalledTimes(1)
    ctrl.dispose()
  })

  it('swallows an autoplay-blocked rejection', async () => {
    const video = makeVideoStub()
    video.play = vi.fn(async () => {
      throw new DOMException('autoplay blocked', 'NotAllowedError')
    }) as unknown as typeof video.play
    const ctrl = createVideoController(video)
    await expect(ctrl.play()).resolves.toBeUndefined()
    ctrl.dispose()
  })

  it('setPlaybackRate writes through to the video', () => {
    const video = makeVideoStub()
    const ctrl = createVideoController(video)
    ctrl.setPlaybackRate(1.5)
    expect(video.playbackRate).toBe(1.5)
    ctrl.dispose()
  })

  it('seek() sets currentTime and suppresses the echoed seeked event', () => {
    const video = makeVideoStub()
    const ctrl = createVideoController(video)
    const onSeek = vi.fn()
    ctrl.onSeek(onSeek)
    ctrl.seek(30)
    expect(video.currentTime).toBe(30)
    // Programmatic seek fires ``seeked`` in the browser — simulate it.
    video.dispatchEvent(new Event('seeked'))
    expect(onSeek).not.toHaveBeenCalled()
    ctrl.dispose()
  })

  it('a user-driven seeked event (no preceding seek()) reports the new time', () => {
    const video = makeVideoStub()
    const ctrl = createVideoController(video)
    const onSeek = vi.fn()
    ctrl.onSeek(onSeek)
    video.currentTime = 75
    video.dispatchEvent(new Event('seeked'))
    expect(onSeek).toHaveBeenCalledWith(75)
    ctrl.dispose()
  })

  it('suppression counter tracks programmatic seeks one-for-one', () => {
    const video = makeVideoStub()
    const ctrl = createVideoController(video)
    const onSeek = vi.fn()
    ctrl.onSeek(onSeek)
    ctrl.seek(10)
    ctrl.seek(20)
    // Two programmatic seeks → two suppressions.
    video.dispatchEvent(new Event('seeked'))
    video.dispatchEvent(new Event('seeked'))
    expect(onSeek).not.toHaveBeenCalled()
    // The third seeked event is a real user seek and fires the callback.
    video.currentTime = 25
    video.dispatchEvent(new Event('seeked'))
    expect(onSeek).toHaveBeenCalledWith(25)
    ctrl.dispose()
  })

  it('play / pause callbacks fire with the right playing flag', () => {
    const video = makeVideoStub()
    const ctrl = createVideoController(video)
    const cb = vi.fn()
    ctrl.onPlayOrPause(cb)
    video.dispatchEvent(new Event('play'))
    expect(cb).toHaveBeenLastCalledWith(true)
    video.dispatchEvent(new Event('pause'))
    expect(cb).toHaveBeenLastCalledWith(false)
    ctrl.dispose()
  })

  it('canplay callbacks fire on canplay events', () => {
    const video = makeVideoStub()
    const ctrl = createVideoController(video)
    const cb = vi.fn()
    ctrl.onCanPlay(cb)
    video.dispatchEvent(new Event('canplay'))
    expect(cb).toHaveBeenCalledTimes(1)
    ctrl.dispose()
  })

  it('subscription callbacks return unsubscribe fns that stop firing', () => {
    const video = makeVideoStub()
    const ctrl = createVideoController(video)
    const play = vi.fn()
    const seek = vi.fn()
    const canPlay = vi.fn()
    const offPlay = ctrl.onPlayOrPause(play)
    const offSeek = ctrl.onSeek(seek)
    const offCanPlay = ctrl.onCanPlay(canPlay)

    offPlay()
    offSeek()
    offCanPlay()

    video.dispatchEvent(new Event('play'))
    video.dispatchEvent(new Event('seeked'))
    video.dispatchEvent(new Event('canplay'))
    expect(play).not.toHaveBeenCalled()
    expect(seek).not.toHaveBeenCalled()
    expect(canPlay).not.toHaveBeenCalled()
    ctrl.dispose()
  })

  it('dispose() removes listeners + clears pending callbacks', () => {
    const video = makeVideoStub()
    const ctrl = createVideoController(video)
    const cb = vi.fn()
    ctrl.onPlayOrPause(cb)
    ctrl.dispose()
    // Events after dispose should be ignored.
    video.dispatchEvent(new Event('play'))
    video.dispatchEvent(new Event('pause'))
    video.dispatchEvent(new Event('seeked'))
    video.dispatchEvent(new Event('canplay'))
    expect(cb).not.toHaveBeenCalled()
  })
})
