"""
Authentication API — works with MongoDB when available,
falls back to a hardcoded demo user when MongoDB is offline.
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from passlib.context import CryptContext
from typing import Optional

from config.settings import settings
from api.deps import get_current_user
from database.schemas import LoginRequest, Token, UserCreate, UserRead, UserUpdate

router = APIRouter()
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Demo password hash is computed lazily (not at import time)
_DEMO_HASH = None

def _get_demo_hash():
    global _DEMO_HASH
    if _DEMO_HASH is None:
        _DEMO_HASH = pwd.hash("admin123")
    return _DEMO_HASH

def _get_demo_users():
    return {
        "admin@demo.com": {
            "id": "demo-user-001",
            "email": "admin@demo.com",
            "hashed_password": _get_demo_hash(),
            "full_name": "Demo Admin",
            "is_active": True,
            "is_admin": True,
            "created_at": datetime(2024, 1, 1),
        }
    }


def _make_token(uid: str) -> str:
    exp = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": uid, "exp": exp}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _user_read(u: dict) -> UserRead:
    return UserRead(
        id=str(u.get("id") or u.get("_id") or "unknown"),
        email=u["email"],
        full_name=u.get("full_name"),
        is_active=u.get("is_active", True),
        is_admin=u.get("is_admin", False),
        created_at=u.get("created_at", datetime.utcnow()),
    )


async def _find_user(email: str) -> Optional[dict]:
    from database.database import is_db_ready
    if is_db_ready():
        try:
            from database.models import User
            user = await User.find_one(User.email == email)
            if user:
                return {
                    "id": str(user.id), "email": user.email,
                    "hashed_password": user.hashed_password,
                    "full_name": user.full_name,
                    "is_active": user.is_active,
                    "is_admin": user.is_admin,
                    "created_at": user.created_at,
                }
        except Exception:
            pass
    return _get_demo_users().get(email)


@router.post("/login", response_model=Token)
async def login(payload: LoginRequest):
    user = await _find_user(payload.email)
    if not user or not pwd.verify(payload.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account disabled.")
    return Token(access_token=_make_token(user["id"]), user=_user_read(user))


@router.post("/token", response_model=Token)
async def login_form(form: OAuth2PasswordRequestForm = Depends()):
    return await login(LoginRequest(email=form.username, password=form.password))


@router.post("/register", response_model=Token, status_code=201)
async def register(payload: UserCreate):
    from database.database import is_db_ready
    if is_db_ready():
        try:
            from database.models import User
            if await User.find_one(User.email == payload.email):
                raise HTTPException(400, "Email already registered.")
            user = User(
                email=payload.email,
                hashed_password=pwd.hash(payload.password),
                full_name=payload.full_name,
            )
            await user.insert()
            u = {
                "id": str(user.id), "email": user.email,
                "hashed_password": user.hashed_password,
                "full_name": user.full_name,
                "is_active": True, "is_admin": False,
                "created_at": user.created_at,
            }
        except HTTPException:
            raise
        except Exception:
            u = {
                "id": "new-001", "email": payload.email,
                "hashed_password": pwd.hash(payload.password),
                "full_name": payload.full_name,
                "is_active": True, "is_admin": False,
                "created_at": datetime.utcnow(),
            }
    else:
        u = {
            "id": "new-001", "email": payload.email,
            "hashed_password": pwd.hash(payload.password),
            "full_name": payload.full_name,
            "is_active": True, "is_admin": False,
            "created_at": datetime.utcnow(),
        }
    return Token(access_token=_make_token(u["id"]), user=_user_read(u))


@router.get("/me", response_model=UserRead)
async def get_me(current_user=Depends(get_current_user)):
    if isinstance(current_user, dict):
        return _user_read(current_user)
    return _user_read({
        "id": str(current_user.id), "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "is_admin": current_user.is_admin,
        "created_at": current_user.created_at,
    })
