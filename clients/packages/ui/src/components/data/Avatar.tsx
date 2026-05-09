'use client'

import { cn } from '@/lib/utils'
import {
  type ComponentProps,
  type ComponentType,
  useCallback,
  useMemo,
  useRef,
  useState,
} from 'react'

/** Derive first + last initials from a display name (or email). */
function extractInitials(displayName: string | undefined | null): string {
  if (!displayName) return ''
  const sanitised = displayName
    .split('@')[0]
    .replace(/[^a-zA-Z ]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  const parts = sanitised.split(' ')
  if (parts.length === 0 || parts[0] === '') return ''

  const first = parts[0].charAt(0).toUpperCase()
  const last =
    parts.length > 1 ? parts[parts.length - 1].charAt(0).toUpperCase() : ''
  return first + last
}

// Shared container classes for both image and fallback states
const CONTAINER_BASE =
  'relative z-2 flex h-6 w-6 shrink-0 items-center justify-center rounded-full font-sans text-[10px]'
const CONTAINER_LIGHT =
  'bg-white/[0.06] backdrop-blur-2xl backdrop-saturate-150 text-slate-700'
const CONTAINER_DARK =
  'dark:bg-white/[0.04] dark:border-white/[0.06] dark:text-slate-400'

interface AvatarInternalProps {
  name: string | undefined | null
  avatar_url: string | null
  className?: string
  height?: number
  width?: number
  loading?: React.ImgHTMLAttributes<HTMLImageElement>['loading']
  CustomImageComponent?: ComponentType<any>
}

function AvatarInner({
  name,
  avatar_url,
  className,
  height,
  width,
  loading = 'eager',
  CustomImageComponent,
}: AvatarInternalProps) {
  const initials = useMemo(() => extractInitials(name), [name])

  // Track image load lifecycle -- start hidden to avoid alt-text flash
  const [imageReady, setImageReady] = useState(false)
  const [useFallback, setUseFallback] = useState(avatar_url === null)
  const imageRef = useRef<HTMLImageElement>(null)

  const handleLoad = useCallback(() => {
    setImageReady(true)
    setUseFallback(false)
  }, [])

  const handleError = useCallback(() => {
    setUseFallback(true)
    setImageReady(true)
  }, [])

  // Callback ref to detect browser-cached images that fire no load event.
  const imageCallbackRef = useCallback((el: HTMLImageElement | null) => {
    imageRef.current = el
    if (el?.complete) {
      setImageReady(true)
      setUseFallback(false)
    }
  }, [])

  const Img = CustomImageComponent ?? 'img'
  const shouldShowInitials = !avatar_url || useFallback

  return (
    <div
      role="img"
      aria-label={name ?? 'Avatar'}
      className={cn(CONTAINER_BASE, CONTAINER_LIGHT, CONTAINER_DARK, className)}
    >
      {/* Inset ring overlay */}
      <span
        aria-hidden="true"
        className="absolute inset-0 z-2 rounded-full ring ring-black/10 ring-inset dark:ring-white/10"
      />

      {shouldShowInitials ? (
        <span className="absolute inset-0 flex items-center justify-center bg-transparent">
          {initials}
        </span>
      ) : (
        /* eslint-disable-next-line @next/next/no-img-element */
        <Img
          ref={imageCallbackRef}
          alt={name ?? ''}
          src={avatar_url}
          height={height}
          width={width}
          loading={loading}
          onLoad={handleLoad}
          onError={handleError}
          className={cn(
            'z-1 aspect-square rounded-full object-cover',
            imageReady ? 'opacity-100' : 'opacity-0',
          )}
        />
      )}
    </div>
  )
}

/** Avatar with image support and initials fallback. Remounts when the URL changes. */
const Avatar = (props: ComponentProps<typeof AvatarInner>) => (
  <AvatarInner {...props} key={props.avatar_url} />
)

export default Avatar
