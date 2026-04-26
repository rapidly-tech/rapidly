'use client'

/**
 * Participant tile for the Call chamber — renders one participant's
 * MediaStream in a <video> with a label. ``muted`` is passed through as
 * the DOM attribute; for the local tile it should be ``true`` to avoid
 * acoustic feedback.
 */

import { useEffect, useRef } from 'react'

interface ParticipantTileProps {
  stream: MediaStream | null
  label: string
  muted?: boolean
  /** When the local participant has video off, we blank the <video>. */
  videoOff?: boolean
}

export function ParticipantTile({
  stream,
  label,
  muted = false,
  videoOff = false,
}: ParticipantTileProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null)

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream
    }
  }, [stream])

  return (
    <div className="relative flex aspect-video w-full items-center justify-center overflow-hidden rounded-xl border border-slate-200 bg-slate-950 shadow dark:border-slate-800">
      {stream && !videoOff ? (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted={muted}
          className="h-full w-full object-cover"
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center text-sm text-slate-400">
          {videoOff ? 'Camera off' : 'Connecting…'}
        </div>
      )}
      <div className="absolute bottom-2 left-2 rounded-md bg-black/60 px-2 py-0.5 text-xs text-white">
        {label}
      </div>
    </div>
  )
}
