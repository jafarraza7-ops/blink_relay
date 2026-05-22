import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { filesApi } from '@/lib/api'
import type { Attachment } from '@/lib/types'

export const fileKeys = {
  all: (requestId: string) => ['files', requestId] as const,
}

export function useFiles(requestId: string) {
  return useQuery({
    queryKey: fileKeys.all(requestId),
    queryFn: () => filesApi.list(requestId),
    enabled: !!requestId,
  })
}

export function useUploadFile(requestId: string) {
  const queryClient = useQueryClient()
  return useMutation<Attachment, Error, File>({
    mutationFn: (file) => filesApi.upload(requestId, file),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: fileKeys.all(requestId) })
    },
  })
}
