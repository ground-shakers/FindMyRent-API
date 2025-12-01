"""Idempotency middleware for FindMyRent API using Redis."""

import json
import asyncio
import base64
import os

from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.requests import Request
from fastapi.responses import Response, JSONResponse

from fastapi import status as status_code

import redis.asyncio as redis


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Custom Middleware to handle idempotency for requests.
    """ 
    def __init__(
        self,
        app,
        redis_url: str = None,
        ttl_seconds: int = 60 * 60,
        lock_ttl: int = 10,
    ):
        super().__init__(app)
        # Use environment variable if redis_url not provided
        if redis_url is None:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis = redis.from_url(
            redis_url, encoding="utf-8", decode_responses=False
        )
        self.ttl = ttl_seconds
        self.lock_ttl = lock_ttl

    async def _acquire_lock(self, key: str) -> bool:
        # Use SET NX with an expiry to act as a lock
        val = str(asyncio.get_event_loop().time()).encode()
        return await self._redis.set(key, val, nx=True, ex=self.lock_ttl)

    async def _release_lock(self, key: str):
        await self._redis.delete(key)

    async def dispatch(self, request: Request, call_next: Callable):
        method = request.method.upper()
        if method not in ("POST", "PUT", "PATCH", "DELETE"):
            # only guard mutating endpoints
            return await call_next(request)

        idemp_key = request.headers.get("Idempotency-Key")
        if not idemp_key:
            # TODO Raise error when no idempotency key is provided
            # no idempotency key -> proceed normally
            return await call_next(request)

        cache_key = f"idemp:resp:{idemp_key}"
        lock_key = f"idemp:lock:{idemp_key}"

        # Check for cached response
        cached = await self._redis.get(cache_key)
        if cached:
            # cached stored as JSON bytes
            payload: dict = json.loads(cached.decode("utf-8"))
            status = payload.get("status", status_code.HTTP_200_OK)
            headers = payload.get("headers", {})
            body_b64 = payload.get("body_b64")
            
            if body_b64 is None:
                body = payload.get("body")
                return JSONResponse(content=body, status_code=status, headers=headers)
            else:
                # binary payload (base64)
                body_bytes = base64.b64decode(body_b64)
                return Response(content=body_bytes, status_code=status, headers=headers)

        # Acquire lock so only one request executes the handler
        locked = await self._acquire_lock(lock_key)
        if not locked:
            # Another worker is processing this idempotency key: wait for result or timeout
            # Poll for cached response for a short time
            for _ in range(20):  # total wait ~ lock_ttl * some fraction
                await asyncio.sleep(0.2)
                cached = await self._redis.get(cache_key)
                if cached:
                    payload = json.loads(cached.decode("utf-8"))
                    status = payload.get("status", status_code.HTTP_200_OK)
                    headers = payload.get("headers", {})
                    body_b64 = payload.get("body_b64")
                    if body_b64 is None:
                        body = payload.get("body")
                        return JSONResponse(
                            content=body, status_code=status, headers=headers
                        )
                    else:
                        body_bytes = base64.b64decode(body_b64)
                        return Response(
                            content=body_bytes, status_code=status, headers=headers
                        )
            # timed out waiting, return 202 accepted
            return JSONResponse({"detail": "Request in progress"}, status_code=status_code.HTTP_202_ACCEPTED)

        # We hold the lock -> call the handler and cache its response
        try:
            response: Response = await call_next(request)
            # Read response body (must consume iterator)
            body_bytes = b""
            async for chunk in response.body_iterator:
                body_bytes += chunk
            # restore body iterator for downstream middleware / final return
            response.body_iterator = iter([body_bytes])

            # Prepare storeable payload
            headers = dict(response.headers)
            status = response.status_code

            # Try to decode body as utf-8 JSON/text; if binary, base64 it
            try:
                body_text = body_bytes.decode("utf-8")
                # If it is JSON-like, load to object for nicer caching; otherwise store as text
                try:
                    body_obj = json.loads(body_text)
                    store_payload = {
                        "status": status,
                        "headers": headers,
                        "body": body_obj,
                    }
                except Exception:
                    store_payload = {
                        "status": status,
                        "headers": headers,
                        "body": body_text,
                    }
            except Exception:
                # binary content, base64 encode
                body_b64 = base64.b64encode(body_bytes).decode("ascii")
                store_payload = {
                    "status": status,
                    "headers": headers,
                    "body_b64": body_b64,
                }

            await self._redis.set(
                cache_key, json.dumps(store_payload).encode("utf-8"), ex=self.ttl
            )
            return response
        finally:
            await self._release_lock(lock_key)