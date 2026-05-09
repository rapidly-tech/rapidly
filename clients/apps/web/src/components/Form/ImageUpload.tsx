'use client'

/**
 * ImageUpload - single-image upload widget for the Rapidly dashboard.
 *
 * Shows either the current image preview or a placeholder, handles
 * upload via Vercel Blob, and runs optional dimension validation.
 */

import { SpinnerNoMargin } from '@/components/Shared/Spinner'
import { Icon } from '@iconify/react'
import { upload } from '@vercel/blob/client'
import { useCallback, useEffect, useRef, useState } from 'react'
import { twMerge } from 'tailwind-merge'

// ── Types ──

interface ImageUploadProps {
  onUploaded: (url: string) => void
  validate?: (el: HTMLImageElement) => string | undefined
  defaultValue?: string
  height?: number
  width?: number
}

// ── Component ──

const ImageUpload = ({
  onUploaded,
  validate,
  defaultValue,
  height,
  width,
}: ImageUploadProps) => {
  const inputRef = useRef<HTMLInputElement>(null)
  const previewRef = useRef<HTMLImageElement>(null)

  const [previewSrc, setPreviewSrc] = useState<string | undefined>()
  const [uploading, setUploading] = useState(false)
  const [validationError, setValidationError] = useState<string | undefined>()

  // Sync preview with controlled default
  useEffect(() => {
    setPreviewSrc(defaultValue)
  }, [defaultValue])

  // ── Upload Logic ──

  const performUpload = useCallback(async () => {
    const selectedFile = inputRef.current?.files?.[0]
    if (!selectedFile) return

    setUploading(true)
    setValidationError(undefined)

    try {
      const result = await upload(selectedFile.name, selectedFile, {
        access: 'public',
        handleUploadUrl: '/api/blob/upload',
      })
      onUploaded(result.url)
    } catch (_err) {
      setValidationError('Failed to upload image')
    } finally {
      setUploading(false)
    }
  }, [onUploaded])

  // ── Event Handlers ──

  const handleFileChange = useCallback(
    async (ev: React.ChangeEvent<HTMLInputElement>) => {
      const chosen = ev.target.files?.[0]
      if (!chosen) {
        setPreviewSrc(undefined)
        return
      }
      // Generate a local preview immediately
      const reader = new FileReader()
      reader.onload = (loadEvent) => {
        const dataUrl = loadEvent.target?.result
        if (typeof dataUrl === 'string') setPreviewSrc(dataUrl)
      }
      reader.readAsDataURL(chosen)
      await performUpload()
    },
    [performUpload],
  )

  const handleImageLoaded = useCallback(
    (ev: React.SyntheticEvent<HTMLImageElement>) => {
      if (validate) setValidationError(validate(ev.currentTarget))
    },
    [validate],
  )

  const openFilePicker = useCallback(() => {
    inputRef.current?.click()
  }, [])

  // ── Sizing ──

  const usesExplicitSize = Boolean(height && width)
  const fallbackSize = !height && !width ? 'h-32 w-32' : ''

  return (
    <div>
      <input
        ref={inputRef}
        name="file"
        type="file"
        required
        accept="image/*"
        style={{ display: 'none', height: 0 }}
        onChange={handleFileChange}
        aria-describedby={validationError ? 'image-upload-error' : undefined}
      />

      <div className="flex flex-col items-start gap-4">
        {previewSrc ? (
          <div className="relative">
            {/* eslint-disable-next-line @next/next/no-img-element, no-restricted-syntax */}
            <img
              ref={previewRef}
              src={previewSrc}
              alt="Uploaded image preview"
              role="button"
              tabIndex={0}
              className={twMerge(
                'flex cursor-pointer items-center justify-center rounded-xl border border-slate-200 bg-slate-50 object-cover hover:opacity-80 dark:border-slate-700 dark:bg-slate-800',
                uploading ? 'opacity-50' : '',
                validationError ? 'border-red-500' : '',
                fallbackSize,
              )}
              onClick={openFilePicker}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') openFilePicker()
              }}
              onLoad={handleImageLoaded}
              height={height}
              width={width}
            />
            {uploading && (
              <div className="absolute top-0 right-0 bottom-0 left-0 flex items-center justify-center">
                <SpinnerNoMargin />
              </div>
            )}
          </div>
        ) : (
          <div
            onClick={openFilePicker}
            role="button"
            tabIndex={0}
            aria-label="Select image file"
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') openFilePicker()
            }}
            className={twMerge(
              'flex cursor-pointer flex-col items-center justify-center gap-y-2 rounded-xl border border-slate-200 bg-slate-50 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800',
              fallbackSize,
            )}
            style={{
              maxWidth: width,
              maxHeight: height,
              width: usesExplicitSize ? '100%' : undefined,
              aspectRatio: usesExplicitSize
                ? `${width} / ${height}`
                : undefined,
            }}
          >
            <Icon
              icon="solar:gallery-linear"
              className="h-6 w-6 text-slate-600 dark:text-slate-400"
            />
            {usesExplicitSize && (
              <div className="text-xs text-slate-600 dark:text-slate-400">
                {height} x {width}px
              </div>
            )}
          </div>
        )}

        {validationError && (
          <div
            id="image-upload-error"
            role="alert"
            className="text-sm text-red-500 dark:text-red-400"
          >
            {validationError}
          </div>
        )}
      </div>
    </div>
  )
}

export default ImageUpload
