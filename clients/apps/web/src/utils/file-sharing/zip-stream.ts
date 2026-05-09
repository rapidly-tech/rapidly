// Based on https://github.com/jimmywarting/StreamSaver.js/blob/master/examples/zip-stream.js
//
// Fully typed port with ZIP64 support. Conditionally emits ZIP64 structures
// only when needed (file >= 4GB, offset >= 4GB, or count >= 65535) to maximize
// compatibility with older unzippers.

import { ZIP64_COUNT_THRESHOLD, ZIP64_THRESHOLD } from './constants'

// ── Types ──

interface DataHelper {
  array: Uint8Array
  view: DataView
}

interface FileLike {
  name: string
  size?: number
  lastModified?: number
  directory?: boolean
  comment?: string
  stream?: () => ReadableStream<Uint8Array>
}

interface ZipObject {
  level: number
  ctrl: ReadableStreamDefaultController<Uint8Array>
  directory: boolean
  nameBuf: Uint8Array
  comment: Uint8Array
  compressedLength: number
  uncompressedLength: number
  header: DataHelper
  offset: number
  needsZip64: boolean
  crc: Crc32 | null
  reader: ReadableStreamDefaultReader<Uint8Array> | null
  fileLike: FileLike
  writeHeader(): void
  writeFooter(): void
}

export interface ZipWriter {
  enqueue(fileLike: FileLike): void
  close(): void
}

/**
 * Custom underlying source interface for the zip stream.
 * Unlike standard UnderlyingSource, the controller passed to start/pull
 * is a ZipWriter (not a ReadableStreamController).
 */
export interface ZipUnderlyingSource {
  start?: (controller: ZipWriter) => void | Promise<void>
  pull?: (controller: ZipWriter) => void | Promise<void>
}

// ── CRC32 ──

// Pre-computed CRC32 lookup table (shared across all instances)
const CRC32_TABLE: number[] = (() => {
  let i: number
  let j: number
  let t: number
  const table: number[] = []
  for (i = 0; i < 256; i++) {
    t = i
    for (j = 0; j < 8; j++) {
      t = t & 1 ? (t >>> 1) ^ 0xedb88320 : t >>> 1
    }
    table[i] = t
  }
  return table
})()

class Crc32 {
  crc: number

  constructor() {
    this.crc = -1
  }

  append(data: Uint8Array): void {
    let crc = this.crc | 0
    const table = CRC32_TABLE
    for (let offset = 0, len = data.length | 0; offset < len; offset++) {
      crc = (crc >>> 8) ^ table[(crc ^ data[offset]) & 0xff]
    }
    this.crc = crc
  }

  get(): number {
    return ~this.crc
  }
}

// ── Helpers ──

const getDataHelper = (byteLength: number): DataHelper => {
  const uint8 = new Uint8Array(byteLength)
  return {
    array: uint8,
    view: new DataView(uint8.buffer),
  }
}

/**
 * Write a 64-bit value as two 32-bit LE words.
 * JavaScript Number is safe to 2^53 (9 PB) — sufficient for browser transfers.
 */
function writeUint64LE(
  view: DataView,
  byteOffset: number,
  value: number,
): void {
  view.setUint32(byteOffset, value >>> 0, true) // low 32 bits
  view.setUint32(byteOffset + 4, Math.floor(value / 0x100000000) >>> 0, true) // high 32 bits
}

/** Check if a file or offset needs ZIP64 structures. */
function needsZip64File(size: number): boolean {
  return size >= ZIP64_THRESHOLD
}

/** Read one chunk from the file stream, update CRC/sizes, and enqueue it. */
const pump = (zipObj: ZipObject): Promise<void> | void => {
  if (!zipObj.reader || !zipObj.crc) {
    throw new Error('ZipObject stream not initialized')
  }
  const reader = zipObj.reader
  const crc = zipObj.crc
  return reader.read().then(
    (chunk: ReadableStreamReadResult<Uint8Array>) => {
      if (chunk.done) return zipObj.writeFooter()
      const outputData = chunk.value
      crc.append(outputData)
      zipObj.uncompressedLength += outputData.length
      zipObj.compressedLength += outputData.length
      zipObj.ctrl.enqueue(outputData)
    },
    (err: unknown) => {
      // Propagate stream read errors to the zip output (e.g. DataChannel closed mid-transfer)
      zipObj.ctrl.error(
        err instanceof Error ? err : new Error('Stream read failed'),
      )
    },
  )
}

// ── Zip Stream ──

export function createZipStream(
  underlyingSource: ZipUnderlyingSource,
): ReadableStream<Uint8Array> {
  const files: Record<string, ZipObject> = Object.create(null)
  const filenames: string[] = []
  const encoder = new TextEncoder()
  let offset = 0
  let activeZipIndex = 0
  let ctrl: ReadableStreamDefaultController<Uint8Array>
  let activeZipObject: ZipObject | undefined
  let closed = false
  // Track whether any file needs ZIP64 (drives EOCD format)
  let archiveNeedsZip64 = false

  function next(): void {
    activeZipIndex++
    activeZipObject = files[filenames[activeZipIndex]]
    if (activeZipObject) processNextChunk()
    else if (closed) closeZip()
  }

  const zipWriter: ZipWriter = {
    enqueue(fileLike: FileLike): void {
      if (closed)
        throw new TypeError(
          'Cannot enqueue a chunk into a readable stream that is closed or has been requested to be closed',
        )

      let name = fileLike.name.trim()
      const date = new Date(
        typeof fileLike.lastModified === 'undefined'
          ? Date.now()
          : fileLike.lastModified,
      )

      if (fileLike.directory && !name.endsWith('/')) name += '/'
      if (files[name]) throw new Error('File already exists.')

      const nameBuf = encoder.encode(name)
      filenames.push(name)

      // Determine if this file needs ZIP64 based on declared size
      const fileNeedsZip64 =
        fileLike.size !== undefined && needsZip64File(fileLike.size)
      if (fileNeedsZip64) archiveNeedsZip64 = true

      const zipObject: ZipObject = (files[name] = {
        level: 0,
        ctrl,
        directory: !!fileLike.directory,
        nameBuf,
        comment: encoder.encode(fileLike.comment || ''),
        compressedLength: 0,
        uncompressedLength: 0,
        header: getDataHelper(26),
        offset: 0,
        needsZip64: fileNeedsZip64,
        crc: null,
        reader: null,
        fileLike,
        writeHeader() {
          const header = getDataHelper(26)
          // ZIP64 extra field for local header: tag(2) + size(2) + uncompressed(8) + compressed(8) = 20 bytes
          const zip64ExtraLen = zipObject.needsZip64 ? 20 : 0
          const data = getDataHelper(30 + nameBuf.length + zip64ExtraLen)

          zipObject.offset = offset
          zipObject.header = header
          if (zipObject.level !== 0 && !zipObject.directory) {
            header.view.setUint16(4, 0x0800)
          }
          // Version needed: 4.5 (45) for ZIP64, 2.0 (20) otherwise
          const versionNeeded = zipObject.needsZip64 ? 0x2d : 0x14
          header.view.setUint32(0, (versionNeeded << 16) | 0x0808)
          header.view.setUint16(
            6,
            (((date.getHours() << 6) | date.getMinutes()) << 5) |
              (date.getSeconds() / 2),
            true,
          )
          header.view.setUint16(
            8,
            ((((date.getFullYear() - 1980) << 4) | (date.getMonth() + 1)) <<
              5) |
              date.getDate(),
            true,
          )
          header.view.setUint16(22, nameBuf.length, true)

          if (zipObject.needsZip64) {
            // Set sizes to 0xFFFFFFFF sentinel in main header
            header.view.setUint32(14, 0xffffffff, true) // compressed
            header.view.setUint32(18, 0xffffffff, true) // uncompressed
            header.view.setUint16(24, zip64ExtraLen, true) // extra field length
          }

          data.view.setUint32(0, 0x504b0304) // local file header signature
          data.array.set(header.array, 4)
          data.array.set(nameBuf, 30)

          if (zipObject.needsZip64) {
            // ZIP64 extra field
            const extraOffset = 30 + nameBuf.length
            data.view.setUint16(extraOffset, 0x0001, true) // ZIP64 tag
            data.view.setUint16(extraOffset + 2, 16, true) // data size
            // Sizes unknown at this point (streaming), will be in data descriptor
            writeUint64LE(data.view, extraOffset + 4, 0) // uncompressed
            writeUint64LE(data.view, extraOffset + 12, 0) // compressed
          }

          offset += data.array.length
          ctrl.enqueue(data.array)
        },
        writeFooter() {
          // Check if sizes exceeded ZIP64 threshold during streaming
          if (
            !zipObject.needsZip64 &&
            (needsZip64File(zipObject.compressedLength) ||
              needsZip64File(zipObject.uncompressedLength))
          ) {
            zipObject.needsZip64 = true
            archiveNeedsZip64 = true
          }

          if (zipObject.needsZip64) {
            // ZIP64 data descriptor: sig(4) + crc(4) + compressed(8) + uncompressed(8) = 24 bytes
            const footer = getDataHelper(24)
            footer.view.setUint32(0, 0x504b0708) // data descriptor signature
            if (zipObject.crc) {
              zipObject.header.view.setUint32(10, zipObject.crc.get(), true)
              footer.view.setUint32(4, zipObject.crc.get(), true)
            }
            writeUint64LE(footer.view, 8, zipObject.compressedLength)
            writeUint64LE(footer.view, 16, zipObject.uncompressedLength)
            ctrl.enqueue(footer.array)
            offset += zipObject.compressedLength + 24
          } else {
            // Standard ZIP32 data descriptor: sig(4) + crc(4) + compressed(4) + uncompressed(4) = 16 bytes
            const footer = getDataHelper(16)
            footer.view.setUint32(0, 0x504b0708)
            if (zipObject.crc) {
              zipObject.header.view.setUint32(10, zipObject.crc.get(), true)
              zipObject.header.view.setUint32(
                14,
                zipObject.compressedLength,
                true,
              )
              zipObject.header.view.setUint32(
                18,
                zipObject.uncompressedLength,
                true,
              )
              footer.view.setUint32(4, zipObject.crc.get(), true)
              footer.view.setUint32(8, zipObject.compressedLength, true)
              footer.view.setUint32(12, zipObject.uncompressedLength, true)
            }
            ctrl.enqueue(footer.array)
            offset += zipObject.compressedLength + 16
          }

          // Check if offset exceeds ZIP64 threshold
          if (offset >= ZIP64_THRESHOLD) {
            archiveNeedsZip64 = true
          }

          next()
        },
      })

      if (!activeZipObject) {
        activeZipObject = zipObject
        processNextChunk()
      }
    },
    close() {
      if (closed)
        throw new TypeError(
          'Cannot close a readable stream that has already been requested to be closed',
        )
      if (!activeZipObject) closeZip()
      closed = true
    },
  }

  function closeZip(): void {
    const fileCount = filenames.length
    // Check if file count exceeds ZIP64 threshold
    if (fileCount >= ZIP64_COUNT_THRESHOLD) {
      archiveNeedsZip64 = true
    }

    // Calculate central directory size
    let cdLength = 0
    for (let idx = 0; idx < fileCount; idx++) {
      const file = files[filenames[idx]]
      const fileZ64 = file.needsZip64 || file.offset >= ZIP64_THRESHOLD
      // Central directory entry: 46 base + name + comment + optional ZIP64 extra (28 bytes: tag(2)+size(2)+uncomp(8)+comp(8)+offset(8))
      const extraLen = fileZ64 ? 28 : 0
      cdLength += 46 + file.nameBuf.length + file.comment.length + extraLen
    }

    // Build central directory
    const cd = getDataHelper(cdLength)
    let cdIndex = 0
    for (let idx = 0; idx < fileCount; idx++) {
      const file = files[filenames[idx]]
      const fileZ64 = file.needsZip64 || file.offset >= ZIP64_THRESHOLD
      const extraLen = fileZ64 ? 28 : 0

      cd.view.setUint32(cdIndex, 0x504b0102) // central directory entry signature
      // Version made by: 4.5 for ZIP64, 2.0 otherwise
      cd.view.setUint16(cdIndex + 4, fileZ64 ? 0x2d00 : 0x1400)
      cd.array.set(file.header.array, cdIndex + 6)

      if (fileZ64) {
        // Override version needed to extract
        cd.view.setUint16(cdIndex + 6, 0x2d, true) // version needed = 45
        // Extra field length in central directory
        cd.view.setUint16(cdIndex + 36, extraLen, true) // extra field length
      }

      cd.view.setUint16(cdIndex + 32, file.comment.length, true)
      if (file.directory) {
        cd.view.setUint8(cdIndex + 38, 0x10)
      }

      if (fileZ64) {
        // Set offset to sentinel
        cd.view.setUint32(cdIndex + 42, 0xffffffff, true)
        // Set sizes to sentinel in header copy
        cd.view.setUint32(cdIndex + 20, 0xffffffff, true) // compressed
        cd.view.setUint32(cdIndex + 24, 0xffffffff, true) // uncompressed
      } else {
        cd.view.setUint32(cdIndex + 42, file.offset, true)
      }

      cd.array.set(file.nameBuf, cdIndex + 46)
      cd.array.set(file.comment, cdIndex + 46 + file.nameBuf.length)

      if (fileZ64) {
        // ZIP64 extra field in central directory
        const extraOff =
          cdIndex + 46 + file.nameBuf.length + file.comment.length
        cd.view.setUint16(extraOff, 0x0001, true) // ZIP64 tag
        cd.view.setUint16(extraOff + 2, 24, true) // data size (8+8+8)
        writeUint64LE(cd.view, extraOff + 4, file.uncompressedLength)
        writeUint64LE(cd.view, extraOff + 12, file.compressedLength)
        writeUint64LE(cd.view, extraOff + 20, file.offset)
      }

      cdIndex += 46 + file.nameBuf.length + file.comment.length + extraLen
    }
    ctrl.enqueue(cd.array)

    const cdStart = offset // offset where central directory starts

    if (archiveNeedsZip64) {
      // ZIP64 End of Central Directory Record (56 bytes)
      const eocd64 = getDataHelper(56)
      eocd64.view.setUint32(0, 0x504b0606) // ZIP64 EOCD signature (PK\x06\x06)
      writeUint64LE(eocd64.view, 4, 44) // size of remaining record (56-12)
      eocd64.view.setUint16(12, 45, true) // version made by
      eocd64.view.setUint16(14, 45, true) // version needed
      eocd64.view.setUint32(16, 0, true) // disk number
      eocd64.view.setUint32(20, 0, true) // disk with CD start
      writeUint64LE(eocd64.view, 24, fileCount) // entries on this disk
      writeUint64LE(eocd64.view, 32, fileCount) // total entries
      writeUint64LE(eocd64.view, 40, cdLength) // CD size
      writeUint64LE(eocd64.view, 48, cdStart) // CD offset
      ctrl.enqueue(eocd64.array)

      // ZIP64 End of Central Directory Locator (20 bytes)
      const locator = getDataHelper(20)
      locator.view.setUint32(0, 0x504b0607) // ZIP64 EOCD locator signature (PK\x06\x07)
      locator.view.setUint32(4, 0, true) // disk with ZIP64 EOCD
      writeUint64LE(locator.view, 8, cdStart + cdLength) // offset of ZIP64 EOCD
      locator.view.setUint32(16, 1, true) // total disks
      ctrl.enqueue(locator.array)
    }

    // Standard End of Central Directory Record (22 bytes)
    const eocd = getDataHelper(22)
    eocd.view.setUint32(0, 0x504b0506) // EOCD signature
    if (archiveNeedsZip64) {
      // Sentinel values for ZIP64
      eocd.view.setUint16(8, 0xffff, true) // entries on this disk
      eocd.view.setUint16(10, 0xffff, true) // total entries
      eocd.view.setUint32(12, 0xffffffff, true) // CD size
      eocd.view.setUint32(16, 0xffffffff, true) // CD offset
    } else {
      eocd.view.setUint16(8, fileCount, true)
      eocd.view.setUint16(10, fileCount, true)
      eocd.view.setUint32(12, cdLength, true)
      eocd.view.setUint32(16, cdStart, true)
    }
    ctrl.enqueue(eocd.array)
    ctrl.close()
  }

  function processNextChunk(): void | Promise<void> {
    if (!activeZipObject) return
    if (activeZipObject.directory) {
      activeZipObject.writeHeader()
      return activeZipObject.writeFooter()
    }
    if (activeZipObject.reader) return pump(activeZipObject)
    if (activeZipObject.fileLike.stream) {
      activeZipObject.crc = new Crc32()
      activeZipObject.reader = activeZipObject.fileLike.stream().getReader()
      activeZipObject.writeHeader()
    } else next()
  }

  return new ReadableStream<Uint8Array>({
    start: (c: ReadableStreamDefaultController<Uint8Array>) => {
      ctrl = c
      if (underlyingSource.start)
        return Promise.resolve(underlyingSource.start(zipWriter))
    },
    pull() {
      return (
        processNextChunk() ||
        (underlyingSource.pull &&
          Promise.resolve(underlyingSource.pull(zipWriter))) ||
        undefined
      )
    },
  })
}
