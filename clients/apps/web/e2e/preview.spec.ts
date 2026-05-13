/**
 * Smoke tests for the /preview route group (the project-management
 * product, gated behind /preview while WIP).
 *
 * Intentionally minimal: load each route, assert the response is
 * 200/3xx (not 404 or 500) and the document title is set. We don't
 * authenticate — these routes are under (main) so they redirect to
 * login when no session exists; the point is to catch routing /
 * build-output regressions, not to drive the authenticated UI.
 *
 * Run locally:
 *   pnpm --filter web dev       # terminal 1
 *   pnpm --filter web test:e2e  # terminal 2
 */

import { expect, test, type Response } from '@playwright/test'

/** A route loaded OK if Next.js returned a final non-error response. */
const okResponse = (response: Response | null): boolean => {
  if (response === null) return false
  const status = response.status()
  return status >= 200 && status < 400
}

test.describe('/preview routes resolve', () => {
  test('/preview renders or redirects (not 404/500)', async ({ page }) => {
    const response = await page.goto('/preview')
    expect(okResponse(response)).toBe(true)
    const title = await page.title()
    expect(title.length).toBeGreaterThan(0)
  })

  test('/preview/projects renders or redirects (not 404/500)', async ({
    page,
  }) => {
    const response = await page.goto('/preview/projects')
    expect(okResponse(response)).toBe(true)
    const title = await page.title()
    expect(title.length).toBeGreaterThan(0)
  })

  test('/preview/my-work renders or redirects (not 404/500)', async ({
    page,
  }) => {
    // Page added in the assigned_to_me PR; this smoke test asserts the
    // route exists and the build output doesn't 404.
    const response = await page.goto('/preview/my-work')
    expect(okResponse(response)).toBe(true)
    const title = await page.title()
    expect(title.length).toBeGreaterThan(0)
  })
})
