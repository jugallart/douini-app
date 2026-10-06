from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from psycopg import AsyncConnection

from douini.api.dependencies import get_current_user, get_db
from douini.auth.email import generate_token as gen_email_token
from douini.auth.email import hash_token as hash_email_token
from douini.auth.jwt import create_access_token, create_refresh_token, decode_token
from douini.auth.password import hash_password, is_common_password, verify_password
from douini.auth.rate_limit import check_rate_limit
from douini.auth.reset import generate_reset_token, hash_token as hash_reset_token
from douini.db.queries import auth as q
from douini.mailer import send_reset_email, send_verification_email
from douini.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup")
async def signup(request: Request, conn: AsyncConnection = Depends(get_db)):
    body = await request.json()
    email = body.get("email", "").lower().strip()
    password = body.get("password", "")

    if not email or "@" not in email:
        raise HTTPException(400, "Valid email required")
    if len(password) < 8:
        raise HTTPException(400, "Password must be >= 8 characters")
    if is_common_password(password):
        raise HTTPException(400, "Password too common")

    existing = await q.get_user_by_email(conn, email)
    if existing:
        raise HTTPException(409, "Email already registered")

    user_id = await q.create_user(conn, email, hash_password(password))
    await q.mark_email_verified(conn, user_id)
    await conn.commit()

    access = create_access_token(user_id, email)
    refresh, jti = create_refresh_token(user_id)
    await q.store_refresh_token(
        conn, user_id, jti,
        datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    await conn.commit()

    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


@router.post("/verify-email")
async def verify_email(request: Request, conn: AsyncConnection = Depends(get_db)):
    body = await request.json()
    token = body.get("token", "")
    token_hash = hash_email_token(token)

    record = await q.consume_email_verification_token(conn, token_hash)
    if not record:
        raise HTTPException(400, "Invalid or expired token")
    if record["used_at"]:
        raise HTTPException(400, "Token already used")
    if record["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(400, "Token expired")

    await q.mark_email_verified(conn, record["user_id"])
    await q.mark_email_verification_used(conn, record["id"])
    await conn.commit()
    return {"status": "verified"}


@router.post("/resend-verification")
async def resend_verification(
    request: Request, conn: AsyncConnection = Depends(get_db)
):
    check_rate_limit(request.client.host if request.client else "unknown")
    body = await request.json()
    email = body.get("email", "").lower().strip()

    user = await q.get_user_by_email(conn, email)
    if user and not user["email_verified"]:
        token = gen_email_token()
        await q.store_email_verification_token(
            conn, user["id"], hash_email_token(token),
            datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        await conn.commit()
        send_verification_email(email, token)

    return {"status": "sent"}


@router.post("/login")
async def login(request: Request, conn: AsyncConnection = Depends(get_db)):
    check_rate_limit(request.client.host if request.client else "unknown")
    body = await request.json()
    email = body.get("email", "").lower().strip()
    password = body.get("password", "")

    user = await q.get_user_by_email(conn, email)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")

    access = create_access_token(user["id"], user["email"])
    refresh, jti = create_refresh_token(user["id"])
    await q.store_refresh_token(
        conn, user["id"], jti,
        datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    await conn.commit()

    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


@router.post("/refresh")
async def refresh_token(request: Request, conn: AsyncConnection = Depends(get_db)):
    body = await request.json()
    token = body.get("refresh_token", "")

    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(401, "Invalid token")

    if payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid token type")

    jti = payload.get("jti")
    record = await q.get_refresh_token(conn, jti)
    if not record or record["invalidated_at"]:
        raise HTTPException(401, "Token revoked")
    if record["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(401, "Token expired")

    await q.invalidate_refresh_token(conn, jti)
    user_id = record["user_id"]
    user = await q.get_user_by_id(conn, user_id)
    if not user:
        raise HTTPException(401, "User not found")

    access = create_access_token(user_id, user["email"])
    new_refresh, new_jti = create_refresh_token(user_id)
    await q.store_refresh_token(
        conn, user_id, new_jti,
        datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    await conn.commit()

    return {"access_token": access, "refresh_token": new_refresh, "token_type": "bearer"}


@router.post("/logout")
async def logout(request: Request, conn: AsyncConnection = Depends(get_db)):
    body = await request.json()
    token = body.get("refresh_token", "")

    try:
        payload = decode_token(token)
    except ValueError:
        return {"status": "ok"}

    if payload.get("type") == "refresh":
        jti = payload.get("jti")
        if jti:
            await q.invalidate_refresh_token(conn, jti)
            await conn.commit()

    return {"status": "ok"}


@router.post("/forgot-password")
async def forgot_password(request: Request, conn: AsyncConnection = Depends(get_db)):
    check_rate_limit(request.client.host if request.client else "unknown")
    body = await request.json()
    email = body.get("email", "").lower().strip()

    user = await q.get_user_by_email(conn, email)
    if user:
        token = generate_reset_token()
        await q.store_reset_token(
            conn, user["id"], hash_reset_token(token),
            datetime.now(timezone.utc) + timedelta(hours=1),
        )
        await conn.commit()
        send_reset_email(email, token)

    return {"status": "sent"}


@router.post("/reset-password")
async def reset_password(request: Request, conn: AsyncConnection = Depends(get_db)):
    body = await request.json()
    token = body.get("token", "")
    new_password = body.get("password", "")

    if len(new_password) < 8:
        raise HTTPException(400, "Password must be >= 8 characters")
    if is_common_password(new_password):
        raise HTTPException(400, "Password too common")

    token_hash = hash_reset_token(token)
    record = await q.consume_reset_token(conn, token_hash)
    if not record:
        raise HTTPException(400, "Invalid or expired token")
    if record["used_at"]:
        raise HTTPException(400, "Token already used")
    if record["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(400, "Token expired")

    await q.update_password(conn, record["user_id"], hash_password(new_password))
    await q.invalidate_all_refresh_tokens(conn, record["user_id"])
    await q.mark_reset_used(conn, record["id"])
    await conn.commit()
    return {"status": "ok"}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {
        "id": user["id"],
        "email": user["email"],
        "email_verified": user["email_verified"],
        "pseudo": user.get("pseudo"),
        "prenom": user.get("prenom"),
    }
