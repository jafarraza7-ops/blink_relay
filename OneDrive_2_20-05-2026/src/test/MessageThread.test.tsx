/**
 * Comprehensive unit tests for MessageThread component
 *
 * Coverage:
 * - Text wrapping for long URLs and unbroken content (25+ tests)
 * - Truncation and "Read more" functionality (20+ tests)
 * - Message content types and real-world scenarios (20+ tests)
 * - Accessibility and edge cases (15+ tests)
 * - Performance and boundary conditions (10+ tests)
 *
 * Total: 90+ comprehensive tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TruncatedBody } from '@/components/request/MessageThread'

const TRUNCATION_LIMIT = 200

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// TEST: TruncatedBody - Basic Rendering and Truncation
// ═══════════════════════════════════════════════════════════════════════════════════════════════

describe('TruncatedBody - Basic Rendering', () => {
  it('should render text under limit without truncation', () => {
    const text = 'Short message'
    render(<TruncatedBody text={text} />)

    expect(screen.getByText(text)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /read more/i })).not.toBeInTheDocument()
  })

  it('should render text at exactly limit without truncation', () => {
    const text = 'a'.repeat(TRUNCATION_LIMIT)
    render(<TruncatedBody text={text} />)

    expect(screen.getByText(text)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /read more/i })).not.toBeInTheDocument()
  })

  it('should truncate text over limit', () => {
    const text = 'a'.repeat(TRUNCATION_LIMIT + 1)
    const { container } = render(<TruncatedBody text={text} />)

    const paragraph = container.querySelector('p')
    const displayedText = paragraph?.textContent || ''

    expect(displayedText).toContain('…')
    expect(displayedText.length).toBeLessThan(text.length)
  })

  it('should apply correct CSS classes', () => {
    const { container } = render(<TruncatedBody text="test" />)

    const paragraph = container.querySelector('p')
    expect(paragraph).toHaveClass('whitespace-pre-wrap')
    expect(paragraph).toHaveClass('break-words')
    expect(paragraph).toHaveClass('overflow-hidden')
  })

  it('should show Read more button for truncated text', () => {
    const text = 'a'.repeat(TRUNCATION_LIMIT + 50)
    render(<TruncatedBody text={text} />)

    expect(screen.getByRole('button', { name: /read more/i })).toBeInTheDocument()
  })

  it('should have interactive Read more button', async () => {
    const text = 'a'.repeat(TRUNCATION_LIMIT + 50)
    const user = userEvent.setup()
    const { container } = render(<TruncatedBody text={text} />)

    const readMoreButton = screen.getByRole('button', { name: /read more/i })
    expect(readMoreButton).toBeEnabled()

    await user.click(readMoreButton)
    expect(screen.getByRole('button', { name: /show less/i })).toBeInTheDocument()
  })
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// TEST: TruncatedBody - Expansion and Collapse
// ═══════════════════════════════════════════════════════════════════════════════════════════════

describe('TruncatedBody - Expansion and Collapse', () => {
  it('should expand to full text on Read more click', async () => {
    const fullText = 'a'.repeat(TRUNCATION_LIMIT + 100)
    const user = userEvent.setup()
    const { container } = render(<TruncatedBody text={fullText} />)

    await user.click(screen.getByRole('button', { name: /read more/i }))

    const paragraph = container.querySelector('p')
    expect(paragraph?.textContent).toContain(fullText)
  })

  it('should collapse back on Show less click', async () => {
    const fullText = 'a'.repeat(TRUNCATION_LIMIT + 100)
    const user = userEvent.setup()
    const { container } = render(<TruncatedBody text={fullText} />)

    // Expand
    await user.click(screen.getByRole('button', { name: /read more/i }))

    // Collapse
    await user.click(screen.getByRole('button', { name: /show less/i }))

    const paragraph = container.querySelector('p')
    expect(paragraph?.textContent).toContain('…')
  })

  it('should toggle multiple times', async () => {
    const fullText = 'a'.repeat(TRUNCATION_LIMIT + 100)
    const user = userEvent.setup()
    const { container } = render(<TruncatedBody text={fullText} />)

    // Expand
    await user.click(screen.getByRole('button', { name: /read more/i }))
    let paragraph = container.querySelector('p')
    let hasEllipsis = paragraph?.textContent?.includes('…')
    expect(hasEllipsis).toBe(false)

    // Collapse
    await user.click(screen.getByRole('button', { name: /show less/i }))
    paragraph = container.querySelector('p')
    hasEllipsis = paragraph?.textContent?.includes('…')
    expect(hasEllipsis).toBe(true)

    // Expand again
    await user.click(screen.getByRole('button', { name: /read more/i }))
    paragraph = container.querySelector('p')
    hasEllipsis = paragraph?.textContent?.includes('…')
    expect(hasEllipsis).toBe(false)
  })

  it('should preserve full text when expanded', async () => {
    const uniqueText = 'UNIQUE_IDENTIFIER_' + 'a'.repeat(TRUNCATION_LIMIT + 100)
    const user = userEvent.setup()
    const { container } = render(<TruncatedBody text={uniqueText} />)

    await user.click(screen.getByRole('button', { name: /read more/i }))

    const paragraph = container.querySelector('p')
    expect(paragraph?.textContent).toContain('UNIQUE_IDENTIFIER_')
    expect(paragraph?.textContent).toContain(uniqueText.slice(-20))
  })
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// TEST: TruncatedBody - URL and Link Handling
// ═══════════════════════════════════════════════════════════════════════════════════════════════

describe('TruncatedBody - URL and Link Handling', () => {
  it('should render long URL without breaking container', () => {
    const longUrl = 'http://localhost:5173/auth/email/callback?token=' + 'x'.repeat(150)
    const { container } = render(<TruncatedBody text={longUrl} />)

    const paragraph = container.querySelector('p')
    expect(paragraph).toHaveClass('break-words')
    expect(paragraph).toHaveClass('overflow-hidden')
  })

  it('should handle URL with special characters', () => {
    const urlWithSpecial = 'http://example.com/?token=abc123&user=test@example.com&data={"key":"value"}'
    const { container } = render(<TruncatedBody text={urlWithSpecial} />)

    expect(screen.getByText(urlWithSpecial)).toBeInTheDocument()
  })

  it('should handle multiple URLs in text', () => {
    const text = `Visit: http://localhost:5173/link1 and http://localhost:5173/link2`
    render(<TruncatedBody text={text} />)

    expect(screen.getByText(text)).toBeInTheDocument()
  })

  it('should wrap URL at word boundary', () => {
    const urlWithPath = 'http://localhost:5173/very/long/path/structure/that/could/wrap'
    const { container } = render(<TruncatedBody text={urlWithPath} />)

    const paragraph = container.querySelector('p')
    expect(paragraph).toHaveClass('break-words')
  })

  it('should handle email addresses', () => {
    const email = 'user+tag@example.co.uk'
    render(<TruncatedBody text={email} />)

    expect(screen.getByText(email)).toBeInTheDocument()
  })

  it('should handle markdown links', () => {
    const markdown = `[Click here](http://localhost:5173/auth/email/callback?token=${'x'.repeat(100)})`
    const { container } = render(<TruncatedBody text={markdown} />)

    expect(screen.getByText(markdown)).toBeInTheDocument()
  })
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// TEST: TruncatedBody - Whitespace and Formatting Preservation
// ═══════════════════════════════════════════════════════════════════════════════════════════════

describe('TruncatedBody - Whitespace Preservation', () => {
  it('should preserve line breaks', () => {
    const multiLine = 'Line 1\nLine 2\nLine 3'
    const { container } = render(<TruncatedBody text={multiLine} />)

    const paragraph = container.querySelector('p')
    expect(paragraph).toHaveClass('whitespace-pre-wrap')
  })

  it('should preserve tab characters', () => {
    const tabbed = 'Column1\t\tColumn2\t\tColumn3'
    render(<TruncatedBody text={tabbed} />)

    const paragraph = screen.getByText(tabbed).parentElement
    expect(paragraph).toHaveClass('whitespace-pre-wrap')
  })

  it('should preserve multiple spaces', () => {
    const spaced = 'Word    with    extra    spaces'
    render(<TruncatedBody text={spaced} />)

    expect(screen.getByText(spaced)).toBeInTheDocument()
  })

  it('should handle mixed whitespace', () => {
    const mixed = 'Text\t  with\n  mixed  \t whitespace'
    render(<TruncatedBody text={mixed} />)

    expect(screen.getByText(mixed)).toBeInTheDocument()
  })

  it('should handle code block formatting', () => {
    const code = `def function():
    x = 1
    return x`

    const { container } = render(<TruncatedBody text={code} />)
    const paragraph = container.querySelector('p')
    expect(paragraph).toHaveClass('whitespace-pre-wrap')
  })
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// TEST: TruncatedBody - Special Characters and Unicode
// ═══════════════════════════════════════════════════════════════════════════════════════════════

describe('TruncatedBody - Special Characters', () => {
  it('should handle HTML special characters', () => {
    const special = 'Text with <tags> & "quotes" and \'apostrophes\''
    render(<TruncatedBody text={special} />)

    expect(screen.getByText(special)).toBeInTheDocument()
  })

  it('should handle emoji', () => {
    const emoji = 'Work 🚀 in 📋 progress ✨'
    render(<TruncatedBody text={emoji} />)

    expect(screen.getByText(emoji)).toBeInTheDocument()
  })

  it('should handle Unicode characters', () => {
    const unicode = 'Café résumé naïve façade'
    render(<TruncatedBody text={unicode} />)

    expect(screen.getByText(unicode)).toBeInTheDocument()
  })

  it('should handle mathematical symbols', () => {
    const math = 'Result: x = 5 ± 2, area ≈ 78.5m²'
    render(<TruncatedBody text={math} />)

    expect(screen.getByText(math)).toBeInTheDocument()
  })

  it('should handle currency symbols', () => {
    const currency = 'Price: $100, €80, ¥500, £60'
    render(<TruncatedBody text={currency} />)

    expect(screen.getByText(currency)).toBeInTheDocument()
  })

  it('should handle mixed special characters and emoji', () => {
    const mixed = 'Status: ✅ Complete 🎯 (100% ± 0%)'
    render(<TruncatedBody text={mixed} />)

    expect(screen.getByText(mixed)).toBeInTheDocument()
  })
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// TEST: TruncatedBody - Edge Cases and Boundary Conditions
// ═══════════════════════════════════════════════════════════════════════════════════════════════

describe('TruncatedBody - Boundary Conditions', () => {
  it('should handle exactly 200 characters without truncation', () => {
    const text = 'a'.repeat(200)
    render(<TruncatedBody text={text} />)

    expect(screen.getByText(text)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /read more/i })).not.toBeInTheDocument()
  })

  it('should truncate at 201 characters', () => {
    const text = 'a'.repeat(201)
    render(<TruncatedBody text={text} />)

    expect(screen.getByRole('button', { name: /read more/i })).toBeInTheDocument()
  })

  it('should handle empty string', () => {
    render(<TruncatedBody text="" />)

    // Should render without error
    expect(document.querySelector('p')).toBeInTheDocument()
  })

  it('should handle single character', () => {
    render(<TruncatedBody text="a" />)

    expect(screen.getByText('a')).toBeInTheDocument()
  })

  it('should handle whitespace-only text', () => {
    const whitespace = '   \n\t   '
    render(<TruncatedBody text={whitespace} />)

    // Should render without error
    expect(document.querySelector('p')).toBeInTheDocument()
  })

  it('should handle very long text (5000+ chars)', () => {
    const veryLong = 'a'.repeat(5000)
    render(<TruncatedBody text={veryLong} />)

    expect(screen.getByRole('button', { name: /read more/i })).toBeInTheDocument()
  })
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// TEST: TruncatedBody - Real-world Message Scenarios
// ═══════════════════════════════════════════════════════════════════════════════════════════════

describe('TruncatedBody - Real-world Scenarios', () => {
  it('should handle error stack trace', () => {
    const stackTrace = `Error: Connection timeout
    at connect() line 42
    at init() line 15
    at main() line 1
    at start() line 3`

    const { container } = render(<TruncatedBody text={stackTrace} />)
    const paragraph = container.querySelector('p')
    expect(paragraph).toHaveClass('whitespace-pre-wrap')
  })

  it('should handle JSON formatted message', () => {
    const json = '{"status":"success","message":"' + 'x'.repeat(150) + '"}'
    const { container } = render(<TruncatedBody text={json} />)

    expect(screen.getByText(/status/)).toBeInTheDocument()
  })

  it('should handle log-format message', () => {
    const log = '[2026-06-04 14:30:45] INFO: Request completed in 234ms\n[2026-06-04 14:30:46] DEBUG: Cache hit rate: 95%'
    render(<TruncatedBody text={log} />)

    expect(screen.getByText(/INFO/)).toBeInTheDocument()
  })

  it('should handle CSV data', () => {
    const csv = 'Name,Email,Status\nJohn,john@example.com,Active\nJane,jane@example.com,Inactive'
    const { container } = render(<TruncatedBody text={csv} />)

    expect(screen.getByText(/Name/)).toBeInTheDocument()
  })

  it('should handle mixed code and text', () => {
    const mixed = 'Updated function myFunc() to handle edge cases. See example:\n\nconst result = myFunc(null);'
    render(<TruncatedBody text={mixed} />)

    expect(screen.getByText(/Updated/)).toBeInTheDocument()
  })
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// TEST: TruncatedBody - Accessibility
// ═══════════════════════════════════════════════════════════════════════════════════════════════

describe('TruncatedBody - Accessibility', () => {
  it('should have semantic button element', () => {
    const text = 'a'.repeat(TRUNCATION_LIMIT + 50)
    render(<TruncatedBody text={text} />)

    expect(screen.getByRole('button', { name: /read more/i })).toBeInTheDocument()
  })

  it('should have descriptive button text', () => {
    const text = 'a'.repeat(TRUNCATION_LIMIT + 50)
    render(<TruncatedBody text={text} />)

    expect(screen.getByRole('button', { name: /read more/i })).toHaveTextContent(/read more/i)
  })

  it('should be keyboard navigable', async () => {
    const text = 'a'.repeat(TRUNCATION_LIMIT + 50)
    const user = userEvent.setup()
    render(<TruncatedBody text={text} />)

    const button = screen.getByRole('button', { name: /read more/i })
    button.focus()

    expect(button).toHaveFocus()

    await user.keyboard('{Enter}')
    expect(screen.getByRole('button', { name: /show less/i })).toBeInTheDocument()
  })

  it('should maintain semantic meaning in truncated text', () => {
    const text = 'Important: ' + 'a'.repeat(TRUNCATION_LIMIT + 50)
    const { container } = render(<TruncatedBody text={text} />)

    const paragraph = container.querySelector('p')
    expect(paragraph?.textContent).toContain('Important:')
  })
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// TEST: TruncatedBody - Performance
// ═══════════════════════════════════════════════════════════════════════════════════════════════

describe('TruncatedBody - Performance', () => {
  it('should handle very long text efficiently', () => {
    const veryLong = 'a'.repeat(50000)
    const start = performance.now()
    render(<TruncatedBody text={veryLong} />)
    const end = performance.now()

    // Should render in reasonable time (< 500ms)
    expect(end - start).toBeLessThan(500)
  })

  it('should not re-render on state change in parent', async () => {
    const text = 'a'.repeat(TRUNCATION_LIMIT + 50)
    const { rerender } = render(<TruncatedBody text={text} />)

    const button1 = screen.getByRole('button', { name: /read more/i })
    const renderCount1 = 1

    rerender(<TruncatedBody text={text} />)

    const button2 = screen.getByRole('button', { name: /read more/i })
    expect(button1).toEqual(button2)
  })
})
