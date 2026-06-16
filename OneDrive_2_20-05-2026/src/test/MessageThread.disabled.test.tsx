import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider, QueryClient } from '@tanstack/react-query'
import { MessageThread } from '@/components/request/MessageThread'
import * as useThreadHook from '@/hooks/useThread'
import * as useAuthHook from '@/hooks/useAuth'

vi.mock('@/hooks/useThread')
vi.mock('@/hooks/useAuth')
vi.mock('@/hooks/usersApi', () => ({
  usersApi: {
    list: vi.fn().mockResolvedValue([]),
  },
}))

const mockMessages = [
  {
    id: 'msg-1',
    request_id: 'req-1',
    author_oid: 'user-1',
    author_name: 'John Doe',
    body: 'Test message',
    is_internal: false,
    message_type: 'comment',
    mentions: [],
    created_at: '2026-06-16T10:00:00Z',
  },
]

describe('MessageThread - Disabled State', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient()
    vi.clearAllMocks()

    vi.mocked(useThreadHook.useThread).mockReturnValue({
      data: mockMessages,
      isLoading: false,
      isError: false,
    } as any)

    vi.mocked(useThreadHook.usePostMessage).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as any)

    vi.mocked(useAuthHook.useAuth).mockReturnValue({
      user: {
        oid: 'user-1',
        email: 'user@example.com',
        name: 'User Name',
        roles: ['ProductManager'],
      },
      isPM: true,
    } as any)
  })

  const renderMessageThread = (disabled = false) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <MessageThread requestId="req-1" disabled={disabled} />
      </QueryClientProvider>
    )
  }

  describe('When disabled={false}', () => {
    it('renders message input textarea', () => {
      renderMessageThread(false)
      const textarea = screen.getByPlaceholderText(/write a message/i)
      expect(textarea).toBeInTheDocument()
    })

    it('renders send button', () => {
      renderMessageThread(false)
      const sendButton = screen.getByRole('button', { name: /send/i })
      expect(sendButton).toBeInTheDocument()
    })

    it('renders attach files button', () => {
      renderMessageThread(false)
      const internalCheckbox = screen.getByLabelText(/visible to requestor/i)
      expect(internalCheckbox).toBeInTheDocument()
    })

    it('textarea is enabled and accepts input', async () => {
      const user = userEvent.setup()
      renderMessageThread(false)

      const textarea = screen.getByPlaceholderText(/write a message/i) as HTMLTextAreaElement
      expect(textarea).not.toBeDisabled()

      await user.type(textarea, 'Test message')
      expect(textarea.value).toBe('Test message')
    })

    it('send button is enabled when textarea has content', async () => {
      const user = userEvent.setup()
      renderMessageThread(false)

      const textarea = screen.getByPlaceholderText(/write a message/i)
      const sendButton = screen.getByRole('button', { name: /send/i })

      expect(sendButton).not.toBeDisabled()

      await user.type(textarea, 'Test message')
      expect(sendButton).not.toBeDisabled()
    })
  })

  describe('When disabled={true}', () => {
    it('does not render message input textarea', () => {
      renderMessageThread(true)
      const textarea = screen.queryByPlaceholderText(/write a message/i)
      expect(textarea).not.toBeInTheDocument()
    })

    it('does not render send button', () => {
      renderMessageThread(true)
      const sendButton = screen.queryByRole('button', { name: /send/i })
      expect(sendButton).not.toBeInTheDocument()
    })

    it('does not render internal note checkbox', () => {
      renderMessageThread(true)
      const internalCheckbox = screen.queryByLabelText(/visible to requestor/i)
      expect(internalCheckbox).not.toBeInTheDocument()
    })

    it('renders read-only message', () => {
      renderMessageThread(true)
      const readOnlyMessage = screen.getByText(/conversation is read-only on finalized requests/i)
      expect(readOnlyMessage).toBeInTheDocument()
    })

    it('still displays existing messages', () => {
      renderMessageThread(true)
      const message = screen.getByText(/test message/i)
      expect(message).toBeInTheDocument()
    })

    it('read-only message has proper styling', () => {
      renderMessageThread(true)
      const readOnlyMessage = screen.getByText(/conversation is read-only on finalized requests/i)
      const container = readOnlyMessage.closest('div')
      expect(container?.className).toContain('text-sm')
      expect(container?.className).toContain('text-muted-foreground')
    })
  })

  describe('Message Display', () => {
    it('displays messages regardless of disabled state', () => {
      const { rerender } = renderMessageThread(false)
      expect(screen.getByText(/test message/i)).toBeInTheDocument()

      rerender(
        <QueryClientProvider client={queryClient}>
          <MessageThread requestId="req-1" disabled={true} />
        </QueryClientProvider>
      )
      expect(screen.getByText(/test message/i)).toBeInTheDocument()
    })
  })

  describe('Default Behavior', () => {
    it('defaults to enabled when disabled prop is not provided', () => {
      render(
        <QueryClientProvider client={queryClient}>
          <MessageThread requestId="req-1" />
        </QueryClientProvider>
      )

      const textarea = screen.getByPlaceholderText(/write a message/i)
      expect(textarea).toBeInTheDocument()

      const sendButton = screen.getByRole('button', { name: /send/i })
      expect(sendButton).toBeInTheDocument()
    })
  })
})
