/**
 * Rapidly currency package build configuration.
 *
 * tsup config for building the @rapidly-tech/currency package.
 * Outputs both CJS and ESM formats with minification and type declarations.
 *
 * @module rapidly/currency/tsup.config
 */
import { defineConfig, Options } from 'tsup'

export const options: Options[] = [
  {
    entry: ['src/index.ts'],
    format: ['cjs', 'esm'],
    minify: true,
    dts: true,
  },
]

export default defineConfig(options)
