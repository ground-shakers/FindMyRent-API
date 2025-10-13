import redis
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from middleware.idempotency import IdempotencyMiddleware

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from models.users import User, Admin, LandLord, Tenant
from models.security import Permissions
from models.messages import Message, Chat
from models.listings import Listing

from dotenv import load_dotenv

from routers import auth, users

load_dotenv()


# noinspection PyUnusedLocal,PyShadowingNames
@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient("mongodb://localhost:27017")  # * Connect to MongoDB

    await init_beanie(
        database=client[os.getenv("DATABASE_NAME")],
        document_models=[User, Admin, LandLord, Tenant, Message, Chat, Listing, Permissions],
    )

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_connection = redis.from_url(
        redis_url, encoding="utf-8", decode_responses=True
    )

    yield
    client.close()
    await redis_connection.close()

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="FindMyRent API",
    description="A comprehensive API for managing rental services, including tenant records, landlord profiles, and rental agreements.",
    lifespan=lifespan,
)
app.state.limiter = limiter

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

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth.router)
app.include_router(users.router)
