"""
core/event_bus.py
==================

セッションIDごとに独立したイベントキューを持つ、シンプルなpub/subバス。

設計方針:
- 1セッション(=1人の管理者が開いているViewerタブ)につき1つのqueue.Queue
- Python側のトレーサー(tracer.py)とJS側(inject.js経由のイベント受信
  エンドポイント)の両方が、同じ publish() を呼ぶだけでよい
- SSEエンドポイント側は、自分のセッションのキューをブロッキングgetで
  読み続けるだけでよい(Flask/FastAPIどちらの統合からも同じように使える)
"""

from __future__ import annotations

import queue
import threading
from typing import Any


class EventBus:
    def __init__(self):
        self._queues: dict[str, "queue.Queue[dict[str, Any]]"] = {}
        self._lock = threading.Lock()

    def _get_queue(self, session_id: str) -> "queue.Queue[dict[str, Any]]":
        with self._lock:
            q = self._queues.get(session_id)
            if q is None:
                q = queue.Queue()
                self._queues[session_id] = q
            return q

    def publish(self, session_id: str, event: dict[str, Any]) -> None:
        """イベントを、そのセッション専用のキューに積む。"""
        self._get_queue(session_id).put(event)

    def get_nowait(self, session_id: str):
        """ノンブロッキングで1件取り出す。無ければqueue.Emptyを送出する。"""
        return self._get_queue(session_id).get_nowait()

    def get(self, session_id: str, timeout: float):
        """ブロッキングで1件取り出す。timeout秒待っても無ければqueue.Emptyを送出する。"""
        return self._get_queue(session_id).get(timeout=timeout)

    def drain_nowait(self, session_id: str) -> list:
        """溜まっているイベントを、ブロッキングせずに全部取り出してリストで返す。

        SSEをやめてポーリング方式に切り替えた際に使う。Gunicornのsyncワーカーは
        長時間ブロックする処理(SSEの待ち受け)があるとワーカーごと強制終了
        されてしまう(WORKER TIMEOUT)ため、「一瞬で返る」この方式に統一する。
        """
        events = []
        q = self._get_queue(session_id)
        while True:
            try:
                events.append(q.get_nowait())
            except queue.Empty:
                break
        return events

    def discard(self, session_id: str) -> None:
        """セッション終了時に、キューごと破棄する(メモリリーク防止)。"""
        with self._lock:
            self._queues.pop(session_id, None)