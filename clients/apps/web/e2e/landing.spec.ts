/**
 * First real Playwright smoke test.
 *
 * Intentionally minimal: load the root landing and the /revolver preview,
 * assert key content renders. The point is to have something the CI E2E
 * job can actually run so regressions in routing / build output get
 * caught, not to cover behaviour.
 *
 * Run locally:
 *   pnpm --filter web dev       # terminal 1 — the test's baseURL
 *   pnpm --filter web test:e2e  # terminal 2
 */

import { expect, test } from '@playwright/test'

test.describe('Landing pages render', () => {
  test('root / renders a landing hero', async ({ page }) => {
    await page.goto('/')
    // Either variant of the landing (revolver or file-sharing hero)
    // should yield a non-empty <main> and a visible logo.
    await expect(page.locator('body')).toBeVisible()
    const title = await page.title()
    expect(title.length).toBeGreaterThan(0)
  })

  test('/revolver renders the 6-chamber preview', async ({ page }) => {
    await page.goto('/revolver')
    // The revolver landing has a distinctive headline we can target.
    await expect(
      page.getByRole('heading', { name: /six chambers/i }),
    ).toBeVisible()
    // Scope to <main> so the nav's "Secret Messages" / "Screen Share"
    // links don't win the .first() lookup. Each chamber renders its
    // label as exact text inside the radial ring.
    const main = page.locator('main')
    for (const label of [
      'Files',
      'Secret',
      'Screen',
      'Watch',
      'Call',
      'Collab',
    ]) {
      await expect(main.getByText(label, { exact: true })).toBeVisible()
    }
  })
})
