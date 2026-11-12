"""Request correlation, JSON logs, and a conservative in-memory rate limiter.

Use a managed edge/API-gateway limiter for a horizontally scaled deployment.
"""
import json
import logging
import time
from collections import defaultdict, deque
from uuid import uuid4
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from .config import settings

logger = logging.getLogger("agentpay")
logging.basicConfig(level=logging.INFO, format="%(message)s")
_buckets: dict[str, deque[float]] = defaultdict(deque)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid4()))
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        logger.info(json.dumps({"event":"http_request", "request_id":request_id, "method":request.method, "path":request.url.path, "status":response.status_code, "duration_ms":round((time.perf_counter()-started)*1000)}))
        return response

async def rate_limit(request: Request) -> None:
    if request.url.path in {"/healthz", "/docs", "/openapi.json"}: return
    client = request.client.host if request.client else "unknown"
    now = time.monotonic(); bucket = _buckets[client]
    while bucket and bucket[0] <= now - 60: bucket.popleft()
    if len(bucket) >= settings.rate_limit_per_minute: raise HTTPException(429, "Rate limit exceeded")
    bucket.append(now)
