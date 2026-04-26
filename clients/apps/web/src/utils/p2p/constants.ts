/**
 * Transport-layer constants shared by all P2P chambers.
 *
 * Lives here (not in any chamber-specific folder) because these govern
 * RTCDataChannel backpressure and binary framing — both are properties of
 * the transport, not of file-sharing or screen-sharing or any one consumer.
 */

/** Backpressure threshold — pause sending when buffered data exceeds this (4 MB). */
export const BUFFER_THRESHOLD = 4 * 1024 * 1024

/** Maximum header size in binary frames (64 KB — matches server MAX_SIGNALING_MESSAGE_SIZE). */
export const MAX_HEADER_SIZE = 64 * 1024

/** Maximum total frame size (64 MB — prevents memory exhaustion from malicious peers). */
export const MAX_FRAME_SIZE = 64 * 1024 * 1024
