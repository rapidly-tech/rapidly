/** Rapidly — Vitest configuration for the web app's unit tests. */
import react from '@vitejs/plugin-react'
import tsconfigPaths from 'vite-tsconfig-paths'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [tsconfigPaths(), react()],
  test: {
    environment: 'jsdom',
    passWithNoTests: true,
    // Playwright owns the e2e/ folder; vitest must ignore it otherwise
    // both runners would try to parse the same ``.spec.ts`` files with
    // conflicting globals (vitest ``expect`` vs @playwright/test
    // ``expect``).
    exclude: ['node_modules', 'dist', '.next', 'e2e'],
  },
})
