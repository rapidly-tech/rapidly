/**
 * Idle timeout and keepalive tracker for P2P connections.
 *
 * Consolidates the duplicated idle-check + ping logic from
 * useUploaderConnections and useDownloader into a reusable class.
 */

import { logger } from './logger'

/** Default interval between idle checks / keepalive pings (ms). */
const DEFAULT_INTERVAL = 30_000

export class IdleTracker {
  private lastActivity = Date.now()
  private idleCheckInterval: ReturnType<typeof setInterval> | null = null
  private pingInterval: ReturnType<typeof setInterval> | null = null
  private pingStartTimeout: ReturnType<typeof setTimeout> | null = null

  /**
   * @param idleTimeout - Close connection after this many ms of inactivity
   * @param onIdle - Called when the idle timeout is reached
   * @param onPing - Optional: called at each ping interval to send a keepalive
   * @param intervalMs - Check/ping interval in ms (default 30s)
   */
  constructor(
    private readonly idleTimeout: number,
    private readonly onIdle: () => void,
    private readonly onPing?: () => void,
    intervalMs = DEFAULT_INTERVAL,
  ) {
    this.idleCheckInterval = setInterval(() => {
      if (Date.now() - this.lastActivity > this.idleTimeout) {
        logger.log('[IdleTracker] idle timeout reached')
        this.destroy()
        this.onIdle()
      }
    }, intervalMs)

    if (onPing) {
      // Offset ping by half the interval so pong responses arrive before the
      // next idle check fires (prevents premature idle disconnects when the
      // only activity keeping the connection alive is the ping/pong mechanism)
      this.pingStartTimeout = setTimeout(() => {
        this.pingStartTimeout = null
        if (this.idleCheckInterval === null) return // already destroyed
        this.onPing?.()
        this.pingInterval = setInterval(() => {
          this.onPing?.()
        }, intervalMs)
      }, intervalMs / 2)
    }
  }

  /** Call when any activity is detected to reset the idle timer. */
  resetActivity(): void {
    this.lastActivity = Date.now()
  }

  /** Stop all timers and clean up. */
  destroy(): void {
    if (this.idleCheckInterval) {
      clearInterval(this.idleCheckInterval)
      this.idleCheckInterval = null
    }
    if (this.pingStartTimeout) {
      clearTimeout(this.pingStartTimeout)
      this.pingStartTimeout = null
    }
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }
}
