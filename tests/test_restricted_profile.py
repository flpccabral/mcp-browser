"""Security tests for MCP Browser restricted profile (Phase 7 — iFood pilot).

These tests verify that the restricted profile enforces:
- HTTPS-only navigation
- Exact hostname matching (no subdomains, no similar domains)
- chrome:// URL rejection
- Tool allowlist enforcement
- JavaScript hash allowlisting
- Token mandatory enforcement
- Loopback-only binding
- Insecure token permission detection
"""

import os
import stat
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from browser_mcp.restricted_profile import (
    ALLOWED_HOSTS,
    ALLOWED_SCRIPT_HASHES,
    ALLOWED_TOOLS,
    RestrictedProfile,
    check_token_permissions,
    compute_script_hash,
    is_domain_allowed,
    is_script_allowed,
    is_tool_allowed,
    sanitize_log_message,
)


# =============================================================================
# Domain allowlist tests
# =============================================================================

class TestDomainAllowlist:
    """Test navigate URL validation."""

    def test_allowed_https_domain(self):
        """Allowed domain with HTTPS passes."""
        assert is_domain_allowed("https://gestordepedidos.ifood.com.br/orders") is True
        assert is_domain_allowed("https://portal.ifood.com.br/dashboard") is True

    def test_http_rejected(self):
        """HTTP scheme is rejected even for allowed hosts."""
        assert is_domain_allowed("http://gestordepedidos.ifood.com.br/") is False
        assert is_domain_allowed("http://portal.ifood.com.br/") is False

    def test_chrome_url_rejected(self):
        """chrome:// URLs are rejected."""
        assert is_domain_allowed("chrome://settings") is False
        assert is_domain_allowed("chrome://version") is False

    def test_similar_domain_rejected(self):
        """Similar but different domain is rejected (typosquatting protection)."""
        assert is_domain_allowed("https://gestordepedidos.ifood.com.br.evil.com") is False
        assert is_domain_allowed("https://portal.ifood.com.br.hacker.net") is False

    def test_unauthorized_subdomain_rejected(self):
        """Subdomain of allowed host is rejected (exact match only)."""
        assert is_domain_allowed("https://api.portal.ifood.com.br") is False
        assert is_domain_allowed("https://admin.gestordepedidos.ifood.com.br") is False
        assert is_domain_allowed("https://sub.portal.ifood.com.br/data") is False

    def test_unauthorized_domain_rejected(self):
        """Completely unauthorized domain is rejected."""
        assert is_domain_allowed("https://google.com") is False
        assert is_domain_allowed("https://github.com") is False
        assert is_domain_allowed("https://evil.com") is False

    def test_malformed_url_rejected(self):
        """Malformed or empty URLs are rejected."""
        assert is_domain_allowed("not-a-url") is False
        assert is_domain_allowed("") is False

    def test_path_and_query_ignored_for_host(self):
        """Only hostname matters; paths and query strings don't affect validation."""
        assert is_domain_allowed("https://portal.ifood.com.br/api/orders?status=active") is True
        assert is_domain_allowed("https://gestordepedidos.ifood.com.br/?token=test#section") is True

    def test_port_in_url(self):
        """URLs with explicit ports are validated by hostname."""
        # urlparse strips the port for hostname
        assert is_domain_allowed("https://portal.ifood.com.br:443/test") is True


# =============================================================================
# Tool allowlist tests
# =============================================================================

class TestToolAllowlist:
    """Test tool name validation."""

    def test_allowed_tools_pass(self):
        """Allowed tools are accepted."""
        for tool in ALLOWED_TOOLS:
            assert is_tool_allowed(tool) is True

    def test_unauthorized_tool_rejected(self):
        """Tools outside the allowlist are rejected."""
        assert is_tool_allowed("browser_click") is False
        assert is_tool_allowed("browser_screenshot") is False
        assert is_tool_allowed("browser_type") is False
        assert is_tool_allowed("browser_network_start") is False
        assert is_tool_allowed("browser_manage_session") is False

    def test_non_existent_tool_rejected(self):
        """Non-existent tool is rejected."""
        assert is_tool_allowed("some_fake_tool") is False
        assert is_tool_allowed("") is False


# =============================================================================
# JavaScript hash tests
# =============================================================================

class TestJavaScriptAllowlist:
    """Test script hash validation."""

    def test_compute_hash_is_deterministic(self):
        """Same code produces same hash."""
        code = "document.title"
        h1 = compute_script_hash(code)
        h2 = compute_script_hash(code)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex is 64 chars

    def test_different_code_different_hash(self):
        """Different code produces different hash."""
        h1 = compute_script_hash("document.title")
        h2 = compute_script_hash("document.body.innerText")
        assert h1 != h2

    def test_script_rejected_when_allowlist_empty(self):
        """When allowlist is empty, all scripts are rejected (secure-by-default)."""
        assert len(ALLOWED_SCRIPT_HASHES) == 0
        assert is_script_allowed("document.title") is False
        assert is_script_allowed("var x = 1") is False

    def test_script_allowed_after_register(self):
        """After adding hash to allowlist, script is allowed."""
        code = "document.title"
        h = compute_script_hash(code)
        ALLOWED_SCRIPT_HASHES.add(h)
        try:
            assert is_script_allowed(code) is True
        finally:
            ALLOWED_SCRIPT_HASHES.discard(h)

    def test_script_with_unknown_hash_rejected(self):
        """Script whose hash is not in allowlist is rejected."""
        code = "alert('test')"
        assert is_script_allowed(code) is False


# =============================================================================
# validate_tool_call integration tests
# =============================================================================

class TestValidateToolCall:
    """Test the full validate_tool_call pipeline."""

    def test_navigate_rejected_in_default_mode(self, monkeypatch):
        """Default mode: no rejection, everything passes."""
        monkeypatch.delenv("IFOOD_RESTRICTED_MODE", raising=False)
        allowed, reason = RestrictedProfile.validate_tool_call(
            "browser_click", {"selector": "a"}
        )
        assert allowed is True
        assert reason == ""

    def test_disallowed_tool_rejected_in_restricted_mode(self, monkeypatch):
        """Restricted mode: tool outside allowlist is rejected."""
        monkeypatch.setenv("IFOOD_RESTRICTED_MODE", "1")
        allowed, reason = RestrictedProfile.validate_tool_call(
            "browser_click", {"selector": "a"}
        )
        assert allowed is False
        assert "REJECTED" in reason
        assert "browser_click" in reason

    def test_navigate_http_rejected(self, monkeypatch):
        """Restricted mode: HTTP URL is rejected."""
        monkeypatch.setenv("IFOOD_RESTRICTED_MODE", "1")
        allowed, reason = RestrictedProfile.validate_tool_call(
            "browser_navigate", {"url": "http://gestordepedidos.ifood.com.br/"}
        )
        assert allowed is False
        assert "REJECTED" in reason

    def test_navigate_unauthorized_domain_rejected(self, monkeypatch):
        """Restricted mode: unauthorized domain is rejected."""
        monkeypatch.setenv("IFOOD_RESTRICTED_MODE", "1")
        allowed, reason = RestrictedProfile.validate_tool_call(
            "browser_navigate", {"url": "https://google.com"}
        )
        assert allowed is False
        assert "REJECTED" in reason

    def test_navigate_allowed_domain_passes(self, monkeypatch):
        """Restricted mode: allowed HTTPS domain passes."""
        monkeypatch.setenv("IFOOD_RESTRICTED_MODE", "1")
        allowed, reason = RestrictedProfile.validate_tool_call(
            "browser_navigate", {"url": "https://portal.ifood.com.br/"}
        )
        assert allowed is True
        assert reason == ""

    def test_execute_js_unknown_hash_rejected(self, monkeypatch):
        """Restricted mode: script with unknown hash is rejected."""
        monkeypatch.setenv("IFOOD_RESTRICTED_MODE", "1")
        allowed, reason = RestrictedProfile.validate_tool_call(
            "browser_execute_javascript", {"code": "document.title"}
        )
        assert allowed is False
        assert "REJECTED" in reason
        assert "hash" in reason.lower() or "Script" in reason

    def test_execute_js_allowed_hash_passes(self, monkeypatch):
        """Restricted mode: script with registered hash passes."""
        code = "document.querySelector('h1').innerText"
        h = compute_script_hash(code)
        ALLOWED_SCRIPT_HASHES.add(h)
        monkeypatch.setenv("IFOOD_RESTRICTED_MODE", "1")
        try:
            allowed, reason = RestrictedProfile.validate_tool_call(
                "browser_execute_javascript", {"code": code}
            )
            assert allowed is True
            assert reason == ""
        finally:
            ALLOWED_SCRIPT_HASHES.discard(h)

    def test_get_content_passes_restricted(self, monkeypatch):
        """Restricted mode: get_content passes (no domain check needed)."""
        monkeypatch.setenv("IFOOD_RESTRICTED_MODE", "1")
        allowed, reason = RestrictedProfile.validate_tool_call(
            "browser_get_content", {}
        )
        assert allowed is True

    def test_navigate_missing_url_rejected(self, monkeypatch):
        """Restricted mode: navigate without URL is rejected."""
        monkeypatch.setenv("IFOOD_RESTRICTED_MODE", "1")
        allowed, reason = RestrictedProfile.validate_tool_call(
            "browser_navigate", {}
        )
        assert allowed is False
        assert "REJECTED" in reason

    def test_execute_js_missing_code_rejected(self, monkeypatch):
        """Restricted mode: execute_javascript without code is rejected."""
        monkeypatch.setenv("IFOOD_RESTRICTED_MODE", "1")
        allowed, reason = RestrictedProfile.validate_tool_call(
            "browser_execute_javascript", {}
        )
        assert allowed is False
        assert "REJECTED" in reason


# =============================================================================
# Token permission tests
# =============================================================================

class TestTokenPermissions:
    """Test token file permission enforcement."""

    def test_missing_token_file(self):
        """Missing token file returns failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)
            fake_token = fake_home / ".mcp_browser_token"
            # Ensure it doesn't exist
            assert not fake_token.exists()

            with mock.patch(
                "browser_mcp.restricted_profile.TOKEN_PATH", fake_token
            ):
                ok, msg = check_token_permissions()
                assert ok is False
                assert "not found" in msg.lower()

    def test_insecure_permissions(self, monkeypatch):
        """Token file with insecure permissions (0644) fails check."""
        if sys.platform == "win32":
            pytest.skip("POSIX-specific test")

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)
            fake_token = fake_home / ".mcp_browser_token"
            fake_token.write_text("test-token-content")
            fake_token.chmod(0o644)  # world-readable — insecure

            with mock.patch(
                "browser_mcp.restricted_profile.TOKEN_PATH", fake_token
            ):
                ok, msg = check_token_permissions()
                assert ok is False
                assert "insecure" in msg.lower() or "permissions" in msg.lower()

    def test_secure_permissions_0600(self, monkeypatch):
        """Token file with secure permissions (0600) passes check."""
        if sys.platform == "win32":
            pytest.skip("POSIX-specific test")

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)
            fake_token = fake_home / ".mcp_browser_token"
            fake_token.write_text("test-token-content")
            fake_token.chmod(0o600)  # owner read/write only

            with mock.patch(
                "browser_mcp.restricted_profile.TOKEN_PATH", fake_token
            ):
                ok, msg = check_token_permissions()
                assert ok is True
                assert msg == ""

    def test_secure_permissions_0400(self, monkeypatch):
        """Token file with read-only owner permissions (0400) passes check."""
        if sys.platform == "win32":
            pytest.skip("POSIX-specific test")

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)
            fake_token = fake_home / ".mcp_browser_token"
            fake_token.write_text("test-token-content")
            fake_token.chmod(0o400)  # owner read only

            with mock.patch(
                "browser_mcp.restricted_profile.TOKEN_PATH", fake_token
            ):
                ok, msg = check_token_permissions()
                assert ok is True
                assert msg == ""


# =============================================================================
# Bind address tests
# =============================================================================

class TestBindRestrictions:
    """Test loopback binding enforcement."""

    def test_get_bind_host_is_loopback(self):
        """Restricted profile forces 127.0.0.1 binding."""
        assert RestrictedProfile.get_bind_host() == "127.0.0.1"

    def test_check_startup_conditions_not_active(self, monkeypatch):
        """check_startup_conditions passes when restricted mode is off."""
        monkeypatch.delenv("IFOOD_RESTRICTED_MODE", raising=False)
        ok, msg = RestrictedProfile.check_startup_conditions()
        assert ok is True


# =============================================================================
# Log sanitization tests
# =============================================================================

class TestLogSanitization:
    """Test that log messages are sanitized in restricted mode."""

    def test_long_message_truncated(self):
        """Messages over 200 chars are truncated."""
        long_msg = "x" * 300
        result = sanitize_log_message(long_msg)
        assert len(result) <= 220  # ~200 + truncation marker
        assert "...[truncated]" in result

    def test_short_message_not_truncated(self):
        """Messages under 200 chars are preserved."""
        short_msg = "OK: navigate_example"
        result = sanitize_log_message(short_msg)
        assert result == short_msg

    def test_sanitize_log_dict_redacts_token(self):
        """Dictionary keys containing 'token' are redacted."""
        data = {"token": "secret123", "auth_token": "abc", "url": "https://example.com"}
        result = RestrictedProfile.sanitize_log_dict(data)
        assert result["token"] == "[REDACTED]"
        assert result["auth_token"] == "[REDACTED]"
        assert result["url"] == "https://example.com"

    def test_sanitize_log_dict_redacts_localstorage(self):
        """Dictionary keys containing 'localStorage' are redacted."""
        data = {"localStorage": {"user": "admin"}, "page": "home"}
        result = RestrictedProfile.sanitize_log_dict(data)
        assert result["localStorage"] == "[REDACTED]"

    def test_sanitize_log_dict_handles_nested(self):
        """Nested dictionaries are recursively sanitized."""
        data = {"event": {"token": "secret", "data": {"auth": "key"}}}
        result = RestrictedProfile.sanitize_log_dict(data)
        assert result["event"]["token"] == "[REDACTED]"
        assert result["event"]["data"]["auth"] == "[REDACTED]"


# =============================================================================
# Restricted mode disabled by default
# =============================================================================

class TestDefaultMode:
    """Verify that restricted mode is disabled by default."""

    def test_default_mode_inactive(self, monkeypatch):
        """Without env var, restricted mode is inactive."""
        monkeypatch.delenv("IFOOD_RESTRICTED_MODE", raising=False)
        assert RestrictedProfile.is_active() is False

    def test_default_mode_all_tools_pass(self, monkeypatch):
        """In default mode, all tools pass validation."""
        monkeypatch.delenv("IFOOD_RESTRICTED_MODE", raising=False)
        for tool in ["browser_click", "browser_screenshot", "browser_type",
                      "browser_navigate", "browser_manage_session"]:
            allowed, reason = RestrictedProfile.validate_tool_call(tool, {})
            assert allowed is True, f"Tool {tool} should pass in default mode"
            assert reason == ""

    def test_default_mode_no_domain_restriction(self, monkeypatch):
        """In default mode, any URL passes validate_tool_call for navigate."""
        monkeypatch.delenv("IFOOD_RESTRICTED_MODE", raising=False)
        allowed, _ = RestrictedProfile.validate_tool_call(
            "browser_navigate", {"url": "http://evil.com"}
        )
        assert allowed is True

    def test_default_mode_any_js_passes(self, monkeypatch):
        """In default mode, any JS passes validate_tool_call."""
        monkeypatch.delenv("IFOOD_RESTRICTED_MODE", raising=False)
        allowed, _ = RestrictedProfile.validate_tool_call(
            "browser_execute_javascript", {"code": "alert('xss')"}
        )
        assert allowed is True
