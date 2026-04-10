import type { PeerDataConnection } from './peer-connection'

export type UploadedFile = File & { entryFullPath?: string }

export enum UploaderConnectionStatus {
  Pending = 'PENDING',
  Ready = 'READY',
  Paused = 'PAUSED',
  Uploading = 'UPLOADING',
  Done = 'DONE',
  Authenticating = 'AUTHENTICATING',
  InvalidPassword = 'INVALID_PASSWORD',
  LockedOut = 'LOCKED_OUT', // Too many failed password attempts
  Closed = 'CLOSED',
}

export type UploaderConnection = {
  status: UploaderConnectionStatus
  dataConnection: PeerDataConnection
  browserName?: string
  browserVersion?: string
  osName?: string
  osVersion?: string
  mobileVendor?: string
  mobileModel?: string
  uploadingFileName?: string
  uploadingOffset?: number
  acknowledgedBytes?: number
  completedFiles: number
  totalFiles: number
  currentFileProgress: number
  bytesSent: number
  totalBytes: number
}
