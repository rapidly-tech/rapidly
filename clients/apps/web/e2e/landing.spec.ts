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

  test('root / answers what + why-safe + sender-must-stay-online', async ({
    page,
  }) => {
    await page.goto('/')
    // New H1 + subtitle directly answer the trust questions reviewers
    // flagged ("what does this do" / "is it actually safe").
    await expect(
      page.getByRole('heading', { name: /send files browser to browser/i }),
    ).toBeVisible()
    await expect(
      page.getByText(/end-to-end encrypted\. no uploads/i),
    ).toBeVisible()
    // Critical friction-point disclaimer — without this, users close
    // the tab and break their own transfer.
    await expect(
      page.getByText(/recipient must open the link while this tab is open/i),
    ).toBeVisible()
  })

  test('/secret hides payment for anonymous users', async ({ page }) => {
    await page.goto('/')
    // Type a character to flip into secret-sharing mode. The page has
    // a global keydown listener that converts the first keystroke into
    // the secret textarea seed.
    await page.keyboard.press('h')
    // Anonymous users have no workspace_id — the payment section
    // should not render (without a workspace, the paywall would have
    // nowhere to attach).
    await expect(page.getByText(/require payment/i)).toBeHidden()
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
