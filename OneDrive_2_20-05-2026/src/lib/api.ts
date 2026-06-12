/**
 * api.ts — Centralized Axios client for all Blink Relay backend calls.
 *
 * Architecture note: this module has zero MSAL/auth imports by design.
 * The token getter is injected at runtime by useAuth (via setTokenGetter),
 * which keeps this file independently testable and free of browser-auth
 * side-effects.
 *
 * API surface is grouped into five namespaces:
 *   authApi     — current user identity (/api/auth/me)
 *   requestsApi — CRUD + listing for BlinkRequest records
 *   workflowApi — status-transition endpoints (approve, reject, updateStatus)
 *   threadApi   — per-request message thread + clarification flow
 *   filesApi    — attachment upload / listing
 *   respondApi  — public (unauthenticated) response endpoint for requestors
 */

import axios, { type AxiosInstance, type AxiosRequestConfig } from 'axios'
import type {
  ApprovePayload,
  Attachment,
  BlinkRequest,
  ClarifyPayload,
  Message,
  MessageCreate,
  RejectPayload,
  RequestCreate,
  RequestFilters,
  RequestListResponse,
  RequestUpdate,
  RespondPayload,
  SimilarRequest,
  StatusUpdatePayload,
  TimelineEvent,
  User,
} from './types'

// ── Centralized API Endpoint Routes ───────────────────────────────────────────
/**
 * Centralized API endpoint routes.
 * Using a constant ensures all route changes are made in one place,
 * preventing typos and making it easier to refactor endpoints.
 */
const API_ROUTES = {
  AUTH: '/auth/me',
  REQUESTS: '/requests',
  REQUESTS_MINE: '/requests/mine',
  REQUEST_DETAIL: (id: string) => `/requests/${id}`,
  REQUEST_SIMILAR: (id: string) => `/requests/${id}/similar`,
  REQUEST_TIMELINE: (id: string) => `/requests/${id}/timeline`,
  REQUEST_STATUS: (id: string) => `/requests/${id}/status`,
  REQUEST_APPROVE: (id: string) => `/requests/${id}/approve`,
  REQUEST_REJECT: (id: string) => `/requests/${id}/reject`,
  REQUEST_CLAIM: (id: string) => `/requests/${id}/claim`,
  REQUEST_UNCLAIM: (id: string) => `/requests/${id}/unclaim`,
  REQUEST_CANCEL: (id: string) => `/requests/${id}/cancel`,
  REQUEST_EXPORT: '/requests/export',
  REQUEST_MESSAGES: (id: string) => `/requests/${id}/messages`,
  REQUEST_CLARIFY: (id: string) => `/requests/${id}/clarify`,
  REQUEST_FILES: (id: string) => `/requests/${id}/files`,
  REQUEST_FILE_DELETE: (id: string, fileId: string) => `/requests/${id}/files/${fileId}`,
  ESCALATIONS_SUMMARY: '/requests/escalations/summary',
  USERS: '/users',
  RESPOND: (id: string) => `/requests/${id}/respond`,
} as const

export type ApiRoute = typeof API_ROUTES

// ── Token injection ───────────────────────────────────────────────────────────

// Token getter is injected by useAuth so api.ts has no direct MSAL dependency.
// In SKIP_AUTH mode useAuth injects a static dev token instead.
let _tokenGetter: (() => Promise<string | null>) | null = null

/** Called once by useAuth on mount to wire up Bearer-token acquisition. */
export function setTokenGetter(getter: () => Promise<string | null>): void {
  _tokenGetter = getter
}

// ── Axios instance ────────────────────────────────────────────────────────────

const apiClient: AxiosInstance = axios.create({
  baseURL: process.env.VITE_API_URL || 'http://localhost:8000/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
  withCredentials: true,
})

// Store CSRF token from response headers
let _csrfToken: string | null = null

// Attach the Bearer token to every request via the injected getter.
// acquireTokenSilent will refresh the MSAL token automatically; if it can't,
// it falls back to a redirect so the user re-authenticates.
apiClient.interceptors.request.use(async (config) => {
  if (_tokenGetter) {
    const token = await _tokenGetter()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
  }

  // Attach CSRF token for state-changing requests
  if (_csrfToken && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(config.method?.toUpperCase() || '')) {
    config.headers['X-CSRF-Token'] = _csrfToken
  }

  return config
})

apiClient.interceptors.response.use(
  (res) => {
    // Capture CSRF token from response header
    const csrfToken = res.headers['x-csrf-token']
    if (csrfToken) {
      _csrfToken = csrfToken
    }
    return res
  },
  (error) => {
    // Normalize FastAPI's `detail` field and generic messages into a single
    // Error so callers only need to handle one shape.
    const message: string =
      error.response?.data?.detail ??
      error.response?.data?.message ??
      error.message ??
      'An unexpected error occurred'
    return Promise.reject(new Error(message))
  }
)

// ── Auth ──────────────────────────────────────────────────────────────────────

export const authApi = {
  me: (): Promise<User> =>
    apiClient.get<User>(API_ROUTES.AUTH).then((r) => r.data),
}

// ── Requests ──────────────────────────────────────────────────────────────────

export const requestsApi = {
  create: (payload: RequestCreate): Promise<BlinkRequest> =>
    apiClient.post<BlinkRequest>(API_ROUTES.REQUESTS, payload).then((r) => r.data),

  /**
   * Fetch a paginated list of all requests (reviewer/PM view).
   * Only scalar filters are serialized here — multi-value filtering
   * (status[], pod[], priority[], type[]) is handled client-side in
   * DashboardPage after fetching page_size=500.
   */
  list: (filters: RequestFilters = {}): Promise<RequestListResponse> => {
    const params: Record<string, string | number> = {}
    if (filters.pod) params.pod = filters.pod
    if (filters.status) params.status = filters.status
    if (filters.request_type) params.request_type = filters.request_type
    if (filters.priority) params.priority = filters.priority
    if (filters.search) params.search = filters.search
    if (filters.page) params.page = filters.page
    if (filters.page_size) params.page_size = filters.page_size
    return apiClient.get<RequestListResponse>(API_ROUTES.REQUESTS, { params }).then((r) => r.data)
  },

  /** Requestor-scoped list — only returns requests owned by the current user. */
  listMine: (filters: RequestFilters = {}): Promise<RequestListResponse> => {
    const params: Record<string, string | number> = {}
    if (filters.status) params.status = filters.status
    if (filters.request_type) params.request_type = filters.request_type
    if (filters.priority) params.priority = filters.priority
    if (filters.search) params.search = filters.search
    if (filters.page) params.page = filters.page
    if (filters.page_size) params.page_size = filters.page_size
    return apiClient.get<RequestListResponse>(API_ROUTES.REQUESTS_MINE, { params }).then((r) => r.data)
  },

  /**
   * Server-side CSV export endpoint — used as a fallback / alternative.
   * Note: DashboardPage generates its CSV client-side from the already-filtered
   * array so that multi-select filters (which can't be passed as single query
   * params) are correctly reflected in the download.
   */
  exportCsv: (filters: Omit<RequestFilters, 'page' | 'page_size'> = {}): Promise<Blob> => {
    const params: Record<string, string> = {}
    if (filters.pod) params.pod = filters.pod
    if (filters.status) params.status = filters.status
    if (filters.request_type) params.request_type = filters.request_type
    if (filters.priority) params.priority = filters.priority
    if (filters.search) params.search = filters.search
    return apiClient
      .get(API_ROUTES.REQUEST_EXPORT, { params, responseType: 'blob' })
      .then((r) => r.data as Blob)
  },

  get: (id: string): Promise<BlinkRequest> =>
    apiClient.get<BlinkRequest>(API_ROUTES.REQUEST_DETAIL(id)).then((r) => r.data),

  getSimilar: (id: string, limit: number = 5): Promise<SimilarRequest[]> =>
    apiClient.get<SimilarRequest[]>(API_ROUTES.REQUEST_SIMILAR(id), { params: { limit } }).then((r) => r.data),

  getTimeline: (id: string): Promise<TimelineEvent[]> =>
    apiClient.get<TimelineEvent[]>(API_ROUTES.REQUEST_TIMELINE(id)).then((r) => r.data),

  getEscalationSummary: (): Promise<{ total: number; by_pod: Record<string, number>; by_priority: Record<string, number>; oldest_days: number | null }> =>
    apiClient.get(API_ROUTES.ESCALATIONS_SUMMARY).then((r) => r.data),

  update: (id: string, payload: RequestUpdate): Promise<BlinkRequest> =>
    apiClient.patch<BlinkRequest>(API_ROUTES.REQUEST_DETAIL(id), payload).then((r) => r.data),
}

// ── Workflow ──────────────────────────────────────────────────────────────────
// Dedicated endpoints for status transitions so the backend can apply
// validation rules, trigger email notifications, and create JSM/Jira
// tickets as side-effects — PATCH /status is for generic moves, while
// /approve and /reject have their own endpoints for richer payloads.

export const workflowApi = {
  updateStatus: (id: string, payload: StatusUpdatePayload): Promise<{ id: string; status: string }> =>
    apiClient.patch(API_ROUTES.REQUEST_STATUS(id), payload).then((r) => r.data),

  approve: (id: string, payload: ApprovePayload = {}): Promise<{ id: string; status: string }> =>
    apiClient.post(API_ROUTES.REQUEST_APPROVE(id), payload).then((r) => r.data),

  /** Uses /reject (not /status) so the backend can fire the rejection email notification. */
  reject: (id: string, payload: RejectPayload): Promise<{ id: string; status: string }> =>
    apiClient.post(API_ROUTES.REQUEST_REJECT(id), payload).then((r) => r.data),

  /** Claim a request — mark that this PM is working on it. */
  claimRequest: (id: string): Promise<{ id: string; claimed_by: string; claimed_at: string }> =>
    apiClient.post(API_ROUTES.REQUEST_CLAIM(id), {}).then((r) => r.data),

  /** Unclaim a request — release it so others can work on it. */
  unclaimRequest: (id: string): Promise<{ id: string; claimed_by: null; message: string }> =>
    apiClient.post(API_ROUTES.REQUEST_UNCLAIM(id), {}).then((r) => r.data),

  /** Cancel a request — only available for requestors on their own requests. */
  cancel: (id: string): Promise<{ id: string; status: string }> =>
    apiClient.post(API_ROUTES.REQUEST_CANCEL(id), {}).then((r) => r.data),
}

// ── Thread ────────────────────────────────────────────────────────────────────

export const threadApi = {
  list: (requestId: string): Promise<Message[]> =>
    apiClient.get<Message[]>(API_ROUTES.REQUEST_MESSAGES(requestId)).then((r) => r.data),

  post: (requestId: string, payload: MessageCreate): Promise<Message> =>
    apiClient.post<Message>(API_ROUTES.REQUEST_MESSAGES(requestId), payload).then((r) => r.data),

  clarify: (requestId: string, payload: ClarifyPayload): Promise<Message> =>
    apiClient.post<Message>(API_ROUTES.REQUEST_CLARIFY(requestId), payload).then((r) => r.data),
}

// ── Files ─────────────────────────────────────────────────────────────────────

export const filesApi = {
  list: (requestId: string): Promise<Attachment[]> =>
    apiClient.get<Attachment[]>(API_ROUTES.REQUEST_FILES(requestId)).then((r) => r.data),

  upload: (requestId: string, file: File): Promise<Attachment> =>
    filesApi.uploadMany(requestId, [file]).then((arr) => arr[0]),

  uploadMany: (requestId: string, files: File[]): Promise<Attachment[]> => {
    const formData = new FormData()
    // Backend expects a list under the field name "files" (multipart spec
    // for repeated fields → list[UploadFile])
    for (const file of files) {
      formData.append('files', file)
    }
    return apiClient
      .post<Attachment[]>(API_ROUTES.REQUEST_FILES(requestId), formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      } as AxiosRequestConfig)
      .then((r) => r.data)
  },

  // FEATURE: Allow requestors to delete incorrectly uploaded attachments
  delete: (requestId: string, attachmentId: string): Promise<void> =>
    apiClient.delete(API_ROUTES.REQUEST_FILE_DELETE(requestId, attachmentId)).then(() => undefined),
}


// ── Users ─────────────────────────────────────────────────────────────────────

export const usersApi = {
  list: (q?: string): Promise<Array<{ oid: string; email: string; display_name: string }>> => {
    const params: Record<string, string> = {}
    if (q) params.q = q
    return apiClient.get(API_ROUTES.USERS, { params }).then((r) => r.data)
  },
}
// ── Respond (public — no auth required) ──────────────────────────────────────
// Requestors follow an emailed link to /respond/:id without logging in.
// The backend validates the request belongs to their email; no Bearer token needed.

export const respondApi = {
  respond: (requestId: string, payload: RespondPayload): Promise<{ id: string; status: string }> =>
    apiClient.post(API_ROUTES.RESPOND(requestId), payload).then((r) => r.data),
}

export default apiClient
