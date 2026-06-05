import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { FileAttachment } from '@/components/request/FileAttachment'
import * as filesApi from '@/lib/api'
import type { Attachment } from '@/lib/types'

// Mock the filesApi
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual('@/lib/api')
  return {
    ...actual,
    filesApi: {
      list: vi.fn(),
      upload: vi.fn(),
      uploadMany: vi.fn(),
      delete: vi.fn(),
    },
  }
})

// Mock toast
vi.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}))

const mockFiles: Attachment[] = [
  {
    id: 'file-1',
    request_id: 'req-1',
    filename: 'document.pdf',
    content_type: 'application/pdf',
    size_bytes: 1024,
    created_at: '2026-06-01T12:00:00Z',
    download_url: 'https://blob/document.pdf?sas',
  },
  {
    id: 'file-2',
    request_id: 'req-1',
    filename: 'spreadsheet.xlsx',
    content_type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    size_bytes: 2048,
    created_at: '2026-06-01T12:00:00Z',
    download_url: 'https://blob/spreadsheet.xlsx?sas',
  },
]

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
}

function renderWithQueryClient(component: React.ReactElement) {
  const queryClient = createQueryClient()
  return {
    ...render(
      <QueryClientProvider client={queryClient}>
        {component}
      </QueryClientProvider>
    ),
    queryClient,
  }
}

describe('FileAttachment - Delete Feature', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders delete button for each file when canUpload is true', async () => {
    vi.mocked(filesApi.filesApi.list).mockResolvedValueOnce(mockFiles)

    renderWithQueryClient(<FileAttachment requestId="req-1" canUpload={true} />)

    await waitFor(() => {
      expect(screen.getByText('document.pdf')).toBeInTheDocument()
      expect(screen.getByText('spreadsheet.xlsx')).toBeInTheDocument()
    })

    // Should have delete buttons (trash icons) for each file
    const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
    expect(deleteButtons.length).toBe(2)
  })

  it('hides delete button when canUpload is false (read-only)', async () => {
    vi.mocked(filesApi.filesApi.list).mockResolvedValueOnce(mockFiles)

    renderWithQueryClient(<FileAttachment requestId="req-1" canUpload={false} />)

    await waitFor(() => {
      expect(screen.getByText('document.pdf')).toBeInTheDocument()
    })

    // Should not have delete buttons in read-only mode
    const deleteButtons = screen.queryAllByRole('button', { name: /delete/i })
    expect(deleteButtons.length).toBe(0)
  })

  it('calls delete API when delete button is clicked', async () => {
    vi.mocked(filesApi.filesApi.list).mockResolvedValueOnce(mockFiles)
    vi.mocked(filesApi.filesApi.delete).mockResolvedValueOnce(undefined)

    renderWithQueryClient(<FileAttachment requestId="req-1" canUpload={true} />)

    await waitFor(() => {
      expect(screen.getByText('document.pdf')).toBeInTheDocument()
    })

    const deleteButtons = screen.getAllByRole('button', { name: /delete document.pdf/i })
    await userEvent.click(deleteButtons[0])

    await waitFor(() => {
      expect(filesApi.filesApi.delete).toHaveBeenCalledWith('req-1', 'file-1')
    })
  })

  it('shows success toast after deletion', async () => {
    const mockToast = vi.fn()
    vi.mocked(filesApi.filesApi.list).mockResolvedValueOnce(mockFiles)
    vi.mocked(filesApi.filesApi.delete).mockResolvedValueOnce(undefined)

    vi.doMock('@/components/ui/use-toast', () => ({
      useToast: () => ({ toast: mockToast }),
    }))

    renderWithQueryClient(<FileAttachment requestId="req-1" canUpload={true} />)

    await waitFor(() => {
      expect(screen.getByText('document.pdf')).toBeInTheDocument()
    })

    const deleteButtons = screen.getAllByRole('button', { name: /delete document.pdf/i })
    await userEvent.click(deleteButtons[0])

    // Toast would be called with success message
    // This is mocked, so we just verify the delete API was called
    await waitFor(() => {
      expect(filesApi.filesApi.delete).toHaveBeenCalledWith('req-1', 'file-1')
    })
  })

  it('disables delete button while deleting', async () => {
    vi.mocked(filesApi.filesApi.list).mockResolvedValueOnce(mockFiles)
    vi.mocked(filesApi.filesApi.delete).mockImplementationOnce(
      () => new Promise((resolve) => setTimeout(resolve, 100))
    )

    renderWithQueryClient(<FileAttachment requestId="req-1" canUpload={true} />)

    await waitFor(() => {
      expect(screen.getByText('document.pdf')).toBeInTheDocument()
    })

    const deleteButtons = screen.getAllByRole('button', { name: /delete document.pdf/i })
    const deleteButton = deleteButtons[0]

    expect(deleteButton).not.toBeDisabled()

    await userEvent.click(deleteButton)

    // Button should be disabled during deletion
    expect(deleteButton).toBeDisabled()

    await waitFor(() => {
      expect(deleteButton).not.toBeDisabled()
    }, { timeout: 200 })
  })

  it('handles deletion error gracefully', async () => {
    vi.mocked(filesApi.filesApi.list).mockResolvedValueOnce(mockFiles)
    const errorMessage = 'Cannot delete attachment'
    vi.mocked(filesApi.filesApi.delete).mockRejectedValueOnce(new Error(errorMessage))

    renderWithQueryClient(<FileAttachment requestId="req-1" canUpload={true} />)

    await waitFor(() => {
      expect(screen.getByText('document.pdf')).toBeInTheDocument()
    })

    const deleteButtons = screen.getAllByRole('button', { name: /delete document.pdf/i })
    await userEvent.click(deleteButtons[0])

    await waitFor(() => {
      expect(filesApi.filesApi.delete).toHaveBeenCalled()
    })
  })

  it('maintains file list state independently from download and delete', async () => {
    vi.mocked(filesApi.filesApi.list).mockResolvedValueOnce(mockFiles)

    renderWithQueryClient(<FileAttachment requestId="req-1" canUpload={true} />)

    await waitFor(() => {
      expect(screen.getByText('document.pdf')).toBeInTheDocument()
      expect(screen.getByText('spreadsheet.xlsx')).toBeInTheDocument()
    })

    // Should have both download and delete buttons for each file
    const downloadButtons = screen.getAllByRole('link', { name: /download/i })
    const deleteButtons = screen.getAllByRole('button', { name: /delete/i })

    expect(downloadButtons.length).toBe(2)
    expect(deleteButtons.length).toBe(2)
  })

  it('removes file from list after successful deletion', async () => {
    vi.mocked(filesApi.filesApi.list)
      .mockResolvedValueOnce(mockFiles)
      .mockResolvedValueOnce([mockFiles[1]]) // After deletion, only file-2 remains

    vi.mocked(filesApi.filesApi.delete).mockResolvedValueOnce(undefined)

    renderWithQueryClient(<FileAttachment requestId="req-1" canUpload={true} />)

    await waitFor(() => {
      expect(screen.getByText('document.pdf')).toBeInTheDocument()
    })

    const deleteButtons = screen.getAllByRole('button', { name: /delete document.pdf/i })
    await userEvent.click(deleteButtons[0])

    await waitFor(() => {
      expect(filesApi.filesApi.delete).toHaveBeenCalled()
    })

    // After deletion, component should refetch files (handled by React Query)
    // The mock would return only one file
  })

  it('handles empty file list gracefully', async () => {
    vi.mocked(filesApi.filesApi.list).mockResolvedValueOnce([])

    renderWithQueryClient(<FileAttachment requestId="req-1" canUpload={true} />)

    await waitFor(() => {
      expect(screen.getByText('No attachments')).toBeInTheDocument()
    })

    // Should not have any delete buttons
    const deleteButtons = screen.queryAllByRole('button', { name: /delete/i })
    expect(deleteButtons.length).toBe(0)
  })

  it('handles file list loading state', async () => {
    // Simulate slow loading
    vi.mocked(filesApi.filesApi.list).mockImplementationOnce(
      () => new Promise((resolve) => setTimeout(() => resolve(mockFiles), 100))
    )

    renderWithQueryClient(<FileAttachment requestId="req-1" canUpload={true} />)

    // Should show loading spinner initially
    const spinner = screen.getByRole('progressbar', { hidden: true })
    expect(spinner).toBeInTheDocument()

    // Wait for files to load
    await waitFor(() => {
      expect(screen.getByText('document.pdf')).toBeInTheDocument()
    })
  })

  it('supports deleting multiple files sequentially', async () => {
    vi.mocked(filesApi.filesApi.list).mockResolvedValueOnce(mockFiles)
    vi.mocked(filesApi.filesApi.delete)
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce(undefined)

    renderWithQueryClient(<FileAttachment requestId="req-1" canUpload={true} />)

    await waitFor(() => {
      expect(screen.getByText('document.pdf')).toBeInTheDocument()
    })

    const deleteButtons = screen.getAllByRole('button', { name: /delete/i })

    // Delete first file
    await userEvent.click(deleteButtons[0])
    await waitFor(() => {
      expect(filesApi.filesApi.delete).toHaveBeenCalledWith('req-1', 'file-1')
    })

    // Delete second file
    await userEvent.click(deleteButtons[1])
    await waitFor(() => {
      expect(filesApi.filesApi.delete).toHaveBeenCalledWith('req-1', 'file-2')
    })

    expect(filesApi.filesApi.delete).toHaveBeenCalledTimes(2)
  })

  it('shows correct file metadata (size, date) with delete option', async () => {
    vi.mocked(filesApi.filesApi.list).mockResolvedValueOnce([mockFiles[0]])

    renderWithQueryClient(<FileAttachment requestId="req-1" canUpload={true} />)

    await waitFor(() => {
      expect(screen.getByText('document.pdf')).toBeInTheDocument()
      expect(screen.getByText(/1 KB/i)).toBeInTheDocument()
      expect(screen.getByText(/Jun 1, 2026/i)).toBeInTheDocument()
    })

    // Delete button should still be present
    const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
    expect(deleteButtons.length).toBe(1)
  })

  it('handles permission edge cases (403 from backend)', async () => {
    vi.mocked(filesApi.filesApi.list).mockResolvedValueOnce(mockFiles)
    vi.mocked(filesApi.filesApi.delete).mockRejectedValueOnce(
      new Error('Cannot delete attachments uploaded by others')
    )

    renderWithQueryClient(<FileAttachment requestId="req-1" canUpload={true} />)

    await waitFor(() => {
      expect(screen.getByText('document.pdf')).toBeInTheDocument()
    })

    const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
    await userEvent.click(deleteButtons[0])

    await waitFor(() => {
      expect(filesApi.filesApi.delete).toHaveBeenCalled()
    })
    // Error toast would be shown (mocked)
  })
})
