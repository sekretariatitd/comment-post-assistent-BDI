import uuid

import jwt
import pytest

from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("s3cret")
    assert hashed != "s3cret"
    assert verify_password("s3cret", hashed)
    assert not verify_password("wrong", hashed)


def test_verify_password_rejects_malformed_hash() -> None:
    assert not verify_password("anything", "not-a-bcrypt-hash")


def test_access_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    payload = decode_access_token(create_access_token(user_id, "admin"))
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "admin"


def test_expired_token_rejected() -> None:
    token = create_access_token(uuid.uuid4(), "reviewer", expires_minutes=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_token_signed_with_other_key_rejected() -> None:
    claims = {"sub": str(uuid.uuid4()), "role": "admin", "exp": 9999999999}
    forged = jwt.encode(claims, "attacker-key-" + "x" * 32, "HS256")
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(forged)


def test_fernet_roundtrip() -> None:
    ciphertext = encrypt_secret("api-token-123")
    assert "api-token-123" not in ciphertext
    assert decrypt_secret(ciphertext) == "api-token-123"
