"""Tests for HR email allowlist authorization."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, status

from workloom.core.config import Settings
from workloom.core.dependencies import _parse_hr_allowlist, require_hr_email
from workloom.models.user import User


def _fake_user(email: str) -> User:
    """Build a User stub with just the email field set."""
    user = MagicMock(spec=User)
    user.email = email
    return user


def _settings_with(emails: str) -> Settings:
    """Build a Settings instance with hr_allowed_emails preset."""
    s = MagicMock(spec=Settings)
    s.hr_allowed_emails = emails
    return s


@pytest.mark.unit
class TestParseHrAllowlist:
    """Tests for _parse_hr_allowlist normalization."""

    def test_empty_string_returns_empty_set(self) -> None:
        assert _parse_hr_allowlist("") == frozenset()

    def test_whitespace_only_returns_empty_set(self) -> None:
        assert _parse_hr_allowlist("   , , ") == frozenset()

    def test_lowercases_and_trims(self) -> None:
        result = _parse_hr_allowlist(" Admin@Acme.Example , hr@acme.example ")
        assert result == frozenset({"admin@acme.example", "hr@acme.example"})

    def test_dedups(self) -> None:
        result = _parse_hr_allowlist("a@x.example,a@x.example,A@X.EXAMPLE")
        assert result == frozenset({"a@x.example"})


@pytest.mark.unit
class TestRequireHrEmail:
    """Tests for require_hr_email dependency."""

    async def test_allows_user_in_allowlist(self) -> None:
        user = _fake_user("hr@acme.example")
        settings = _settings_with("admin@acme.example,hr@acme.example")
        result = await require_hr_email(user, settings)
        assert result is user

    async def test_case_insensitive_match(self) -> None:
        user = _fake_user("HR@Acme.Example")
        settings = _settings_with("hr@acme.example")
        result = await require_hr_email(user, settings)
        assert result is user

    async def test_rejects_user_not_in_allowlist(self) -> None:
        user = _fake_user("employee@acme.example")
        settings = _settings_with("admin@acme.example,hr@acme.example")
        with pytest.raises(HTTPException) as exc_info:
            await require_hr_email(user, settings)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    async def test_empty_allowlist_rejects_everyone(self) -> None:
        """Fail-closed: empty HR_ALLOWED_EMAILS means no HR access."""
        user = _fake_user("admin@acme.example")
        settings = _settings_with("")
        with pytest.raises(HTTPException) as exc_info:
            await require_hr_email(user, settings)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
