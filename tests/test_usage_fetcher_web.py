"""Unit tests for Phase 4 fetch_web_usage() and auth priority order.

Uses unittest.mock to avoid real network calls. All tests are offline.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest

from core.usage_fetcher import (
    fetch_web_usage,
    _discover_org_id,
    _read_auth_cookies,
    _migrate_config_to_keyring,
)


# ---------------------------------------------------------------------------
# fetch_web_usage: Teams/Enterprise branch (extra_usage)
# ---------------------------------------------------------------------------

def _make_teams_response(utilization=64.26, is_enabled=True):
    return {
        "five_hour": None,
        "seven_day": None,
        "extra_usage": {
            "is_enabled": is_enabled,
            "monthly_limit": 75000,
            "used_credits": 48197.0,
            "utilization": utilization,
            "currency": "USD",
            "disabled_reason": None,
        },
    }

def _make_max_response(utilization=45.0, resets_at="2025-01-01T12:00:00Z"):
    return {
        "five_hour": {
            "utilization": utilization,
            "resets_at": resets_at,
        },
        "seven_day": None,
        "extra_usage": None,
    }

CONFIG_DIR = Path.home() / ".claude-monitor"


@patch("core.usage_fetcher._read_auth_cookies", return_value=("sk_test", None))
@patch("core.usage_fetcher.httpx")
def test_fetch_web_usage_teams_branch(mock_httpx, mock_auth, tmp_path):
    """Teams account: five_hour=null, extra_usage.utilization=64.26 → WebUsageData."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = _make_teams_response(utilization=64.26)
    resp.raise_for_status = MagicMock()
    mock_httpx.get.return_value = resp

    result = fetch_web_usage("org-abc", tmp_path)

    assert result is not None
    assert result.utilization_pct == pytest.approx(64.26)
    assert result.plan_limit_tokens is None  # Teams: monthly_limit is cents, not tokens


@patch("core.usage_fetcher._read_auth_cookies", return_value=("sk_test", None))
@patch("core.usage_fetcher.httpx")
def test_fetch_web_usage_max_branch(mock_httpx, mock_auth, tmp_path):
    """Max/Pro account: five_hour.utilization=45.0 with resets_at → WebUsageData."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = _make_max_response(utilization=45.0, resets_at="2025-06-01T12:00:00Z")
    resp.raise_for_status = MagicMock()
    mock_httpx.get.return_value = resp

    result = fetch_web_usage("org-xyz", tmp_path)

    assert result is not None
    assert result.utilization_pct == pytest.approx(45.0)
    assert result.reset_at == datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


@patch("core.usage_fetcher._read_auth_cookies", return_value=("sk_test", None))
@patch("core.usage_fetcher.httpx")
def test_fetch_web_usage_401_returns_none(mock_httpx, mock_auth, tmp_path):
    """401 auth error → returns None without raising."""
    resp = MagicMock()
    resp.status_code = 401
    mock_httpx.get.return_value = resp

    result = fetch_web_usage("org-abc", tmp_path)
    assert result is None


@patch("core.usage_fetcher._read_auth_cookies", return_value=("sk_test", None))
@patch("core.usage_fetcher.httpx")
def test_fetch_web_usage_403_returns_none(mock_httpx, mock_auth, tmp_path):
    """403 auth error → returns None without raising."""
    resp = MagicMock()
    resp.status_code = 403
    mock_httpx.get.return_value = resp

    result = fetch_web_usage("org-abc", tmp_path)
    assert result is None


@patch("core.usage_fetcher._read_auth_cookies", return_value=("sk_test", None))
@patch("core.usage_fetcher.httpx")
def test_fetch_web_usage_network_error_returns_none(mock_httpx, mock_auth, tmp_path):
    """Network exception → returns None without raising."""
    mock_httpx.get.side_effect = Exception("connection refused")

    result = fetch_web_usage("org-abc", tmp_path)
    assert result is None


@patch("core.usage_fetcher._read_auth_cookies", return_value=(None, None))
def test_fetch_web_usage_no_session_key_returns_none(mock_auth, tmp_path):
    """No sessionKey → returns None without making HTTP call."""
    result = fetch_web_usage("org-abc", tmp_path)
    assert result is None


@patch("core.usage_fetcher._read_auth_cookies", return_value=("sk_test", None))
@patch("core.usage_fetcher.httpx")
def test_fetch_web_usage_extra_usage_disabled_returns_none(mock_httpx, mock_auth, tmp_path):
    """extra_usage.is_enabled=false → returns None."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = _make_teams_response(is_enabled=False)
    resp.raise_for_status = MagicMock()
    mock_httpx.get.return_value = resp

    result = fetch_web_usage("org-abc", tmp_path)
    assert result is None


@patch("core.usage_fetcher._read_auth_cookies", return_value=("sk_test", None))
@patch("core.usage_fetcher.httpx")
def test_fetch_web_usage_both_null_returns_none(mock_httpx, mock_auth, tmp_path):
    """five_hour=null, extra_usage=null → returns None."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"five_hour": None, "extra_usage": None}
    resp.raise_for_status = MagicMock()
    mock_httpx.get.return_value = resp

    result = fetch_web_usage("org-abc", tmp_path)
    assert result is None


# ---------------------------------------------------------------------------
# Auth priority order
# ---------------------------------------------------------------------------

@patch("core.usage_fetcher._read_chrome_cookies", return_value=(None, None))
@patch("core.usage_fetcher._read_firefox_cookies", return_value=(None, None))
@patch("core.usage_fetcher.keyring")
def test_auth_priority_keyring_first(mock_keyring, mock_firefox, mock_chrome, tmp_path):
    """keyring returns sessionKey → Firefox and Chrome never called."""
    mock_keyring.get_password.side_effect = lambda svc, usr: "sk_from_keyring" if usr == "sessionKey" else None

    session_key, _ = _read_auth_cookies(tmp_path)

    assert session_key == "sk_from_keyring"
    mock_firefox.assert_not_called()
    mock_chrome.assert_not_called()


@patch("core.usage_fetcher._read_chrome_cookies", return_value=(None, None))
@patch("core.usage_fetcher._read_firefox_cookies", return_value=("sk_from_firefox", None))
@patch("core.usage_fetcher.keyring")
def test_auth_priority_firefox_second(mock_keyring, mock_firefox, mock_chrome, tmp_path):
    """keyring empty → Firefox checked; Firefox returns key → Chrome never called."""
    mock_keyring.get_password.return_value = None

    session_key, _ = _read_auth_cookies(tmp_path)

    assert session_key == "sk_from_firefox"
    mock_chrome.assert_not_called()


# ---------------------------------------------------------------------------
# _migrate_config_to_keyring
# ---------------------------------------------------------------------------

@patch("core.usage_fetcher.keyring")
def test_migrate_config_to_keyring(mock_keyring, tmp_path):
    """session_key in config.json → migrated to keyring, deleted from file."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"session_key": "sk_plaintext", "org_id": "org-abc"}))

    _migrate_config_to_keyring(tmp_path)

    mock_keyring.set_password.assert_called_once_with("claude-monitor", "sessionKey", "sk_plaintext")
    # session_key must be removed from config.json
    cfg = json.loads(config_file.read_text())
    assert "session_key" not in cfg
    assert cfg.get("org_id") == "org-abc"  # other keys preserved


@patch("core.usage_fetcher.keyring")
def test_migrate_config_no_op_when_no_keys(mock_keyring, tmp_path):
    """config.json has no session_key or cf_clearance → keyring.set_password never called."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"org_id": "org-abc"}))

    _migrate_config_to_keyring(tmp_path)

    mock_keyring.set_password.assert_not_called()


@patch("core.usage_fetcher.keyring")
def test_migrate_config_missing_file_no_error(mock_keyring, tmp_path):
    """config.json missing → returns without error."""
    _migrate_config_to_keyring(tmp_path)  # should not raise
    mock_keyring.set_password.assert_not_called()


# ---------------------------------------------------------------------------
# fetch_web_usage: five_hour.resets_at absent fallback
# ---------------------------------------------------------------------------

@patch("core.usage_fetcher._read_auth_cookies", return_value=("sk_test", None))
@patch("core.usage_fetcher.httpx")
def test_fetch_web_usage_five_hour_no_resets_at_falls_back(mock_httpx, mock_auth, tmp_path):
    """five_hour present but resets_at absent → falls back to billing cycle reset."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"five_hour": {"utilization": 30.0}, "extra_usage": None}
    resp.raise_for_status = MagicMock()
    mock_httpx.get.return_value = resp

    result = fetch_web_usage("org-xyz", tmp_path)

    assert result is not None
    assert result.utilization_pct == pytest.approx(30.0)
    # reset_at should be a future billing-cycle date, not None
    assert result.reset_at is not None
    assert result.reset_at.tzinfo is not None
