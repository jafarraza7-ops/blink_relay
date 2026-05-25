import type { Pod, Region, RequestStatus, RequestType, Role, Priority } from './types'

export const PODS = ['Charger', 'Driver', 'Revenue', 'Data', 'DevOps', 'Denali'] as const satisfies readonly Pod[]

export const REQUEST_TYPES: RequestType[] = ['Feature', 'Defect']

export const PRIORITIES: Priority[] = ['Critical', 'High', 'Medium', 'Low']

export const REGIONS: Region[] = ['NA', 'UK', 'EU']

export const REGION_LABELS: Record<Region, string> = {
  NA: 'North America',
  UK: 'United Kingdom',
  EU: 'Europe',
}

export const REQUEST_STATUSES: RequestStatus[] = [
  'Submitted',
  'InReview',
  'AwaitingInfo',
  'InfoReceived',
  'Approved',
  'Rejected',
  'InProgress',
  'Completed',
  'Closed',
]

export const STATUS_LABELS: Record<RequestStatus, string> = {
  Submitted: 'Submitted',
  InReview: 'In Review',
  AwaitingInfo: 'Awaiting Info',
  InfoReceived: 'Info Received',
  Approved: 'Approved',
  Rejected: 'Rejected',
  InProgress: 'In Progress',
  Completed: 'Completed',
  Closed: 'Closed',
}

export const STATUS_COLORS: Record<RequestStatus, string> = {
  Submitted: 'bg-slate-100 text-slate-700 border-slate-200',
  InReview: 'bg-blue-100 text-blue-700 border-blue-200',
  AwaitingInfo: 'bg-amber-100 text-amber-700 border-amber-200',
  InfoReceived: 'bg-cyan-100 text-cyan-700 border-cyan-200',
  Approved: 'bg-green-100 text-green-700 border-green-200',
  Rejected: 'bg-red-100 text-red-700 border-red-200',
  InProgress: 'bg-violet-100 text-violet-700 border-violet-200',
  Completed: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  Closed: 'bg-gray-100 text-gray-500 border-gray-200',
}

export const POD_COLORS: Record<Pod, string> = {
  Charger: 'bg-orange-100 text-orange-700 border-orange-200',
  Driver: 'bg-sky-100 text-sky-700 border-sky-200',
  Revenue: 'bg-green-100 text-green-700 border-green-200',
  Data: 'bg-purple-100 text-purple-700 border-purple-200',
  DevOps: 'bg-zinc-100 text-zinc-700 border-zinc-200',
  Denali: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  Unknown: 'bg-gray-100 text-gray-500 border-gray-200',
}

export const PRIORITY_COLORS: Record<Priority, string> = {
  Critical: 'bg-red-100 text-red-700 border-red-200',
  High: 'bg-orange-100 text-orange-700 border-orange-200',
  Medium: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  Low: 'bg-slate-100 text-slate-600 border-slate-200',
}

export const TYPE_COLORS: Record<RequestType, string> = {
  Feature: 'bg-blue-100 text-blue-700 border-blue-200',
  Defect: 'bg-rose-100 text-rose-700 border-rose-200',
}

export const ALLOWED_TRANSITIONS: Record<RequestStatus, RequestStatus[]> = {
  Submitted:    ['InReview', 'AwaitingInfo', 'Approved', 'Rejected'],
  InReview:     ['AwaitingInfo', 'Approved', 'Rejected', 'InProgress'],
  AwaitingInfo: ['InfoReceived'],
  InfoReceived: ['InReview', 'Approved'],
  Approved:     ['InReview', 'InProgress', 'Rejected'],
  Rejected:     [],
  InProgress:   ['Completed'],
  Completed:    ['Closed'],
  Closed:       [],
}

export const REVIEWER_ROLES: Role[] = ['PodReviewer', 'ProductManager', 'Admin']
export const PM_ROLES: Role[] = ['ProductManager', 'Admin']

export const MAX_FILE_SIZE_MB = 25
export const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
export const ALLOWED_FILE_TYPES = [
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/plain',
  'text/csv',
]

export const POD_DESCRIPTIONS: Record<Pod, string> = {
  Charger: 'Hardware, firmware, and charger network',
  Driver: 'Driver-facing apps and experience',
  Revenue: 'Billing, payments, and revenue systems',
  Data: 'Analytics, reporting, and data pipelines',
  DevOps: 'Infrastructure, CI/CD, and platform',
  Denali: 'Enterprise and fleet solutions',
  Unknown: 'Not yet classified',
}
