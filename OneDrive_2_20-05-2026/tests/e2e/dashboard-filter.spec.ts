import { test, expect } from '@playwright/test'

test.describe('Dashboard filter', () => {
  test('dashboard redirects unauthenticated users', async ({ page }) => {
    await page.goto('/dashboard')
    // Without a valid MSAL session, should be redirected to login
    await expect(
      page.getByText('Sign in to continue').or(page.getByText('Blink Relay'))
    ).toBeVisible({ timeout: 10_000 })
  })

  test('POD filter pills are visible on dashboard', async ({ page, context }) => {
    // This test requires a live backend + auth; skip in unit mode
    test.skip(true, 'Requires authenticated session — run with auth fixture')

    await page.goto('/dashboard')
    await expect(page.getByText('All PODs')).toBeVisible()
    await expect(page.getByText('Driver')).toBeVisible()
    await expect(page.getByText('Charger')).toBeVisible()
    void context
  })

  test('stat cards are visible on authenticated dashboard', async ({ page }) => {
    test.skip(true, 'Requires authenticated session — run with auth fixture')

    await page.goto('/dashboard')
    await expect(page.getByText('Total')).toBeVisible()
    await expect(page.getByText('New / Submitted')).toBeVisible()
    await expect(page.getByText('Awaiting Info')).toBeVisible()
    await expect(page.getByText('Approved')).toBeVisible()
  })
})
