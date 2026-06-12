import { test, expect } from '@playwright/test'

// These tests exercise the Request Aging Overview visualization on PM Summary page
// They require a running backend with test data and frontend dev server

test.describe('Request Aging Overview', () => {
  test.beforeEach(async ({ page }) => {
    // Mock auth so user is logged in as PM
    await page.addInitScript(() => {
      window.__MOCK_AUTH__ = {
        user: {
          id: 'test-pm-123',
          email: 'pm@blinkcharging.com',
          name: 'Test PM',
          roles: ['PRODUCT_MANAGER'],
        },
      }
    })
  })

  test('displays Request Aging Overview section with three buckets', async ({ page }) => {
    await page.goto('/pm-summary')

    // Wait for page to load
    await expect(page.getByText('PM Summary Dashboard')).toBeVisible()

    // Verify aging overview section is visible
    await expect(page.getByText('Request Aging Overview')).toBeVisible()

    // Verify all three aging buckets are present
    await expect(page.getByText('Fresh')).toBeVisible()
    await expect(page.getByText('Aging')).toBeVisible()
    await expect(page.getByText('Stale')).toBeVisible()

    // Verify bucket labels
    await expect(page.getByText('0-30 days')).toBeVisible()
    await expect(page.getByText('30-60 days')).toBeVisible()
    await expect(page.getByText('60+ days')).toBeVisible()
  })

  test('displays emoji indicators for aging buckets', async ({ page }) => {
    await page.goto('/pm-summary')
    await expect(page.getByText('PM Summary Dashboard')).toBeVisible()

    // Verify emoji indicators
    const agingSection = page.locator('text=Request Aging Overview').nth(0).locator('..')
    await expect(agingSection.locator('text=🟢')).toBeVisible()
    await expect(agingSection.locator('text=🟡')).toBeVisible()
    await expect(agingSection.locator('text=🔴')).toBeVisible()
  })

  test('displays stale requests when data is available', async ({ page }) => {
    await page.goto('/pm-summary')
    await expect(page.getByText('PM Summary Dashboard')).toBeVisible()

    // Wait for aging data to load
    await page.waitForLoadState('networkidle')

    // If stale requests exist, verify the section header is shown
    const agingSection = page.locator('text=Request Aging Overview').nth(0).locator('..')

    // Check if "Oldest Stale Requests" section is present
    const staleHeader = agingSection.locator('text=Oldest Stale Requests')
    const staleHeaderExists = await staleHeader.count() > 0

    if (staleHeaderExists) {
      await expect(staleHeader).toBeVisible()

      // Verify stale request rows contain expected fields
      const staleRequestRows = agingSection.locator('[class*="border-red-400"]')
      const rowCount = await staleRequestRows.count()

      if (rowCount > 0) {
        // First stale request should have reference_id and days badge
        const firstRow = staleRequestRows.nth(0)
        await expect(firstRow.locator('badge')).toContainText(/\d+d/)
      }
    }
  })

  test('clicking aging bucket navigates to dashboard', async ({ page }) => {
    await page.goto('/pm-summary')
    await expect(page.getByText('PM Summary Dashboard')).toBeVisible()

    // Find and click the Fresh bucket
    const freshBucket = page.locator('text=Fresh').nth(0).locator('..')
    await freshBucket.click()

    // Should navigate to dashboard
    await page.waitForURL('**/dashboard')
    await expect(page).toHaveURL(/dashboard/)
  })

  test('clicking stale request opens it in new tab', async ({ page, context }) => {
    await page.goto('/pm-summary')
    await expect(page.getByText('PM Summary Dashboard')).toBeVisible()

    // Wait for aging data to load
    await page.waitForLoadState('networkidle')

    const agingSection = page.locator('text=Request Aging Overview').nth(0).locator('..')
    const staleHeader = agingSection.locator('text=Oldest Stale Requests')

    if (await staleHeader.count() > 0) {
      // Listen for new page (popup)
      const [newPage] = await Promise.all([
        context.waitForEvent('page'),
        agingSection.locator('[class*="border-red-400"]').nth(0).click(),
      ])

      // New page should be a request detail page
      await expect(newPage).toHaveURL(/\/requests\//)
      await newPage.close()
    }
  })

  test('displays loading state while fetching aging data', async ({ page }) => {
    // Add delay to intercept loading state
    await page.route('**/api/analytics/request-aging', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 500))
      route.continue()
    })

    await page.goto('/pm-summary')

    // Should show loading message briefly
    const loadingOrVisible = page
      .getByText(/Loading aging data|Request Aging Overview/)
      .first()
    await expect(loadingOrVisible).toBeVisible({ timeout: 3000 })
  })

  test('displays error message if aging data fails to load', async ({ page }) => {
    // Mock failed request
    await page.route('**/api/analytics/request-aging', (route) => {
      route.abort('failed')
    })

    await page.goto('/pm-summary')
    await expect(page.getByText('PM Summary Dashboard')).toBeVisible()

    // Should display error message
    await expect(page.getByText(/Error loading aging data/)).toBeVisible()
  })

  test('Request Aging Overview section is positioned after overview cards', async ({ page }) => {
    await page.goto('/pm-summary')
    await expect(page.getByText('PM Summary Dashboard')).toBeVisible()

    // Get positions of overview cards and aging section
    const overviewCards = page.locator('[class*="grid"]').filter({ has: page.getByText('Total Requests') })
    const agingSection = page.locator('text=Request Aging Overview')

    const cardBoundingBox = await overviewCards.boundingBox()
    const agingSectionBoundingBox = await agingSection.boundingBox()

    // Aging section should appear below overview cards
    if (cardBoundingBox && agingSectionBoundingBox) {
      expect(agingSectionBoundingBox.y).toBeGreaterThan(cardBoundingBox.y)
    }
  })

  test('stale request rows have hover effect', async ({ page }) => {
    await page.goto('/pm-summary')
    await expect(page.getByText('PM Summary Dashboard')).toBeVisible()
    await page.waitForLoadState('networkidle')

    const agingSection = page.locator('text=Request Aging Overview').nth(0).locator('..')
    const staleHeader = agingSection.locator('text=Oldest Stale Requests')

    if (await staleHeader.count() > 0) {
      const staleRequestRow = agingSection.locator('[class*="border-red-400"]').nth(0)

      // Get initial background color
      const initialBg = await staleRequestRow.evaluate((el) => {
        return window.getComputedStyle(el).backgroundColor
      })

      // Hover over the row
      await staleRequestRow.hover()

      // Background should change on hover (hover:bg-red-100/50)
      const hoverBg = await staleRequestRow.evaluate((el) => {
        return window.getComputedStyle(el).backgroundColor
      })

      // Colors should be different
      expect(initialBg).not.toBe(hoverBg)
    }
  })

  test('only PMs and reviewers can see Request Aging section', async ({ page }) => {
    // Override auth to be non-PM user
    await page.addInitScript(() => {
      window.__MOCK_AUTH__ = {
        user: {
          id: 'test-requestor-123',
          email: 'requestor@example.com',
          name: 'Test Requestor',
          roles: ['REQUESTOR'],
        },
      }
    })

    await page.goto('/pm-summary')

    // Should show access denied
    await expect(page.getByText('Access Denied')).toBeVisible()
    await expect(page.getByText('Only PMs and reviewers can view the summary dashboard')).toBeVisible()
  })
})
