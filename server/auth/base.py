"""
Base classes for the NetAlertX pluggable authentication system.

Each concrete provider must implement :class:`AuthProvider` and return an
:class:`AuthResult` object so callers never need to import provider-specific
modules directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AuthResult:
    """Outcome of an authentication attempt."""

    success: bool
    username: str = ""
    provider: str = ""
    error: str = ""

    @classmethod
    def ok(cls, username: str, provider: str) -> "AuthResult":
        return cls(success=True, username=username, provider=provider)

    @classmethod
    def fail(cls, provider: str, error: str = "Invalid credentials") -> "AuthResult":
        return cls(success=False, provider=provider, error=error)


class AuthProvider(ABC):
    """Abstract base class every auth provider must implement."""

    #: Short lowercase identifier shown in the ``provider`` field of AuthResult
    name: str = "unknown"

    @abstractmethod
    def authenticate(self, username: str, password: str) -> AuthResult:
        """
        Validate *username* / *password* and return an :class:`AuthResult`.

        Implementations MUST NOT raise exceptions for invalid credentials —
        they should return ``AuthResult.fail(...)`` instead.  Only
        infrastructure errors (e.g. LDAP server unreachable) should propagate
        as exceptions so the caller can decide how to handle them gracefully.
        """
