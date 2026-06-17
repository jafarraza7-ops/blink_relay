# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: request-aging-complete.spec.ts >> Request Aging Visualization - Complete Suite >> Component Visibility >> displays time ranges for each bucket
- Location: tests/e2e/request-aging-complete.spec.ts:31:5

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('0-30 days')
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for getByText('0-30 days')
    2 × waiting for" https://login.microsoftonline.com/dev-tenant-id/oauth2/v2.0/authorize?client_id=dev-client-id&scope=api%3A%2F%2Fdev-client-id%2Fuser_impersonation%20openid%20profile%20offline_access&redirect_uri=htt…" navigation to finish...
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
                    - generic [ref=e30]: "Request Id: 75dbe23f-5489-4c97-bc6c-8a4bd3371500"
                    - generic [ref=e31]: "Correlation Id: 019ecfc0-6477-7d44-8c67-f5406841ca70"
                    - generic [ref=e32]: "Timestamp: 2026-06-16T09:25:54Z"
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
  - textbox [ref=e44]: "Request Id: 75dbe23f-5489-4c97-bc6c-8a4bd3371500 Correlation Id: 019ecfc0-6477-7d44-8c67-f5406841ca70 Timestamp: 2026-06-16T09:25:54Z Message: AADSTS900023: Specified tenant identifier 'dev-tenant-id' is neither a valid DNS name, nor a valid external domain."
```

# Test source

```ts
  1   | import { test, expect } from '@playwright/test'
  2   | 
  3   | test.describe('Request Aging Visualization - Complete Suite', () => {
  4   |   test.beforeEach(async ({ page }) => {
  5   |     // Mock auth
  6   |     await page.addInitScript(() => {
  7   |       window.__MOCK_AUTH__ = {
  8   |         user: {
  9   |           id: 'pm-123',
  10  |           email: 'pm@example.com',
  11  |           name: 'PM User',
  12  |           roles: ['PRODUCT_MANAGER'],
  13  |         },
  14  |       }
  15  |     })
  16  |   })
  17  | 
  18  |   test.describe('Component Visibility', () => {
  19  |     test('Request Aging Overview section is visible on PM Summary', async ({ page }) => {
  20  |       await page.goto('/pm-summary')
  21  |       await expect(page.getByText('Request Aging Overview')).toBeVisible()
  22  |     })
  23  | 
  24  |     test('displays three aging buckets: Fresh, Aging, Stale', async ({ page }) => {
  25  |       await page.goto('/pm-summary')
  26  |       await expect(page.getByText('Fresh', { exact: true })).toBeVisible()
  27  |       await expect(page.getByText('Aging', { exact: true })).toBeVisible()
  28  |       await expect(page.getByText('Stale', { exact: true })).toBeVisible()
  29  |     })
  30  | 
  31  |     test('displays time ranges for each bucket', async ({ page }) => {
  32  |       await page.goto('/pm-summary')
> 33  |       await expect(page.getByText('0-30 days')).toBeVisible()
      |                                                 ^ Error: expect(locator).toBeVisible() failed
  34  |       await expect(page.getByText('30-60 days')).toBeVisible()
  35  |       await expect(page.getByText('60+ days')).toBeVisible()
  36  |     })
  37  | 
  38  |     test('displays emoji indicators for each bucket', async ({ page }) => {
  39  |       await page.goto('/pm-summary')
  40  |       const agingSection = page.locator('text=Request Aging Overview').locator('..')
  41  | 
  42  |       // Green circle for Fresh
  43  |       await expect(agingSection.locator('text=🟢')).toBeVisible()
  44  |       // Yellow circle for Aging
  45  |       await expect(agingSection.locator('text=🟡')).toBeVisible()
  46  |       // Red circle for Stale
  47  |       await expect(agingSection.locator('text=🔴')).toBeVisible()
  48  |     })
  49  |   })
  50  | 
  51  |   test.describe('Positioning', () => {
  52  |     test('Request Aging Overview appears after overview cards', async ({ page }) => {
  53  |       await page.goto('/pm-summary')
  54  | 
  55  |       const overviewCards = page.locator('text=Total Requests').nth(0)
  56  |       const agingSection = page.locator('text=Request Aging Overview')
  57  | 
  58  |       const cardBox = await overviewCards.boundingBox()
  59  |       const agingBox = await agingSection.boundingBox()
  60  | 
  61  |       expect(cardBox && agingBox && agingBox.y > cardBox.y).toBeTruthy()
  62  |     })
  63  | 
  64  |     test('section has distinct visual styling (border and background)', async ({ page }) => {
  65  |       await page.goto('/pm-summary')
  66  | 
  67  |       const agingCard = page.locator('text=Request Aging Overview').locator('..')
  68  |       const classList = await agingCard.evaluate(el => el.className)
  69  | 
  70  |       // Should have border and gradient background
  71  |       expect(classList).toContain('border')
  72  |       expect(classList).toContain('gradient')
  73  |     })
  74  |   })
  75  | 
  76  |   test.describe('Bucket Cards', () => {
  77  |     test('Fresh bucket displays correct count and styling', async ({ page }) => {
  78  |       await page.goto('/pm-summary')
  79  | 
  80  |       const freshCard = page.locator('text=Fresh').nth(0)
  81  |       const freshParent = freshCard.locator('..')
  82  | 
  83  |       // Should show emoji and count
  84  |       await expect(freshCard).toBeVisible()
  85  |       // Green styling
  86  |       const classList = await freshParent.evaluate(el => el.className)
  87  |       expect(classList).toContain('green')
  88  |     })
  89  | 
  90  |     test('Aging bucket displays correct count and styling', async ({ page }) => {
  91  |       await page.goto('/pm-summary')
  92  | 
  93  |       const agingCard = page.locator('text=Aging').nth(0)
  94  |       const agingParent = agingCard.locator('..')
  95  | 
  96  |       await expect(agingCard).toBeVisible()
  97  |       const classList = await agingParent.evaluate(el => el.className)
  98  |       expect(classList).toContain('yellow')
  99  |     })
  100 | 
  101 |     test('Stale bucket displays correct count and styling', async ({ page }) => {
  102 |       await page.goto('/pm-summary')
  103 | 
  104 |       const staleCard = page.locator('text=Stale').nth(0)
  105 |       const staleParent = staleCard.locator('..')
  106 | 
  107 |       await expect(staleCard).toBeVisible()
  108 |       const classList = await staleParent.evaluate(el => el.className)
  109 |       expect(classList).toContain('red')
  110 |     })
  111 | 
  112 |     test('bucket cards are clickable and navigate to dashboard', async ({ page }) => {
  113 |       await page.goto('/pm-summary')
  114 | 
  115 |       const freshBucket = page.locator('text=Fresh').nth(0).locator('..')
  116 | 
  117 |       await Promise.all([
  118 |         page.waitForURL(/dashboard/),
  119 |         freshBucket.click(),
  120 |       ])
  121 | 
  122 |       expect(page.url()).toContain('/dashboard')
  123 |     })
  124 |   })
  125 | 
  126 |   test.describe('Stale Requests List', () => {
  127 |     test('displays "Oldest Stale Requests" section when stale requests exist', async ({ page }) => {
  128 |       await page.goto('/pm-summary')
  129 |       await page.waitForLoadState('networkidle')
  130 | 
  131 |       const staleHeader = page.locator('text=Oldest Stale Requests')
  132 |       const headerCount = await staleHeader.count()
  133 | 
```