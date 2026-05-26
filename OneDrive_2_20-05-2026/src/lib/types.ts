export type Region = 'NA' | 'UK' | 'EU'
export type Pod = 'Charger' | 'Driver' | 'Revenue' | 'Data' | 'DevOps' | 'Denali' | 'Unknown'
export type RequestType = 'Feature' | 'Defect'
export type Priority = 'Critical' | 'High' | 'Medium' | 'Low'
export type RequestStatus =
  | 'Submitted'
  | 'InReview'
  | 'AwaitingInfo'
  | 'InfoReceived'
  | 'Approved'
  | 'Rejected'
  | 'InProgress'
  | 'Completed'
  | 'Closed'
export type Role = 'Requestor' | 'PodReviewer' | 'ProductManager' | 'Admin' | 'ReadOnly'

export interface User {
  oid: string
  email: string
  name: string
  roles: Role[]
}

export interface BlinkRequest {
  id: string
  reference_id: string | null
  title: string
  request_type: RequestType
  pod: Pod
  region: Region[]
  priority: Priority
  status: RequestStatus
  business_problem: string
  expected_outcome: string | null
  steps_to_reproduce: string | null
  affected_area: string
  additional_context: string | null
  submitter_email: string
  submitter_name: string
  jira_ticket_key: string | null
  jira_ticket_url: string | null
  jsm_ticket_key: string | null
  jsm_ticket_url: string | null
  jsm_resolved_at: string | null
  created_at: string
  updated_at: string
}

export interface RequestCreate {
  title: string
  request_type: RequestType
  pod: Pod
  region: Region[]
  priority: Priority
  business_problem: string
  expected_outcome?: string
  steps_to_reproduce?: string
  affected_area: string
  additional_context?: string
}

export interface RequestUpdate {
  title?: string
  priority?: Priority
  region?: Region[]
  business_problem?: string
  expected_outcome?: string
  steps_to_reproduce?: string
  affected_area?: string
  additional_context?: string
}

export interface RequestListResponse {
  items: BlinkRequest[]
  total: number
  page: number
  page_size: number
}

export type MessageType = 'comment' | 'clarification_question' | 'clarification_response' | 'status_change'

export interface Message {
  id: string
  request_id: string
  author_email: string
  author_name: string
  body: string
  is_internal: boolean
  message_type: MessageType
  created_at: string
}

export interface MessageCreate {
  body: string
  is_internal?: boolean
}

export interface ClarifyPayload {
  body: string
}

export interface Attachment {
  id: string
  request_id: string
  filename: string
  content_type: string
  size_bytes: number
  created_at: string
  download_url: string | null
}

export interface RequestFilters {
  pod?: Pod
  status?: RequestStatus
  request_type?: RequestType
  priority?: Priority
  search?: string
  page?: number
  page_size?: number
}

export interface ApprovePayload {
  jira_project_override?: string
  epic_title?: string
}

export interface RejectPayload {
  reason: string
  comment?: string
}

export interface StatusUpdatePayload {
  status: RequestStatus
  comment?: string
}

export interface RespondPayload {
  body: string
  responder_name?: string
  responder_email?: string
}
