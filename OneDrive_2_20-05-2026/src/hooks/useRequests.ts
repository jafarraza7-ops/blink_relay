/**
 * useRequests.ts — React Query hooks for all BlinkRequest data operations.
 *
 * Query key factory (requestKeys) ensures consistent cache scoping:
 *   ['requests', 'list', filters]   → paginated reviewer/PM list
 *   ['requests', 'mine', filters]   → requestor-scoped list
 *   ['requests', 'detail', id]      → single request detail
 *
 * After any mutation that changes a request, we invalidate the relevant
 * list caches so UI counts and tables stay in sync without a manual refresh.
 * The detail cache is also updated/invalidated so open modals reflect the
 * latest state immediately.
 */

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

// ── Query key factory ─────────────────────────────────────────────────────────
// Structured keys let us invalidate by prefix (e.g. all list queries) without
// needing to track exact filter objects at call sites.

export const requestKeys = {
  all: ['requests'] as const,
  lists: () => [...requestKeys.all, 'list'] as const,
  list: (filters: RequestFilters) => [...requestKeys.lists(), filters] as const,
  mineLists: () => [...requestKeys.all, 'mine'] as const,
  mineList: (filters: RequestFilters) => [...requestKeys.mineLists(), filters] as const,
  details: () => [...requestKeys.all, 'detail'] as const,
  detail: (id: string) => [...requestKeys.details(), id] as const,
}

// ── Queries ───────────────────────────────────────────────────────────────────

/** Reviewer/PM view — all requests, filtered + paginated. */
export function useRequests(filters: RequestFilters = {}, options: { refetchInterval?: number } = {}) {
  return useQuery({
    queryKey: requestKeys.list(filters),
    queryFn: () => requestsApi.list(filters),
    ...options,
  })
}

/** Requestor view — only requests submitted by the current user. */
export function useMyRequests(filters: RequestFilters = {}, options: { refetchInterval?: number } = {}) {
  return useQuery({
    queryKey: requestKeys.mineList(filters),
    queryFn: () => requestsApi.listMine(filters),
    ...options,
  })
}

/** Single request detail — disabled until `id` is available (avoids 404 on mount). */
export function useRequest(id: string) {
  return useQuery({
    queryKey: requestKeys.detail(id),
    queryFn: () => requestsApi.get(id),
    enabled: !!id,
  })
}

export function useSimilarRequests(id: string | null) {
  return useQuery({
    queryKey: [...requestKeys.detail(id ?? ''), 'similar'],
    queryFn: () => requestsApi.getSimilar(id!),
    enabled: !!id,
  })
}

// ── Mutations ─────────────────────────────────────────────────────────────────

export function useCreateRequest() {
  const queryClient = useQueryClient()
  return useMutation<BlinkRequest, Error, RequestCreate>({
    mutationFn: requestsApi.create,
    onSuccess: () => {
      // New request added — refresh all list views (dashboard, mine)
      void queryClient.invalidateQueries({ queryKey: requestKeys.lists() })
    },
  })
}

export function useUpdateRequest(requestId: string) {
  const queryClient = useQueryClient()
  return useMutation<BlinkRequest, Error, RequestUpdate>({
    mutationFn: (payload) => requestsApi.update(requestId, payload),
    onSuccess: (req) => {
      // Directly set the detail cache with the response so the UI reflects
      // changes immediately without waiting for an extra refetch.
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
      // Invalidate detail + lists + thread: status change may add a system message
      void queryClient.invalidateQueries({ queryKey: requestKeys.detail(requestId) })
      void queryClient.invalidateQueries({ queryKey: requestKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: threadKeys.all(requestId) })
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

/** Uses /reject endpoint (not /status) so the backend fires the rejection email. */
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

export function useCancelRequest(requestId: string) {
  const queryClient = useQueryClient()
  return useMutation<{ id: string; status: string }, Error>({
    mutationFn: () => workflowApi.cancel(requestId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: requestKeys.detail(requestId) })
      void queryClient.invalidateQueries({ queryKey: requestKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: requestKeys.mineLists() })
      void queryClient.invalidateQueries({ queryKey: threadKeys.all(requestId) })
    },
  })
}

/**
 * Used on the public /respond/:id page — no reviewer auth required.
 * Only invalidates the detail cache; the requestor has no list view.
 */
export function useRespondToRequest(requestId: string) {
  const queryClient = useQueryClient()
  return useMutation<{ id: string; status: string }, Error, RespondPayload>({
    mutationFn: (payload) => respondApi.respond(requestId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: requestKeys.detail(requestId) })
    },
  })
}

/** Reviewer sends a clarification request, transitioning status to AwaitingInfo. */
export function useSendClarification(requestId: string) {
  const queryClient = useQueryClient()
  return useMutation<Message, Error, ClarifyPayload>({
    mutationFn: (payload) => threadApi.clarify(requestId, payload),
    onSuccess: () => {
      // Refresh detail (status change) + thread (new system message added)
      void queryClient.invalidateQueries({ queryKey: requestKeys.detail(requestId) })
      void queryClient.invalidateQueries({ queryKey: threadKeys.all(requestId) })
    },
  })
}
