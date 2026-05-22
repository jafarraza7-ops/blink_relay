import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, test, vi, beforeEach } from 'vitest'

// Mock MSAL before importing anything that uses it
vi.mock('@azure/msal-react', () => ({
  useMsal: () => ({
    instance: { getActiveAccount: () => null, loginRedirect: vi.fn() },
    accounts: [],
    inProgress: 'none',
  }),
  useIsAuthenticated: () => true,
  MsalProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('@azure/msal-browser', () => ({
  InteractionStatus: { None: 'none' },
}))

vi.mock('@/hooks/useRequests', () => ({
  useCreateRequest: () => ({ mutate: vi.fn(), isPending: false }),
}))

vi.mock('@/lib/api', () => ({
  filesApi: { upload: vi.fn() },
  setTokenGetter: vi.fn(),
}))

import { SubmitPage } from '@/pages/SubmitPage'

function renderSubmitPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <SubmitPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('SubmitPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  test('renders step 1 with type toggle', () => {
    renderSubmitPage()
    expect(screen.getByText('What kind of request?')).toBeInTheDocument()
    expect(screen.getByText('Feature')).toBeInTheDocument()
    expect(screen.getByText('Defect')).toBeInTheDocument()
  })

  test('renders priority cards on step 1', () => {
    renderSubmitPage()
    expect(screen.getByText('Critical')).toBeInTheDocument()
    expect(screen.getByText('High')).toBeInTheDocument()
    expect(screen.getByText('Medium')).toBeInTheDocument()
    expect(screen.getByText('Low')).toBeInTheDocument()
  })

  test('renders POD options on step 1', () => {
    renderSubmitPage()
    expect(screen.getByText('Driver')).toBeInTheDocument()
    expect(screen.getByText('Charger')).toBeInTheDocument()
  })

  test('Next button is present on step 1', () => {
    renderSubmitPage()
    expect(screen.getByText('Next')).toBeInTheDocument()
  })

  test('Back button is not shown on step 1', () => {
    renderSubmitPage()
    expect(screen.queryByText('Back')).not.toBeInTheDocument()
  })

  test('Back button appears on step 2', async () => {
    renderSubmitPage()

    // Advance to step 2
    const driverBtn = screen.getByText('Driver').closest('button')!
    fireEvent.click(driverBtn)
    fireEvent.click(screen.getByText('Next').closest('button')!)

    await waitFor(() => {
      expect(screen.getByText('Tell us about the request')).toBeInTheDocument()
    })

    expect(screen.getByText('Back').closest('button')).toBeInTheDocument()
  })

  test('can select Defect type', async () => {
    renderSubmitPage()
    const defectBtn = screen.getByText('Defect').closest('button')!
    fireEvent.click(defectBtn)
    await waitFor(() => {
      expect(defectBtn).toHaveAttribute('aria-pressed', 'true')
    })
  })

  test('advances to step 2 after valid step 1', async () => {
    renderSubmitPage()

    // Select a POD (required for step 1 validation)
    const driverBtn = screen.getByText('Driver').closest('button')!
    fireEvent.click(driverBtn)

    const nextBtn = screen.getByText('Next').closest('button')!
    fireEvent.click(nextBtn)

    await waitFor(() => {
      expect(screen.getByText('Tell us about the request')).toBeInTheDocument()
    })
  })
})
