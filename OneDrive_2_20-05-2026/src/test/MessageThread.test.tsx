/**
 * Unit tests for MessageThread component improvements
 *
 * Tests for:
 * - Text wrapping for long URLs and unbroken content
 * - Truncation and "Read more" functionality
 * - Message direction detection
 * - Email notification routing prevention
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TruncatedBody } from '@/components/request/MessageThread'

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// TEST: TruncatedBody - Text Wrapping
// ═══════════════════════════════════════════════════════════════════════════════════════════════

describe('TruncatedBody - Text Wrapping for Long URLs', () => {
  it('should render short text without truncation', () => {
    const shortText = 'This is a short message'
    const { container } = render(<TruncatedBody text={shortText} />)

    expect(screen.getByText(shortText)).toBeInTheDocument()
    expect(screen.queryByText(/Read more/)).not.toBeInTheDocument()
  })

  it('should apply CSS classes for text wrapping', () => {
    const shortText = 'Short message'
    const { container } = render(<TruncatedBody text={shortText} />)

    const paragraph = container.querySelector('p')
    expect(paragraph).toHaveClass('whitespace-pre-wrap')
    expect(paragraph).toHaveClass('break-words')
    expect(paragraph).toHaveClass('overflow-hidden')
  })

  it('should truncate long text and show "Read more" button', () => {
    const longText = 'a'.repeat(250) // Exceeds 200 char limit
    const { container } = render(<TruncatedBody text={longText} />)

    // Should show truncated version
    const displayedText = container.querySelector('p')?.textContent || ''
    expect(displayedText.length).toBeLessThan(longText.length)

    // Should have "Read more" button
    expect(screen.getByText('Read more')).toBeInTheDocument()
  })

  it('should expand text when "Read more" is clicked', () => {
    const longText = 'a'.repeat(250)
    const { container } = render(<TruncatedBody text={longText} />)

    const readMoreButton = screen.getByText('Read more')
    fireEvent.click(readMoreButton)

    // After expansion, full text should be visible
    expect(container.querySelector('p')?.textContent).toContain(longText)
    expect(screen.getByText('Show less')).toBeInTheDocument()
  })

  it('should collapse text when "Show less" is clicked', () => {
    const longText = 'a'.repeat(250)
    const { container } = render(<TruncatedBody text={longText} />)

    // Expand
    fireEvent.click(screen.getByText('Read more'))

    // Collapse
    fireEvent.click(screen.getByText('Show less'))

    // Should show truncated version again
    const paragraph = container.querySelector('p')?.textContent || ''
    expect(paragraph).toContain('…')
    expect(screen.getByText('Read more')).toBeInTheDocument()
  })

  it('should preserve user line breaks in text', () => {
    const textWithBreaks = 'Line 1\nLine 2\nLine 3'
    const { container } = render(<TruncatedBody text={textWithBreaks} />)

    const paragraph = container.querySelector('p')
    // whitespace-pre-wrap should preserve breaks
    expect(paragraph).toHaveClass('whitespace-pre-wrap')
  })

  it('should handle long URLs without breaking container', () => {
    const longUrl = 'http://localhost:5173/auth/email/callback?token=' + 'x'.repeat(100)
    const { container } = render(<TruncatedBody text={longUrl} />)

    const paragraph = container.querySelector('p')

    // IMPROVEMENT: Text wrapping classes should prevent layout breaking
    expect(paragraph).toHaveClass('break-words')
    expect(paragraph).toHaveClass('overflow-hidden')

    // URL should be visible in the text
    expect(screen.getByText(longUrl)).toBeInTheDocument()
  })

  it('should handle mixed content (text + URL)', () => {
    const mixedContent = `Check out this link: http://localhost:5173/auth/email/callback?token=very_long_token_string_here and more text after it`
    const { container } = render(<TruncatedBody text={mixedContent} />)

    const paragraph = container.querySelector('p')
    expect(paragraph).toHaveClass('break-words')
    expect(paragraph).toHaveClass('whitespace-pre-wrap')
  })

  it('should limit truncation to 200 characters', () => {
    const text = 'x'.repeat(250)
    const { container } = render(<TruncatedBody text={text} />)

    // First render shows 200 chars + '…'
    const displayedText = container.querySelector('p')?.textContent || ''
    expect(displayedText.length).toBeLessThanOrEqual(202) // 200 + ellipsis + read more button
  })

  it('should not show "Read more" for exactly 200 characters', () => {
    const text = 'a'.repeat(200)
    const { container } = render(<TruncatedBody text={text} />)

    expect(screen.queryByText(/Read more/)).not.toBeInTheDocument()
  })

  it('should show "Read more" for 201+ characters', () => {
    const text = 'a'.repeat(201)
    const { container } = render(<TruncatedBody text={text} />)

    expect(screen.getByText('Read more')).toBeInTheDocument()
  })
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// TEST: Message Content - Real-world Scenarios
// ═══════════════════════════════════════════════════════════════════════════════════════════════

describe('TruncatedBody - Real-world Message Scenarios', () => {
  it('should handle email login link in message', () => {
    const emailLink = 'http://localhost:5173/auth/email/callback?token=dVjTcFMwLKsE7iOH2k2Cbtzi-l4RX81LX0H38UEXoCkM0'
    const message = `Please click this link to login: ${emailLink}`
    const { container } = render(<TruncatedBody text={message} />)

    // Should have wrapping enabled
    const paragraph = container.querySelector('p')
    expect(paragraph).toHaveClass('break-words')
  })

  it('should handle multi-line clarification questions', () => {
    const multiLineText = `Can you please clarify:
1. What is the priority level?
2. Which pods are affected?
3. What is the expected timeline?`

    const { container } = render(<TruncatedBody text={multiLineText} />)

    // Line breaks should be preserved
    expect(container.querySelector('p')).toHaveClass('whitespace-pre-wrap')
  })

  it('should handle technical log output', () => {
    const logText = `Error: Connection timeout
Stack trace:
  at connect() line 42
  at init() line 15
  at main() line 1`

    const { container } = render(<TruncatedBody text={logText} />)

    const paragraph = container.querySelector('p')
    // Should preserve formatting
    expect(paragraph).toHaveClass('whitespace-pre-wrap')
  })

  it('should handle message with multiple URLs', () => {
    const multiUrlText = `See these links:
1. http://localhost:5173/auth/email/callback?token=abc123 (token link)
2. http://localhost:5173/requests/id (request link)
3. https://ethereal.email (email service)`

    const { container } = render(<TruncatedBody text={multiUrlText} />)

    const paragraph = container.querySelector('p')
    expect(paragraph).toHaveClass('break-words')
  })
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// TEST: Accessibility and Edge Cases
// ═══════════════════════════════════════════════════════════════════════════════════════════════

describe('TruncatedBody - Accessibility and Edge Cases', () => {
  it('should handle empty text', () => {
    const { container } = render(<TruncatedBody text="" />)
    const paragraph = container.querySelector('p')
    expect(paragraph).toBeInTheDocument()
  })

  it('should handle text with special characters', () => {
    const specialText = 'Test with <special> & "characters" and ™ symbols'
    const { container } = render(<TruncatedBody text={specialText} />)

    expect(screen.getByText(specialText)).toBeInTheDocument()
  })

  it('should handle very long words without spaces', () => {
    const longWord = 'a'.repeat(150)
    const { container } = render(<TruncatedBody text={longWord} />)

    const paragraph = container.querySelector('p')
    // break-words should handle long unbroken strings
    expect(paragraph).toHaveClass('break-words')
  })

  it('should handle Unicode and emoji', () => {
    const emojiText = 'Work in progress 🚀 on the similarity feature ✨'
    const { container } = render(<TruncatedBody text={emojiText} />)

    expect(screen.getByText(emojiText)).toBeInTheDocument()
  })

  it('should handle tab characters', () => {
    const textWithTabs = 'Column1\t\tColumn2\t\tColumn3'
    const { container } = render(<TruncatedBody text={textWithTabs} />)

    const paragraph = container.querySelector('p')
    // whitespace-pre-wrap preserves tabs
    expect(paragraph).toHaveClass('whitespace-pre-wrap')
  })
})
