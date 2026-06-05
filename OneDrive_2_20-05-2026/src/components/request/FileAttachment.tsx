import { useRef } from 'react'
import { Download, File, Paperclip, Trash2, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useFiles, useUploadFile, useDeleteFile } from '@/hooks/useFiles'
import { useToast } from '@/components/ui/use-toast'
import { formatBytes, formatDate } from '@/lib/utils'
import { ALLOWED_FILE_TYPES, MAX_FILE_SIZE_BYTES } from '@/lib/constants'

interface FileAttachmentProps {
  requestId: string
  canUpload?: boolean
}

export function FileAttachment({ requestId, canUpload = true }: FileAttachmentProps) {
  const { data: files = [], isLoading } = useFiles(requestId)
  const { mutate: uploadFile, isPending } = useUploadFile(requestId)
  const { mutate: deleteFile, isPending: isDeleting } = useDeleteFile(requestId)
  const { toast } = useToast()
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDelete = (attachmentId: string, filename: string) => {
    deleteFile(attachmentId, {
      onSuccess: () => {
        toast({
          title: 'Attachment deleted',
          description: `${filename} has been removed`,
        })
      },
      onError: (err) => {
        toast({
          title: 'Delete failed',
          description: err.message,
          variant: 'destructive',
        })
      },
    })
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files
    if (!selectedFiles || selectedFiles.length === 0) return

    // Validate all files before uploading
    const filesToUpload: File[] = []

    for (let i = 0; i < selectedFiles.length; i++) {
      const file = selectedFiles[i]

      if (!ALLOWED_FILE_TYPES.includes(file.type)) {
        toast({
          title: 'Unsupported file type',
          description: `${file.name}: Allowed types are PDF, images, Word, Excel, CSV, text`,
          variant: 'destructive'
        })
        continue
      }

      if (file.size > MAX_FILE_SIZE_BYTES) {
        toast({
          title: 'File too large',
          description: `${file.name}: Maximum file size is 25 MB`,
          variant: 'destructive'
        })
        continue
      }

      filesToUpload.push(file)
    }

    if (filesToUpload.length === 0) return

    uploadFile(filesToUpload, {
      onSuccess: (uploadedCount) => {
        toast({
          title: 'Files uploaded successfully',
          description: `${uploadedCount} file${uploadedCount !== 1 ? 's' : ''} uploaded`
        })
      },
      onError: (err) => toast({ title: 'Upload failed', description: err.message, variant: 'destructive' }),
    })

    // Reset input so the same files can be re-selected
    if (inputRef.current) inputRef.current.value = ''
  }

  if (isLoading) {
    return <div className="flex items-center justify-center py-4"><div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" /></div>
  }

  return (
    <div className="space-y-3">
      {/* File list */}
      {files.length === 0 ? (
        <p className="text-sm text-muted-foreground py-2">No attachments</p>
      ) : (
        <ul className="space-y-2">
          {files.map((file) => (
            <li key={file.id} className="flex items-center gap-3 rounded-md border px-3 py-2 text-sm">
              <File className="h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="flex-1 min-w-0">
                <p className="truncate font-medium">{file.filename}</p>
                <p className="text-xs text-muted-foreground">
                  {formatBytes(file.size_bytes)} · {formatDate(file.created_at)}
                </p>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                {file.download_url && (
                  <Button asChild variant="ghost" size="icon" className="h-7 w-7">
                    <a href={file.download_url} target="_blank" rel="noopener noreferrer" download={file.filename}>
                      <Download className="h-4 w-4" />
                      <span className="sr-only">Download {file.filename}</span>
                    </a>
                  </Button>
                )}
                {/* FEATURE: Delete button for requestors to remove wrong attachments */}
                {canUpload && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-destructive hover:text-destructive hover:bg-destructive/10"
                    disabled={isDeleting}
                    onClick={() => handleDelete(file.id, file.filename)}
                  >
                    <Trash2 className="h-4 w-4" />
                    <span className="sr-only">Delete {file.filename}</span>
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Upload */}
      {canUpload && (
        <div>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ALLOWED_FILE_TYPES.join(',')}
            onChange={handleFileChange}
            className="sr-only"
            id="file-upload"
          />
          <Button
            variant="outline"
            size="sm"
            disabled={isPending}
            onClick={() => inputRef.current?.click()}
            className="gap-2"
          >
            {isPending ? (
              <>
                <Upload className="h-4 w-4 animate-bounce" />
                Uploading…
              </>
            ) : (
              <>
                <Paperclip className="h-4 w-4" />
                Attach files
              </>
            )}
          </Button>
          <p className="mt-1 text-xs text-muted-foreground">Select multiple files · PDF, images, Word, Excel, CSV · Max 25 MB each</p>
        </div>
      )}
    </div>
  )
}
