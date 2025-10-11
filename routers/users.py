from fastapi import APIRouter, status

from schema.users import CreateUserRequest

from fastapi.requests import Request

from middleware.rate_limiting import limiter

router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"],
)

@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def create_user(payload: CreateUserRequest, request: Request):
    return {"message": "User created successfully", "user": payload}