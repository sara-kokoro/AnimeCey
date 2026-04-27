from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from database import get_db
from models import User
from schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserPublic,
)

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(User).where(or_(User.email == body.email, User.username == body.username))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email ou nom d'utilisateur déjà utilisé")
    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserPublic.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserPublic.model_validate(user))


@router.get("/me", response_model=UserPublic)
async def me(user: User = Depends(get_current_user)):
    return UserPublic.model_validate(user)


@router.put("/me", response_model=UserPublic)
async def update_me(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.username is not None:
        dup = await db.execute(
            select(User).where(User.username == body.username, User.id != user.id)
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Nom d'utilisateur déjà pris")
        user.username = body.username
    if body.email is not None:
        dup = await db.execute(
            select(User).where(User.email == body.email, User.id != user.id)
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email déjà utilisé")
        user.email = body.email
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url
    await db.commit()
    await db.refresh(user)
    return UserPublic.model_validate(user)


@router.put("/password")
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Ancien mot de passe incorrect")
    user.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"detail": "Mot de passe modifié"}


@router.delete("/me", status_code=204)
async def delete_account(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.delete(user)
    await db.commit()
