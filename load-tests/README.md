# Blink Relay Load Test Suite 🚀

Comprehensive load testing using **Locust** to simulate realistic user behavior across all critical paths.

## Quick Start (5 minutes)

### 1. Install
```bash
cd load-tests
pip install -r requirements.txt
```

### 2. Start Backend
```bash
cd backend/backend
CELERY_TASK_ALWAYS_EAGER=true python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### 3. Run Tests
```bash
# Interactive dashboard (http://localhost:8089)
locust -f locustfile.py --host=http://localhost:8000

# Or run preset profile
python run_profile.py baseline
```

## Load Profiles

| Profile | Users | Duration | Use Case |
|---------|-------|----------|----------|
| **baseline** | 100 | 30m | Normal business day |
| **peak** | 500 | 45m | Peak traffic hours |
| **spike** | 1000 | 15m | Sudden traffic surge |
| **soak** | 200 | 120m | 2-hour stability test |
| **stress** | 2000 | 20m | Find breaking point |

## Critical Path Scenarios

### 1. Request Submission (6% weight)
- POST /requests (create)
- GET /requests/{id} (view)
- PATCH /requests/{id} (update)

### 2. Request Management (18% weight)
- GET /requests (list with filters)
- GET /requests/{id}/timeline (history)
- GET /requests/mine (user's requests)

### 3. Analytics Dashboard (13% weight)
- GET /analytics/summary
- GET /analytics/request-aging
- GET /analytics/pod-performance
- GET /requests/export (CSV)

### 4. Messaging & Collaboration (9% weight)
- POST /requests/{id}/messages (post comment)
- GET /requests/{id}/messages (fetch thread)

### 5. List & Filter (18% weight)
- GET /requests (default)
- GET /requests (with filters)

## Performance Targets

| Metric | Target |
|--------|--------|
| p95 Response Time | < 2 seconds |
| p99 Response Time | < 5 seconds |
| Average Response Time | < 500ms |
| Error Rate | < 1% |
| Throughput | > 50 RPS |

## Running Your First Test

```bash
# Terminal 1: Backend
cd backend/backend && CELERY_TASK_ALWAYS_EAGER=true python3 -m uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2: Load Test
cd load-tests
python run_profile.py baseline

# Results appear in console and saved to results/baseline_*.csv
```

## Reading Results

```
Response Time (ms):
  Average:  450ms  ✓ (target: 500ms)
  p95:      1200ms ✓ (target: 2000ms)
  p99:      4500ms ✓ (target: 5000ms)

Error Rate: 0.8% ✓ (target: <1%)
```

## User Types

- **BRUser (70%)** - Full CRUD, creates requests, posts messages
- **LightLoadUser (20%)** - Read-only, views dashboards
- **HeavyLoadUser (10%)** - Admin/PM, aggressive writes

## Troubleshooting

### Connection refused
```bash
curl http://localhost:8000/health  # Check backend
```

### Authentication fails
- Ensure backend is running
- Check database connectivity

### High error rate
- Check server logs for exceptions
- Monitor database locks
- Verify sufficient disk space

## Next Steps

1. ✅ Run baseline profile
2. ✅ Identify slow endpoints  
3. ✅ Optimize bottlenecks
4. ✅ Re-run to verify
5. ✅ Integrate into CI/CD

## References

- [Locust Docs](https://docs.locust.io/)
- [config.yaml](config.yaml) - Load profiles
- [locustfile.py](locustfile.py) - User tasks
