from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger

from api.constants import OSS_ACCESS_TOKEN_MINUTES
from api.db import db_client
from api.db.models import UserModel
from api.enums import OrganizationConfigurationKey, PostHogEvent, UserConfigurationKey
from api.schemas.auth import (
    AuthResponse,
    LoginRequest,
    MfaDisableRequest,
    MfaEnrollResponse,
    MfaVerifyRequest,
    RefreshRequest,
    SignupRequest,
    UserResponse,
)
from api.services.auth.depends import create_user_configuration_with_mps_key, get_user
from api.services.configuration.ai_model_configuration import (
    convert_legacy_ai_model_configuration_to_v2,
)
from api.services.posthog_client import capture_event
from api.services.security.audit import (
    LOGIN_FAILURE,
    LOGIN_SUCCESS,
    MFA_DISABLED,
    MFA_ENABLED,
    TOKEN_REFRESH,
    TOKEN_REFRESH_REUSE,
    log_security_event,
)
from api.services.security.login_protection import (
    assert_login_allowed,
    record_login_failure,
    record_login_success,
)
from api.services.security.mfa import (
    generate_totp_secret,
    new_recovery_codes,
    provisioning_uri,
    verify_totp,
)
from api.utils.auth import (
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_jwt_token,
    hash_password,
    verify_password,
)

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


def _to_user_response(user: UserModel) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        organization_id=user.selected_organization_id,
        provider_id=user.provider_id,
    )


def _tokens(user: UserModel) -> AuthResponse:
    email = user.email or ""
    return AuthResponse(
        token=create_access_token(user.id, email),
        refresh_token=create_refresh_token(user.id, email),
        expires_in=OSS_ACCESS_TOKEN_MINUTES * 60,
        user=_to_user_response(user),
    )


async def _load_security(user_id: int) -> dict:
    return (
        await db_client.get_user_configuration_value(
            user_id, UserConfigurationKey.SECURITY.value
        )
        or {}
    )


async def _save_security(user_id: int, state: dict) -> None:
    await db_client.upsert_user_configuration_value(
        user_id, UserConfigurationKey.SECURITY.value, state
    )


@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignupRequest):
    existing_user = await db_client.get_user_by_email(request.email)
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = await db_client.create_user_with_email(
        email=request.email,
        password_hash=hash_password(request.password),
        name=request.name,
    )

    organization, _ = await db_client.get_or_create_organization_by_provider_id(
        org_provider_id=f"org_{user.provider_id}", user_id=user.id
    )
    await db_client.add_user_to_organization(user.id, organization.id)
    await db_client.update_user_selected_organization(user.id, organization.id)
    user.selected_organization_id = organization.id

    try:
        mps_config = await create_user_configuration_with_mps_key(
            user.id, organization.id, user.provider_id
        )
        if mps_config:
            await db_client.update_user_configuration(user.id, mps_config)
            model_config_v2 = convert_legacy_ai_model_configuration_to_v2(mps_config)
            await db_client.upsert_configuration(
                organization.id,
                OrganizationConfigurationKey.MODEL_CONFIGURATION_V2.value,
                model_config_v2.model_dump(mode="json", exclude_none=True),
            )
    except Exception:
        logger.warning(
            "Failed to create default configuration for OSS user", exc_info=True
        )

    capture_event(
        distinct_id=str(user.provider_id),
        event=PostHogEvent.SIGNED_UP,
        properties={"organization_id": organization.id, "auth_provider": "local"},
    )
    return _tokens(user)


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, http_request: Request):
    identity = f"{request.email.lower()}|{(http_request.client.host if http_request.client else 'unknown')}"
    assert_login_allowed(identity)

    user = await db_client.get_user_by_email(request.email)
    if not user or not user.password_hash or not verify_password(request.password, user.password_hash):
        record_login_failure(identity)
        await log_security_event(
            action=LOGIN_FAILURE,
            resource_type="session",
            outcome="denied",
            actor_user_id=getattr(user, "id", None),
            organization_id=getattr(user, "selected_organization_id", None),
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    state = await _load_security(user.id)
    if state.get("mfa_enabled"):
        code = request.totp_code or ""
        totp_ok = verify_totp(state.get("totp_secret", ""), code)
        recovery = state.get("recovery_codes") or []
        recovery_ok = code in recovery
        if not totp_ok and not recovery_ok:
            record_login_failure(identity)
            raise HTTPException(status_code=401, detail="Multi-factor authentication required")
        if recovery_ok:
            state["recovery_codes"] = [item for item in recovery if item != code]
            await _save_security(user.id, state)

    record_login_success(identity)
    await log_security_event(
        action=LOGIN_SUCCESS,
        resource_type="session",
        actor_user_id=user.id,
        organization_id=user.selected_organization_id,
    )
    capture_event(
        distinct_id=str(user.provider_id),
        event=PostHogEvent.SIGNED_IN,
        properties={"organization_id": user.selected_organization_id, "auth_provider": "local"},
    )
    return _tokens(user)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(body: RefreshRequest):
    try:
        payload = decode_jwt_token(body.refresh_token, expected_type=TOKEN_TYPE_REFRESH)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from None

    user = await db_client.get_user_by_id(int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    state = await _load_security(user.id)
    jti = payload.get("jti")
    used = set(state.get("used_refresh_jtis") or [])
    if state.get("refresh_family_revoked") or (jti and jti in used):
        state["refresh_family_revoked"] = True
        await _save_security(user.id, state)
        await log_security_event(
            action=TOKEN_REFRESH_REUSE,
            resource_type="session",
            outcome="denied",
            actor_user_id=user.id,
            organization_id=user.selected_organization_id,
        )
        raise HTTPException(status_code=401, detail="Refresh token reused")
    if jti:
        used.add(jti)
        state["used_refresh_jtis"] = list(used)[-50:]
        await _save_security(user.id, state)
    await log_security_event(
        action=TOKEN_REFRESH,
        resource_type="session",
        actor_user_id=user.id,
        organization_id=user.selected_organization_id,
    )
    return _tokens(user)


@router.post("/mfa/enroll", response_model=MfaEnrollResponse)
async def enroll_mfa(user: UserModel = Depends(get_user)):
    secret = generate_totp_secret()
    codes = new_recovery_codes()
    state = await _load_security(user.id)
    state["pending_totp_secret"] = secret
    state["pending_recovery_codes"] = codes
    await _save_security(user.id, state)
    return MfaEnrollResponse(
        secret=secret,
        otpauth_uri=provisioning_uri(email=user.email or str(user.id), secret=secret),
        recovery_codes=codes,
    )


@router.post("/mfa/verify")
async def verify_mfa(body: MfaVerifyRequest, user: UserModel = Depends(get_user)):
    state = await _load_security(user.id)
    secret = body.secret or state.get("pending_totp_secret") or state.get("totp_secret")
    if not secret or not verify_totp(secret, body.totp_code):
        raise HTTPException(status_code=400, detail="Invalid authenticator code")
    state["mfa_enabled"] = True
    state["totp_secret"] = secret
    state["recovery_codes"] = (
        state.get("pending_recovery_codes") or state.get("recovery_codes") or []
    )
    state.pop("pending_totp_secret", None)
    await _save_security(user.id, state)
    await log_security_event(
        action=MFA_ENABLED,
        resource_type="user",
        actor_user_id=user.id,
        organization_id=user.selected_organization_id,
        resource_id=str(user.id),
    )
    return {"mfa_enabled": True}


@router.post("/mfa/disable")
async def disable_mfa(body: MfaDisableRequest, user: UserModel = Depends(get_user)):
    if not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid password")
    state = await _load_security(user.id)
    if not verify_totp(state.get("totp_secret", ""), body.totp_code):
        raise HTTPException(status_code=400, detail="Invalid authenticator code")
    await _save_security(user.id, {"mfa_enabled": False})
    await log_security_event(
        action=MFA_DISABLED,
        resource_type="user",
        actor_user_id=user.id,
        organization_id=user.selected_organization_id,
        resource_id=str(user.id),
    )
    return {"mfa_enabled": False}


@router.get("/me", response_model=UserResponse)
async def get_current_user(user: UserModel = Depends(get_user)):
    return _to_user_response(user)
