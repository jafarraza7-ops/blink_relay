import { render, screen } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { StatusBadge } from '@/components/request/StatusBadge'

describe('StatusBadge', () => {
  test('renders human-readable label for InReview', () => {
    render(<StatusBadge status="InReview" />)
    expect(screen.getByText('In Review')).toBeInTheDocument()
  })

  test('renders label for AwaitingInfo', () => {
    render(<StatusBadge status="AwaitingInfo" />)
    expect(screen.getByText('Awaiting Info')).toBeInTheDocument()
  })

  test('applies green color class for Approved', () => {
    const { container } = render(<StatusBadge status="Approved" />)
    expect(container.firstChild).toHaveClass('bg-green-100')
    expect(container.firstChild).toHaveClass('text-green-700')
  })

  test('applies red color class for Rejected', () => {
    const { container } = render(<StatusBadge status="Rejected" />)
    expect(container.firstChild).toHaveClass('bg-red-100')
  })

  test('applies amber color class for AwaitingInfo', () => {
    const { container } = render(<StatusBadge status="AwaitingInfo" />)
    expect(container.firstChild).toHaveClass('bg-amber-100')
  })

  test('accepts extra className', () => {
    const { container } = render(<StatusBadge status="Submitted" className="text-lg" />)
    expect(container.firstChild).toHaveClass('text-lg')
  })
})
