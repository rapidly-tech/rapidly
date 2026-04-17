/**
 * Shared helpers for signaling message handling.
 *
 * Consolidates duplicated ICE candidate parsing and signaling
 * message routing from useUploaderConnections and useDownloader.
 */

import { SignalingMessage } from '@/utils/p2p/signaling'

/**
 * Parse an ICE candidate from a signaling relay message
 * into a standard RTCIceCandidateInit object.
 */
export function parseIceCandidate(
  msg: SignalingMessage,
): RTCIceCandidateInit | null {
  // Reject messages without a valid candidate string — an empty string would
  // signal end-of-candidates per the WebRTC spec, inadvertently closing ICE gathering.
  if (typeof msg.candidate !== 'string' || msg.candidate === '') {
    return null
  }
  return {
    candidate: msg.candidate,
    sdpMid: typeof msg.sdpMid === 'string' ? msg.sdpMid : null,
    sdpMLineIndex:
      typeof msg.sdpMLineIndex === 'number' ? msg.sdpMLineIndex : null,
    usernameFragment:
      typeof msg.usernameFragment === 'string'
        ? msg.usernameFragment
        : undefined,
  }
}
