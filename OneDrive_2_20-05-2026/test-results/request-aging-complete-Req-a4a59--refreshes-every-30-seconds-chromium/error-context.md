# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: request-aging-complete.spec.ts >> Request Aging Visualization - Complete Suite >> Refresh & Real-time Updates >> aging data auto-refreshes every 30 seconds
- Location: tests/e2e/request-aging-complete.spec.ts:324:5

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: locator('text=Request Aging Overview')
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for locator('text=Request Aging Overview')
    - waiting for" https://login.microsoftonline.com/dev-tenant-id/oauth2/v2.0/authorize?client_id=dev-client-id&scope=api%3A%2F%2Fdev-client-id%2Fuser_impersonation%20openid%20profile%20offline_access&redirect_uri=htt…" navigation to finish...
    - navigated to "https://login.microsoftonline.com/dev-tenant-id/oauth2/v2.0/authorize?client_id=dev-client-id&scope=api%3A%2F%2Fdev-client-id%2Fuser_impersonation%20openid%20profile%20offline_access&redirect_uri=htt…"

```

# Page snapshot

```yaml
- generic [ref=e1]:
  - generic:
    - generic:
      - generic:
        - generic:
          - img "Organization background image" [ref=e2]
          - generic [ref=e3]:
            - generic [ref=e8]:
              - generic [ref=e9]:
                - img "Microsoft" [ref=e12]
                - main [ref=e13]:
                  - generic [ref=e16]:
                    - heading "Sign in" [level=1] [ref=e17]
                    - paragraph [ref=e19]: Sorry, but we’re having trouble signing you in.
                    - generic [ref=e20]: "AADSTS900023: Specified tenant identifier 'dev-tenant-id' is neither a valid DNS name, nor a valid external domain."
              - generic [ref=e23]:
                - generic [ref=e24]:
                  - generic [ref=e25]:
                    - heading "Troubleshooting details" [level=2] [ref=e26]
                    - generic [ref=e27]: If you contact your administrator, send this info to them.
                    - button "Copy info to clipboard" [ref=e28] [cursor=pointer]
                  - generic [ref=e29]:
                    - generic [ref=e30]: "Request Id: 88e96a85-5e4d-4561-a5f4-0fbd1d644f00"
                    - generic [ref=e31]: "Correlation Id: 019ecfc1-1536-7843-9f9c-5a9f54aa8046"
                    - generic [ref=e32]: "Timestamp: 2026-06-16T09:26:38Z"
                    - generic [ref=e33]: "Message: AADSTS900023: Specified tenant identifier 'dev-tenant-id' is neither a valid DNS name, nor a valid external domain."
                  - generic [ref=e34]:
                    - generic [ref=e35]:
                      - text: "Flag sign-in errors for review:"
                      - button "Enable flagging" [ref=e36] [cursor=pointer]
                    - generic [ref=e37]: If you plan on getting help for this problem, enable flagging and try to reproduce the error within 20 minutes. Flagged events make diagnostics available and are raised to admin attention.
                - button "Close troubleshooting details" [ref=e38] [cursor=pointer]
            - contentinfo [ref=e39]:
              - generic [ref=e40]:
                - link "Terms of use" [ref=e41] [cursor=pointer]:
                  - /url: https://www.microsoft.com/en-US/servicesagreement/
                - link "Privacy & cookies" [ref=e42] [cursor=pointer]:
                  - /url: https://privacy.microsoft.com/en-US/privacystatement
                - button "Click here for troubleshooting information" [ref=e43] [cursor=pointer]: ...
  - textbox [ref=e44]: "Request Id: 88e96a85-5e4d-4561-a5f4-0fbd1d644f00 Correlation Id: 019ecfc1-1536-7843-9f9c-5a9f54aa8046 Timestamp: 2026-06-16T09:26:38Z Message: AADSTS900023: Specified tenant identifier 'dev-tenant-id' is neither a valid DNS name, nor a valid external domain."
```

# Test source

```ts
  243 |         route.abort('failed')
  244 |       })
  245 | 
  246 |       await page.goto('/pm-summary')
  247 | 
  248 |       // Page should still be visible
  249 |       await expect(page.locator('h1')).toBeVisible()
  250 |     })
  251 |   })
  252 | 
  253 |   test.describe('Data Accuracy', () => {
  254 |     test('counts are accurate based on request updated_at timestamps', async ({ page }) => {
  255 |       await page.goto('/pm-summary')
  256 |       await page.waitForLoadState('networkidle')
  257 | 
  258 |       // Get the counts displayed
  259 |       const freshCount = await page.locator('text=Fresh').locator('..').locator('text=/\\d+/').first()
  260 |       const agingCount = await page.locator('text=Aging').locator('..').locator('text=/\\d+/').first()
  261 |       const staleCount = await page.locator('text=Stale').locator('..').locator('text=/\\d+/').first()
  262 | 
  263 |       // All should be visible
  264 |       await expect(freshCount).toBeVisible()
  265 |       await expect(agingCount).toBeVisible()
  266 |       await expect(staleCount).toBeVisible()
  267 |     })
  268 | 
  269 |     test('stale requests are sorted by age (oldest first)', async ({ page }) => {
  270 |       await page.goto('/pm-summary')
  271 |       await page.waitForLoadState('networkidle')
  272 | 
  273 |       const staleHeader = page.locator('text=Oldest Stale Requests')
  274 | 
  275 |       if (await staleHeader.count() > 0) {
  276 |         const staleRows = page.locator('[class*="border-red"]')
  277 |         const rowCount = await staleRows.count()
  278 | 
  279 |         if (rowCount > 1) {
  280 |           // First row should have higher days count than subsequent rows
  281 |           const firstDays = await staleRows.nth(0).locator('text=/\\d+d/').first().textContent()
  282 |           const secondDays = await staleRows.nth(1).locator('text=/\\d+d/').first().textContent()
  283 | 
  284 |           if (firstDays && secondDays) {
  285 |             const firstNum = parseInt(firstDays)
  286 |             const secondNum = parseInt(secondDays)
  287 |             expect(firstNum >= secondNum).toBeTruthy()
  288 |           }
  289 |         }
  290 |       }
  291 |     })
  292 |   })
  293 | 
  294 |   test.describe('Accessibility', () => {
  295 |     test('section has proper heading hierarchy', async ({ page }) => {
  296 |       await page.goto('/pm-summary')
  297 | 
  298 |       const heading = page.locator('text=Request Aging Overview')
  299 |       expect(heading).toBeDefined()
  300 |     })
  301 | 
  302 |     test('emoji indicators are accessible with proper context', async ({ page }) => {
  303 |       await page.goto('/pm-summary')
  304 | 
  305 |       const freshCard = page.locator('text=Fresh').nth(0)
  306 |       expect(await freshCard.isVisible()).toBeTruthy()
  307 |     })
  308 | 
  309 |     test('clickable elements are keyboard navigable', async ({ page }) => {
  310 |       await page.goto('/pm-summary')
  311 | 
  312 |       // Tab to the Fresh bucket
  313 |       await page.keyboard.press('Tab')
  314 | 
  315 |       // Should be able to interact with keyboard
  316 |       const freshCard = page.locator('text=Fresh').nth(0)
  317 |       const focusedElement = await page.evaluate(() => document.activeElement?.textContent)
  318 | 
  319 |       expect(focusedElement).toBeDefined()
  320 |     })
  321 |   })
  322 | 
  323 |   test.describe('Refresh & Real-time Updates', () => {
  324 |     test('aging data auto-refreshes every 30 seconds', async ({ page }) => {
  325 |       await page.goto('/pm-summary')
  326 | 
  327 |       const initialTime = Date.now()
  328 | 
  329 |       // Wait for initial load
  330 |       await page.waitForLoadState('networkidle')
  331 | 
  332 |       // Should make another request within 30-35 seconds for refresh
  333 |       let requestCount = 0
  334 |       await page.on('requestfinished', (request) => {
  335 |         if (request.url().includes('request-aging')) {
  336 |           requestCount++
  337 |         }
  338 |       })
  339 | 
  340 |       // Just verify the endpoint exists and can be called
  341 |       await page.goto('/pm-summary')
  342 |       const agingSection = page.locator('text=Request Aging Overview')
> 343 |       await expect(agingSection).toBeVisible()
      |                                  ^ Error: expect(locator).toBeVisible() failed
  344 |     })
  345 |   })
  346 | })
  347 | 
```