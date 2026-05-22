import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, test, vi, beforeEach } from 'vitest'

vi.mock('@azure/msal-react', () => ({
  useMsal: () => ({
    instance: { getActiveAccount: () => null },
    accounts: [],
    inProgress: 'none',
  }),
  useIsAuthenticated: () => true,
}))

vi.mock('@azure/msal-browser', () => ({
  InteractionStatus: { None: 'none' },
}))

const mockUseRequests = vi.fn().mockReturnValue({ data: undefined, isLoading: false })
vi.mock('@/hooks/useRequests', () => ({
  useRequests: (...args: unknown[]) => mockUseRequests(...args),
}))

import { DashboardPage } from '@/pages/DashboardPage'

const mockListResponse = {
  items: [
    {
      id: 'req-1',
      reference_id: 'BLR-2026-0001',
      title: 'Fix driver crash',
      request_type: 'Defect',
      pod: 'Driver',
      severity: 'High',
      status: 'InReview',
      business_problem: 'Crash on checkout',
      expected_outcome: null,
      steps_to_reproduce: null,
      affected_area: 'Driver app',
      additional_context: null,
      submitter_email: 'test@blink.com',
      submitter_name: 'Test User',
      jira_ticket_key: null,
      jira_ticket_url: null,
      created_at: '2026-05-01T10:00:00Z',
      updated_at: '2026-05-01T10:00:00Z',
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
}

function renderDashboard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('DashboardPage', () => {
  beforeEach(() => {
    mockUseRequests.mockReturnValue({ data: mockListResponse, isLoading: false })
  })


  test('renders dashboard heading', () => {
    renderDashboard()
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  test('renders stat card labels', () => {
    mockUseRequests.mockReturnValue({ data: { items: [], total: 42, page: 1, page_size: 20 }, isLoading: false })
    renderDashboard()
    expect(screen.getByText('Total')).toBeInTheDocument()
    expect(screen.getByText('New / Submitted')).toBeInTheDocument()
    // "Awaiting Info" appears in both stat card and status tab — use getAllByText
    expect(screen.getAllByText('Awaiting Info').length).toBeGreaterThanOrEqual(1)
    // "Approved" also appears in stat card + tab; use getAllByText
    expect(screen.getAllByText('Approved').length).toBeGreaterThanOrEqual(1)
  })

  test('renders POD filter pills', () => {
    renderDashboard()
    expect(screen.getByText('All PODs')).toBeInTheDocument()
    // Driver/Charger appear in both pills and table rows — just confirm at least one exists
    expect(screen.getAllByText('Driver').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Charger').length).toBeGreaterThanOrEqual(1)
  })

  test('renders status tabs', () => {
    renderDashboard()
    expect(screen.getAllByText('New').length).toBeGreaterThanOrEqual(1)
    // "In Review" appears in tab + status badge in the table row
    expect(screen.getAllByText('In Review').length).toBeGreaterThanOrEqual(1)
  })

  test('renders request in table', () => {
    renderDashboard()
    expect(screen.getByText('Fix driver crash')).toBeInTheDocument()
  })

  test('shows loading spinner when isLoading=true', () => {
    mockUseRequests.mockReturnValue({ data: undefined, isLoading: true })
    const { container } = renderDashboard()
    expect(container.querySelector('.animate-spin')).toBeInTheDocument()
  })
})
