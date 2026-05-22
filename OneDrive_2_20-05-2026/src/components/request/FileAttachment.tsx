import { useRef } from 'react'
import { Download, File, Paperclip, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useFiles, useUploadFile } from '@/hooks/useFiles'
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
  const { toast } = useToast()
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!ALLOWED_FILE_TYPES.includes(file.type)) {
      toast({ title: 'Unsupported file type', description: `Allowed: PDF, images, Word, Excel, CSV, text`, variant: 'destructive' })
      return
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      toast({ title: 'File too large', description: 'Maximum file size is 25 MB', variant: 'destructive' })
      return
    }

    uploadFile(file, {
      onSuccess: () => toast({ title: 'File uploaded successfully' }),
      onError: (err) => toast({ title: 'Upload failed', description: err.message, variant: 'destructive' }),
    })
    // Reset input so the same file can be re-selected
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
              {file.download_url && (
                <Button asChild variant="ghost" size="icon" className="h-7 w-7 shrink-0">
                  <a href={file.download_url} target="_blank" rel="noopener noreferrer" download={file.filename}>
                    <Download className="h-4 w-4" />
                    <span className="sr-only">Download {file.filename}</span>
                  </a>
                </Button>
              )}
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
                Attach file
              </>
            )}
          </Button>
          <p className="mt-1 text-xs text-muted-foreground">PDF, images, Word, Excel, CSV · Max 25 MB</p>
        </div>
      )}
    </div>
  )
}
