import redis
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from contextlib import asynccontextmanager

import redis.asyncio

from middleware.idempotency import IdempotencyMiddleware
from middleware.rate_limiting import RateLimitMiddleware

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from models.users import User, Admin, LandLord
from models.security import Permissions
from models.messages import Message, Chat
from models.listings import Listing

from dotenv import load_dotenv

from routers import auth, users

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient(
        os.getenv("DATABASE_CONNECTION_STRING")
    )  # * Connect to MongoDB

    await init_beanie(
        database=client[os.getenv("DATABASE_NAME")],
        document_models=[User, Admin, LandLord, Message, Chat, Listing, Permissions],
    )

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_connection = await redis.asyncio.from_url(
        redis_url, encoding="utf-8", decode_responses=True
    )

    yield
    client.close()
    await redis_connection.close()

app = FastAPI(
    title="FindMyRent API",
    description="A comprehensive API for managing rental services, including tenant records, landlord profiles, and rental agreements.",
    lifespan=lifespan,
)

app.add_middleware(HTTPSRedirectMiddleware)  # Redirect HTTP to HTTPS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=100,  # 100 requests per minute
    bucket_capacity=120,  # Allow small bursts
)
app.add_middleware(
    IdempotencyMiddleware,
    ttl_seconds=3600,
    lock_ttl=10,
)
app.add_middleware(GZipMiddleware, minimum_size=500) # Compress responses larger than 500 bytes

app.include_router(auth.router)
app.include_router(users.router)
