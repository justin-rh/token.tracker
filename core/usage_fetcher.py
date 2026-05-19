"""Fetch current pool spend from Anthropic's usage API.

Calls https://claude.ai/api/organizations/{org_id}/usage to get the live
extra_usage.used_credits value (in cents). Returns dollars.

Auth is resolved in priority order per D-06:
  1. Windows Credential Manager (keyring) — always checked first
  2. Firefox cookie store (browser-cookie3) — primary auto-extraction
  3. Chrome cookie store (auto-extracted, Windows only, Chrome not running)
  4. Manual paste prompt — handled in cli/main.py

Config keys (in ~/.claude-monitor/config.json):
  org_id:        Anthropic organization UUID (required)
  auto_seed:     set false to disable auto-seeding at startup (default true)

Credentials (D-03/D-04/D-05):
  sessionKey and cf_clearance are stored exclusively in Windows Credential Manager
  via keyring (service: claude-monitor). session_key/cf_clearance found in config.json
  are auto-migrated to keyring on startup and deleted from the file.
"""
import base64
import json
import logging
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import httpx
import keyring

logger = logging.getLogger(__name__)

_USAGE_URL = "https://claude.ai/api/organizations/{org_id}/usage"
_ACCOUNT_URL = "https://claude.ai/api/account"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_CHROME_COOKIE_DB_PATHS = [
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "Google" / "Chrome" / "User Data" / "Default" / "Network" / "Cookies",
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "Google" / "Chrome" / "User Data" / "Default" / "Cookies",
]
_CHROME_LOCAL_STATE = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "Google" / "Chrome" / "User Data" / "Local State"
)


# ---------------------------------------------------------------------------
# Chrome cookie decryption (Windows DPAPI + AES-GCM)
# ---------------------------------------------------------------------------

def _dpapi_decrypt(data: bytes) -> bytes:
    """Decrypt bytes with Windows DPAPI (CryptUnprotectData)."""
    import ctypes
    import ctypes.wintypes

    class _BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = _BLOB(ctypes.sizeof(buf), buf)
    blob_out = _BLOB()

    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    )
    if not ok:
        raise RuntimeError("CryptUnprotectData failed")

    result = ctypes.string_at(blob_out.pbData, blob_out.cbData)
    ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    return result


def _get_chrome_aes_key() -> Optional[bytes]:
    """Return Chrome's AES-256 cookie encryption key, or None on any failure."""
    if not _CHROME_LOCAL_STATE.exists():
        return None
    try:
        state = json.loads(_CHROME_LOCAL_STATE.read_text(encoding="utf-8"))
        b64 = state["os_crypt"]["encrypted_key"]
        encrypted = base64.b64decode(b64)[5:]  # strip b"DPAPI" prefix
        return _dpapi_decrypt(encrypted)
    except Exception as exc:
        logger.debug("chrome_cookies: failed to get AES key: %s", exc)
        return None


def _copy_locked_file(src: Path, dst: Path) -> bool:
    """Copy a file that Chrome has open, using Windows shared-access flags.

    Python's shutil.copy2 uses CreateFile with no sharing, which fails on
    Chrome's cookie DB. This opens with FILE_SHARE_READ|WRITE|DELETE so the
    copy succeeds while Chrome is running.
    Returns True on success, False on any failure (caller falls back to shutil).
    """
    import ctypes
    import ctypes.wintypes

    GENERIC_READ = 0x80000000
    FILE_SHARE_ALL = 0x7  # READ | WRITE | DELETE
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x80
    INVALID_HANDLE = ctypes.c_void_p(-1).value

    handle = ctypes.windll.kernel32.CreateFileW(
        str(src), GENERIC_READ, FILE_SHARE_ALL, None,
        OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None,
    )
    if handle == INVALID_HANDLE:
        return False
    try:
        # Use GetFileSizeEx to get a 64-bit size — avoids signed/unsigned ambiguity
        file_size = ctypes.c_int64(0)
        if not ctypes.windll.kernel32.GetFileSizeEx(handle, ctypes.byref(file_size)):
            return False
        size = file_size.value
        if size <= 0:
            return False
        buf = ctypes.create_string_buffer(size)
        read = ctypes.wintypes.DWORD(0)
        ok = ctypes.windll.kernel32.ReadFile(handle, buf, size, ctypes.byref(read), None)
        if not ok:
            return False
        dst.write_bytes(buf.raw[: read.value])
        return True
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def _decrypt_chrome_value(encrypted_value: bytes, aes_key: bytes) -> Optional[str]:
    """Decrypt a single Chrome cookie value (AES-GCM v10/v11 or legacy plaintext)."""
    if not encrypted_value:
        return None
    if encrypted_value[:3] in (b"v10", b"v11"):
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            nonce = encrypted_value[3:15]
            ciphertext = encrypted_value[15:]
            return AESGCM(aes_key).decrypt(nonce, ciphertext, None).decode("utf-8")
        except Exception as exc:
            logger.debug("chrome_cookies: AES-GCM decrypt failed: %s", exc)
            return None
    # Older Chrome stored cookies as plain UTF-8
    try:
        return encrypted_value.decode("utf-8")
    except Exception:
        return None


def _chrome_is_running() -> bool:
    """Return True if any chrome.exe process is active."""
    import subprocess
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/NH"],
            capture_output=True, text=True, timeout=3,
        ).stdout
        return "chrome.exe" in out
    except Exception:
        return False


def _read_chrome_cookies() -> Tuple[Optional[str], Optional[str]]:
    """Extract sessionKey and cf_clearance cookies for claude.ai from Chrome.

    Returns (session_key, cf_clearance). Either may be None if not found.

    Chrome 127+ holds an exclusive lock on the Cookies DB while running and
    uses App-Bound Encryption that prevents third-party decryption. Extraction
    is only attempted when Chrome is not running. When Chrome is open, callers
    should fall back to manually configured values in config.json.
    """
    cookie_db: Optional[Path] = None
    for candidate in _CHROME_COOKIE_DB_PATHS:
        if candidate.exists():
            cookie_db = candidate
            break
    if cookie_db is None:
        logger.debug("chrome_cookies: no Chrome cookie DB found")
        return None, None

    if _chrome_is_running():
        logger.debug(
            "chrome_cookies: Chrome is running — cookie DB is locked. "
            "To skip manual updates, add 'session_key' to ~/.claude-monitor/config.json "
            "(DevTools → Application → Cookies → claude.ai → sessionKey)."
        )
        return None, None

    aes_key = _get_chrome_aes_key()
    if aes_key is None:
        logger.debug("chrome_cookies: could not obtain AES key")
        return None, None

    tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        if not _copy_locked_file(cookie_db, tmp_path):
            shutil.copy2(cookie_db, tmp_path)

        con = sqlite3.connect(f"file:{tmp_path}?mode=ro", uri=True)
        try:
            rows = con.execute(
                "SELECT name, encrypted_value FROM cookies "
                "WHERE host_key LIKE '%claude.ai' "
                "AND name IN ('sessionKey', 'cf_clearance') "
                "ORDER BY last_access_utc DESC",
            ).fetchall()
        finally:
            con.close()
    except Exception as exc:
        logger.debug("chrome_cookies: DB read failed: %s", exc)
        return None, None
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    session_key: Optional[str] = None
    cf_clearance: Optional[str] = None
    for name, enc_val in rows:
        if name == "sessionKey" and session_key is None:
            session_key = _decrypt_chrome_value(enc_val, aes_key)
        elif name == "cf_clearance" and cf_clearance is None:
            cf_clearance = _decrypt_chrome_value(enc_val, aes_key)
        if session_key and cf_clearance:
            break

    if session_key:
        logger.debug("chrome_cookies: extracted sessionKey and cf_clearance=%s", bool(cf_clearance))
    else:
        logger.debug("chrome_cookies: sessionKey not found in Chrome cookies")

    return session_key, cf_clearance


# ---------------------------------------------------------------------------
# Auth cookie resolution
# ---------------------------------------------------------------------------

def _read_firefox_cookies() -> Tuple[Optional[str], Optional[str]]:
    """Extract sessionKey and cf_clearance from Firefox cookie store for claude.ai.

    Uses browser-cookie3 for profile discovery and cookie extraction.
    Firefox stores cookies in cleartext (unlike Chrome) — no decryption needed.
    Returns (session_key, cf_clearance). Either may be None if not found.

    Silently returns (None, None) on any failure, including Firefox WAL lock.
    """
    try:
        import browser_cookie3
        cj = browser_cookie3.firefox(domain_name=".claude.ai")
        session_key: Optional[str] = None
        cf_clearance: Optional[str] = None
        for cookie in cj:
            if cookie.name == "sessionKey" and session_key is None:
                session_key = cookie.value
            elif cookie.name == "cf_clearance" and cf_clearance is None:
                cf_clearance = cookie.value
        if session_key:
            logger.debug("firefox_cookies: extracted sessionKey, cf_clearance=%s", bool(cf_clearance))
        else:
            logger.debug("firefox_cookies: sessionKey not found in Firefox cookies")
        return session_key, cf_clearance
    except Exception as exc:
        logger.debug("firefox_cookies: extraction failed: %s", exc)
        return None, None


def _migrate_config_to_keyring(config_dir: Path) -> None:
    """One-time migration: move session_key and cf_clearance from config.json to keyring.

    Reads config.json, copies any session_key / cf_clearance values to Windows
    Credential Manager via keyring, removes them from config.json, and writes the
    cleaned config back atomically using the .tmp -> .replace() pattern.

    Safe to call on every startup: no-op if keys are not present or file missing.
    Per D-04 — one-way migration, logged at INFO, no user prompt.
    """
    config_file = config_dir / "config.json"
    if not config_file.exists():
        return
    try:
        cfg = json.loads(config_file.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("auth: failed to read config.json for migration: %s", exc)
        return

    changed = False
    for config_key, keyring_username in [
        ("session_key", "sessionKey"),
        ("cf_clearance", "cf_clearance"),
    ]:
        value = cfg.get(config_key)
        if value:
            try:
                keyring.set_password("claude-monitor", keyring_username, value)
                del cfg[config_key]
                logger.info("auth: migrated %s from config.json to keyring", config_key)
                changed = True
            except Exception as exc:
                logger.warning("auth: failed to migrate %s to keyring: %s", config_key, exc)

    if changed:
        try:
            tmp = config_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
            tmp.replace(config_file)
        except Exception as exc:
            logger.warning("auth: failed to write cleaned config.json: %s", exc)


def _read_auth_cookies(config_dir: Path) -> Tuple[Optional[str], Optional[str]]:
    """Resolve sessionKey and cf_clearance in priority order per D-06.

    Priority:
      1. Windows Credential Manager (keyring) — checked first on every call
      2. Firefox cookie store (browser-cookie3) — primary auto-extraction
      3. Chrome cookie store — existing implementation; Chrome 127+ may fail
      4. Caller handles manual paste when this returns (None, None)

    Returns (session_key, cf_clearance). Either or both may be None.
    SECURITY: Never logs the actual key value — only logs source or failure.
    """
    # Priority 1: keyring (Windows Credential Manager)
    try:
        session_key = keyring.get_password("claude-monitor", "sessionKey") or None
        cf_clearance = keyring.get_password("claude-monitor", "cf_clearance") or None
        if session_key:
            logger.debug("auth: sessionKey from keyring")
            return session_key, cf_clearance
    except Exception as exc:
        logger.debug("auth: keyring read error: %s", exc)

    # Priority 2: Firefox cookie store
    session_key, cf_clearance = _read_firefox_cookies()
    if session_key:
        logger.debug("auth: sessionKey from Firefox")
        return session_key, cf_clearance

    # Priority 3: Chrome cookie store (only when Chrome not running)
    session_key, cf_clearance = _read_chrome_cookies()
    if session_key:
        logger.debug("auth: sessionKey from Chrome")
        return session_key, cf_clearance

    logger.warning("auth: no sessionKey found in keyring, Firefox, or Chrome")
    return None, None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _discover_org_id(session_key: str) -> Optional[str]:
    """Auto-discover org_id using /api/account endpoint.

    Calls GET https://claude.ai/api/account and returns the first
    organization UUID from memberships. No org_id required to call this.
    Returns None on any failure or empty memberships.

    Per D-01: result should be written to config.json["org_id"] by the caller.
    Per D-02: caller should skip this if org_id already in config.json.
    """
    try:
        resp = httpx.get(
            _ACCOUNT_URL,
            headers={
                "Cookie": f"sessionKey={session_key}",
                "Accept": "application/json",
                "User-Agent": _USER_AGENT,
                "anthropic-client-platform": "web_claude_ai",
            },
            timeout=10,
            verify=False,
        )
        resp.raise_for_status()
        body = resp.json()
        logger.debug("_discover_org_id: raw response memberships count=%d", len(body.get("memberships", [])))
        for m in body.get("memberships", []):
            uuid = m.get("organization", {}).get("uuid")
            if uuid:
                logger.info("_discover_org_id: discovered org_id (omitted from log)")
                return uuid
        logger.warning("_discover_org_id: no organization UUID found in memberships")
        return None
    except Exception as exc:
        logger.warning("_discover_org_id: request failed: %s", exc)
        return None


def _derive_billing_cycle_reset(config_dir: Path) -> datetime:
    """Derive billing cycle reset datetime from config.json billing_cycle_start_day.

    For Teams accounts, the /usage endpoint has no resets_at for extra_usage.
    We derive the next billing cycle start from config.json.
    Returns a timezone-aware UTC datetime.
    """
    config_file = config_dir / "config.json"
    cycle_day = 1
    try:
        cfg = json.loads(config_file.read_text(encoding="utf-8")) if config_file.exists() else {}
        raw_day = cfg.get("billing_cycle_start_day")
        if isinstance(raw_day, int) and 1 <= raw_day <= 28:
            cycle_day = raw_day
    except Exception:
        pass

    today = datetime.now(timezone.utc).date()
    try:
        if today.day >= cycle_day:
            # Next reset is next month
            if today.month == 12:
                reset_date = today.replace(year=today.year + 1, month=1, day=cycle_day)
            else:
                reset_date = today.replace(month=today.month + 1, day=cycle_day)
        else:
            reset_date = today.replace(day=cycle_day)
    except ValueError:
        reset_date = today.replace(day=1)

    return datetime(reset_date.year, reset_date.month, reset_date.day, tzinfo=timezone.utc)


def fetch_web_usage(org_id: str, config_dir: Path) -> Optional["WebUsageData"]:
    """Fetch authoritative usage data from claude.ai API. Returns None on any failure.

    Endpoint: GET https://claude.ai/api/organizations/{org_id}/usage
    Auth: sessionKey cookie from _read_auth_cookies() — resolved per D-06 priority order.

    Account type branching (CRITICAL — verified via live spike):
      - five_hour is non-null: Max/Pro plan — use five_hour.utilization and resets_at
      - extra_usage is non-null and is_enabled: Teams/Enterprise — use extra_usage.utilization;
        reset_at derived from billing cycle config (no API-provided resets_at for Teams)
      - Both null/disabled: returns None

    SECURITY: never logs the sessionKey value at any log level.
    Per D-22: uses .get() for all JSON field access; logs raw response at DEBUG.
    """
    from claude_monitor.core.models import WebUsageData
    try:
        session_key, cf_clearance = _read_auth_cookies(config_dir)
        if not session_key:
            logger.warning("fetch_web_usage: no sessionKey available")
            return None

        cookie_parts = [f"sessionKey={session_key}"]
        if cf_clearance:
            cookie_parts.append(f"cf_clearance={cf_clearance}")

        resp = httpx.get(
            _USAGE_URL.format(org_id=org_id),
            headers={
                "Cookie": "; ".join(cookie_parts),
                "Accept": "application/json",
                "User-Agent": _USER_AGENT,
                "anthropic-client-platform": "web_claude_ai",
            },
            timeout=10,
            verify=False,
        )

        if resp.status_code in (401, 403):
            logger.warning(
                "fetch_web_usage: auth rejected (%d) — sessionKey may be stale",
                resp.status_code,
            )
            return None

        resp.raise_for_status()
        body = resp.json()
        logger.debug("fetch_web_usage: raw response: %s", body)

        five_hour = body.get("five_hour")
        extra_usage = body.get("extra_usage")

        if five_hour is not None:
            # Max/Pro individual plan — 5-hour rolling window
            # ASSUMED: five_hour.utilization scale is 0-100 (same as extra_usage; add comment)
            utilization_pct = float(five_hour.get("utilization", 0.0))  # ASSUMED: 0-100 scale
            reset_at_str = five_hour.get("resets_at")
            if reset_at_str:
                reset_at = datetime.fromisoformat(reset_at_str.replace("Z", "+00:00"))
            else:
                reset_at = _derive_billing_cycle_reset(config_dir)
            plan_limit_tokens = None  # not in API
        elif extra_usage and extra_usage.get("is_enabled"):
            # Teams/Enterprise plan — monthly pool (extra_usage.utilization is % of monthly spend)
            utilization_pct = float(extra_usage.get("utilization", 0.0))
            # Teams has no resets_at — use billing cycle reset date from config
            reset_at = _derive_billing_cycle_reset(config_dir)
            plan_limit_tokens = None  # monthly_limit is in CENTS, not tokens
        else:
            logger.info("fetch_web_usage: no usable usage field in response (five_hour=null, extra_usage disabled or null)")
            return None

        return WebUsageData(
            utilization_pct=utilization_pct,
            reset_at=reset_at,
            fetched_at=datetime.now(timezone.utc),
            plan_limit_tokens=plan_limit_tokens,
        )

    except Exception as exc:
        logger.warning("fetch_web_usage: request failed: %s", exc)
        return None


def fetch_pool_spend_usd(org_id: str, config_dir: Path) -> Optional[float]:
    """Return current extra_usage spend in USD, or None on failure."""
    try:
        session_key, cf_clearance = _read_auth_cookies(config_dir)
        if not session_key:
            logger.warning("usage_fetcher: no sessionKey available (config or Chrome)")
            return None

        cookie_parts = [f"sessionKey={session_key}"]
        if cf_clearance:
            cookie_parts.append(f"cf_clearance={cf_clearance}")

        url = _USAGE_URL.format(org_id=org_id)
        resp = httpx.get(
            url,
            headers={
                "Cookie": "; ".join(cookie_parts),
                "Accept": "application/json",
                "User-Agent": _USER_AGENT,
                "anthropic-client-platform": "web_claude_ai",
            },
            timeout=10,
            verify=False,
        )
        resp.raise_for_status()
        body = resp.json()

        extra = body.get("extra_usage")
        if not extra or not extra.get("is_enabled"):
            logger.info("usage_fetcher: extra_usage not enabled or missing")
            return None

        credits = extra.get("used_credits")
        if credits is None:
            logger.warning("usage_fetcher: used_credits field missing")
            return None

        return round(float(credits) / 100, 2)

    except Exception as exc:
        logger.warning("usage_fetcher: request failed: %s", exc)
        return None


def auto_seed_from_anthropic(config_dir: Path) -> Optional[float]:
    """Fetch live spend and update pool_spend_seed_usd/date in config.json.

    Returns the fetched dollar value on success, None on failure.
    Silently skips if org_id is not configured or auto_seed is false.
    """
    from datetime import date, datetime, timezone

    config_file = config_dir / "config.json"
    try:
        cfg = json.loads(config_file.read_text(encoding="utf-8")) if config_file.exists() else {}
    except Exception:
        cfg = {}

    if not cfg.get("auto_seed", True):
        return None

    org_id = cfg.get("org_id")
    if not org_id:
        logger.debug("usage_fetcher: org_id not set in config.json — skipping auto-seed")
        return None

    spend = fetch_pool_spend_usd(org_id, config_dir)
    if spend is None:
        return None

    now_utc = datetime.now(timezone.utc)
    cfg["pool_spend_seed_usd"] = spend
    cfg["pool_spend_seed_datetime"] = now_utc.isoformat()
    cfg["pool_spend_seed_date"] = now_utc.date().isoformat()  # kept for backward compat

    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        tmp = config_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        tmp.replace(config_file)
        logger.info("usage_fetcher: seeded pool_spend_seed_usd=%.2f, datetime=%s", spend, now_utc.isoformat())
    except Exception as exc:
        logger.warning("usage_fetcher: failed to write config.json: %s", exc)

    return spend
