"""Fetch current pool spend from Anthropic's usage API.

Calls https://claude.ai/api/organizations/{org_id}/usage to get the live
extra_usage.used_credits value (in cents). Returns dollars.

Auth is resolved in priority order:
  1. session_key / cf_clearance keys in ~/.claude-monitor/config.json
  2. Chrome cookie store (auto-extracted, Windows only)

Config keys (in ~/.claude-monitor/config.json):
  org_id:        Anthropic organization UUID (required)
  session_key:   sessionKey cookie from claude.ai (optional, overrides Chrome)
  cf_clearance:  cf_clearance cookie from claude.ai (optional, overrides Chrome)
  auto_seed:     set false to disable auto-seeding at startup (default true)
"""
import base64
import json
import logging
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_USAGE_URL = "https://claude.ai/api/organizations/{org_id}/usage"
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

def _read_auth_cookies(config_dir: Path) -> Tuple[Optional[str], Optional[str]]:
    """Resolve sessionKey and cf_clearance with config.json taking priority over Chrome.

    Priority:
      1. Explicit values in config.json (session_key / cf_clearance keys)
      2. Chrome cookie store (auto-extracted)

    Returns (session_key, cf_clearance).
    """
    cfg: dict = {}
    config_file = config_dir / "config.json"
    try:
        cfg = json.loads(config_file.read_text(encoding="utf-8")) if config_file.exists() else {}
    except Exception as exc:
        logger.warning("usage_fetcher: failed to read config.json: %s", exc)

    session_key: Optional[str] = cfg.get("session_key") or None
    cf_clearance: Optional[str] = cfg.get("cf_clearance") or None

    if not session_key:
        logger.debug("usage_fetcher: session_key not in config — trying Chrome cookies")
        chrome_sk, chrome_cf = _read_chrome_cookies()
        session_key = session_key or chrome_sk
        cf_clearance = cf_clearance or chrome_cf

    return session_key, cf_clearance


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_pool_spend_usd(org_id: str, config_dir: Path) -> Optional[float]:
    """Return current extra_usage spend in USD, or None on failure."""
    try:
        import urllib.request

        session_key, cf_clearance = _read_auth_cookies(config_dir)
        if not session_key:
            logger.warning("usage_fetcher: no sessionKey available (config or Chrome)")
            return None

        cookie_parts = [f"sessionKey={session_key}"]
        if cf_clearance:
            cookie_parts.append(f"cf_clearance={cf_clearance}")

        url = _USAGE_URL.format(org_id=org_id)
        req = urllib.request.Request(
            url,
            headers={
                "Cookie": "; ".join(cookie_parts),
                "Accept": "application/json",
                "User-Agent": _USER_AGENT,
                "anthropic-client-platform": "web_claude_ai",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))

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
