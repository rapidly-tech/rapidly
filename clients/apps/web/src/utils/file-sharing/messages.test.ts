import { describe, expect, it } from 'vitest'
import {
  ChunkAckMessage,
  ChunkMessage,
  InfoMessage,
  MessageType,
  safeFileName,
  StartMessage,
} from './messages'

describe('safeFileName validation', () => {
  describe('valid filenames', () => {
    it('accepts simple filenames', () => {
      expect(() => safeFileName.parse('document.pdf')).not.toThrow()
      expect(() => safeFileName.parse('image.png')).not.toThrow()
      expect(() => safeFileName.parse('file-name_123.txt')).not.toThrow()
    })

    it('accepts filenames with directory structure', () => {
      expect(() => safeFileName.parse('folder/document.pdf')).not.toThrow()
      expect(() => safeFileName.parse('a/b/c/file.txt')).not.toThrow()
    })

    it('normalizes backslashes to forward slashes', () => {
      const result = safeFileName.parse('folder\\subfolder\\file.txt')
      expect(result).toBe('folder/subfolder/file.txt')
    })
  })

  describe('path traversal attacks', () => {
    it('rejects ../ path traversal', () => {
      expect(() => safeFileName.parse('../etc/passwd')).toThrow()
      expect(() => safeFileName.parse('folder/../../../etc/passwd')).toThrow()
      expect(() => safeFileName.parse('a/b/../../c')).toThrow()
    })

    it('rejects ..\\ path traversal', () => {
      expect(() => safeFileName.parse('..\\Windows\\System32')).toThrow()
      expect(() => safeFileName.parse('folder\\..\\..\\secret')).toThrow()
    })

    it('rejects absolute paths', () => {
      expect(() => safeFileName.parse('/etc/passwd')).toThrow()
      expect(() => safeFileName.parse('\\Windows\\System32')).toThrow()
    })
  })

  describe('dangerous characters', () => {
    it('rejects null bytes', () => {
      expect(() => safeFileName.parse('file\x00.txt')).toThrow()
    })

    it('sanitizes Windows-unsafe characters to underscores', () => {
      expect(safeFileName.parse('file<script>.txt')).toBe('file_script_.txt')
      expect(safeFileName.parse('file>.txt')).toBe('file_.txt')
      expect(safeFileName.parse('file|pipe.txt')).toBe('file_pipe.txt')
      expect(safeFileName.parse('file"quote.txt')).toBe('file_quote.txt')
      expect(safeFileName.parse('file:colon.txt')).toBe('file_colon.txt')
      expect(safeFileName.parse('file?.txt')).toBe('file_.txt')
      expect(safeFileName.parse('file*.txt')).toBe('file_.txt')
    })
  })

  describe('length limits', () => {
    it('rejects empty filenames', () => {
      expect(() => safeFileName.parse('')).toThrow()
    })

    it('rejects filenames exceeding 255 characters', () => {
      const longName = 'a'.repeat(256)
      expect(() => safeFileName.parse(longName)).toThrow()
    })

    it('accepts filenames at the 255 character limit', () => {
      const maxName = 'a'.repeat(255)
      expect(() => safeFileName.parse(maxName)).not.toThrow()
    })
  })
})

describe('InfoMessage validation', () => {
  it('validates file info with safe filenames', () => {
    const message = {
      type: MessageType.Info,
      files: [
        { fileName: 'document.pdf', size: 1024, type: 'application/pdf' },
        { fileName: 'folder/image.png', size: 2048, type: 'image/png' },
      ],
    }
    expect(() => InfoMessage.parse(message)).not.toThrow()
  })

  it('rejects file info with path traversal in filename', () => {
    const message = {
      type: MessageType.Info,
      files: [
        { fileName: '../../../etc/passwd', size: 1024, type: 'text/plain' },
      ],
    }
    expect(() => InfoMessage.parse(message)).toThrow()
  })

  it('rejects negative file sizes', () => {
    const message = {
      type: MessageType.Info,
      files: [{ fileName: 'file.txt', size: -100, type: 'text/plain' }],
    }
    expect(() => InfoMessage.parse(message)).toThrow()
  })
})

describe('StartMessage validation', () => {
  it('validates with safe filename', () => {
    const message = {
      type: MessageType.Start,
      fileName: 'document.pdf',
      offset: 0,
    }
    expect(() => StartMessage.parse(message)).not.toThrow()
  })

  it('rejects path traversal', () => {
    const message = {
      type: MessageType.Start,
      fileName: '../secret.txt',
      offset: 0,
    }
    expect(() => StartMessage.parse(message)).toThrow()
  })

  it('rejects negative offsets', () => {
    const message = {
      type: MessageType.Start,
      fileName: 'file.txt',
      offset: -1,
    }
    expect(() => StartMessage.parse(message)).toThrow()
  })
})

describe('ChunkMessage validation', () => {
  it('validates with safe filename', () => {
    const message = {
      type: MessageType.Chunk,
      fileName: 'file.txt',
      offset: 1024,
      bytes: new ArrayBuffer(256),
      final: false,
    }
    expect(() => ChunkMessage.parse(message)).not.toThrow()
  })

  it('rejects dangerous filenames', () => {
    const message = {
      type: MessageType.Chunk,
      fileName: '/etc/passwd',
      offset: 0,
      bytes: new ArrayBuffer(256),
      final: true,
    }
    expect(() => ChunkMessage.parse(message)).toThrow()
  })
})

describe('ChunkAckMessage validation', () => {
  it('validates with safe filename', () => {
    const message = {
      type: MessageType.ChunkAck,
      fileName: 'folder/file.txt',
      offset: 512,
      bytesReceived: 256,
    }
    expect(() => ChunkAckMessage.parse(message)).not.toThrow()
  })

  it('rejects negative bytesReceived', () => {
    const message = {
      type: MessageType.ChunkAck,
      fileName: 'file.txt',
      offset: 0,
      bytesReceived: -100,
    }
    expect(() => ChunkAckMessage.parse(message)).toThrow()
  })
})
