/**
 * Development-only logger for the P2P transport layer.
 *
 * All logging is stripped in production to prevent information leakage
 * through browser DevTools (peer IDs, connection states, message types).
 */
const isDev = process.env.NODE_ENV === 'development'

const noop = () => {}

export const logger = {
  log: isDev ? console.log.bind(console) : noop,
  warn: isDev ? console.warn.bind(console) : noop,
  error: isDev ? console.error.bind(console) : noop,
}
