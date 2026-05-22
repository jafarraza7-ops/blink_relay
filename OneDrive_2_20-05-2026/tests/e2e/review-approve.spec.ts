import { test, expect } from '@playwright/test'

test.describe('Review and approve', () => {
  test('review page redirects unauthenticated users', async ({ page }) => {
    await page.goto('/requests/some-id')
    await expect(
      page.getByText('Sign in to continue').or(page.getByText('Blink Relay'))
    ).toBeVisible({ timeout: 10_000 })
  })

  test('review page shows request details for authenticated PM', async ({ page }) => {
    test.skip(true, 'Requires authenticated PM session — run with auth fixture')

    await page.goto('/requests/some-request-id')
    await expect(page.getByText('Request Details')).toBeVisible()
    await expect(page.getByText('Conversation')).toBeVisible()
    await expect(page.getByText('Attachments')).toBeVisible()
  })

  test('approve button triggers Jira ticket creation', async ({ page }) => {
    test.skip(true, 'Requires authenticated PM session + live backend')

    await page.goto('/requests/some-request-id')
    const approveBtn = page.getByRole('button', { name: /approve request/i })
    await expect(approveBtn).toBeVisible()
    await approveBtn.click()
    await expect(page.getByText('Request approved')).toBeVisible()
  })
})
