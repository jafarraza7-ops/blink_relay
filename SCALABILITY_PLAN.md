# Blink Relay Scalability Plan

## Executive Summary
Current system is designed for small teams (<500 users). This plan outlines how to scale to 10,000+ users and handle 1,000+ concurrent requests.

---

## Current Architecture Assessment

### ✅ Already Scalable
- **Async database access** (SQLAlchemy async)
- **Celery task queue** for async processing
- **FastAPI** (async framework, handles concurrency well)
- **React Query** client-side caching
- **Modular service architecture** (easy to scale components independently)

### ⚠️ Bottlenecks to Fix

| Bottleneck | Current | Impact | Solution |
|-----------|---------|--------|----------|
| **SQLite database** | Single file, local | Can't handle >100 concurrent writes | Migrate to PostgreSQL |
| **Similarity matching** | Scores 50 candidates | Linear time, O(n) queries | Add caching, pagination, async |
| **Email sending** | Sync in tasks | Can hang on timeout | Async SMTP, queue batching |
| **File storage** | Local disk | Can't scale across servers | Use S3/blob storage |
| **Session storage** | In-memory JWT | No cross-server session sync | Add Redis cache layer |
| **Notification emails** | Immediate send | Thundering herd on status changes | Batch and debounce |

---

## Phase 1: Database Migration (Week 1-2)

### SQLite → PostgreSQL

**Why:**
- SQLite locks file on writes (one write at a time)
- PostgreSQL handles 1000+ concurrent connections
- ACID compliance with distributed transactions
- Better query optimization

**Implementation:**

1. **Install PostgreSQL locally for dev**
   ```bash
   brew install postgresql
   brew services start postgresql
   createdb blink_relay_dev
   ```

2. **Update connection string** (app/core/database.py)
   ```python
   DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/blink_relay"
   ```

3. **Create migration** (alembic)
   ```bash
   alembic revision --autogenerate -m "Add PostgreSQL compatibility"
   alembic upgrade head
   ```

4. **Data migration script**
   - Export from SQLite
   - Import to PostgreSQL
   - Verify data integrity

**Performance gain:** 10-100x more concurrent connections

---

## Phase 2: Caching Layer (Week 1-2)

### Redis for Session & Query Cache

**Why:**
- Cache frequently accessed data (users, requests, similarity results)
- Store JWT sessions across servers
- Rate limiting and throttling
- Message queues for email batching

**Implementation:**

1. **Install Redis**
   ```bash
   brew install redis
   brew services start redis
   ```

2. **Update core/cache.py** (NEW FILE)
   ```python
   import aioredis
   from functools import wraps
   
   redis_client = None
   
   async def init_cache():
       global redis_client
       redis_client = await aioredis.create_redis_pool('redis://localhost')
   
   async def cache_get(key):
       return await redis_client.get(key)
   
   async def cache_set(key, value, ttl=3600):
       await redis_client.setex(key, ttl, value)
   ```

3. **Cache user requests** (api/requests.py)
   ```python
   @router.get("/requests/{request_id}")
   async def get_request(request_id: uuid.UUID):
       cache_key = f"request:{request_id}"
       cached = await cache_get(cache_key)
       if cached:
           return RequestResponse.model_validate_json(cached)
       
       req = await db.get(Request, request_id)
       await cache_set(cache_key, req.model_dump_json())
       return RequestResponse.model_validate(req)
   ```

4. **Cache similarity results** (services/similarity_service.py)
   ```python
   async def find_similar_requests(db, req_id, limit=5):
       cache_key = f"similar:{req_id}"
       cached = await cache_get(cache_key)
       if cached:
           return json.loads(cached)
       
       results = await _compute_similarity(db, req_id, limit)
       await cache_set(cache_key, json.dumps(results), ttl=3600)
       return results
   ```

**Performance gain:** 100-1000x faster for cached queries

---

## Phase 3: Async Email Processing (Week 2-3)

### Email Queue & Batching

**Why:**
- Current: Each email blocks the request
- Goal: Queue emails, batch send (reduces SMTP connections)

**Implementation:**

1. **Create email queue** (workers/email_queue.py)
   ```python
   async def queue_email(to, subject, body):
       """Queue email for batch sending"""
       key = f"email_queue:{uuid.uuid4()}"
       await cache_set(key, {
           'to': to,
           'subject': subject,
           'body': body,
           'created_at': datetime.now().isoformat()
       }, ttl=3600)
   
   async def batch_send_emails(limit=100):
       """Send emails in batches"""
       # Get up to 100 queued emails
       # Group by recipient domain
       # Send via SMTP with connection pooling
   ```

2. **Update email endpoints** (api/thread.py, api/requests.py)
   ```python
   # Instead of: task_send_new_message_email.delay(...)
   # Use: await queue_email(recipient, subject, body)
   ```

3. **Background worker** (runs every 30 seconds)
   ```python
   @app.on_event("startup")
   async def start_email_worker():
       asyncio.create_task(email_batch_worker())
   
   async def email_batch_worker():
       while True:
           await batch_send_emails()
           await asyncio.sleep(30)
   ```

**Performance gain:** 10x fewer SMTP connections, faster request completion

---

## Phase 4: API Rate Limiting & Pagination (Week 3)

### Request Throttling

**Why:**
- Prevent abuse
- Ensure fair resource allocation
- Enable predictable performance

**Implementation:**

1. **Rate limiting middleware** (app/middleware.py - NEW FILE)
   ```python
   from slowapi import Limiter
   from slowapi.util import get_remote_address
   
   limiter = Limiter(key_func=get_remote_address)
   
   @app.get("/requests")
   @limiter.limit("100/minute")
   async def list_requests(request: Request):
       return ...
   ```

2. **Pagination for large lists**
   ```python
   @router.get("/requests")
   async def list_requests(
       skip: int = Query(0, ge=0),
       limit: int = Query(25, ge=1, le=1000)
   ):
       # Only fetch requested page
       items = await db.execute(
           select(Request)
           .offset(skip)
           .limit(limit)
       )
   ```

3. **Connection pooling**
   ```python
   DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/db?min_size=10&max_size=50"
   ```

**Performance gain:** Prevents resource exhaustion

---

## Phase 5: Async Similarity Matching (Week 3-4)

### Background Similarity Computation

**Why:**
- Current: Similarity computed on request creation (blocks response)
- Goal: Compute async, cache results

**Implementation:**

1. **Async similarity job** (workers/similarity_tasks.py)
   ```python
   @shared_task
   async def compute_similar_requests(request_id):
       """Compute similarities in background"""
       db = get_db()
       similar = await find_similar_requests(db, request_id)
       await cache_set(f"similar:{request_id}", similar, ttl=86400)
   ```

2. **Trigger on request creation**
   ```python
   @router.post("/requests")
   async def create_request(...):
       req = Request(...)
       db.add(req)
       await db.commit()
       
       # Queue similarity computation (don't wait)
       compute_similar_requests.delay(str(req.id))
       
       return RequestResponse.model_validate(req)
   ```

3. **Return cached or partial results**
   ```python
   @router.get("/requests/{request_id}/similar")
   async def get_similar(request_id):
       # Returns cached if ready, or shows "computing" status
       cached = await cache_get(f"similar:{request_id}")
       if cached:
           return cached
       return {"status": "computing", "data": []}
   ```

**Performance gain:** Request creation 5x faster

---

## Phase 6: CDN & Static Asset Optimization (Week 4)

### Frontend Distribution

**Why:**
- Serve React build files from CDN (global distribution)
- Reduce server load
- Faster asset delivery

**Implementation:**

1. **S3 + CloudFront setup**
   ```bash
   # Upload built frontend to S3
   npm run build
   aws s3 sync dist/ s3://blink-relay-frontend/
   ```

2. **Asset versioning**
   ```javascript
   // Vite automatically generates hashes
   // dist/index-a1b2c3d4.js
   ```

3. **Gzip compression**
   ```javascript
   // vite.config.ts
   import compression from 'vite-plugin-compression'
   
   export default {
     plugins: [
       compression({
         algorithm: 'gzip',
         ext: '.js.gz'
       })
     ]
   }
   ```

**Performance gain:** 10x faster asset delivery for global users

---

## Phase 7: Database Indexing & Query Optimization (Week 4)

### Strategic Indexes

**Implementation:**

1. **Add indexes** (alembic migration)
   ```python
   op.create_index('ix_requests_submitter_email', 'requests', ['submitter_email'])
   op.create_index('ix_requests_status', 'requests', ['status'])
   op.create_index('ix_requests_created_at', 'requests', ['created_at'])
   op.create_index('ix_messages_request_id', 'messages', ['request_id'])
   op.create_index('ix_users_email', 'users', ['email'])
   ```

2. **Query analysis**
   ```python
   # Use EXPLAIN ANALYZE to find slow queries
   EXPLAIN ANALYZE
   SELECT * FROM requests 
   WHERE submitter_email = 'user@example.com'
   ORDER BY created_at DESC
   ```

**Performance gain:** 10-100x for indexed queries

---

## Phase 8: Horizontal Scaling (Week 5)

### Multiple Server Instances

**Why:**
- Load balancing across servers
- Redundancy and failover
- Handle peaks without manual scaling

**Implementation:**

1. **Docker containerization**
   ```dockerfile
   FROM python:3.11
   WORKDIR /app
   COPY . .
   RUN pip install -r requirements.txt
   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
   ```

2. **Docker Compose** (local testing)
   ```yaml
   version: '3.8'
   services:
     postgres:
       image: postgres:15
       environment:
         POSTGRES_DB: blink_relay
     redis:
       image: redis:7
     backend:
       build: ./backend/backend
       ports:
         - "8000:8000"
       depends_on:
         - postgres
         - redis
       environment:
         DATABASE_URL: postgresql://postgres@postgres/blink_relay
         REDIS_URL: redis://redis
     backend-2:
       # Second instance
       build: ./backend/backend
       ports:
         - "8001:8000"
   ```

3. **Nginx load balancer**
   ```nginx
   upstream backend {
       server localhost:8000;
       server localhost:8001;
       server localhost:8002;
   }
   
   server {
       listen 80;
       location /api {
           proxy_pass http://backend;
       }
   }
   ```

**Performance gain:** Handle 10x more concurrent users

---

## Performance Targets

### Current (SQLite, Single Server)
- Concurrent users: 10-20
- Requests/sec: 5-10
- Response time: 200-500ms
- Database: Single file, sequential writes

### After Phase 1-3 (PostgreSQL + Redis + Async Email)
- Concurrent users: 100-200
- Requests/sec: 50-100
- Response time: 50-100ms (cached), 100-200ms (fresh)
- Database: Parallel writes, indexed queries

### After Phase 8 (Full Scale)
- Concurrent users: 1,000-5,000
- Requests/sec: 500-1,000
- Response time: 20-50ms (cached)
- Database: Distributed queries, connection pooling

---

## Monitoring & Observability

### Key Metrics to Track

1. **Performance**
   - Request latency (p50, p95, p99)
   - Database query time
   - Cache hit rate
   - Email queue size

2. **Resource Usage**
   - CPU/Memory per server
   - Database connections
   - Redis memory
   - Disk I/O

3. **Reliability**
   - Error rate
   - Failed requests
   - Database connection failures
   - Email send failures

### Tools

```python
# app/observability/metrics.py
from prometheus_client import Counter, Histogram, Gauge

request_latency = Histogram('request_latency_seconds', 'Request latency')
cache_hits = Counter('cache_hits_total', 'Cache hits')
db_connections = Gauge('db_connections', 'Active DB connections')
email_queue_size = Gauge('email_queue_size', 'Emails in queue')
```

---

## Migration Path

### Week 1-2: Foundation
- [ ] PostgreSQL setup and data migration
- [ ] Redis caching layer
- [ ] Basic cache invalidation

### Week 2-3: Optimization
- [ ] Async email queuing
- [ ] Email batch processing
- [ ] Rate limiting middleware

### Week 3-4: Background Processing
- [ ] Async similarity matching
- [ ] Query caching strategy
- [ ] Database indexing

### Week 4-5: Distribution
- [ ] Frontend CDN setup
- [ ] Docker containerization
- [ ] Load balancing setup

### Week 5+: Monitoring
- [ ] Prometheus metrics
- [ ] Performance alerting
- [ ] Continuous optimization

---

## Estimated Costs

### Infrastructure
- **PostgreSQL (RDS):** $15-50/month
- **Redis (ElastiCache):** $20-50/month
- **S3 + CloudFront:** $5-20/month
- **Server instances (2-3x):** $40-120/month
- **Total:** ~$100-200/month (vs $5-10 for current SQLite setup)

### Benefits
- Support 100x more users
- 10x faster request handling
- 99.9% uptime (with redundancy)
- Global content delivery

---

## Testing Scalability

```python
# tests/load_test.py
import asyncio
import aiohttp

async def load_test():
    """Simulate 1000 concurrent requests"""
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(1000):
            task = session.get('http://localhost:8000/api/requests')
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        success = sum(1 for r in results if r.status == 200)
        print(f"Success rate: {success}/1000")

# Run: python -m pytest tests/load_test.py
```

---

## Summary

| Phase | Timeline | Impact | Effort |
|-------|----------|--------|--------|
| 1: PostgreSQL | Week 1-2 | 10x concurrent users | High |
| 2: Redis caching | Week 1-2 | 10x faster queries | Medium |
| 3: Async email | Week 2-3 | 5x faster requests | Low |
| 4: CDN | Week 4 | 10x faster assets | Low |
| 5: Indexing | Week 4 | 10x query speed | Low |
| 6: Horizontal scaling | Week 5 | 10x concurrent users | High |

**Expected result:** 100x improvement in scalability with 5-week effort
