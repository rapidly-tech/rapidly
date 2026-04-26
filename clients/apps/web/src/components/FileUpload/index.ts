'use client'

/**
 * useFileUpload - Rapidly file upload hook.
 *
 * Manages multi-file upload state including processing, progress tracking,
 * and completion. Wraps the Upload class and react-dropzone together.
 */

import { schemas } from '@rapidly-tech/client'
import { useState } from 'react'
import { Accept, FileRejection, useDropzone } from 'react-dropzone'
import { FileRead, Upload } from './Upload'

// ── Types ──

export type FileObject<
  T extends FileRead | schemas['FileUpload'] = FileRead | schemas['FileUpload'],
> = T & {
  isProcessing: boolean
  isUploading: boolean
  uploadedBytes: number
  file?: File
}

// ── Internal Helpers ──

/** Wrap a raw file record into a FileObject with default tracking fields. */
function wrapAsFileObject<T extends FileRead | schemas['FileUpload']>(
  raw: T,
): FileObject<T> {
  return {
    ...raw,
    isProcessing: false,
    isUploading: false,
    uploadedBytes: raw.is_uploaded ? raw.size : 0,
  }
}

/**
 * Widen a concrete FileObject to the generic FileObject<T>.
 *
 * TypeScript cannot verify that FileObject<FileRead> is assignable to
 * FileObject<T> when T is a generic parameter, even though T is bounded
 * by `FileRead | FileUpload`. This helper centralises the unavoidable
 * assertion so every call-site stays clean and the reason is documented
 * in one place.
 */
function toFileObject<T extends FileRead | schemas['FileUpload']>(
  obj: FileObject<FileRead> | FileObject<schemas['FileUpload']>,
): FileObject<T> {
  // The intermediate `unknown` is required because TS generic constraints
  // cannot prove that a concrete union member is assignable to an
  // unconstrained generic T, even when T is bounded by that same union.
  return obj as unknown as FileObject<T>
}

/** Create a temporary placeholder FileObject for a file that is being hashed/processed. */
function createPlaceholder(
  tempId: string,
  nativeFile: File,
): FileObject<FileRead> {
  return {
    ...wrapAsFileObject({
      id: tempId,
      name: nativeFile.name,
      size: nativeFile.size,
      mime_type: nativeFile.type || 'application/octet-stream',
      is_uploaded: false,
    } as FileRead),
    isProcessing: true,
  }
}

// ── Hook Props ──

interface UseFileUploadOptions<T extends FileRead | schemas['FileUpload']> {
  service: schemas['FileServiceTypes']
  accept?: Accept
  maxSize?: number
  workspace: schemas['Workspace']
  initialFiles: FileRead[]
  onFilesUpdated: (files: FileObject<T>[]) => void
  onFilesRejected?: (rejections: FileRejection[]) => void
}

// ── Hook ──

export const useFileUpload = <T extends FileRead | schemas['FileUpload']>({
  service,
  accept,
  maxSize,
  workspace,
  onFilesUpdated,
  onFilesRejected,
  initialFiles = [],
}: UseFileUploadOptions<T>) => {
  const [files, setFilesRaw] = useState<FileObject<T>[]>(
    initialFiles.map((f) => toFileObject<T>(wrapAsFileObject(f))),
  )

  // Wrapped setter that notifies the parent on every state change
  const applyUpdate = (updater: (prev: FileObject<T>[]) => FileObject<T>[]) => {
    setFilesRaw((prev) => {
      const next = updater(prev)
      onFilesUpdated?.(next)
      return next
    })
  }

  // Patch a single file by id
  const patchFile = (
    fileId: string,
    patcher: (f: FileObject<T>) => FileObject<T>,
  ) => {
    applyUpdate((prev) => prev.map((f) => (f.id === fileId ? patcher(f) : f)))
  }

  const removeFile = (fileId: string) => {
    applyUpdate((prev) => prev.filter((f) => f.id !== fileId))
  }

  // ── Upload Lifecycle Callbacks ──

  const handleProcessing = (tempId: string, nativeFile: File) => {
    applyUpdate((prev) => [
      ...prev,
      toFileObject<T>(createPlaceholder(tempId, nativeFile)),
    ])
  }

  const handleCreated = (tempId: string, response: schemas['FileUpload']) => {
    applyUpdate((prev) => {
      const cleaned = prev.filter((f) => f.id !== tempId)
      const entry = wrapAsFileObject(response)
      entry.isUploading = true
      return [...cleaned, toFileObject<T>(entry)]
    })
  }

  const handleProgress = (file: schemas['FileUpload'], bytes: number) => {
    patchFile(file.id, (f) => ({ ...f, uploadedBytes: bytes }))
  }

  const handleComplete = (response: FileRead) => {
    patchFile(response.id, (f) => ({
      ...f,
      ...response,
      isProcessing: false,
      isUploading: false,
      uploadedBytes: response.size,
    }))
  }

  // ── Dropzone Handler ──

  const onDrop = (accepted: File[], rejected: FileRejection[]) => {
    for (const nativeFile of accepted) {
      const uploadTask = new Upload({
        service,
        workspace,
        file: nativeFile,
        onFileProcessing: handleProcessing,
        onFileCreate: handleCreated,
        onFileUploadProgress: handleProgress,
        onFileUploaded: handleComplete,
      })
      uploadTask.run()
    }
    onFilesRejected?.(rejected)
  }

  const dropzone = useDropzone({ maxSize, accept, onDrop })

  return {
    files,
    setFiles: applyUpdate,
    updateFile: patchFile,
    removeFile,
    ...dropzone,
  }
}
