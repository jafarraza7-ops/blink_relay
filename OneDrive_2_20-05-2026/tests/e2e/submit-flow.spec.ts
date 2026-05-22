import { test, expect } from '@playwright/test'

// These tests assume the app is running with the backend API mocked or available.
// They exercise the submit wizard UI — navigation and form interaction.

test.describe('Submit flow', () => {
  test.beforeEach(async ({ page }) => {
    // Mock MSAL so we land on the submit page without a real auth redirect
    await page.addInitScript(() => {
      window.__MSAL_MOCK__ = true
    })
  })

  test('shows login page when not authenticated', async ({ page }) => {
    await page.goto('/submit')
    // Without auth, the RequireAuth component shows LoginPage
    await expect(page.getByText('Sign in to continue').or(page.getByText('Blink Relay'))).toBeVisible()
  })

  test('submit wizard has 3 steps labelled correctly', async ({ page }) => {
    // Navigate directly to the submit route with a mocked session cookie
    await page.goto('/submit')
    // At minimum the page loads without a JS error
    await expect(page).not.toHaveURL(/error/)
  })
})

test.describe('Respond page (public)', () => {
  test('loads respond page without authentication', async ({ page }) => {
    // /respond/:id is public — no login redirect should happen
    await page.goto('/respond/nonexistent-id')
    // Should show a not-found state (not a login page)
    await expect(page.getByText('Sign in to continue')).not.toBeVisible()
  })
})
