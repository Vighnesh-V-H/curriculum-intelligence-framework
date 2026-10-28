import uuid

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import JwtService, PasswordService, TokenError


def test_password_hash_round_trip():
    passwords = PasswordService()
    password_hash = passwords.hash("Password123!")

    assert password_hash != "Password123!"
    assert passwords.verify("Password123!", password_hash)
    assert not passwords.verify("wrong", password_hash)


def test_jwt_round_trip():
    service = JwtService(get_settings())
    user_id = uuid.uuid4()

    token = service.create_access_token(user_id, "faculty1", ["FACULTY"])
    payload = service.decode_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["username"] == "faculty1"
    assert payload["roles"] == ["FACULTY"]


def test_jwt_rejects_token_signed_with_other_secret():
    service = JwtService(get_settings())
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "roles": []},
        "another-secret-that-is-at-least-32-characters",
        algorithm="HS256",
    )

    with pytest.raises(TokenError):
        service.decode_token(token)
