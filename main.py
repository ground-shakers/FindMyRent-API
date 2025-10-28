import redis
import os
import logfire

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

from routers import auth, users, kyc

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

    redis_connection = await redis.asyncio.Redis()

    yield
    client.close()
    await redis_connection.close()

logfire.configure(token=os.getenv("LOGFIRE_WRITE_TOKEN"))

app = FastAPI(
    title="FindMyRent API",
    description="A comprehensive API for managing rental services, including tenant records, landlord profiles, and rental agreements.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    IdempotencyMiddleware,
    ttl_seconds=3600,
    lock_ttl=10,
)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=100,  # 100 requests per minute
    bucket_capacity=120,  # Allow small bursts
)

app.include_router(auth.router)
app.include_router(users.router)
# app.include_router(kyc.router)
