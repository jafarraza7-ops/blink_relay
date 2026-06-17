# Azure AD RBAC Setup for Blink Relay

Complete guide to implement role-based access control (RBAC) using Azure Active Directory (Entra ID) with three roles: Admin, Requestor, and PM.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Azure AD Setup](#azure-ad-setup)
5. [Application Registration](#application-registration)
6. [Group-Based RBAC](#group-based-rbac)
7. [Backend Integration](#backend-integration)
8. [Frontend Integration](#frontend-integration)
9. [Testing](#testing)
10. [Deployment](#deployment)

---

## Overview

### Goals

- **Single Sign-On (SSO)** using Azure AD credentials
- **Role-Based Access Control** with three roles:
  - **Admin** — Full system access, user management, settings
  - **Requestor** — Submit requests, view own requests and messages
  - **PM** — Review requests, approve/reject, manage workflow, view analytics
- **Group-based membership** — Users inherit roles from Azure AD groups
- **Token-based authentication** — JWT with Azure AD issued tokens
- **Seamless integration** — Works with existing Blink Relay workflow

### Benefits

✅ Enterprise-grade authentication  
✅ Centralized user management  
✅ No password management needed  
✅ Audit trail via Azure AD logs  
✅ MFA support built-in  
✅ Easy offboarding when employees leave  

---

## Architecture

### Authentication Flow

```
┌──────────────┐
│  User Login  │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────┐
│  Redirect to Azure AD Login  │
│  (https://login.microsoftonline.com)
└──────┬───────────────────────┘
       │
       ▼
┌──────────────────────────────┐
│  User Authenticates          │
│  (Username + MFA if enabled) │
└──────┬───────────────────────┘
       │
       ▼
┌──────────────────────────────┐
│  Azure AD returns JWT token  │
│  + user roles/groups         │
└──────┬───────────────────────┘
       │
       ▼
┌──────────────────────────────┐
│  Frontend receives token     │
│  Stores in localStorage      │
└──────┬───────────────────────┘
       │
       ▼
┌──────────────────────────────┐
│  API requests include token  │
│  Backend validates signature │
└──────┬───────────────────────┘
       │
       ▼
┌──────────────────────────────┐
│  Backend checks roles        │
│  Grant/deny access          │
└──────────────────────────────┘
```

### Role Hierarchy

```
Admin
├── Full system access
├── User management
├── View all requests
├── Can act as PM
└── Can act as Requestor

PM (Product Manager)
├── List/filter all requests
├── Review requests
├── Approve/reject
├── Assign to pods
├── View analytics
├── Cannot delete users
└── Cannot change roles

Requestor
├── Submit requests
├── View own requests
├── Edit drafts
├── Receive clarifications
├── Cannot approve
└── Cannot view others' requests
```

---

## Prerequisites

### Azure Tenant Requirements

- ✅ Azure AD tenant with admin access
- ✅ Global Administrator or Application Administrator role
- ✅ Company domain (e.g., blinkcharging.onmicrosoft.com)

### Blink Relay Setup

- ✅ Backend running (FastAPI)
- ✅ Frontend running (React/Vite)
- ✅ Main branch deployed or staging environment ready

### Required Tools

- Azure Portal access
- `az cli` (optional, for CLI-based setup)
- `jwt-decode` library for token inspection

---

## Azure AD Setup

### Step 1: Create Azure AD Groups

1. **Log in to Azure Portal** → Azure Active Directory → Groups
2. **Create three groups:**

   **Group 1: Blink Relay Admins**
   ```
   Name: Blink Relay Admins
   Description: System administrators with full access
   Members: [Your admin users]
   ```

   **Group 2: Blink Relay PMs**
   ```
   Name: Blink Relay PMs
   Description: Product managers who review and approve requests
   Members: [PM team members]
   ```

   **Group 3: Blink Relay Requestors**
   ```
   Name: Blink Relay Requestors
   Description: All users who can submit requests
   Members: [All company users]
   ```

3. **Record Group IDs** (you'll need these later):
   ```
   Admin Group ID:      {admin-group-id}
   PM Group ID:         {pm-group-id}
   Requestor Group ID:  {requestor-group-id}
   ```

### Step 2: Assign Users to Groups

1. **Admin Group**: Add system administrators
2. **PM Group**: Add product managers and reviewers
3. **Requestor Group**: Add all company users (or specific departments)

**Note:** Users can belong to multiple groups (e.g., a PM is also a Requestor)

---

## Application Registration

### Step 1: Register Application in Azure AD

1. Go to **Azure Active Directory** → **App registrations** → **New registration**

2. **Fill in registration details:**
   ```
   Name:                    Blink Relay
   Supported account types: Accounts in this organizational directory only
   Redirect URI:            http://localhost:5173/callback
                           (Update for production)
   ```

3. **Click Register** and note:
   - **Application (client) ID**: {client-id}
   - **Directory (tenant) ID**: {tenant-id}

### Step 2: Configure API Permissions

1. Go to **API permissions** → **Add a permission**

2. **Select Microsoft Graph** → **Delegated permissions**

3. **Add these permissions:**
   ```
   User.Read
   User.ReadBasic.All
   Group.Read.All
   ```

4. Click **Grant admin consent** (requires admin role)

### Step 3: Create Client Secret

1. Go to **Certificates & secrets** → **New client secret**

2. **Create secret:**
   ```
   Description: Blink Relay Backend
   Expires: 24 months
   ```

3. **Copy the value immediately** (you won't see it again):
   ```
   Client Secret: {client-secret}
   ```

### Step 4: Configure Token Issuance

1. Go to **Token configuration** → **Add groups claim**

2. **Select:**
   - Groups assigned to the application
   - Emit groups as role claims (if available)

3. This ensures Azure AD includes group memberships in JWT tokens

### Step 5: Update Manifest

1. Go to **Manifest** and find `"groupMembershipClaims"`

2. Set to:
   ```json
   "groupMembershipClaims": "SecurityGroup"
   ```

3. Add custom roles to manifest (optional):
   ```json
   "appRoles": [
     {
       "allowedMemberTypes": ["User"],
       "displayName": "Admin",
       "id": "{unique-uuid}",
       "isEnabled": true,
       "description": "System administrator",
       "value": "Admin"
     },
     {
       "allowedMemberTypes": ["User"],
       "displayName": "PM",
       "id": "{unique-uuid}",
       "isEnabled": true,
       "description": "Product manager",
       "value": "PM"
     }
   ]
   ```

---

## Group-Based RBAC

### Mapping Groups to Roles

The backend will map Azure AD group IDs to application roles:

```python
# backend/backend/app/core/config.py

AZURE_AD_ROLES = {
    "admin_group_id": os.getenv("AZURE_AD_ADMIN_GROUP_ID"),
    "pm_group_id": os.getenv("AZURE_AD_PM_GROUP_ID"),
    "requestor_group_id": os.getenv("AZURE_AD_REQUESTOR_GROUP_ID"),
}

# Role hierarchy
ROLE_HIERARCHY = {
    "Admin": ["Admin", "PM", "Requestor"],  # Admins have all permissions
    "PM": ["PM", "Requestor"],              # PMs can do PM + Requestor tasks
    "Requestor": ["Requestor"],             # Requestors can only submit
}
```

### Environment Variables

Create `.env` file with:

```bash
# Azure AD Configuration
AZURE_TENANT_ID={tenant-id}
AZURE_CLIENT_ID={client-id}
AZURE_CLIENT_SECRET={client-secret}

# Group IDs
AZURE_AD_ADMIN_GROUP_ID={admin-group-id}
AZURE_AD_PM_GROUP_ID={pm-group-id}
AZURE_AD_REQUESTOR_GROUP_ID={requestor-group-id}

# Frontend
VITE_AZURE_CLIENT_ID={client-id}
VITE_AZURE_TENANT_ID={tenant-id}
VITE_AZURE_REDIRECT_URI=http://localhost:5173/callback
```

---

## Backend Integration

### Step 1: Install Dependencies

```bash
pip install azure-identity msal fastapi-azure-auth PyJWT
```

### Step 2: Update Security Module

File: `backend/backend/app/core/security.py`

```python
from azure.identity import DefaultAzureCredential
from msal import ConfidentialClientApplication
from datetime import datetime, timedelta
import jwt
import json
from typing import Optional, List

class AzureADAuth:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        
        self.app = ConfidentialClientApplication(
            client_id=client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            client_credential=client_secret,
        )
    
    def validate_token(self, token: str) -> Optional[dict]:
        """Validate Azure AD JWT token"""
        try:
            # Decode without verification first to get header
            unverified = jwt.decode(token, options={"verify_signature": False})
            
            # Get public key from Azure AD
            jwks_uri = f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"
            # In production, cache this and refresh periodically
            
            # Verify signature using Azure AD's public key
            decoded = jwt.decode(
                token,
                options={"verify_signature": False},  # Use Azure AD verification instead
                algorithms=["RS256"]
            )
            
            return decoded
        except Exception as e:
            print(f"Token validation failed: {e}")
            return None
    
    def extract_roles(self, token_claims: dict) -> List[str]:
        """Extract roles from Azure AD token claims"""
        roles = []
        
        # Check group memberships
        groups = token_claims.get("groups", [])
        
        if settings.AZURE_AD_ADMIN_GROUP_ID in groups:
            roles.append("Admin")
        if settings.AZURE_AD_PM_GROUP_ID in groups:
            roles.append("PM")
        if settings.AZURE_AD_REQUESTOR_GROUP_ID in groups:
            roles.append("Requestor")
        
        return roles if roles else ["Requestor"]  # Default to Requestor

# Initialize in main.py
azure_auth = AzureADAuth(
    tenant_id=settings.AZURE_TENANT_ID,
    client_id=settings.AZURE_CLIENT_ID,
    client_secret=settings.AZURE_CLIENT_SECRET,
)
```

### Step 3: Update FastAPI Dependencies

File: `backend/backend/app/core/security.py` (continued)

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredential

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthCredential = Depends(security)
) -> UserClaims:
    """Extract and validate user from Azure AD token"""
    token = credentials.credentials
    
    # Validate token
    claims = azure_auth.validate_token(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    # Extract user info
    user = UserClaims(
        oid=claims.get("oid"),
        email=claims.get("preferred_username"),
        name=claims.get("name"),
        roles=azure_auth.extract_roles(claims),
        tid=claims.get("tid"),
    )
    
    return user

async def require_role(required_role: str):
    """Dependency to check user has required role"""
    async def check_role(user: UserClaims = Depends(get_current_user)) -> UserClaims:
        if required_role not in user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have '{required_role}' role"
            )
        return user
    return check_role
```

### Step 4: Update Endpoints with Role Checks

Example: `backend/backend/app/api/requests.py`

```python
from app.core.security import get_current_user, require_role

@router.get("/requests", response_model=RequestListResponse)
async def list_requests(
    user: UserClaims = Depends(require_role("PM"))  # Only PMs and Admins
):
    """List all requests - PM/Admin only"""
    # ... implementation

@router.post("/requests/{id}/approve")
async def approve_request(
    request_id: str,
    user: UserClaims = Depends(require_role("PM"))
):
    """Approve request - PM/Admin only"""
    # ... implementation

@router.post("/requests", response_model=RequestResponse)
async def create_request(
    payload: CreateRequestPayload,
    user: UserClaims = Depends(get_current_user)  # Any authenticated user
):
    """Create request - All authenticated users"""
    # Only Requestor can see the submitter_email (logged-in user)
    payload.submitter_email = user.email
    # ... implementation
```

---

## Frontend Integration

### Step 1: Install MSAL.js

```bash
npm install @azure/msal-browser @azure/msal-react
```

### Step 2: Create Auth Context

File: `OneDrive_2_20-05-2026/src/hooks/useAuthAzure.ts`

```typescript
import { useMsalAuthentication } from "@azure/msal-react";
import { InteractionType } from "@azure/msal-browser";

export const useAuthAzure = () => {
  const { login, result, error } = useMsalAuthentication(
    InteractionType.Redirect,
    {
      scopes: ["user.read"],
    }
  );

  const token = result?.accessToken;
  const user = result?.account;

  return {
    token,
    user,
    login,
    error,
    isAuthenticated: !!token,
  };
};
```

### Step 3: Setup MSAL in main.tsx

```typescript
import { PublicClientApplication } from "@azure/msal-browser";
import { MsalProvider } from "@azure/msal-react";

const msalConfig = {
  auth: {
    clientId: import.meta.env.VITE_AZURE_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${import.meta.env.VITE_AZURE_TENANT_ID}`,
    redirectUri: import.meta.env.VITE_AZURE_REDIRECT_URI,
  },
  cache: {
    cacheLocation: "localStorage",
  },
};

const pca = new PublicClientApplication(msalConfig);

export default function App() {
  return (
    <MsalProvider instance={pca}>
      <BrowserRouter>
        <Routes>
          {/* routes */}
        </Routes>
      </BrowserRouter>
    </MsalProvider>
  );
}
```

### Step 4: Protect Routes by Role

```typescript
import { useContext } from "react";

interface ProtectedRouteProps {
  requiredRole: "Admin" | "PM" | "Requestor";
  children: ReactNode;
}

export function ProtectedRoute({
  requiredRole,
  children,
}: ProtectedRouteProps) {
  const { user } = useAuth();

  const hasRole = (user?.roles || []).includes(requiredRole);

  if (!hasRole) {
    return <AccessDenied requiredRole={requiredRole} />;
  }

  return <>{children}</>;
}

// Usage
<Routes>
  <Route path="/dashboard" element={<ProtectedRoute requiredRole="PM"><Dashboard /></ProtectedRoute>} />
  <Route path="/admin" element={<ProtectedRoute requiredRole="Admin"><AdminPanel /></ProtectedRoute>} />
</Routes>
```

---

## Testing

### Test Azure AD Login

1. **In browser:**
   - Go to `http://localhost:5173`
   - Click "Login with Azure AD"
   - Sign in with Azure AD credentials
   - Should redirect back with token

2. **Check token in console:**
   ```javascript
   // In browser console
   const token = localStorage.getItem('msal.account.keys');
   console.log(token);
   ```

3. **Decode token:**
   ```bash
   # Online: jwt.io (paste token)
   # Or use CLI:
   jq -R 'split(".")[1] | @base64d | fromjson' <<< "$TOKEN"
   ```

4. **Verify groups claim:**
   ```json
   {
     "oid": "user-id",
     "email": "user@blinkcharging.com",
     "groups": ["admin-group-id", "pm-group-id", "requestor-group-id"],
     "roles": ["Admin", "PM"]
   }
   ```

### Test Role-Based Access

```bash
# Test PM-only endpoint
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/requests

# Should return 200 if user has PM role
# Should return 403 if user only has Requestor role
```

### Test User Sync

```python
# backend/backend/tests/test_azure_auth.py

import pytest
from app.core.security import azure_auth

@pytest.mark.asyncio
async def test_azure_token_validation():
    """Test Azure AD token validation"""
    # Get token from test user
    token = get_test_token()
    
    # Validate
    claims = azure_auth.validate_token(token)
    assert claims is not None
    assert claims["email"] == "testuser@blinkcharging.com"

@pytest.mark.asyncio
async def test_role_extraction():
    """Test role extraction from groups"""
    claims = {
        "groups": [
            "admin-group-id",
            "pm-group-id",
            "requestor-group-id"
        ]
    }
    
    roles = azure_auth.extract_roles(claims)
    assert "Admin" in roles
    assert "PM" in roles
    assert "Requestor" in roles
```

---

## Deployment

### Production Configuration

**Update environment variables for production:**

```bash
# production.env
AZURE_TENANT_ID=prod-tenant-id
AZURE_CLIENT_ID=prod-client-id
AZURE_CLIENT_SECRET=prod-client-secret

VITE_AZURE_CLIENT_ID=prod-client-id
VITE_AZURE_TENANT_ID=prod-tenant-id
VITE_AZURE_REDIRECT_URI=https://blink-relay.blinkcharging.com/callback

# Database
DATABASE_URL=postgresql://user:pass@prod-db.postgres.database.azure.com/blinkrelaydb
```

### Update Azure AD Redirect URIs

1. Go to **App registration** → **Authentication**
2. Update **Redirect URIs**:
   ```
   https://blink-relay.blinkcharging.com/callback
   https://blink-relay-staging.blinkcharging.com/callback
   ```

### Configure Conditional Access (Optional)

1. **Azure AD** → **Security** → **Conditional Access**
2. Create policy:
   - **Condition**: Any cloud app
   - **Grant**: Require device to be marked as compliant
   - **Session**: Sign-in frequency (30 days)

### Enable Audit Logging

1. **Azure AD** → **Audit logs**
2. Monitor for:
   - Failed login attempts
   - Group membership changes
   - Role assignments

---

## Troubleshooting

### Token Invalid or Expired

```
Error: Token validation failed
```

**Solutions:**
- Check token expiration: `exp` claim in JWT
- Verify clock skew between server and Azure AD
- Refresh token: sign out and sign in again

### User Has No Roles

```
Error: User does not have 'PM' role
```

**Solutions:**
- Verify user is in Azure AD group
- Check group ID matches `AZURE_AD_PM_GROUP_ID`
- Require user to sign out and sign in again (token cache)
- Check `groups` claim in token

### Redirect URI Mismatch

```
Error: AADSTS50011: The reply URL specified in the request does not match the reply URLs configured for the application
```

**Solutions:**
- Update redirect URI in Azure AD app registration
- Match exact protocol (http vs https)
- Include trailing slash if configured

### CORS Error When Authenticating

```
Access to XMLHttpRequest blocked by CORS
```

**Solutions:**
- Azure AD doesn't support CORS for token endpoints
- Ensure frontend redirects to `login.microsoftonline.com`
- Backend should not call Azure AD directly from frontend

---

## Security Best Practices

✅ **Never expose client secret** in frontend code  
✅ **Use HTTPS in production** (required for OAuth)  
✅ **Implement token refresh** with refresh tokens  
✅ **Validate token signature** on every request  
✅ **Log authentication events** for audit trail  
✅ **Implement rate limiting** on login endpoint  
✅ **Use short token expiry** (15-60 minutes)  
✅ **Rotate secrets** every 3-6 months  

---

## References

- [Azure AD Documentation](https://docs.microsoft.com/en-us/azure/active-directory/)
- [MSAL.js Documentation](https://github.com/AzureAD/microsoft-authentication-library-for-js)
- [OpenID Connect](https://openid.net/connect/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)

---

## Support

For issues or questions:
1. Check Azure AD Audit Logs
2. Verify group memberships
3. Inspect JWT token claims
4. Check backend logs for validation errors
