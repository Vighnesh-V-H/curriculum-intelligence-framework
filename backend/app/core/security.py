import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import Settings, get_settings


class TokenError(Exception):
    pass


class PasswordService:
    def __init__(self) -> None:
        self._hasher = PasswordHash.recommended()
        self._dummy_hash = self._hasher.hash("dummy-password-for-timing")

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return self._hasher.verify(password, password_hash)

    def verify_dummy(self, password: str) -> None:
        self._hasher.verify(password, self._dummy_hash)


class JwtService:
    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret.get_secret_value()
        self._algorithm = settings.jwt_algorithm
        self._expire_minutes = settings.access_token_expire_minutes

    @property
    def expires_in_seconds(self) -> int:
        return self._expire_minutes * 60

    def create_access_token(
        self,
        user_id: uuid.UUID,
        username: str,
        roles: list[str],
        expires_delta: timedelta | None = None,
    ) -> str:
        issued_at = datetime.now(UTC)
        expires_at = issued_at + (expires_delta or timedelta(minutes=self._expire_minutes))
        payload = {
            "sub": str(user_id),
            "username": username,
            "roles": roles,
            "iat": issued_at,
            "exp": expires_at,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_token(self, token: str) -> dict:
        try:
            return jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except InvalidTokenError as exc:
            raise TokenError("Invalid or expired token") from exc


@lru_cache
def get_password_service() -> PasswordService:
    return PasswordService()


@lru_cache
def get_jwt_service() -> JwtService:
    return JwtService(get_settings())
