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
  StatusUpdatePayload,
  User,
} from './types'

// Token getter is injected by useAuth so api.ts has no direct MSAL dependency
let _tokenGetter: (() => Promise<string | null>) | null = null

export function setTokenGetter(getter: () => Promise<string | null>): void {
  _tokenGetter = getter
}

const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL as string | undefined ?? 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
})

apiClient.interceptors.request.use(async (config) => {
  if (_tokenGetter) {
    const token = await _tokenGetter()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
  }
  return config
})

apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    // Normalize error messages for UI consumption
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
    apiClient.get<User>('/api/auth/me').then((r) => r.data),
}

// ── Requests ──────────────────────────────────────────────────────────────────

export const requestsApi = {
  create: (payload: RequestCreate): Promise<BlinkRequest> =>
    apiClient.post<BlinkRequest>('/api/requests', payload).then((r) => r.data),

  list: (filters: RequestFilters = {}): Promise<RequestListResponse> => {
    const params: Record<string, string | number> = {}
    if (filters.pod) params.pod = filters.pod
    if (filters.status) params.status = filters.status
    if (filters.request_type) params.request_type = filters.request_type
    if (filters.priority) params.priority = filters.priority
    if (filters.search) params.search = filters.search
    if (filters.page) params.page = filters.page
    if (filters.page_size) params.page_size = filters.page_size
    return apiClient.get<RequestListResponse>('/api/requests', { params }).then((r) => r.data)
  },

  listMine: (filters: RequestFilters = {}): Promise<RequestListResponse> => {
    const params: Record<string, string | number> = {}
    if (filters.status) params.status = filters.status
    if (filters.request_type) params.request_type = filters.request_type
    if (filters.priority) params.priority = filters.priority
    if (filters.search) params.search = filters.search
    if (filters.page) params.page = filters.page
    if (filters.page_size) params.page_size = filters.page_size
    return apiClient.get<RequestListResponse>('/api/requests/mine', { params }).then((r) => r.data)
  },

  get: (id: string): Promise<BlinkRequest> =>
    apiClient.get<BlinkRequest>(`/api/requests/${id}`).then((r) => r.data),

  update: (id: string, payload: RequestUpdate): Promise<BlinkRequest> =>
    apiClient.patch<BlinkRequest>(`/api/requests/${id}`, payload).then((r) => r.data),
}

// ── Workflow ──────────────────────────────────────────────────────────────────

export const workflowApi = {
  updateStatus: (id: string, payload: StatusUpdatePayload): Promise<{ id: string; status: string }> =>
    apiClient.patch(`/api/requests/${id}/status`, payload).then((r) => r.data),

  approve: (id: string, payload: ApprovePayload = {}): Promise<{ id: string; status: string }> =>
    apiClient.post(`/api/requests/${id}/approve`, payload).then((r) => r.data),

  reject: (id: string, payload: RejectPayload): Promise<{ id: string; status: string }> =>
    apiClient.post(`/api/requests/${id}/reject`, payload).then((r) => r.data),
}

// ── Thread ────────────────────────────────────────────────────────────────────

export const threadApi = {
  list: (requestId: string): Promise<Message[]> =>
    apiClient.get<Message[]>(`/api/requests/${requestId}/messages`).then((r) => r.data),

  post: (requestId: string, payload: MessageCreate): Promise<Message> =>
    apiClient.post<Message>(`/api/requests/${requestId}/messages`, payload).then((r) => r.data),

  clarify: (requestId: string, payload: ClarifyPayload): Promise<Message> =>
    apiClient.post<Message>(`/api/requests/${requestId}/clarify`, payload).then((r) => r.data),
}

// ── Files ─────────────────────────────────────────────────────────────────────

export const filesApi = {
  list: (requestId: string): Promise<Attachment[]> =>
    apiClient.get<Attachment[]>(`/api/requests/${requestId}/files`).then((r) => r.data),

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
      .post<Attachment[]>(`/api/requests/${requestId}/files`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      } as AxiosRequestConfig)
      .then((r) => r.data)
  },
}

// ── Respond (public — no auth required) ──────────────────────────────────────

export const respondApi = {
  respond: (requestId: string, payload: RespondPayload): Promise<{ id: string; status: string }> =>
    apiClient.post(`/api/requests/${requestId}/respond`, payload).then((r) => r.data),
}

export default apiClient
