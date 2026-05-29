"""Authentication routes - Login, Register, 2FA, Token refresh."""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime, timezone

from ...core.security import password_manager, jwt_manager, two_factor_auth, ip_whitelist
from ...core.logging import get_audit_logger
from ...db.repositories.user_repo import UserRepository
from ..dependencies import get_db, get_current_user

router = APIRouter()
audit_logger = get_audit_logger()


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None
    preferred_language: str = "en"

    @validator("password")
    def validate_password(cls, v):
        is_strong, msg = password_manager.is_strong_password(v)
        if not is_strong:
            raise ValueError(msg)
        return v

    @validator("username")
    def validate_username(cls, v):
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Username must be 3-50 characters")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, - and _")
        return v.lower()


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class TwoFARequest(BaseModel):
    token: str


class TwoFASetupResponse(BaseModel):
    secret: str
    qr_uri: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db=Depends(get_db)):
    """Register a new user account."""
    repo = UserRepository(db)

    if await repo.get_by_email(request.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    if await repo.get_by_username(request.username):
        raise HTTPException(status_code=400, detail="Username already taken")

    hashed_pw = password_manager.hash_password(request.password)
    user = await repo.create({
        "email": request.email,
        "username": request.username,
        "hashed_password": hashed_pw,
        "full_name": request.full_name,
        "preferred_language": request.preferred_language,
    })

    return {"message": "Account created successfully", "user_id": str(user.id)}


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db=Depends(get_db)
):
    """Login with email/username and password."""
    client_ip = request.client.host if request else "unknown"
    repo = UserRepository(db)

    # Find user by email or username
    user = await repo.get_by_email(form_data.username) or \
           await repo.get_by_username(form_data.username)

    if not user or not password_manager.verify_password(form_data.password, user.hashed_password):
        audit_logger.log_login(
            user_id=str(user.id) if user else "unknown",
            ip=client_ip,
            success=False
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    # IP whitelist check
    if user.ip_whitelist:
        allowed = user.ip_whitelist.split(",")
        if client_ip not in allowed:
            raise HTTPException(status_code=403, detail="IP not whitelisted")

    # If 2FA is enabled, return partial token requiring 2FA
    if user.two_fa_enabled:
        partial_token = jwt_manager.create_access_token(
            str(user.id),
            extra_claims={"requires_2fa": True},
        )
        return {
            "access_token": partial_token,
            "refresh_token": "",
            "token_type": "bearer",
            "expires_in": 300,  # 5 min to complete 2FA
            "requires_2fa": True,
        }

    # Update last login
    await repo.update(user.id, {"last_login": datetime.now(timezone.utc)})

    access_token = jwt_manager.create_access_token(str(user.id))
    refresh_token = jwt_manager.create_refresh_token(str(user.id))

    audit_logger.log_login(user_id=str(user.id), ip=client_ip, success=True)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=30 * 60,
    )


@router.post("/login/2fa", response_model=TokenResponse)
async def verify_2fa(
    body: TwoFARequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """Complete 2FA verification after initial login."""
    if not current_user.two_fa_enabled or not current_user.two_fa_secret:
        raise HTTPException(status_code=400, detail="2FA is not enabled for this account")

    from ...core.security import decrypt_api_key
    secret = decrypt_api_key(current_user.two_fa_secret)

    if not two_factor_auth.verify_token(secret, body.token):
        audit_logger.log_2fa_event(str(current_user.id), "verify", False)
        raise HTTPException(status_code=401, detail="Invalid 2FA token")

    audit_logger.log_2fa_event(str(current_user.id), "verify", True)

    access_token = jwt_manager.create_access_token(str(current_user.id))
    refresh_token = jwt_manager.create_refresh_token(str(current_user.id))

    return TokenResponse(access_token=access_token, refresh_token=refresh_token, expires_in=30 * 60)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest):
    """Refresh access token using refresh token."""
    try:
        user_id = jwt_manager.verify_refresh_token(body.refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    access_token = jwt_manager.create_access_token(user_id)
    refresh_token = jwt_manager.create_refresh_token(user_id)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token, expires_in=30 * 60)


@router.post("/2fa/setup", response_model=TwoFASetupResponse)
async def setup_2fa(current_user=Depends(get_current_user), db=Depends(get_db)):
    """Generate 2FA secret and QR code URI."""
    secret = two_factor_auth.generate_secret()
    qr_uri = two_factor_auth.get_provisioning_uri(secret, current_user.email)

    # Store encrypted secret temporarily (user must verify before enabling)
    from ...core.security import encrypt_api_key
    repo = UserRepository(db)
    await repo.update(current_user.id, {"two_fa_secret": encrypt_api_key(secret)})

    audit_logger.log_2fa_event(str(current_user.id), "setup", True)
    return TwoFASetupResponse(secret=secret, qr_uri=qr_uri)


@router.post("/2fa/enable")
async def enable_2fa(body: TwoFARequest, current_user=Depends(get_current_user), db=Depends(get_db)):
    """Enable 2FA after verifying the setup code."""
    if not current_user.two_fa_secret:
        raise HTTPException(status_code=400, detail="Run /2fa/setup first")

    from ...core.security import decrypt_api_key
    secret = decrypt_api_key(current_user.two_fa_secret)

    if not two_factor_auth.verify_token(secret, body.token):
        raise HTTPException(status_code=401, detail="Invalid token. Please scan QR again.")

    repo = UserRepository(db)
    await repo.update(current_user.id, {"two_fa_enabled": True})

    audit_logger.log_2fa_event(str(current_user.id), "enable", True)
    return {"message": "2FA enabled successfully"}


@router.post("/logout")
async def logout(current_user=Depends(get_current_user)):
    """Logout (client should discard tokens)."""
    return {"message": "Logged out successfully"}
