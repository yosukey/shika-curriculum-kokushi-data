"""アップデートチェック"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, Slot

RELEASE_API_URL = "https://api.github.com/repos/yosukey/shika-curriculum-kokushi-data/releases/latest"
RELEASES_URL = "https://github.com/yosukey/shika-curriculum-kokushi-data/releases"
REQUEST_TIMEOUT_SECONDS = 5


@dataclass(slots=True)
class UpdateCheckResult:
    status: str
    current_version: str
    latest_version: str | None = None
    release_url: str = RELEASES_URL
    published_at: str | None = None
    error_message: str | None = None


class UpdateCheckWorker(QObject):
    finished = Signal(object)

    def __init__(self, current_version: str):
        super().__init__()
        self._current_version = current_version

    @Slot()
    def run(self):
        self.finished.emit(check_for_updates(self._current_version))


def check_for_updates(current_version: str) -> UpdateCheckResult:
    try:
        latest_release = _fetch_latest_release()
    except urllib.error.HTTPError as exc:
        detail = f"HTTP {exc.code}"
        if exc.code == 404:
            detail = "指定されたリポジトリ、または最新リリースが見つかりませんでした。"
        return UpdateCheckResult(
            status="error",
            current_version=current_version,
            error_message=f"更新情報を取得できませんでした: {detail}",
        )
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        return UpdateCheckResult(
            status="error",
            current_version=current_version,
            error_message=f"ネットワークエラー: {reason}",
        )
    except Exception as exc:  # pragma: no cover - 想定外の応答も画面上で扱う
        return UpdateCheckResult(
            status="error",
            current_version=current_version,
            error_message=f"更新情報を取得できませんでした: {exc}",
        )

    latest_version = latest_release.get("tag_name") or latest_release.get("name") or "unknown"
    release_url = latest_release.get("html_url") or RELEASES_URL
    published_at = latest_release.get("published_at")

    comparison = _compare_versions(current_version, latest_version)
    if comparison is None:
        return UpdateCheckResult(
            status="comparison_unavailable",
            current_version=current_version,
            latest_version=latest_version,
            release_url=release_url,
            published_at=published_at,
        )
    if comparison < 0:
        return UpdateCheckResult(
            status="update_available",
            current_version=current_version,
            latest_version=latest_version,
            release_url=release_url,
            published_at=published_at,
        )
    return UpdateCheckResult(
        status="up_to_date",
        current_version=current_version,
        latest_version=latest_version,
        release_url=release_url,
        published_at=published_at,
    )


def _fetch_latest_release() -> dict:
    request = urllib.request.Request(
        RELEASE_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "cc-viewer-update-checker",
        },
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("GitHub API response is not an object")
    return payload


def _compare_versions(current_version: str, latest_version: str) -> int | None:
    current_parts = _normalize_version(current_version)
    latest_parts = _normalize_version(latest_version)
    if current_parts is None or latest_parts is None:
        return None

    max_len = max(len(current_parts), len(latest_parts))
    current_key = current_parts + (0,) * (max_len - len(current_parts))
    latest_key = latest_parts + (0,) * (max_len - len(latest_parts))
    if current_key < latest_key:
        return -1
    if current_key > latest_key:
        return 1
    return 0


def _normalize_version(version: str) -> tuple[int, ...] | None:
    normalized = version.strip().lower()
    if not normalized:
        return None
    normalized = normalized.removeprefix("release-").removeprefix("ver-").removeprefix("version-")
    normalized = normalized.removeprefix("v")
    parts = re.findall(r"\d+", normalized)
    if not parts:
        return None
    return tuple(int(part) for part in parts)
