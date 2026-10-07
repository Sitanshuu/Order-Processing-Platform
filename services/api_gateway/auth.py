from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from shared.config import settings
from shared.exceptions import AuthenticationException

security = HTTPBearer(auto_error=False)


class TokenData(BaseModel):
    user_id: str
    username: str
    role: str = "customer"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[TokenData]:
    """
    Validates JWT token from Authorization Bearer header.
    Returns TokenData or None for public routes.
    """
    if not credentials:
        return None

    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        username: str = payload.get("username", "user")
        role: str = payload.get("role", "customer")
        if user_id is None:
            raise AuthenticationException("Could not validate credentials: sub missing.")
        return TokenData(user_id=user_id, username=username, role=role)
    except JWTError:
        raise AuthenticationException("Invalid or expired access token.")


async def require_auth(current_user: Optional[TokenData] = Depends(get_current_user)) -> TokenData:
    if not current_user:
        raise AuthenticationException("Authentication required. Please provide a Bearer token.")
    return current_user
