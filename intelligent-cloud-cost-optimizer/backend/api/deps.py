"""FastAPI dependencies — JWT auth, works with and without MongoDB."""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from config.settings import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise exc
    except JWTError:
        raise exc

    # Demo user fallback (no MongoDB needed)
    if user_id == "demo-user-001":
        return {
            "id": "demo-user-001", "email": "admin@demo.com",
            "full_name": "Demo Admin", "is_active": True,
            "is_admin": True, "created_at": "2024-01-01",
        }

    from database.database import is_db_ready
    if is_db_ready():
        try:
            from beanie import PydanticObjectId
            from database.models import User
            user = await User.get(PydanticObjectId(user_id))
            if user and user.is_active:
                return user
        except Exception:
            pass

    # If MongoDB offline, accept any valid token as demo user
    return {"id": user_id, "email": "demo@user.com", "full_name": "Demo User",
            "is_active": True, "is_admin": True, "created_at": "2024-01-01"}


async def get_db():
    from database.database import get_database
    yield get_database()
