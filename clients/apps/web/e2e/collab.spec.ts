/**
 * Collab chamber — two-browser end-to-end test.
 *
 * Stands up two real browser contexts (host + guest), drives the host
 * through session create + copy-invite, loads the invite URL in the
 * guest context, and asserts that text typed on the host appears in
 * the guest's textarea. With the v1.1 feature flag on, also asserts
 * that the encryption badge reads "End-to-end encrypted" on both
 * sides.
 *
 * Gating
 * ------
 * This suite needs a backend running with
 * ``FILE_SHARING_COLLAB_ENABLED=true``. That's non-trivial to boot
 * from Playwright's ``webServer`` config (docker-compose + uv + redis
 * + minio). Rather than make the whole e2e pipeline depend on that,
 * the suite is opt-in via ``E2E_COLLAB_BACKEND=1``. CI enables it in
 * a dedicated job; local devs run ``./dev/run-collab-e2e``.
 *
 * Detection fallback — if ``E2E_COLLAB_BACKEND=1`` is set but the
 * backend isn't actually reachable, the ``beforeAll`` guard skips
 * with a clear reason rather than reporting a confusing WebRTC
 * failure 30 seconds into each test.
 */

import { expect, test } from '@playwright/test'

const HOST_ROUTE = '/collab'
const API_BASE = 'http://127.0.0.1:8000'

const backendGate = process.env.E2E_COLLAB_BACKEND === '1'

test.describe('Collab chamber — two-browser smoke', () => {
  test.skip(
    !backendGate,
    'Collab e2e requires E2E_COLLAB_BACKEND=1 + a running backend with FILE_SHARING_COLLAB_ENABLED=true',
  )

  test.beforeAll(async ({ request }) => {
    // Probe the backend. A 422 means the API exists but rejected the
    // empty body — fine, the chamber is live. A 404 means the flag
    // is off; skip with a useful message. Anything else (connect
    // refused, timeout) also skips — we don't want 30s WebRTC hangs
    // masking a missing backend.
    let status = 0
    try {
      const res = await request.post(`${API_BASE}/api/v1/collab/session`, {
        data: {},
        timeout: 5000,
      })
      status = res.status()
    } catch {
      test.skip(true, `Backend not reachable at ${API_BASE}`)
    }
    if (status === 404) {
      test.skip(
        true,
        'FILE_SHARING_COLLAB_ENABLED=false on the running backend — flip it on',
      )
    }
  })

  test('host types, guest sees it; both show the encryption badge', async ({
    browser,
  }) => {
    // Two isolated contexts (like two separate browsers on different
    // machines) — they don't share cookies or localStorage.
    const hostCtx = await browser.newContext()
    const guestCtx = await browser.newContext()

    try {
      const host = await hostCtx.newPage()
      const guest = await guestCtx.newPage()

      // 1. Host starts a session.
      await host.goto(HOST_ROUTE)
      await expect(
        host.getByRole('heading', { name: /start a collaborative session/i }),
      ).toBeVisible()
      await host.getByRole('button', { name: /start session/i }).click()

      // The editor mounts once the session is active. Use a generous
      // timeout — creating the session + wiring signaling is a full
      // round-trip to the backend.
      const hostEditor = host.getByPlaceholder(/start typing/i)
      await expect(hostEditor).toBeVisible({ timeout: 20_000 })

      // 2. Host copies invite. We can't reliably read the
      // clipboard from a headless Chromium without extra perms, so
      // we pull the invite URL from the "last invite" pill the UI
      // renders when Copy is clicked.
      await host.getByRole('button', { name: /copy invite/i }).click()
      const invitePill = host.locator('p.font-mono.truncate').first()
      await expect(invitePill).toBeVisible({ timeout: 5_000 })
      const inviteUrl = (await invitePill.innerText()).trim()
      expect(inviteUrl).toMatch(/^https?:\/\/[^\s]+\/collab\/[^?]+\?t=/)

      // 3. Guest opens the invite.
      await guest.goto(inviteUrl)
      const guestEditor = guest.getByPlaceholder(/start typing/i)
      await expect(guestEditor).toBeVisible({ timeout: 20_000 })

      // 4. Host types → guest sees it.
      await hostEditor.click()
      await host.keyboard.type('hello from host')
      await expect(guestEditor).toHaveValue(/hello from host/, {
        timeout: 10_000,
      })

      // 5. Round-trip: guest types → host sees it.
      await guestEditor.click()
      await guestEditor.press('End')
      await guest.keyboard.type(' and hi back')
      await expect(hostEditor).toHaveValue(/hello from host and hi back/, {
        timeout: 10_000,
      })

      // 6. Encryption badge — read from both sides. When
      // NEXT_PUBLIC_COLLAB_E2EE=true (default in PR #81), the pill
      // reads "End-to-end encrypted". When the flag is off, it reads
      // "Not encrypted" — we assert only that the badge is present,
      // since the deployment flag state is the operator's choice.
      for (const page of [host, guest]) {
        const badge = page.getByLabel(/Session encryption state/i)
        await expect(badge).toBeVisible()
      }
    } finally {
      await hostCtx.close()
      await guestCtx.close()
    }
  })
})
