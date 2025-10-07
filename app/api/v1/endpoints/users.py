import hashlib

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserRead

router = APIRouter()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


@router.get("/", response_model=list[UserRead])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[UserRead]:
    result = await db.execute(select(User))
    return list(result.scalars().all())


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)) -> UserRead:
    email_exists = await db.execute(select(User).where(User.email == user_in.email))
    if email_exists.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        is_active=user_in.is_active,
        hashed_password=_hash_password(user_in.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
