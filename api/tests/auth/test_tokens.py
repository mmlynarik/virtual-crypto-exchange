"""JWT access, refresh and pending link tokens (vce.auth.security)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest

from tests.fakes import (
    FAMILY_ID,
    GITHUB_ID,
    USER_ID,
    encode_token,
)
from vce.auth.exceptions import (
    InvalidToken,
)
from vce.auth.security import (
    create_access_token,
    create_github_pending_link_token,
    create_refresh_token,
    decode_token,
)
from vce.settings import (
    JWT_AUDIENCE,
)


def test_access_token_roundtrip():
    payload = decode_token(create_access_token(USER_ID), expected_type="access")
    assert payload["userId"] == USER_ID
    assert payload["aud"] == JWT_AUDIENCE


def test_refresh_token_roundtrip():
    record = create_refresh_token(USER_ID, FAMILY_ID)
    assert record.token is not None
    payload = decode_token(record.token, expected_type="refresh")
    assert payload["jti"] == record.jti
    assert payload["fam"] == FAMILY_ID
    assert record.family_id == FAMILY_ID
    assert record.user_id == USER_ID
    assert payload["userId"] == USER_ID


@pytest.mark.parametrize("claim", ["userId", "jti", "fam"])
@pytest.mark.parametrize("value", ["not-a-uuid", 123])
def test_malformed_refresh_uuid_claims_rejected(claim, value):
    claims: dict[str, Any] = {"type": "refresh", "jti": str(uuid.uuid7()), "fam": str(FAMILY_ID)}
    claims[claim] = value
    with pytest.raises(InvalidToken):
        decode_token(encode_token(**claims), expected_type="refresh")


def test_access_token_with_integer_user_id_rejected():
    # Tokens issued before user ids became UUIDs
    with pytest.raises(InvalidToken):
        decode_token(encode_token(userId=42), expected_type="access")


def test_token_type_is_enforced():
    refresh = create_refresh_token(USER_ID, FAMILY_ID).token
    assert refresh is not None
    with pytest.raises(InvalidToken):
        decode_token(refresh, expected_type="access")
    with pytest.raises(InvalidToken):
        decode_token(create_access_token(USER_ID), expected_type="refresh")


def test_github_pending_link_token_roundtrip():
    payload = decode_token(
        create_github_pending_link_token(USER_ID, GITHUB_ID), expected_type="github_pending_link"
    )
    assert payload["userId"] == USER_ID
    assert payload["githubId"] == GITHUB_ID


def test_github_pending_link_token_type_is_enforced():
    pending = create_github_pending_link_token(USER_ID, GITHUB_ID)
    with pytest.raises(InvalidToken):
        decode_token(pending, expected_type="access")
    with pytest.raises(InvalidToken):
        decode_token(pending, expected_type="refresh")

    refresh = create_refresh_token(USER_ID, FAMILY_ID).token
    assert refresh is not None
    for other in (create_access_token(USER_ID), refresh):
        with pytest.raises(InvalidToken):
            decode_token(other, expected_type="github_pending_link")


def test_github_pending_link_token_without_github_id_rejected():
    with pytest.raises(InvalidToken):
        decode_token(encode_token(type="github_pending_link"), expected_type="github_pending_link")


@pytest.mark.parametrize("value", ["12345678", 1.5, True, None])
def test_github_pending_link_token_non_int_github_id_rejected(value):
    with pytest.raises(InvalidToken):
        decode_token(
            encode_token(type="github_pending_link", githubId=value), expected_type="github_pending_link"
        )


def test_github_pending_link_token_malformed_user_id_rejected():
    with pytest.raises(InvalidToken):
        decode_token(
            encode_token(type="github_pending_link", githubId=GITHUB_ID, userId="not-a-uuid"),
            expected_type="github_pending_link",
        )


def test_wrong_audience_rejected():
    with pytest.raises(InvalidToken):
        decode_token(encode_token(aud="other"), expected_type="access")


def test_expired_token_rejected():
    with pytest.raises(InvalidToken):
        decode_token(encode_token(exp=datetime.now(UTC) - timedelta(seconds=1)), expected_type="access")


def test_bad_signature_rejected():
    token = jwt.encode(
        {"userId": str(USER_ID), "type": "access", "aud": JWT_AUDIENCE}, "other-secret", algorithm="HS256"
    )
    with pytest.raises(InvalidToken):
        decode_token(token, expected_type="access")
