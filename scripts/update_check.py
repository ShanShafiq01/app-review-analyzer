"""
Update check — hits the GitHub Releases API, caches the result for 24h, and
returns whether a newer version is available. Fails silently on every error
path so the pipeline never blocks on this.

Design:
  - Cache in ~/.cache/app-review-analyzer/update-check.json (cross-platform via Path.home())
  - 24-hour TTL — most users run the pipeline a few times per day; checking
    GitHub on every run is wasteful and would brush against unauthenticated rate limits
  - 3-second network timeout — never delays the pipeline meaningfully
  - urllib.request (stdlib) — no extra dependency
  - Repo not yet public, repo deleted, network down, GitHub down, parse error,
    cache file corrupt: all return None silently
  - Pre-release / dev versions (e.g. "0.4.0-dev") are detected as "newer" only
    if the numeric tuple is strictly greater — suffixes are dropped during compare

Called from run_pipeline.py at end of run. Disabled via --no-update-check.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_GITHUB_API = "https://api.github.com/repos/ShanShafiq01/app-review-analyzer/releases/latest"
_CACHE_TTL_SECONDS = 24 * 60 * 60   # 24h
_NETWORK_TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True)
class UpdateInfo:
    """The result of an update check. `update_available` is the only field
    callers usually need; the rest are for the banner message."""
    current_version: str
    latest_version: str
    update_available: bool
    repo_url: str = "https://github.com/ShanShafiq01/app-review-analyzer"


# ──────────────────────────────────────────────────────────────────
# Local version detection — read from SKILL.md frontmatter
# ──────────────────────────────────────────────────────────────────

def _read_local_version(skill_md_path: Path) -> Optional[str]:
    """Parse `version: X.Y.Z` from SKILL.md YAML frontmatter."""
    try:
        text = skill_md_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    # Frontmatter is between the first two `---` lines
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    frontmatter = parts[1]

    for line in frontmatter.splitlines():
        m = re.match(r"^\s*version\s*:\s*(.+?)\s*$", line)
        if m:
            return m.group(1).strip()
    return None


# ──────────────────────────────────────────────────────────────────
# Version comparison
# ──────────────────────────────────────────────────────────────────

def _parse_version_tuple(version: str) -> Optional[tuple[int, ...]]:
    """'v0.3.4' / '0.3.4' / '0.3.4-rc1' → (0, 3, 4). Returns None if unparseable.

    Pre-release suffixes (-rc, -dev, etc.) are stripped during compare. This is
    deliberately lax — we just want to know if the user is meaningfully behind,
    not run a strict PEP 440 comparison."""
    if not version:
        return None
    stripped = version.lstrip("vV").strip()
    # Drop pre-release suffix (-rc1, -dev, +build, etc.)
    stripped = re.split(r"[-+]", stripped, maxsplit=1)[0]
    parts = stripped.split(".")
    if not parts:
        return None
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def _is_newer(latest: str, current: str) -> bool:
    """True iff `latest` is strictly newer than `current`."""
    lt = _parse_version_tuple(latest)
    ct = _parse_version_tuple(current)
    if lt is None or ct is None:
        return False
    return lt > ct


# ──────────────────────────────────────────────────────────────────
# Cache
# ──────────────────────────────────────────────────────────────────

def _cache_path() -> Path:
    """Cross-platform cache file path."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "app-review-analyzer" / "update-check.json"
    # XDG-compliant on Linux; ~/.cache works fine on macOS too
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "app-review-analyzer" / "update-check.json"


def _read_cache() -> Optional[dict]:
    """Return cached check result if present and fresh, else None."""
    path = _cache_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None

    checked_at = data.get("checked_at")
    if not isinstance(checked_at, (int, float)):
        return None
    age = datetime.now(timezone.utc).timestamp() - float(checked_at)
    if age < 0 or age > _CACHE_TTL_SECONDS:
        return None

    if not isinstance(data.get("latest_version"), str):
        return None
    return data


def _write_cache(latest_version: str) -> None:
    """Best-effort cache write. Failure is OK — next run will just re-fetch."""
    try:
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({
                "checked_at": datetime.now(timezone.utc).timestamp(),
                "latest_version": latest_version,
            }),
            encoding="utf-8",
        )
    except OSError:
        pass


# ──────────────────────────────────────────────────────────────────
# Network fetch
# ──────────────────────────────────────────────────────────────────

def _fetch_latest_version(current_version: str) -> Optional[str]:
    """Hit GitHub Releases API. Returns version string or None on any failure."""
    req = urllib.request.Request(
        _GITHUB_API,
        headers={
            # GitHub recommends a User-Agent identifying the client
            "User-Agent": f"app-review-analyzer/{current_version}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_NETWORK_TIMEOUT_SECONDS) as resp:
            if resp.status != 200:
                return None
            body = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return None

    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None

    tag = data.get("tag_name") or data.get("name")
    if not isinstance(tag, str):
        return None
    return tag.strip()


# ──────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────

def check_for_update(
    skill_md_path: Optional[Path] = None,
    force_refresh: bool = False,
) -> Optional[UpdateInfo]:
    """Return UpdateInfo if a newer version is available, else None.

    Returns None for any failure path:
      - local SKILL.md unreadable / version unparseable
      - cache present and fresh but already says no update
      - network failure, GitHub API error, malformed response
      - the repo isn't published yet (404)

    The pipeline calls this and just suppresses None. The only output the user
    ever sees is the banner printed when this returns an UpdateInfo with
    update_available=True.
    """
    if skill_md_path is None:
        skill_md_path = Path(__file__).resolve().parent.parent / "SKILL.md"

    current = _read_local_version(skill_md_path)
    if not current:
        return None

    latest: Optional[str] = None
    if not force_refresh:
        cached = _read_cache()
        if cached:
            latest = cached["latest_version"]

    if latest is None:
        latest = _fetch_latest_version(current)
        if latest:
            _write_cache(latest)

    if not latest:
        return None

    return UpdateInfo(
        current_version=current,
        latest_version=latest.lstrip("vV"),
        update_available=_is_newer(latest, current),
    )


def format_banner(info: UpdateInfo, install_dir: Optional[Path] = None) -> str:
    """Format a one-line update banner suitable for end-of-pipeline output."""
    if not info.update_available:
        return ""
    cmd = "cd <install-dir> && git pull && ./setup.sh"
    if install_dir:
        if sys.platform == "win32":
            cmd = f"cd {install_dir} && git pull && .\\setup.ps1"
        else:
            cmd = f"cd {install_dir} && git pull && ./setup.sh"
    return (
        f"\nUpdate available: v{info.current_version} → v{info.latest_version}\n"
        f"  {cmd}\n"
        f"  (changelog: {info.repo_url}/blob/main/CHANGELOG.md)"
    )


if __name__ == "__main__":
    # Manual exercise: `python -m scripts.update_check`
    info = check_for_update(force_refresh=True)
    if info is None:
        print("No update info (network failure, repo not public, or version unparseable).")
        sys.exit(0)
    print(f"Current: v{info.current_version}")
    print(f"Latest:  v{info.latest_version}")
    print(f"Update available: {info.update_available}")
    if info.update_available:
        print(format_banner(info, Path(__file__).resolve().parent.parent))
