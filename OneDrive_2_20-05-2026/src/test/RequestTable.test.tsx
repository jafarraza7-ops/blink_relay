import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, test } from 'vitest'
import { RequestTable } from '@/components/request/RequestTable'
import type { BlinkRequest } from '@/lib/types'

const mockRequest: BlinkRequest = {
  id: 'req-1',
  reference_id: 'BLR-2026-0001',
  title: 'Fix driver app crash on checkout',
  request_type: 'Defect',
  pod: 'Driver',
  severity: 'High',
  status: 'InReview',
  business_problem: 'App crashes on checkout',
  expected_outcome: null,
  steps_to_reproduce: null,
  affected_area: 'Driver app',
  additional_context: null,
  submitter_email: 'test@blink.com',
  submitter_name: 'Test User',
  jira_ticket_key: null,
  jira_ticket_url: null,
  jsm_ticket_key: null,
  jsm_ticket_url: null,
  jsm_resolved_at: null,
  created_at: '2026-05-01T10:00:00Z',
  updated_at: '2026-05-01T10:00:00Z',
}

function wrap(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('RequestTable', () => {
  test('shows loading spinner when isLoading=true', () => {
    const { container } = wrap(<RequestTable requests={[]} isLoading />)
    expect(container.querySelector('.animate-spin')).toBeInTheDocument()
  })

  test('shows empty state when requests is empty', () => {
    wrap(<RequestTable requests={[]} />)
    expect(screen.getByText('No requests found')).toBeInTheDocument()
  })

  test('renders a request row with title', () => {
    wrap(<RequestTable requests={[mockRequest]} />)
    expect(screen.getByText('Fix driver app crash on checkout')).toBeInTheDocument()
  })

  test('renders reference ID', () => {
    wrap(<RequestTable requests={[mockRequest]} />)
    expect(screen.getByText('BLR-2026-0001')).toBeInTheDocument()
  })

  test('renders submitter name', () => {
    wrap(<RequestTable requests={[mockRequest]} />)
    expect(screen.getByText('Test User')).toBeInTheDocument()
  })

  test('renders multiple rows', () => {
    const requests = [
      { ...mockRequest, id: 'req-1', title: 'First request' },
      { ...mockRequest, id: 'req-2', title: 'Second request' },
    ]
    wrap(<RequestTable requests={requests} />)
    expect(screen.getByText('First request')).toBeInTheDocument()
    expect(screen.getByText('Second request')).toBeInTheDocument()
  })
})
