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
  Cancelled: 'Cancelled',
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
  Cancelled: 'bg-orange-100 text-orange-700 border-orange-200',
}

export const POD_COLORS: Record<Pod, string> = {
  Charger: 'bg-gray-100 text-gray-700 border-gray-200',
  Driver: 'bg-gray-100 text-gray-700 border-gray-200',
  Revenue: 'bg-gray-100 text-gray-700 border-gray-200',
  Data: 'bg-gray-100 text-gray-700 border-gray-200',
  DevOps: 'bg-gray-100 text-gray-700 border-gray-200',
  Denali: 'bg-gray-100 text-gray-700 border-gray-200',
  Unknown: 'bg-gray-100 text-gray-500 border-gray-200',
}

export const PRIORITY_COLORS: Record<Priority, string> = {
  Critical: 'bg-red-50 text-red-700 border-red-200',
  High: 'bg-orange-50 text-orange-700 border-orange-200',
  Medium: 'bg-gray-100 text-gray-600 border-gray-200',
  Low: 'bg-gray-50 text-gray-500 border-gray-200',
}

export const TYPE_COLORS: Record<RequestType, string> = {
  Feature: 'bg-blue-50 text-blue-700 border-blue-200',
  Defect: 'bg-red-50 text-red-700 border-red-200',
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
  Charger: 'bg-gray-200 text-gray-900 border-gray-400',
  Driver:  'bg-gray-200 text-gray-900 border-gray-400',
  Revenue: 'bg-gray-200 text-gray-900 border-gray-400',
  Data:    'bg-gray-200 text-gray-900 border-gray-400',
  DevOps:  'bg-gray-200 text-gray-900 border-gray-400',
  Denali:  'bg-gray-200 text-gray-900 border-gray-400',
  Unknown: 'bg-gray-200 text-gray-800 border-gray-400',
}

export const PRIORITY_ACTIVE_COLORS: Record<Priority, string> = {
  Critical: 'bg-gray-200 text-red-900 border-gray-400 font-bold',
  High:     'bg-gray-200 text-orange-800 border-gray-400 font-bold',
  Medium:   'bg-gray-200 text-gray-700 border-gray-400',
  Low:      'bg-gray-200 text-gray-600 border-gray-400',
}

export const TYPE_ACTIVE_COLORS: Record<RequestType, string> = {
  Feature: 'bg-gray-200 text-blue-900 border-gray-400 font-bold',
  Defect:  'bg-gray-200 text-red-900 border-gray-400 font-bold',
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

// ── Pod labels (user-friendly names) ──────────────────────────────────────────
// Maps technical pod enum values to business-focused labels that end users understand.
// Philosophy: Users think in terms of "which Blink product is affected?" not "which
// engineering team owns this?" This constant is the single source of truth for all
// pod labels across the app — update here and it propagates everywhere.

export const POD_LABELS: Record<Pod, string> = {
  Charger: 'Charging Stations',
  Driver: 'Driver Mobile App',
  Revenue: 'Payments & Billing',
  Data: 'Data & Analytics',
  DevOps: 'System & Infrastructure',
  Denali: 'Enterprise Fleet',
  Unknown: 'Not yet classified',
}

// ── Pod descriptions ──────────────────────────────────────────────────────────
// Shown in the submit form to help requestors pick the right product area.
// Each description focuses on business impact and user-facing features, not
// technical implementation details. Guides end-users to select the correct area
// for their specific problem.

export const POD_DESCRIPTIONS: Record<Pod, string> = {
  Charger: 'Issues with charging hardware, stations, or network',
  Driver: 'Problems with the mobile app drivers use',
  Revenue: 'Payment processing, invoicing, or subscription issues',
  Data: 'Reporting, dashboards, or data accuracy issues',
  DevOps: 'Overall system stability or performance',
  Denali: 'Fleet management or corporate solutions',
  Unknown: 'Not yet classified',
}

// ── UI component refresh intervals ───────────────────────────────────────────
// Used by data-fetching hooks to auto-refresh component state at regular intervals.

export const PAGE_SIZE = 10
export const DASHBOARD_REFRESH_INTERVAL_MS = 30_000
export const MY_REQUESTS_REFRESH_INTERVAL_MS = 30_000
