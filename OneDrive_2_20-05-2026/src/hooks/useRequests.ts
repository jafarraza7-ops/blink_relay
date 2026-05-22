import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { requestsApi, workflowApi, respondApi, threadApi } from '@/lib/api'
import type {
  ApprovePayload,
  BlinkRequest,
  ClarifyPayload,
  Message,
  RejectPayload,
  RequestCreate,
  RequestFilters,
  RequestUpdate,
  RespondPayload,
  StatusUpdatePayload,
} from '@/lib/types'
import { threadKeys } from './useThread'

export const requestKeys = {
  all: ['requests'] as const,
  lists: () => [...requestKeys.all, 'list'] as const,
  list: (filters: RequestFilters) => [...requestKeys.lists(), filters] as const,
  mineLists: () => [...requestKeys.all, 'mine'] as const,
  mineList: (filters: RequestFilters) => [...requestKeys.mineLists(), filters] as const,
  details: () => [...requestKeys.all, 'detail'] as const,
  detail: (id: string) => [...requestKeys.details(), id] as const,
}

export function useRequests(filters: RequestFilters = {}, options: { refetchInterval?: number } = {}) {
  return useQuery({
    queryKey: requestKeys.list(filters),
    queryFn: () => requestsApi.list(filters),
    ...options,
  })
}

export function useMyRequests(filters: RequestFilters = {}, options: { refetchInterval?: number } = {}) {
  return useQuery({
    queryKey: requestKeys.mineList(filters),
    queryFn: () => requestsApi.listMine(filters),
    ...options,
  })
}

export function useRequest(id: string) {
  return useQuery({
    queryKey: requestKeys.detail(id),
    queryFn: () => requestsApi.get(id),
    enabled: !!id,
  })
}

export function useCreateRequest() {
  const queryClient = useQueryClient()
  return useMutation<BlinkRequest, Error, RequestCreate>({
    mutationFn: requestsApi.create,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: requestKeys.lists() })
    },
  })
}

export function useUpdateRequest(requestId: string) {
  const queryClient = useQueryClient()
  return useMutation<BlinkRequest, Error, RequestUpdate>({
    mutationFn: (payload) => requestsApi.update(requestId, payload),
    onSuccess: (req) => {
      // Optimistically update the detail cache so the modal closes onto fresh data
      queryClient.setQueryData(requestKeys.detail(requestId), req)
      void queryClient.invalidateQueries({ queryKey: requestKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: requestKeys.mineLists() })
    },
  })
}

export function useUpdateStatus(requestId: string) {
  const queryClient = useQueryClient()
  return useMutation<{ id: string; status: string }, Error, StatusUpdatePayload>({
    mutationFn: (payload) => workflowApi.updateStatus(requestId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: requestKeys.detail(requestId) })
      void queryClient.invalidateQueries({ queryKey: requestKeys.lists() })
    },
  })
}

export function useApproveRequest(requestId: string) {
  const queryClient = useQueryClient()
  return useMutation<{ id: string; status: string }, Error, ApprovePayload>({
    mutationFn: (payload) => workflowApi.approve(requestId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: requestKeys.detail(requestId) })
      void queryClient.invalidateQueries({ queryKey: requestKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: requestKeys.mineLists() })
      void queryClient.invalidateQueries({ queryKey: threadKeys.all(requestId) })
    },
  })
}

export function useRejectRequest(requestId: string) {
  const queryClient = useQueryClient()
  return useMutation<{ id: string; status: string }, Error, RejectPayload>({
    mutationFn: (payload) => workflowApi.reject(requestId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: requestKeys.detail(requestId) })
      void queryClient.invalidateQueries({ queryKey: requestKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: requestKeys.mineLists() })
      void queryClient.invalidateQueries({ queryKey: threadKeys.all(requestId) })
    },
  })
}

export function useRespondToRequest(requestId: string) {
  const queryClient = useQueryClient()
  return useMutation<{ id: string; status: string }, Error, RespondPayload>({
    mutationFn: (payload) => respondApi.respond(requestId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: requestKeys.detail(requestId) })
    },
  })
}

export function useSendClarification(requestId: string) {
  const queryClient = useQueryClient()
  return useMutation<Message, Error, ClarifyPayload>({
    mutationFn: (payload) => threadApi.clarify(requestId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: requestKeys.detail(requestId) })
      void queryClient.invalidateQueries({ queryKey: threadKeys.all(requestId) })
    },
  })
}
