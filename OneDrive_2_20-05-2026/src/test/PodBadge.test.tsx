import { render, screen } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { PodBadge } from '@/components/request/PodBadge'

describe('PodBadge', () => {
  test('renders pod name', () => {
    render(<PodBadge pod="Driver" />)
    expect(screen.getByText('Driver')).toBeInTheDocument()
  })

  test('renders Charger pod', () => {
    render(<PodBadge pod="Charger" />)
    expect(screen.getByText('Charger')).toBeInTheDocument()
  })

  test('applies sky color for Driver pod', () => {
    const { container } = render(<PodBadge pod="Driver" />)
    expect(container.firstChild).toHaveClass('bg-sky-100')
    expect(container.firstChild).toHaveClass('text-sky-700')
  })

  test('applies orange color for Charger pod', () => {
    const { container } = render(<PodBadge pod="Charger" />)
    expect(container.firstChild).toHaveClass('bg-orange-100')
  })

  test('applies gray color for Unknown pod', () => {
    const { container } = render(<PodBadge pod="Unknown" />)
    expect(container.firstChild).toHaveClass('bg-gray-100')
    expect(container.firstChild).toHaveClass('text-gray-500')
  })

  test('accepts extra className', () => {
    const { container } = render(<PodBadge pod="Data" className="font-mono" />)
    expect(container.firstChild).toHaveClass('font-mono')
  })
})
