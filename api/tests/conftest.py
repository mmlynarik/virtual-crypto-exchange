import asyncio
import os

import pytest

# Must be set before vce.settings is imported
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-test-secret-key-0123456789")


@pytest.fixture
def login_github(monkeypatch):
    """Logs in with GitHub through login_with_github, against a fake GitHub that has the given emails."""
    # Imported here: vce.settings, which reads JWT_SECRET_KEY, must not load before it's set above
    from tests.fakes import FakeUnitOfWork, github_client
    from vce.auth import services

    async def exchange_code_for_token(client, code):
        return "gh-token"

    monkeypatch.setattr(services, "exchange_code_for_token", exchange_code_for_token)

    def login(users, emails, github_id=7, failing_commits=0, concurrent_write=None):
        client = github_client(emails, github_id)
        uow = FakeUnitOfWork(users=users, failing_commits=failing_commits, concurrent_write=concurrent_write)
        return asyncio.run(services.login_with_github("code", uow, client))

    return login
