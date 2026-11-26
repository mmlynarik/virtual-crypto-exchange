"""Password hashing (vce.utils), compatible with the web app's hasher."""

from tests.fakes import (
    NODE_HASH,
    NODE_SALT,
)
from vce.utils import hash_password, verify_password


def test_hash_password_matches_node_scrypt():
    assert hash_password("pässword 123", NODE_SALT) == NODE_HASH


def test_verify_password():
    assert verify_password("pässword 123", NODE_HASH, NODE_SALT)
    assert not verify_password("wrong password", NODE_HASH, NODE_SALT)
