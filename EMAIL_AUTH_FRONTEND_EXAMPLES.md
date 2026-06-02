# Email Login Frontend Integration Examples

## Overview

This document provides React/TypeScript examples for integrating the email login system on the frontend.

## 1. Login Request Page

```typescript
// components/EmailLoginForm.tsx
import React, { useState } from 'react';

interface EmailLoginFormProps {
  onSuccess?: () => void;
}

export const EmailLoginForm: React.FC<EmailLoginFormProps> = ({ onSuccess }) => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setMessage('');
    setLoading(true);

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.toLowerCase() }),
      });

      if (response.status === 202) {
        setMessage('Check your email for a login link (expires in 15 minutes)');
        setEmail('');
        onSuccess?.();
      } else {
        setError('Failed to send login link. Please try again.');
      }
    } catch (err) {
      setError('Network error. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-md mx-auto p-6">
      <h2 className="text-2xl font-bold mb-6">Sign in with Email</h2>

      <div className="mb-4">
        <label htmlFor="email" className="block text-sm font-medium mb-2">
          Email Address
        </label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          disabled={loading}
          required
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      {message && (
        <div className="mb-4 p-3 bg-green-50 text-green-700 rounded-lg text-sm">
          {message}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full bg-blue-600 text-white font-medium py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? 'Sending link...' : 'Send Login Link'}
      </button>

      <p className="text-xs text-gray-600 mt-4 text-center">
        We'll send a secure link to your email. No password needed.
      </p>
    </form>
  );
};
```

## 2. Email Verification Link Handler

```typescript
// components/EmailVerifyPage.tsx
import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

interface TokenStatus {
  valid: boolean;
  reason: 'valid' | 'not_found' | 'expired' | 'already_used';
  email?: string;
}

interface VerifyResponse {
  user_id: string;
  email: string;
  display_name: string;
  access_token: string;
}

export const EmailVerifyPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [tokenStatus, setTokenStatus] = useState<TokenStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [showNameForm, setShowNameForm] = useState(false);
  const [verifying, setVerifying] = useState(false);

  const token = searchParams.get('token');

  // Step 1: Check token validity on page load
  useEffect(() => {
    if (!token) {
      setError('No login token provided');
      setLoading(false);
      return;
    }

    checkTokenStatus();
  }, [token]);

  const checkTokenStatus = async () => {
    try {
      const response = await fetch(`/api/auth/login-status/${token}`);
      const data: TokenStatus = await response.json();

      setTokenStatus(data);

      if (!data.valid) {
        const reasons: Record<string, string> = {
          not_found: 'Login link not found',
          expired: 'Login link has expired (15 min limit)',
          already_used: 'Login link was already used',
        };
        setError(reasons[data.reason] || 'Invalid login link');
      } else {
        // Token is valid, check if user exists or if we need name
        // For now, assume name is needed for new signups
        setShowNameForm(true);
      }
    } catch (err) {
      setError('Failed to verify link');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Complete verification with token
  const handleVerify = async (e?: React.FormEvent) => {
    e?.preventDefault();

    if (!token || !tokenStatus?.valid) {
      setError('Invalid token');
      return;
    }

    setVerifying(true);
    setError('');

    try {
      const response = await fetch('/api/auth/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token,
          display_name: displayName || undefined,
        }),
      });

      if (response.status === 200) {
        const data: VerifyResponse = await response.json();

        // Store JWT token
        localStorage.setItem('accessToken', data.access_token);
        localStorage.setItem('currentUser', JSON.stringify({
          id: data.user_id,
          email: data.email,
          displayName: data.display_name,
        }));

        // Redirect to dashboard
        navigate('/dashboard');
      } else if (response.status === 422) {
        setError('Please provide your name to sign up');
      } else {
        setError('Verification failed. Try requesting a new link.');
      }
    } catch (err) {
      setError('Network error during verification');
      console.error(err);
    } finally {
      setVerifying(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p>Checking your login link...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md">
          <div className="text-red-600 mb-4">
            <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4v2m0-12a9 9 0 110 18 9 9 0 010-18z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold mb-4 text-center">Link Invalid</h2>
          <p className="text-gray-600 mb-6 text-center">{error}</p>
          <button
            onClick={() => navigate('/login')}
            className="w-full bg-blue-600 text-white font-medium py-2 rounded-lg hover:bg-blue-700"
          >
            Request New Link
          </button>
        </div>
      </div>
    );
  }

  if (tokenStatus?.valid && showNameForm) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md w-full">
          <h2 className="text-2xl font-bold mb-2">Welcome to Blink Relay</h2>
          <p className="text-gray-600 mb-6">
            Signing in as <strong>{tokenStatus.email}</strong>
          </p>

          <form onSubmit={handleVerify}>
            <div className="mb-4">
              <label htmlFor="displayName" className="block text-sm font-medium mb-2">
                Your Name (optional)
              </label>
              <input
                id="displayName"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="John Doe"
                disabled={verifying}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">
                Your name will be displayed on requests you submit.
              </p>
            </div>

            {error && (
              <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={verifying}
              className="w-full bg-blue-600 text-white font-medium py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {verifying ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          <p className="text-xs text-gray-500 mt-4 text-center">
            This is a secure link. Never share it with anyone.
          </p>
        </div>
      </div>
    );
  }

  return null;
};
```

## 3. Authenticated API Request Utility

```typescript
// utils/api.ts
export class APIError extends Error {
  constructor(
    public status: number,
    public details: string,
  ) {
    super(`API Error ${status}: ${details}`);
  }
}

export async function authFetch(
  url: string,
  options: RequestInit = {},
): Promise<any> {
  const token = localStorage.getItem('accessToken');

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    // Handle 401 — redirect to login
    if (response.status === 401) {
      localStorage.removeItem('accessToken');
      localStorage.removeItem('currentUser');
      window.location.href = '/login';
    }
    const details = await response.text();
    throw new APIError(response.status, details);
  }

  return response.json();
}

// Usage examples:
export const requests = {
  list: () => authFetch('/api/requests'),
  get: (id: string) => authFetch(`/api/requests/${id}`),
  submit: (data: any) =>
    authFetch('/api/requests', { method: 'POST', body: JSON.stringify(data) }),
};
```

## 4. Authentication Context (Optional but Recommended)

```typescript
// context/AuthContext.tsx
import React, { createContext, useContext, useEffect, useState } from 'react';

interface User {
  id: string;
  email: string;
  displayName: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Load user from localStorage on mount
    const stored = localStorage.getItem('currentUser');
    if (stored) {
      try {
        setUser(JSON.parse(stored));
      } catch (e) {
        console.error('Failed to parse stored user', e);
        localStorage.removeItem('currentUser');
      }
    }
    setLoading(false);
  }, []);

  const logout = () => {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('currentUser');
    setUser(null);
    window.location.href = '/login';
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: !!user,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
```

## 5. Protected Routes

```typescript
// components/ProtectedRoute.tsx
import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }

  return <>{children}</>;
};
```

## 6. Router Configuration

```typescript
// App.tsx
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { EmailLoginForm } from './components/EmailLoginForm';
import { EmailVerifyPage } from './components/EmailVerifyPage';
import { Dashboard } from './pages/Dashboard';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<EmailLoginForm />} />
          <Route path="/auth/email-verify" element={<EmailVerifyPage />} />

          {/* Protected routes */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />

          {/* Redirect */}
          <Route path="/" element={<Navigate to="/dashboard" />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
```

## 7. Using in Components

```typescript
// pages/Dashboard.tsx
import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { authFetch, APIError } from '../utils/api';

interface Request {
  id: string;
  reference_id: string;
  title: string;
  status: string;
}

export const Dashboard: React.FC = () => {
  const { user, logout } = useAuth();
  const [requests, setRequests] = useState<Request[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchRequests();
  }, []);

  const fetchRequests = async () => {
    try {
      const data = await authFetch('/api/requests');
      setRequests(data);
    } catch (err) {
      if (err instanceof APIError) {
        setError(`Failed to load requests: ${err.details}`);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold">Blink Relay</h1>
          <div className="flex items-center gap-4">
            <span className="text-gray-600">
              Signed in as <strong>{user?.displayName}</strong>
            </span>
            <button
              onClick={logout}
              className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h2 className="text-xl font-bold mb-4">Your Requests</h2>

        {loading && <p>Loading...</p>}
        {error && <div className="text-red-600 mb-4">{error}</div>}

        {requests.length === 0 && !loading && (
          <p className="text-gray-500">No requests yet.</p>
        )}

        {requests.length > 0 && (
          <div className="grid gap-4">
            {requests.map((req) => (
              <div key={req.id} className="bg-white rounded-lg shadow p-4">
                <div className="flex justify-between">
                  <div>
                    <p className="font-mono text-sm text-gray-500">{req.reference_id}</p>
                    <h3 className="text-lg font-semibold">{req.title}</h3>
                  </div>
                  <span className="px-3 py-1 bg-gray-200 text-gray-800 text-sm rounded-lg">
                    {req.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
};
```

## Environment Setup

Add to `.env.local` (frontend):

```bash
VITE_API_BASE_URL=http://localhost:8000
```

Update API utilities to use it:

```typescript
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function authFetch(url: string, options?: RequestInit) {
  const fullUrl = `${API_BASE}${url}`;
  // ... rest of implementation
}
```

## Testing Locally

1. Start backend: `cd backend && python -m uvicorn main:app --reload`
2. Start frontend: `npm run dev` (or `yarn dev`)
3. Open http://localhost:5173
4. Enter email → Check Ethereal inbox → Click link → Sign in!

## Common Issues

### "Authorization header not sent"
- Check that token is stored in localStorage
- Verify header syntax: `Authorization: Bearer <token>`

### "401 Unauthorized on protected routes"
- Token may be expired (25+ hours old)
- Check that JWT was properly generated by backend
- Verify token is sent in every request

### "CORS error"
- Ensure backend CORS middleware allows frontend origin
- Check `FRONTEND_URL` config matches your dev server

### "Email not received"
- Check Ethereal inbox: https://ethereal.email/messages
- Verify SMTP credentials in backend `.env`
- Check backend logs for email service errors
