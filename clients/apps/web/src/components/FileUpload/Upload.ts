/**
 * Upload - Rapidly multipart file upload pipeline.
 *
 * 1. Hash the file (SHA-256) and split it into chunks.
 * 2. Create the file resource on the server.
 * 3. Upload each chunk sequentially to S3 (preserving order for checksum validation).
 * 4. Notify the server that all parts have been uploaded.
 */

import { api } from '@/utils/client'
import { schemas } from '@rapidly-tech/client'
import { createSHA256 } from 'hash-wasm'

// ── Configuration ──

/** Each chunk is at most 10 MB. */
const PART_SIZE_BYTES = 10_000_000

// ── Types ──

export type FileRead =
  | schemas['DownloadableFileRead']
  | schemas['ShareMediaFileRead']
  | schemas['WorkspaceAvatarFileRead']

interface UploadCallbacks {
  onFileProcessing: (tempId: string, file: File) => void
  onFileCreate: (tempId: string, response: schemas['FileUpload']) => void
  onFileUploadProgress: (file: schemas['FileUpload'], uploaded: number) => void
  onFileUploaded: (response: FileRead) => void
}

interface UploadConfig extends UploadCallbacks {
  workspace: schemas['Workspace']
  service: schemas['FileServiceTypes']
  file: File
}

// ── Standalone Helpers ──

/** Compute a base64-encoded SHA-256 digest of an ArrayBuffer via the Web Crypto API. */
async function sha256Base64(buffer: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', buffer)
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
}

/** Slice a file into chunk descriptors with per-chunk SHA-256 checksums. */
async function prepareChunks(
  file: File,
): Promise<{ fileHash: string; chunks: schemas['S3FileCreatePart'][] }> {
  const totalChunks = Math.ceil(file.size / PART_SIZE_BYTES) || 1
  const chunks: schemas['S3FileCreatePart'][] = []
  const hasher = await createSHA256()

  for (let partNum = 1; partNum <= totalChunks; partNum++) {
    const start = (partNum - 1) * PART_SIZE_BYTES
    const end = Math.min(partNum * PART_SIZE_BYTES, file.size)
    const slice = file.slice(start, end)
    const buf = await slice.arrayBuffer()

    const chunkHash = await sha256Base64(buf)
    hasher.update(new Uint8Array(buf))

    chunks.push({
      number: partNum,
      chunk_start: start,
      chunk_end: end,
      checksum_sha256_base64: chunkHash,
    })
  }

  const finalDigest = hasher.digest('binary')
  const fileHash = btoa(String.fromCharCode(...finalDigest))
  return { fileHash, chunks }
}

/** Upload a single part to S3 via XHR (needed for progress tracking). */
function uploadPart(
  file: File,
  part: schemas['S3FileUploadPart'],
  onProgress: (loaded: number) => void,
): Promise<schemas['S3FileUploadCompletedPart']> {
  const slice = file.slice(part.chunk_start, part.chunk_end)
  const payload = new Blob([slice], { type: file.type })

  return new Promise((resolve, reject) => {
    const req = new XMLHttpRequest()

    req.onreadystatechange = () => {
      if (req.readyState !== 4) return
      if (req.status === 200) {
        const etag = req.getResponseHeader('ETag')
        if (!etag) {
          reject(new Error('S3 response missing ETag header'))
          return
        }
        resolve({
          number: part.number,
          checksum_etag: etag,
          checksum_sha256_base64: part.checksum_sha256_base64 || null,
        })
      } else {
        reject(new Error(`Part upload failed: ${req.status} ${req.statusText}`))
      }
    }

    req.upload.onprogress = (ev) => {
      if (ev.lengthComputable) onProgress(ev.loaded)
    }

    req.open('PUT', part.url, true)
    if (part.headers) {
      for (const [key, val] of Object.entries(part.headers)) {
        req.setRequestHeader(key, val)
      }
    }
    req.send(payload)
  })
}

// ── Upload Class ──

export class Upload {
  private readonly ws: schemas['Workspace']
  private readonly svc: schemas['FileServiceTypes']
  private readonly file: File
  private readonly uid: string
  private readonly cb: UploadCallbacks

  constructor(config: UploadConfig) {
    this.ws = config.workspace
    this.svc = config.service
    this.file = config.file
    this.uid = `tmp-${Date.now()}-${Math.random().toString(36).slice(2)}`
    this.cb = {
      onFileProcessing: config.onFileProcessing,
      onFileCreate: config.onFileCreate,
      onFileUploadProgress: config.onFileUploadProgress,
      onFileUploaded: config.onFileUploaded,
    }
  }

  /** Register the file on the Rapidly API. */
  private async register() {
    const { fileHash, chunks } = await prepareChunks(this.file)
    const contentType = this.file.type || 'application/octet-stream'

    const body: schemas['FileCreate'] = {
      workspace_id: this.ws.id,
      service: this.svc,
      name: this.file.name,
      size: this.file.size,
      mime_type: contentType,
      checksum_sha256_base64: fileHash,
      upload: { parts: chunks },
    }

    return api.POST('/api/files/', { body })
  }

  /**
   * Upload all parts in sequence. S3 requires consecutive ordering
   * for SHA-256 validation, so parallel uploads are not used here.
   */
  private async transferParts(
    parts: schemas['S3FileUploadPart'][],
    onProgress: (totalUploaded: number) => void,
  ): Promise<schemas['S3FileUploadCompletedPart'][]> {
    const completed: schemas['S3FileUploadCompletedPart'][] = []
    let cumulativeBytes = 0

    for (const part of parts) {
      const result = await uploadPart(this.file, part, (partBytes) => {
        onProgress(cumulativeBytes + partBytes)
      })
      cumulativeBytes += part.chunk_end - part.chunk_start
      onProgress(cumulativeBytes)
      completed.push(result)
    }

    return completed
  }

  /** Mark the upload as completed on the server and retrieve the final file record. */
  private async finalize(
    created: schemas['FileUpload'],
    parts: schemas['S3FileUploadCompletedPart'][],
  ) {
    const { data, error } = await api.POST('/api/files/{id}/uploaded', {
      params: { path: { id: created.id } },
      body: {
        id: created.upload.id,
        path: created.upload.path,
        parts,
      },
    })

    if (!error) {
      this.cb.onFileUploaded(data)
    }
  }

  /** Execute the full upload pipeline. */
  async run() {
    this.cb.onFileProcessing(this.uid, this.file)

    const { data: fileRecord, error } = await this.register()
    if (error) return

    this.cb.onFileCreate(this.uid, fileRecord)

    const completedParts = await this.transferParts(
      fileRecord.upload.parts,
      (bytes) => this.cb.onFileUploadProgress(fileRecord, bytes),
    )

    await this.finalize(fileRecord, completedParts)
  }
}
