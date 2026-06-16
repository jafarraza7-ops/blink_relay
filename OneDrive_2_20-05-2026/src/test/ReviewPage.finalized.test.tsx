import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import { QueryClientProvider, QueryClient } from '@tanstack/react-query'
import { ReviewPage } from '@/pages/ReviewPage'
import * as useRequestsHook from '@/hooks/useRequests'

// Mock dependencies
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useParams: () => ({ id: 'test-request-123' }),
  }
})

vi.mock('@/hooks/useRequests')
vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    user: {
      oid: 'pm-001',
      email: 'pm@example.com',
      name: 'Product Manager',
      roles: ['ProductManager'],
    },
    isPM: true,
  }),
}))

const mockRequestCancelled = {
  id: 'test-request-123',
  reference_id: 'BLR-001',
  title: 'Test Request',
  request_type: 'Feature',
  pod: 'Driver',
  region: ['NA'],
  priority: 'High',
  status: 'Cancelled',
  business_problem: 'Test problem',
  expected_outcome: 'Test outcome',
  affected_area: 'Test area',
  submitter_email: 'user@example.com',
  submitter_name: 'Test User',
  jira_ticket_key: null,
  jsm_ticket_key: null,
  created_at: '2026-06-01T10:00:00Z',
  updated_at: '2026-06-16T10:00:00Z',
}

const mockRequestRejected = {
  ...mockRequestCancelled,
  status: 'Rejected',
}

describe('ReviewPage - Finalized Requests (Cancelled/Rejected)', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient()
    vi.clearAllMocks()
  })

  const renderReviewPage = (request = mockRequestCancelled) => {
    vi.mocked(useRequestsHook.useRequest).mockReturnValue({
      data: request,
      isLoading: false,
      isError: false,
    } as any)

    vi.mocked(useRequestsHook.useRequestTimeline).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    } as any)

    return render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ReviewPage />
        </BrowserRouter>
      </QueryClientProvider>
    )
  }

  describe('Watermark Display', () => {
    it('displays CANCELLED watermark for cancelled requests', () => {
      renderReviewPage(mockRequestCancelled)
      const watermark = screen.getByText('CANCELLED', { exact: false })
      expect(watermark).toBeInTheDocument()
    })

    it('displays REJECTED watermark for rejected requests', () => {
      renderReviewPage(mockRequestRejected)
      const watermark = screen.getByText('REJECTED', { exact: false })
      expect(watermark).toBeInTheDocument()
    })

    it('watermark has correct styling (orange for cancelled, red for rejected)', () => {
      const { rerender } = renderReviewPage(mockRequestCancelled)

      // For cancelled: should have text-orange-600
      let watermarkDiv = screen.getByText('CANCELLED').closest('div')?.parentElement
      expect(watermarkDiv?.className).toContain('text-orange-600')

      // For rejected
      rerender(
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <ReviewPage />
          </BrowserRouter>
        </QueryClientProvider>
      )
      watermarkDiv = screen.getByText('REJECTED').closest('div')?.parentElement
      expect(watermarkDiv?.className).toContain('text-red-600')
    })
  })

  describe('Action Buttons Disabled', () => {
    it('hides approve button for cancelled requests', () => {
      renderReviewPage(mockRequestCancelled)
      // Approve button should not be rendered for finalized requests
      const approveButtons = screen.queryAllByRole('button', { name: /approve/i })
      expect(approveButtons.length).toBe(0)
    })

    it('hides status update section for cancelled requests', () => {
      renderReviewPage(mockRequestCancelled)
      const statusSection = screen.queryByText(/update status/i)
      expect(statusSection).not.toBeInTheDocument()
    })

    it('hides request clarification section for cancelled requests', () => {
      renderReviewPage(mockRequestCancelled)
      const clarifySection = screen.queryByText(/request clarification/i)
      expect(clarifySection).not.toBeInTheDocument()
    })

    it('displays "Request Finalized" info card for cancelled requests', () => {
      renderReviewPage(mockRequestCancelled)
      const finalizedCard = screen.getByText(/request finalized/i)
      expect(finalizedCard).toBeInTheDocument()
    })
  })

  describe('Conversation Section', () => {
    it('conversation section is visible but read-only for cancelled requests', () => {
      renderReviewPage(mockRequestCancelled)
      const conversationCard = screen.getByText(/conversation/i)
      expect(conversationCard).toBeInTheDocument()

      // Should have read-only label
      const readOnlyLabel = screen.getByText(/read-only/i)
      expect(readOnlyLabel).toBeInTheDocument()
    })

    it('displays info message about read-only conversation', () => {
      renderReviewPage(mockRequestCancelled)
      const infoMessage = screen.getByText(/conversation is read-only/i)
      expect(infoMessage).toBeInTheDocument()
    })

    it('conversation section has reduced opacity styling', () => {
      renderReviewPage(mockRequestCancelled)
      const conversationCard = screen.getByText(/conversation/i).closest('div')
      const cardParent = conversationCard?.parentElement
      expect(cardParent?.className).toContain('opacity-60')
    })
  })

  describe('Attachments', () => {
    it('FileAttachment component receives canUpload={false} for cancelled requests', async () => {
      renderReviewPage(mockRequestCancelled)

      // The upload button should be hidden/disabled
      await waitFor(() => {
        const uploadButton = screen.queryByRole('button', { name: /attach files/i })
        expect(uploadButton).not.toBeInTheDocument()
      })
    })

    it('FileAttachment component receives canUpload={true} for active requests', async () => {
      vi.mocked(useRequestsHook.useRequest).mockReturnValue({
        data: {
          ...mockRequestCancelled,
          status: 'Submitted',
        },
        isLoading: false,
        isError: false,
      } as any)

      vi.mocked(useRequestsHook.useRequestTimeline).mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
      } as any)

      render(
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <ReviewPage />
          </BrowserRouter>
        </QueryClientProvider>
      )

      // For active requests, upload button should be visible
      await waitFor(() => {
        const uploadButton = screen.getByRole('button', { name: /attach files/i })
        expect(uploadButton).toBeInTheDocument()
      })
    })
  })

  describe('Claim/Unclaim Buttons', () => {
    it('claim button is hidden for cancelled requests', () => {
      renderReviewPage(mockRequestCancelled)
      const claimButton = screen.queryByRole('button', { name: /claim/i })
      expect(claimButton).not.toBeInTheDocument()
    })

    it('unclaim button is hidden for cancelled requests', () => {
      renderReviewPage(mockRequestCancelled)
      const unclaimButton = screen.queryByRole('button', { name: /unclaim/i })
      expect(unclaimButton).not.toBeInTheDocument()
    })
  })
})
