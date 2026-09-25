import hashlib
import hmac
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, Header, Query
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from .database import get_db
from . import models

SECRET = os.environ.get("GST_SECRET", "gst-invoice-dev-secret-change-me")
ALGO = "HS256"


def hash_password(password: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), SECRET.encode(), 120000).hex()


def verify_password(password: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_password(password), hashed)


def create_token(user: models.User) -> str:
    payload = {
        "sub": str(user.id),
        "cid": user.company_id,
        "role": user.role,
        "exp": datetime.utcnow() + timedelta(hours=18),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGO)


def current_user(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> models.User:
    raw = None
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization.split(" ", 1)[1]
    elif token:
        raw = token
    if not raw:
        raise HTTPException(401, "Not authenticated")
    try:
        data = jwt.decode(raw, SECRET, algorithms=[ALGO])
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")
    user = db.get(models.User, int(data["sub"]))
    if not user or not user.active:
        raise HTTPException(401, "User not found")
    return user


def require_roles(*roles):
    def _inner(user: models.User = Depends(current_user)):
        if user.role not in roles and user.role != "OWNER":
            raise HTTPException(403, "Insufficient permissions")
        return user
    return _inner
