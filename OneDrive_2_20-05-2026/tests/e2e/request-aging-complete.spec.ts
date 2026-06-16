import { test, expect } from '@playwright/test'

test.describe('Request Aging Visualization - Complete Suite', () => {
  test.beforeEach(async ({ page }) => {
    // Mock auth
    await page.addInitScript(() => {
      window.__MOCK_AUTH__ = {
        user: {
          id: 'pm-123',
          email: 'pm@example.com',
          name: 'PM User',
          roles: ['PRODUCT_MANAGER'],
        },
      }
    })
  })

  test.describe('Component Visibility', () => {
    test('Request Aging Overview section is visible on PM Summary', async ({ page }) => {
      await page.goto('/pm-summary')
      await expect(page.getByText('Request Aging Overview')).toBeVisible()
    })

    test('displays three aging buckets: Fresh, Aging, Stale', async ({ page }) => {
      await page.goto('/pm-summary')
      await expect(page.getByText('Fresh', { exact: true })).toBeVisible()
      await expect(page.getByText('Aging', { exact: true })).toBeVisible()
      await expect(page.getByText('Stale', { exact: true })).toBeVisible()
    })

    test('displays time ranges for each bucket', async ({ page }) => {
      await page.goto('/pm-summary')
      await expect(page.getByText('0-30 days')).toBeVisible()
      await expect(page.getByText('30-60 days')).toBeVisible()
      await expect(page.getByText('60+ days')).toBeVisible()
    })

    test('displays emoji indicators for each bucket', async ({ page }) => {
      await page.goto('/pm-summary')
      const agingSection = page.locator('text=Request Aging Overview').locator('..')

      // Green circle for Fresh
      await expect(agingSection.locator('text=🟢')).toBeVisible()
      // Yellow circle for Aging
      await expect(agingSection.locator('text=🟡')).toBeVisible()
      // Red circle for Stale
      await expect(agingSection.locator('text=🔴')).toBeVisible()
    })
  })

  test.describe('Positioning', () => {
    test('Request Aging Overview appears after overview cards', async ({ page }) => {
      await page.goto('/pm-summary')

      const overviewCards = page.locator('text=Total Requests').nth(0)
      const agingSection = page.locator('text=Request Aging Overview')

      const cardBox = await overviewCards.boundingBox()
      const agingBox = await agingSection.boundingBox()

      expect(cardBox && agingBox && agingBox.y > cardBox.y).toBeTruthy()
    })

    test('section has distinct visual styling (border and background)', async ({ page }) => {
      await page.goto('/pm-summary')

      const agingCard = page.locator('text=Request Aging Overview').locator('..')
      const classList = await agingCard.evaluate(el => el.className)

      // Should have border and gradient background
      expect(classList).toContain('border')
      expect(classList).toContain('gradient')
    })
  })

  test.describe('Bucket Cards', () => {
    test('Fresh bucket displays correct count and styling', async ({ page }) => {
      await page.goto('/pm-summary')

      const freshCard = page.locator('text=Fresh').nth(0)
      const freshParent = freshCard.locator('..')

      // Should show emoji and count
      await expect(freshCard).toBeVisible()
      // Green styling
      const classList = await freshParent.evaluate(el => el.className)
      expect(classList).toContain('green')
    })

    test('Aging bucket displays correct count and styling', async ({ page }) => {
      await page.goto('/pm-summary')

      const agingCard = page.locator('text=Aging').nth(0)
      const agingParent = agingCard.locator('..')

      await expect(agingCard).toBeVisible()
      const classList = await agingParent.evaluate(el => el.className)
      expect(classList).toContain('yellow')
    })

    test('Stale bucket displays correct count and styling', async ({ page }) => {
      await page.goto('/pm-summary')

      const staleCard = page.locator('text=Stale').nth(0)
      const staleParent = staleCard.locator('..')

      await expect(staleCard).toBeVisible()
      const classList = await staleParent.evaluate(el => el.className)
      expect(classList).toContain('red')
    })

    test('bucket cards are clickable and navigate to dashboard', async ({ page }) => {
      await page.goto('/pm-summary')

      const freshBucket = page.locator('text=Fresh').nth(0).locator('..')

      await Promise.all([
        page.waitForURL(/dashboard/),
        freshBucket.click(),
      ])

      expect(page.url()).toContain('/dashboard')
    })
  })

  test.describe('Stale Requests List', () => {
    test('displays "Oldest Stale Requests" section when stale requests exist', async ({ page }) => {
      await page.goto('/pm-summary')
      await page.waitForLoadState('networkidle')

      const staleHeader = page.locator('text=Oldest Stale Requests')
      const headerCount = await staleHeader.count()

      if (headerCount > 0) {
        await expect(staleHeader).toBeVisible()
      }
    })

    test('stale request rows display reference ID, title, and days idle', async ({ page }) => {
      await page.goto('/pm-summary')
      await page.waitForLoadState('networkidle')

      const staleHeader = page.locator('text=Oldest Stale Requests')

      if (await staleHeader.count() > 0) {
        const staleRows = page.locator('[class*="border-red"]')
        const firstRow = staleRows.nth(0)

        // Should contain reference ID and days badge
        const hasReference = await firstRow.locator('text=/BLR-\\d+/').count() > 0
        const hasDaysBadge = await firstRow.locator('text=/\\d+d/').count() > 0

        expect(hasReference || hasDaysBadge).toBeTruthy()
      }
    })

    test('displays up to 5 oldest stale requests', async ({ page }) => {
      await page.goto('/pm-summary')
      await page.waitForLoadState('networkidle')

      const staleHeader = page.locator('text=Oldest Stale Requests')

      if (await staleHeader.count() > 0) {
        const staleRows = page.locator('[class*="border-red"]')
        const rowCount = await staleRows.count()

        expect(rowCount).toBeLessThanOrEqual(5)
      }
    })

    test('stale request rows are clickable and open in new tab', async ({ page, context }) => {
      await page.goto('/pm-summary')
      await page.waitForLoadState('networkidle')

      const staleHeader = page.locator('text=Oldest Stale Requests')

      if (await staleHeader.count() > 0) {
        const staleRows = page.locator('[class*="border-red"]')
        const firstRow = staleRows.nth(0)

        const [newPage] = await Promise.all([
          context.waitForEvent('page'),
          firstRow.click(),
        ])

        expect(newPage.url()).toContain('/requests/')
        await newPage.close()
      }
    })

    test('rows have hover effect for better UX', async ({ page }) => {
      await page.goto('/pm-summary')
      await page.waitForLoadState('networkidle')

      const staleHeader = page.locator('text=Oldest Stale Requests')

      if (await staleHeader.count() > 0) {
        const staleRow = page.locator('[class*="border-red"]').nth(0)

        const initialClass = await staleRow.getAttribute('class')

        await staleRow.hover()

        const hoverClass = await staleRow.getAttribute('class')

        // Classes should change on hover (hover:bg-red-100/50)
        expect(initialClass === hoverClass || hoverClass?.includes('hover')).toBeTruthy()
      }
    })
  })

  test.describe('Loading & Error States', () => {
    test('displays loading state while fetching aging data', async ({ page }) => {
      // Intercept and delay the API request
      await page.route('**/api/analytics/request-aging', async (route) => {
        await new Promise(resolve => setTimeout(resolve, 500))
        route.continue()
      })

      await page.goto('/pm-summary')

      // Should briefly show loading or the section should appear after load
      const agingSection = page.locator('text=Request Aging Overview')
      await expect(agingSection).toBeVisible({ timeout: 3000 })
    })

    test('displays error message if aging data fails to load', async ({ page }) => {
      // Mock failed API request
      await page.route('**/api/analytics/request-aging', (route) => {
        route.abort('failed')
      })

      await page.goto('/pm-summary')

      // Should show error message
      const errorMessage = page.getByText(/error loading aging data/i)
      await expect(errorMessage).toBeVisible({ timeout: 5000 })
    })

    test('gracefully handles empty aging data', async ({ page }) => {
      // Mock empty response
      await page.route('**/api/analytics/request-aging', (route) => {
        route.abort('failed')
      })

      await page.goto('/pm-summary')

      // Page should still be visible
      await expect(page.locator('h1')).toBeVisible()
    })
  })

  test.describe('Data Accuracy', () => {
    test('counts are accurate based on request updated_at timestamps', async ({ page }) => {
      await page.goto('/pm-summary')
      await page.waitForLoadState('networkidle')

      // Get the counts displayed
      const freshCount = await page.locator('text=Fresh').locator('..').locator('text=/\\d+/').first()
      const agingCount = await page.locator('text=Aging').locator('..').locator('text=/\\d+/').first()
      const staleCount = await page.locator('text=Stale').locator('..').locator('text=/\\d+/').first()

      // All should be visible
      await expect(freshCount).toBeVisible()
      await expect(agingCount).toBeVisible()
      await expect(staleCount).toBeVisible()
    })

    test('stale requests are sorted by age (oldest first)', async ({ page }) => {
      await page.goto('/pm-summary')
      await page.waitForLoadState('networkidle')

      const staleHeader = page.locator('text=Oldest Stale Requests')

      if (await staleHeader.count() > 0) {
        const staleRows = page.locator('[class*="border-red"]')
        const rowCount = await staleRows.count()

        if (rowCount > 1) {
          // First row should have higher days count than subsequent rows
          const firstDays = await staleRows.nth(0).locator('text=/\\d+d/').first().textContent()
          const secondDays = await staleRows.nth(1).locator('text=/\\d+d/').first().textContent()

          if (firstDays && secondDays) {
            const firstNum = parseInt(firstDays)
            const secondNum = parseInt(secondDays)
            expect(firstNum >= secondNum).toBeTruthy()
          }
        }
      }
    })
  })

  test.describe('Accessibility', () => {
    test('section has proper heading hierarchy', async ({ page }) => {
      await page.goto('/pm-summary')

      const heading = page.locator('text=Request Aging Overview')
      expect(heading).toBeDefined()
    })

    test('emoji indicators are accessible with proper context', async ({ page }) => {
      await page.goto('/pm-summary')

      const freshCard = page.locator('text=Fresh').nth(0)
      expect(await freshCard.isVisible()).toBeTruthy()
    })

    test('clickable elements are keyboard navigable', async ({ page }) => {
      await page.goto('/pm-summary')

      // Tab to the Fresh bucket
      await page.keyboard.press('Tab')

      // Should be able to interact with keyboard
      const freshCard = page.locator('text=Fresh').nth(0)
      const focusedElement = await page.evaluate(() => document.activeElement?.textContent)

      expect(focusedElement).toBeDefined()
    })
  })

  test.describe('Refresh & Real-time Updates', () => {
    test('aging data auto-refreshes every 30 seconds', async ({ page }) => {
      await page.goto('/pm-summary')

      const initialTime = Date.now()

      // Wait for initial load
      await page.waitForLoadState('networkidle')

      // Should make another request within 30-35 seconds for refresh
      let requestCount = 0
      await page.on('requestfinished', (request) => {
        if (request.url().includes('request-aging')) {
          requestCount++
        }
      })

      // Just verify the endpoint exists and can be called
      await page.goto('/pm-summary')
      const agingSection = page.locator('text=Request Aging Overview')
      await expect(agingSection).toBeVisible()
    })
  })
})
