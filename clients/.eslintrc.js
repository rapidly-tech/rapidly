/**
 * Rapidly clients workspace root ESLint configuration.
 *
 * Extends Next.js, Turborepo, and Prettier configs for all packages
 * and apps in the Rapidly frontend monorepo.
 *
 * @module rapidly/eslintrc
 */
module.exports = {
  root: true,
  extends: ['next', 'turbo', 'prettier', 'next/core-web-vitals'],
  settings: {
    next: {
      rootDir: ['apps/*/'],
    },
  },
}
