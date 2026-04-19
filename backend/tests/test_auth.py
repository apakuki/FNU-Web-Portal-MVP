import uuid

import pytest

from src.backend.auth import (
    create_access_token,
    decode_token,
    hash_jti,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "my-secure-password"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2


class TestJwt:
    def test_create_and_decode(self):
        user_id = str(uuid.uuid4())
        token, jti = create_access_token(user_id, "student")
        payload = decode_token(token)
        assert payload["sub"] == user_id
        assert payload["role"] == "student"
        assert payload["jti"] == jti

    def test_jti_hash_is_deterministic(self):
        jti = "test-jti-value"
        assert hash_jti(jti) == hash_jti(jti)

    def test_invalid_token_raises(self):
        with pytest.raises(Exception):
            decode_token("not-a-valid-token")
