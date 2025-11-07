import redis
import os
import logfire

from logging import basicConfig

from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

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

from routers import auth, users, kyc


# Load environment variables first
load_dotenv()

# Configure logfire BEFORE creating FastAPI app
logfire.configure(token=os.getenv("LOGFIRE_WRITE_TOKEN"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    logfire.info("Starting FindMyRent application...")

    client = AsyncIOMotorClient(
        os.getenv("DATABASE_CONNECTION_STRING")
    )  # * Connect to MongoDB

    await init_beanie(
        database=client[os.getenv("DATABASE_NAME")],
        document_models=[User, Admin, LandLord, Message, Chat, Listing, Permissions],
    )
    logfire.info("Database initialized successfully")

    redis_connection = await redis.asyncio.Redis()
    logfire.info("Redis connection established")

    yield

    logfire.info("Shutting down FindMyRent application...")
    client.close()
    await redis_connection.close()
    logfire.info("Application shutdown complete")


app = FastAPI(
    title="FindMyRent API",
    description="A comprehensive API for managing rental services, including tenant records, landlord profiles, and rental agreements.",
    lifespan=lifespan,
)

# Instrument FastAPI app with logfire
# logfire.instrument_fastapi(app)
# logfire.info("FastAPI application instrumented with logfire")

# app.add_middleware(HTTPSRedirectMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["127.0.0.1"])
app.add_middleware(
    IdempotencyMiddleware,
    ttl_seconds=3600,
    lock_ttl=10,
)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=100,  # 100 requests per minute
    bucket_capacity=120,  # Allow small bursts
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(kyc.router)