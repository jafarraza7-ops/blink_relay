# Blink Relay — Entity Relationship Diagram

```mermaid
erDiagram

    users {
        UUID id PK
        string oid UK "Entra ID object ID"
        string email
        string display_name
        JSON roles "e.g. [ProductManager, Requestor]"
        datetime last_seen_at
        bool email_verified
        string auth_source "azure_ad | email"
        string last_login_method
        int failed_login_attempts
        datetime locked_until
        datetime created_at
    }

    email_login_tokens {
        UUID id PK
        string email
        string token_hash UK "SHA-256 of plaintext token"
        UUID user_id FK "nullable — null for new signups"
        bool is_used
        datetime created_at
        datetime expires_at
        datetime used_at
        string used_ip_address
        string used_user_agent
        string request_ip_address
        string invalidation_reason
        datetime invalidated_at
    }

    login_tokens {
        UUID id PK
        string token UK "legacy plaintext token (auth.py)"
        string email
        UUID user_id FK "nullable"
        datetime created_at
        datetime expires_at
        datetime used_at
    }

    requests {
        UUID id PK
        string reference_id UK "BLR-YYYY-NNNN"
        string title
        enum request_type "Feature | Defect"
        enum pod "Charger | Driver | Revenue | Data | DevOps | Denali | Unknown"
        enum priority "Critical | High | Medium | Low"
        JSON region "e.g. [NA, UK]"
        enum status "Submitted | InReview | AwaitingInfo | InfoReceived | Approved | Rejected | InProgress | Completed | Closed | Cancelled"
        text business_problem
        text expected_outcome
        text steps_to_reproduce
        string affected_area
        text additional_context
        string submitter_oid
        string submitter_email
        string submitter_name
        string rejection_reason
        text rejection_comment
        string rejected_by_oid
        string jira_ticket_key
        string jira_ticket_url
        string jsm_ticket_key
        string jsm_ticket_url
        datetime jsm_resolved_at
        datetime reminder_sent_at
        string claimed_by_oid
        string claimed_by_email
        datetime claimed_at
        datetime created_at
        datetime updated_at
    }

    messages {
        UUID id PK
        UUID request_id FK
        string author_oid
        string author_email
        string author_name
        text body
        bool is_internal "hidden from requestor if true"
        enum message_type "comment | clarification_question | clarification_response | status_change"
        string jsm_comment_id "set after JSM sync"
        JSON mentions "array of mentioned OIDs"
        datetime created_at
    }

    attachments {
        UUID id PK
        UUID request_id FK
        string filename
        string content_type
        string blob_name "Azure Blob path"
        int size_bytes
        string uploaded_by_oid
        datetime created_at
    }

    audit_logs {
        UUID id PK
        UUID request_id FK
        string actor_oid
        string actor_email
        string action "e.g. status_change | edit:title | file_deleted"
        text previous_value
        text new_value
        JSON event_data
        datetime created_at
    }

    email_groups {
        UUID id PK
        string name UK "e.g. Product Managers"
        string email UK "group inbox address"
        string description
        bool is_active
        datetime created_at
        datetime updated_at
    }

    email_group_members {
        UUID id PK
        UUID group_id FK
        string user_email "member's email address"
        datetime created_at
    }

    %% Relationships
    users ||--o{ email_login_tokens : "authenticates via"
    users ||--o{ login_tokens       : "legacy auth"
    requests ||--o{ messages        : "has thread"
    requests ||--o{ attachments     : "has files"
    requests ||--o{ audit_logs      : "has audit trail"
    email_groups ||--o{ email_group_members : "has members"
```

## Status State Machine

```
Submitted ──► InReview ──► Approved ──► InProgress ──► Completed ──► Closed
    │              │            │
    │              └──► AwaitingInfo ──► InfoReceived ──► InReview
    │                                                   └──► Approved
    │
    └──► (any state) ──► Cancelled
    └──► Rejected  (terminal)
```

## Key Design Notes

| Concern | Decision |
|---|---|
| Auth | Dual-path: Azure AD (OIDC) or email magic-link. Both upsert into `users`. |
| Token storage | `email_login_tokens` stores SHA-256 hash only — plaintext never persisted. `login_tokens` is a legacy table (plaintext). |
| Soft deletes | None — `attachments`, `messages`, `audit_logs` cascade-delete with the parent `request`. |
| Claim lock | `claimed_by_oid` / `claimed_at` on `requests` — no separate table. |
| PM groups | `email_groups` + `email_group_members` are denormalised by email, not FK to `users`, so group membership survives user account deletion. |
| JSM sync | `jsm_ticket_key` / `jsm_resolved_at` on `requests`; `jsm_comment_id` on `messages` track sync state without a separate join table. |
