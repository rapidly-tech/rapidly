/**
 * HTMLVideoElement → SyncMediaController adapter (PR 11).
 *
 * Bridges the browser's ``<video>`` events to the narrow interface the
 * PR 10 sync engines expect. Keeping this adapter in its own file means
 * the engines stay DOM-independent and unit-testable.
 *
 * Caller must hold a ref to the returned controller and call
 * ``dispose()`` when the video element unmounts.
 */

import type { SyncMediaController } from './sync-protocol'

/** When the sync engine calls ``seek()``, we set ``currentTime`` which
 *  fires a ``seeked`` DOM event that would re-enter the user-seek
 *  listener and echo a bogus seek back to the host. Track suppression
 *  so programmatic seeks don't emit. */
export interface VideoSyncController extends SyncMediaController {
  dispose(): void
}

export function createVideoController(
  video: HTMLVideoElement,
): VideoSyncController {
  let suppressUserSeek = 0

  const playCbs = new Set<(playing: boolean) => void>()
  const seekCbs = new Set<(time: number) => void>()
  const canPlayCbs = new Set<() => void>()

  const onPlay = () => playCbs.forEach((c) => c(true))
  const onPause = () => playCbs.forEach((c) => c(false))
  const onSeeked = () => {
    if (suppressUserSeek > 0) {
      suppressUserSeek--
      return
    }
    seekCbs.forEach((c) => c(video.currentTime))
  }
  const onCanPlay = () => canPlayCbs.forEach((c) => c())

  video.addEventListener('play', onPlay)
  video.addEventListener('pause', onPause)
  video.addEventListener('seeked', onSeeked)
  video.addEventListener('canplay', onCanPlay)

  return {
    get playing(): boolean {
      return !video.paused
    },
    get currentTime(): number {
      return video.currentTime
    },
    async play(): Promise<void> {
      try {
        await video.play()
      } catch {
        // Autoplay blocked is a recoverable state; surface via the
        // host/guest hook's status rather than as a thrown promise.
      }
    },
    pause(): void {
      video.pause()
    },
    seek(time: number): void {
      suppressUserSeek++
      video.currentTime = time
    },
    setPlaybackRate(rate: number): void {
      video.playbackRate = rate
    },
    onPlayOrPause(cb): () => void {
      playCbs.add(cb)
      return () => {
        playCbs.delete(cb)
      }
    },
    onSeek(cb): () => void {
      seekCbs.add(cb)
      return () => {
        seekCbs.delete(cb)
      }
    },
    onCanPlay(cb): () => void {
      canPlayCbs.add(cb)
      return () => {
        canPlayCbs.delete(cb)
      }
    },
    dispose(): void {
      video.removeEventListener('play', onPlay)
      video.removeEventListener('pause', onPause)
      video.removeEventListener('seeked', onSeeked)
      video.removeEventListener('canplay', onCanPlay)
      playCbs.clear()
      seekCbs.clear()
      canPlayCbs.clear()
    },
  }
}
