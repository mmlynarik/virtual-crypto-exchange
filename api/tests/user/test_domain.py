"""The User domain class."""

import ast
import inspect

import pytest

from tests.fakes import (
    GITHUB_ID,
    NODE_HASH,
    NODE_SALT,
    USER_ID,
)
from vce.user import domain as user_domain
from vce.user.domain import User
from vce.user.exceptions import CannotLinkGithub, WrongPassword


@pytest.mark.parametrize(
    "password, github_id, expected",
    [("x", None, True), ("x", 99, False), (None, None, False), (None, 99, False)],
)
def test_user_can_link_github(password, github_id, expected):
    salt = "y" if password else None
    user = User(id=USER_ID, email="a@b.c", password=password, salt=salt, github_id=github_id)
    assert user.can_link_github is expected


def test_user_from_password():
    user = User.from_password(email="a@example.com", password="correct horse")
    assert (user.email, user.github_id) == ("a@example.com", None)
    assert user.id.version == 7
    # Stored hashed and salted: the same password gets another hash for another user
    assert user.password not in (None, "correct horse")
    assert user.password != User.from_password(email="b@example.com", password="correct horse").password
    user.check_password("correct horse")
    with pytest.raises(WrongPassword):
        user.check_password("wrong horse")


def test_user_from_github():
    user = User.from_github(github_id=GITHUB_ID, email="octo@example.com")
    assert (user.github_id, user.email, user.password, user.salt) == (
        GITHUB_ID,
        "octo@example.com",
        None,
        None,
    )
    assert user.id.version == 7
    assert User.from_github(github_id=GITHUB_ID, email="octo@example.com").id != user.id


def test_user_link_github_sets_github_id():
    user = User(id=USER_ID, email="octo@example.com", password="x", salt="y", github_id=None)
    user.link_github(GITHUB_ID)
    assert user.github_id == GITHUB_ID


@pytest.mark.parametrize("password, github_id", [("x", 99), (None, None)], ids=["linked", "no-password"])
def test_user_link_github_rejected_when_it_cannot_link(password, github_id):
    salt = "y" if password else None
    user = User(id=USER_ID, email="octo@example.com", password=password, salt=salt, github_id=github_id)
    with pytest.raises(CannotLinkGithub):
        user.link_github(GITHUB_ID)
    assert user.github_id == github_id


def test_user_check_password():
    user = User(id=USER_ID, email="a@b.c", password=NODE_HASH, salt=NODE_SALT, github_id=None)
    user.check_password("pässword 123")  # doesn't raise
    with pytest.raises(WrongPassword):
        user.check_password("wrong password")


def test_user_without_password_rejects_any_password():
    user = User(id=USER_ID, email="a@b.c", password=None, salt=None, github_id=7)
    with pytest.raises(WrongPassword):
        user.check_password("")


def test_user_domain_does_not_depend_on_auth():
    # Auth builds on users, not the other way round: auth translates the user errors (WrongPassword,
    # CannotLinkGithub) into its own
    tree = ast.parse(inspect.getsource(user_domain))
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not [m for m in imported if m.split(".")[:2] == ["vce", "auth"]]
