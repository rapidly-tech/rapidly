/** @rapidly-tech/ui — tsup build configuration for the shared component library. */
import { defineConfig, type Options } from 'tsup'

export const options: Options = {
  entry: ['./src', '!./src/**/*.stories.*'],
  format: ['cjs', 'esm'],
  dts: true,
  bundle: true,
  minify: true,
  sourcemap: false,
}

export default defineConfig(options)
