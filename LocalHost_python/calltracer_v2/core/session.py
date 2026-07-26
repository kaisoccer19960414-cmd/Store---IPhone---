"""
core/session.py
================

管理者が「今CallTracerで見ている」状態を表すセッションを発行・検証する。

設計方針:
- セッションが有効な間だけ、そのセッションIDに紐づくリクエストがトレース対象になる
  (常時トレースは行わない = 本番運用での安全性・パフォーマンスを優先)
- セッションはプロセスメモリ上で管理する(単一プロセス前提。複数ワーカー
  プロセスで動かす場合は、後述の「既知の制約」を参照)
- 有効期限(デフォルト30分)を過ぎたセッションは自動的に無効とみなす
  (Viewerのタブを閉じ忘れて本番トレースが永遠に有効になり続ける事故を防ぐ)
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Session:
    session_id: str
    created_at: float
    last_seen_at: float = field(default_factory=time.time)


class SessionRegistry:
    """アクティブな管理者セッションの集合を管理する、スレッドセーフなレジストリ。"""

    def __init__(self, ttl_seconds: float = 30 * 60):
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._ttl_seconds = ttl_seconds

    def start(self) -> str:
        """新しいセッションを発行し、そのIDを返す。"""
        session_id = secrets.token_urlsafe(24)
        now = time.time()
        with self._lock:
            self._sessions[session_id] = Session(session_id=session_id, created_at=now)
        return session_id

    def stop(self, session_id: str) -> None:
        """セッションを明示的に終了する(Viewerを閉じた時などに呼ばれる想定)。"""
        with self._lock:
            self._sessions.pop(session_id, None)

    def touch(self, session_id: str) -> None:
        """セッションの最終アクセス時刻を更新する(有効期限の延長)。"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                session.last_seen_at = time.time()

    def is_active(self, session_id: Optional[str]) -> bool:
        """このセッションIDが、現在有効なセッションかどうかを判定する。"""
        if not session_id:
            return False
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            if time.time() - session.last_seen_at > self._ttl_seconds:
                # 期限切れ。ついでに掃除しておく。
                del self._sessions[session_id]
                return False
            return True

    def active_count(self) -> int:
        with self._lock:
            return len(self._sessions)