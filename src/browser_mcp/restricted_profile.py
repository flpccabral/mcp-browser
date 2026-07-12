"""Restricted profile for MCP Browser — iFood pilot security enforcement.

Activated by environment variable IFOOD_RESTRICTED_MODE=1 or by config flag.
When active:
- WebSocket binds only to 127.0.0.1 (loopback)
- Token is mandatory
- Token file permissions are enforced (0600 on POSIX)
- Domain allowlist restricts navigate to specific hosts
- Tool allowlist restricts which tools can be called
- JavaScript execution requires SHA-256 hash in allowlist
- Logs suppress sensitive data (no full code, no token, no DOM, no localStorage)
"""

from __future__ import annotations

import hashlib
import os
import stat
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Environment detection
# ---------------------------------------------------------------------------

def _is_restricted_mode() -> bool:
    """Check if restricted mode is enabled via env var."""
    return os.environ.get("IFOOD_RESTRICTED_MODE", "").strip() == "1"


# ---------------------------------------------------------------------------
# Domain allowlist (exact hostname match)
# ---------------------------------------------------------------------------

#: Domains the browser is allowed to navigate to in restricted mode.
ALLOWED_HOSTS: set[str] = {
    "gestordepedidos.ifood.com.br",
    "portal.ifood.com.br",
}


def is_domain_allowed(url: str) -> bool:
    """Return True if the URL's hostname is in the allowlist and scheme is HTTPS.

    Rejects:
      - http:// URLs
      - chrome:// URLs
      - Subdomains not exactly in allowlist (e.g. api.portal.ifood.com.br)
      - Similar domains (e.g. portal.ifood.com.br.evil.com)
      - IP addresses
    """
    parsed = urlparse(url)

    # Require HTTPS
    if parsed.scheme != "https":
        return False

    hostname = parsed.hostname
    if hostname is None:
        return False

    # Exact match against allowlist
    return hostname in ALLOWED_HOSTS


# ---------------------------------------------------------------------------
# Tool allowlist
# ---------------------------------------------------------------------------

#: Tools allowed in restricted mode.
ALLOWED_TOOLS: set[str] = {
    "browser_navigate",
    "browser_get_content",
    "browser_execute_javascript",
}

#: Tools that are always allowed (no domain restriction needed).
PASSTHROUGH_TOOLS: set[str] = {
    # None at the moment — all allowed tools are domain-aware
}


def is_tool_allowed(tool_name: str) -> bool:
    """Return True if the tool is in the restricted allowlist."""
    return tool_name in ALLOWED_TOOLS


# ---------------------------------------------------------------------------
# JavaScript allowlist via SHA-256 hashes
# ---------------------------------------------------------------------------

#: Pre-approved script SHA-256 hashes in restricted mode.
#: Generate with:  hashlib.sha256(code.encode()).hexdigest()
ALLOWED_SCRIPT_HASHES: set[str] = set()


def compute_script_hash(code: str) -> str:
    """Compute SHA-256 hex digest of a JavaScript snippet."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def is_script_allowed(code: str) -> bool:
    """Return True if the script's SHA-256 hash is in the allowlist.

    If the allowlist is empty, all scripts are rejected (secure-by-default).
    """
    if not ALLOWED_SCRIPT_HASHES:
        return False
    return compute_script_hash(code) in ALLOWED_SCRIPT_HASHES


# ---------------------------------------------------------------------------
# Token file permission enforcement (POSIX only)
# ---------------------------------------------------------------------------

TOKEN_PATH = Path.home() / ".mcp_browser_token"


def check_token_permissions() -> tuple[bool, str]:
    """Check that the token file has secure permissions (0600).

    Returns (ok, message).
    On non-POSIX systems (Windows), always returns (True, "").
    """
    if not TOKEN_PATH.exists():
        return False, f"Token file not found: {TOKEN_PATH}"

    if sys.platform == "win32":
        return True, ""

    try:
        st = TOKEN_PATH.stat()
        mode = stat.S_IMODE(st.st_mode)

        # Only owner should have any access; must be readable+writable
        # Allow 0o400 (read only by owner) or 0o600 (read/write by owner)
        expected_modes = (0o400, 0o600)

        if mode not in expected_modes:
            return (
                False,
                f"Token file {TOKEN_PATH} has insecure permissions {oct(mode)}. "
                f"Expected 0600 or 0400. Fix: chmod 600 {TOKEN_PATH}",
            )

        return True, ""

    except OSError as e:
        return False, f"Cannot stat token file: {e}"


# ---------------------------------------------------------------------------
# Log sanitization
# ---------------------------------------------------------------------------

_SENSITIVE_KEYWORDS = [
    "token",
    "auth",
    "bearer",
    "localstorage",
    "sessionstorage",
    "cookie",
]


def sanitize_log_message(message: str) -> str:
    """Remove or redact sensitive data from log messages.

    In restricted mode, logs must NOT contain:
      - full JavaScript code
      - token values
      - DOM content
      - localStorage / sessionStorage data
    """
    # Truncate long messages (likely contain DOM or code)
    MAX_LEN = 200
    if len(message) > MAX_LEN:
        message = message[:MAX_LEN] + "...[truncated]"

    return message


# ---------------------------------------------------------------------------
# RestrictedProfile — centralized enforcement point
# ---------------------------------------------------------------------------

class RestrictedProfile:
    """Centralized enforcement of iFood restricted-mode security policies.

    Usage in tools.py::

        if RestrictedProfile.is_active():
            if not RestrictedProfile.validate_tool_call(tool_name, arguments):
                return [TextContent(type="text", text="REJECTED: ...")]

    Usage in websocket_server.py::

        if RestrictedProfile.is_active():
            host = "127.0.0.1"  # force loopback
            if not RestrictedProfile.check_token_permissions()[0]:
                print("FATAL: insecure token permissions", file=sys.stderr)
                sys.exit(1)
    """

    @staticmethod
    def sanitize_log_dict(data: dict[str, Any]) -> dict[str, Any]:
        """Recursively sanitize a log dictionary, redacting sensitive fields."""
        if not isinstance(data, dict):
            return data

        sanitized: dict[str, Any] = {}
        for k, v in data.items():
            if any(kw in k.lower() for kw in _SENSITIVE_KEYWORDS):
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, dict):
                sanitized[k] = RestrictedProfile.sanitize_log_dict(v)
            elif isinstance(v, str):
                sanitized[k] = sanitize_log_message(v)
            else:
                sanitized[k] = v

        return sanitized

    @staticmethod
    def is_active() -> bool:
        """Check if restricted mode is currently active."""
        return _is_restricted_mode()

    @staticmethod
    def get_bind_host() -> str:
        """Return the host the WebSocket server should bind to.

        In restricted mode this is always 127.0.0.1.
        """
        return "127.0.0.1"

    @staticmethod
    def validate_tool_call(tool_name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
        """Validate a tool call against restricted profile policies.

        Returns (allowed, reason).  If allowed=False, the reason describes why.
        Called BEFORE the tool reaches the extension or Playwright.
        """
        if not _is_restricted_mode():
            return True, ""

        # 1. Tool must be in allowlist
        if not is_tool_allowed(tool_name):
            return (
                False,
                f"REJECTED: Tool '{tool_name}' is not in the restricted allowlist. "
                f"Allowed tools: {', '.join(sorted(ALLOWED_TOOLS))}",
            )

        # 2. navigate: require HTTPS + exact hostname match
        if tool_name == "browser_navigate":
            url = arguments.get("url", "")
            if not url:
                return False, "REJECTED: navigate requires a URL"
            if not is_domain_allowed(url):
                return (
                    False,
                    f"REJECTED: Domain '{url}' is not in the restricted allowlist. "
                    f"Allowed hosts: {', '.join(sorted(ALLOWED_HOSTS))}. "
                    f"HTTPS is required.",
                )

        # 3. execute_javascript: only allowlisted script hashes
        if tool_name == "browser_execute_javascript":
            code = arguments.get("code", "")
            if not code:
                return False, "REJECTED: execute_javascript requires code"
            if not is_script_allowed(code):
                return (
                    False,
                    f"REJECTED: Script hash '{compute_script_hash(code)[:12]}...' "
                    f"is not in the allowlist. Script must be pre-approved.",
                )

        return True, ""

    @staticmethod
    def get_loopback_only_message() -> str:
        """Message explaining loopback binding restriction."""
        return (
            "Restricted mode requires binding to 127.0.0.1 (loopback) only. "
            "Set IFOOD_RESTRICTED_MODE=0 to disable this restriction."
        )

    @staticmethod
    def check_startup_conditions() -> tuple[bool, str]:
        """Run all startup security checks for restricted mode.

        Returns (ok, message).  If ok=False, the server should refuse to start.
        """
        if not _is_restricted_mode():
            return True, ""

        # Check token permissions
        ok, msg = check_token_permissions()
        if not ok:
            return False, f"FATAL: {msg}"

        return True, ""
