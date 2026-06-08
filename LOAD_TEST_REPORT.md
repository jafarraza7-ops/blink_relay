# Load Test Report - Blink Relay

**Date:** 2026-06-08  
**Test Duration:** ~2 hours  

## Summary

✅ **Basic endpoints:** Excellent performance (100% success, P99 < 54ms)
✅ **Stress test (30 concurrent):** Strong performance (100% success, P99 < 85ms)  
❌ **POST /requests under load:** Significant issues discovered and partially fixed

## Issues Found and Fixed

### 1. ✅ FIXED - Invalid Email for Anonymous Users
- **Issue:** Email "unknown@external" invalid for JSM API
- **Impact:** Celery tasks failing and retrying every 30s, blocking API
- **Fix:** Changed to "intake-system@blinkcharging.com"
- **Commit:** d6d0e69

### 2. ✅ FIXED - SQLAlchemy Enum Configuration
- **Issue:** Enum types using names instead of values
- **Impact:** 72-hour reminder queries failing
- **Fix:** Added `values_callable` to all Enum columns
- **Commit:** 643d091

### 3. ⚠️ REMAINING - POST /requests Performance
- **Issue:** Timeouts under 20+ concurrent users
- **Root Cause:** Celery eager mode blocking on external APIs + SQLite concurrency limits
- **Recommended Fixes:**
  1. Disable `CELERY_TASK_ALWAYS_EAGER` (use Redis broker)
  2. Migrate SQLite to PostgreSQL
  3. Optimize database connection pooling

## Load Test Results

| Test | Concurrency | Success | P99 Latency | Status |
|------|-------------|---------|-------------|--------|
| Basic | 10 | 100% | 53.6ms | ✅ Pass |
| Stress | 30 | 100% | 84.9ms | ✅ Pass |  
| Comprehensive | 20 | 7.8% | 97ms | ⚠️ Needs work |

## Next Actions

1. **Disable Celery eager mode** (Critical for production)
2. **Migrate to PostgreSQL** (Required for scalability)
3. **Re-run load tests** after above changes
4. **Optimize JSM/Jira integration** to reduce blocking

See code comments in requests.py and celery_app.py for implementation details.
