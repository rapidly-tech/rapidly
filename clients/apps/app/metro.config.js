/**
 * Rapidly mobile app Metro bundler configuration.
 *
 * Uses the Sentry-enhanced Expo Metro config to enable source map
 * uploads for error tracking in the Rapidly mobile app.
 *
 * @module rapidly/metro.config
 */
const { getSentryExpoConfig } = require('@sentry/react-native/metro')

const config = getSentryExpoConfig(__dirname)

module.exports = config
