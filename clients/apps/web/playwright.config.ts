import { defineConfig } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const envFile = resolve(__dirname, '.env.local')
try {
  const content = readFileSync(envFile, 'utf-8')
  for (const line of content.split('\n')) {
    const match = line.match(/^\s*([\w.-]+)\s*=\s*"?(.*?)"?\s*$/)
    if (match && !process.env[match[1]]) {
      process.env[match[1]] = match[2]
    }
  }
} catch {
  // ignore
}

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://127.0.0.1:3000',
    trace: 'on-first-retry',
  },
  // Boot the Next.js dev server for the duration of the test run so
  // devs can just ``pnpm test:e2e`` without a second terminal. CI
  // reuses an already-running server if one is up (rare), otherwise
  // starts one.
  webServer: {
    command: 'pnpm dev',
    url: 'http://127.0.0.1:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],
})
