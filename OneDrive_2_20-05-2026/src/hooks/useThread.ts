import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { threadApi } from '@/lib/api'
import type { Message, MessageCreate } from '@/lib/types'

export const threadKeys = {
  all: (requestId: string) => ['thread', requestId] as const,
}

export function useThread(requestId: string) {
  return useQuery({
    queryKey: threadKeys.all(requestId),
    queryFn: () => threadApi.list(requestId),
    enabled: !!requestId,
    refetchInterval: 30_000,
  })
}

export function usePostMessage(requestId: string) {
  const queryClient = useQueryClient()
  return useMutation<Message, Error, MessageCreate>({
    mutationFn: (payload) => threadApi.post(requestId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: threadKeys.all(requestId) })
    },
  })
}
