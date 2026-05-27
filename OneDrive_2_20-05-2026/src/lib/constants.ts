/**
 * constants.ts — App-wide enumerations, display labels, Tailwind color maps,
 * workflow transition rules, and upload constraints.
 *
 * Color map convention (used for status/pod/priority/type badges and filter pills):
 *   *_COLORS        — soft -100 bg / -700 text / -200 border  → resting/inactive state
 *   *_ACTIVE_COLORS — bold -300 bg / -900 text / -500 border  → selected filter pill state
 *
 * Both maps are needed because a single Tailwind class set can't be toggled
 * safely with opacity alone — dark text on a light chip would become unreadable.
 */

import type { Pod, Region, RequestStatus, RequestType, Role, Priority } from './types'

// ── Domain enumerations ───────────────────────────────────────────────────────

export const PODS = ['Charger', 'Driver', 'Revenue', 'Data', 'DevOps', 'Denali'] as const satisfies readonly Pod[]

export const REQUEST_TYPES: RequestType[] = ['Feature', 'Defect']

export const PRIORITIES: Priority[] = ['Critical', 'High', 'Medium', 'Low']

export const REGIONS: Region[] = ['NA', 'UK', 'EU']

export const REGION_LABELS: Record<Region, string> = {
  NA: 'North America',
  UK: 'United Kingdom',
  EU: 'Europe',
}

// Full lifecycle order — used by DashboardPage filter pills and status dropdowns.
// Note: region was migrated from a single string to string[] in migration 007;
// REGIONS here reflects the canonical list post-migration.
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

// ── Display labels ────────────────────────────────────────────────────────────
// CamelCase enum values need human-readable labels for the UI and CSV export.

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

// ── Badge / pill color maps (inactive) ───────────────────────────────────────
// Applied when a filter pill is NOT selected, or on read-only status badges.
// Uses -100 bg + -700 text for low visual weight.

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

// ── Badge / pill color maps (active/selected) ─────────────────────────────────
// Applied when a filter pill IS selected. Uses -300 bg / -900 text / -500 border
// to make the selection visually prominent without switching to a different hue.

export const STATUS_ACTIVE_COLORS: Record<RequestStatus, string> = {
  Submitted:    'bg-slate-300 text-slate-900 border-slate-500',
  InReview:     'bg-blue-300 text-blue-900 border-blue-500',
  AwaitingInfo: 'bg-amber-300 text-amber-900 border-amber-500',
  InfoReceived: 'bg-cyan-300 text-cyan-900 border-cyan-500',
  Approved:     'bg-green-300 text-green-900 border-green-500',
  Rejected:     'bg-red-300 text-red-900 border-red-500',
  InProgress:   'bg-violet-300 text-violet-900 border-violet-500',
  Completed:    'bg-emerald-300 text-emerald-900 border-emerald-500',
  Closed:       'bg-gray-300 text-gray-800 border-gray-500',
}

export const POD_ACTIVE_COLORS: Record<Pod, string> = {
  Charger: 'bg-orange-300 text-orange-900 border-orange-500',
  Driver:  'bg-sky-300 text-sky-900 border-sky-500',
  Revenue: 'bg-green-300 text-green-900 border-green-500',
  Data:    'bg-purple-300 text-purple-900 border-purple-500',
  DevOps:  'bg-zinc-300 text-zinc-900 border-zinc-500',
  Denali:  'bg-indigo-300 text-indigo-900 border-indigo-500',
  Unknown: 'bg-gray-300 text-gray-800 border-gray-500',
}

export const PRIORITY_ACTIVE_COLORS: Record<Priority, string> = {
  Critical: 'bg-red-300 text-red-900 border-red-500',
  High:     'bg-orange-300 text-orange-900 border-orange-500',
  Medium:   'bg-yellow-300 text-yellow-900 border-yellow-500',
  Low:      'bg-slate-300 text-slate-800 border-slate-500',
}

export const TYPE_ACTIVE_COLORS: Record<RequestType, string> = {
  Feature: 'bg-blue-300 text-blue-900 border-blue-500',
  Defect:  'bg-rose-300 text-rose-900 border-rose-500',
}

// ── Workflow transition rules ─────────────────────────────────────────────────
// Defines which target statuses are legal from each source status.
// Enforced client-side in the UpdateStatus dropdown so reviewers only see
// valid next steps. The backend also validates these transitions independently.
//
// Key flows:
//   AwaitingInfo → InfoReceived  (requestor responds via /respond/:id)
//   InfoReceived → InReview | Approved  (reviewer resumes)
//   Rejected / Closed → []  (terminal states — no further moves)

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

// ── Role sets ─────────────────────────────────────────────────────────────────
// Used by useAuth to derive isPM / isReviewer booleans.
// Admin inherits all permissions by being included in every role set.

export const REVIEWER_ROLES: Role[] = ['PodReviewer', 'ProductManager', 'Admin']
export const PM_ROLES: Role[] = ['ProductManager', 'Admin']

// ── File upload constraints ───────────────────────────────────────────────────

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

// ── Pod descriptions ──────────────────────────────────────────────────────────
// Shown in the submit form to help requestors pick the right product pod.

export const POD_DESCRIPTIONS: Record<Pod, string> = {
  Charger: 'Hardware, firmware, and charger network',
  Driver: 'Driver-facing apps and experience',
  Revenue: 'Billing, payments, and revenue systems',
  Data: 'Analytics, reporting, and data pipelines',
  DevOps: 'Infrastructure, CI/CD, and platform',
  Denali: 'Enterprise and fleet solutions',
  Unknown: 'Not yet classified',
}
