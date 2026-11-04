from pydantic import BaseModel, EmailStr, field_validator

from api.services.security.password_policy import PasswordPolicyError, validate_password_policy


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        try:
            return validate_password_policy(v)
        except PasswordPolicyError as exc:
            raise ValueError(str(exc)) from exc


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None
    mfa_challenge_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    email: str | None
    name: str | None = None
    organization_id: int | None = None
    provider_id: str | None = None


class AuthResponse(BaseModel):
    token: str
    refresh_token: str | None = None
    expires_in: int | None = None
    mfa_required: bool = False
    mfa_challenge_token: str | None = None
    user: UserResponse | None = None


class MfaEnrollResponse(BaseModel):
    secret: str
    otpauth_uri: str
    recovery_codes: list[str]


class MfaVerifyRequest(BaseModel):
    totp_code: str
    secret: str | None = None


class MfaDisableRequest(BaseModel):
    totp_code: str
    password: str
