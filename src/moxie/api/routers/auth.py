from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from moxie.api.auth import create_access_token, verify_password
from moxie.api.schemas.auth import LoginRequest, TokenResponse
from moxie.db.models import User
from moxie.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate with email + password; returns JWT access token."""
    user = db.query(User).filter(User.email == body.email).first()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user.id)
    return TokenResponse(access_token=access_token)
