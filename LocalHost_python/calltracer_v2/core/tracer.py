"""
core/tracer.py
================

sys.settrace ベースのPython呼び出しトレーサー。v1(PythonAdapter)との違いは:

- include_pathsによるフィルタは維持しつつ、「今のリクエストが管理者の
  アクティブなセッションに紐づいているか」を contextvars で判定し、
  紐づいていないリクエストは即座に(1行で)トレースを打ち切る。
- スレッド(Flask/WSGI)・asyncioタスク(FastAPI/ASGI)のどちらでも、
  呼び出し深さ(depth)を正しく分離するために、v1の「thread_idごとのdict」
  ではなく contextvars を使う。contextvarsはスレッドごと・asyncioタスク
  ごとに自動的に分離されるため、同時並行リクエストが混線しない。
- sys.settrace自体は、管理者セッションが1つも無い間は完全に無効化する
  (sys.settrace(None))。有効化中は「同一プロセス内の全関数呼び出しが
  この関数を通る」というPython自体の制約上、無視できないオーバーヘッドが
  生じるため、本番運用では「管理者が実際に見ている間だけ」に絞ることが
  重要。

既知の制約(README・docstringレベルで必ず明記すること):
- sys.settraceはプロセス単位の設定。gunicorn等で複数ワーカープロセスを
  使っている場合、管理者のリクエストがどのワーカーに割り当たるかは
  リクエストごとに変わりうるため、セッション開始をそのワーカーだけに
  伝える形にはならない(全ワーカーがそれぞれ自分の中でセッション有効化
  ロジックを持つ設計にしてあるので、動作はするが、各ワーカーが個別に
  オーバーヘッドを負う点は理解しておくこと)。
"""

from __future__ import annotations

import itertools
import os
import sys
import threading
import time
from contextvars import ContextVar
from types import FrameType
from typing import Any, Callable, Optional

from .event_bus import EventBus

_CALLTRACER_PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# このリクエスト/タスクが、どの管理者セッションに属しているか。
# Noneなら「トレース対象外の、普通のユーザーのリクエスト」を意味する。
_current_session: ContextVar[Optional[str]] = ContextVar(
    "calltracer_current_session", default=None
)
# このリクエスト/タスク内での、現在の呼び出し深さ。
_current_depth: ContextVar[int] = ContextVar("calltracer_current_depth", default=0)


class Tracer:
    """sys.settraceの有効/無効を管理し、有効時にイベントをEventBusへ流す。"""

    def __init__(self, event_bus: EventBus, include_paths: list[str]):
        self._event_bus = event_bus
        self._include_paths = [os.path.abspath(p) for p in include_paths]
        self._id_counter = itertools.count(1)
        self._active_sessions = 0
        self._lock = threading.Lock()
        self._prev_trace: Optional[Callable] = None

    # ------------------------------------------------------------------
    # セッションのライフサイクルに連動した有効化/無効化
    # ------------------------------------------------------------------

    def on_session_start(self) -> None:
        """管理者セッションが1つ増えた。必要ならsys.settraceを有効化する。"""
        with self._lock:
            self._active_sessions += 1
            if self._active_sessions == 1:
                self._prev_trace = sys.gettrace()
                sys.settrace(self._trace_dispatch)
                threading.settrace(self._trace_dispatch)

    def on_session_stop(self) -> None:
        """管理者セッションが1つ減った。誰もいなくなったらsys.settraceを無効化する。"""
        with self._lock:
            self._active_sessions = max(0, self._active_sessions - 1)
            if self._active_sessions == 0:
                sys.settrace(self._prev_trace)
                threading.settrace(self._prev_trace)

    # ------------------------------------------------------------------
    # リクエストの開始/終了時に、統合レイヤー(Flask/FastAPI adapter)から
    # 呼ばれる、contextvarのセット/リセット
    # ------------------------------------------------------------------

    def bind_session_to_current_context(self, session_id: str):
        """現在のリクエストコンテキストにsession_idを紐付ける。
        戻り値はcontextvarのtoken(リクエスト終了時にresetへ渡すこと)。
        """
        return _current_session.set(session_id)

    def unbind_session_from_current_context(self, token) -> None:
        _current_session.reset(token)

    # ------------------------------------------------------------------
    # トレース本体
    # ------------------------------------------------------------------

    def _trace_dispatch(self, frame: FrameType, event: str, arg: Any):
        # 最初に、最も軽いチェックから: このコンテキストに紐づく
        # session_idが無ければ、即座に何もせず抜ける
        # (無関係なユーザーのリクエストへのオーバーヘッドを最小化する)
        session_id = _current_session.get()
        if session_id is None:
            return None

        if event != "call":
            return None

        filename = frame.f_code.co_filename

        # 疑似パス(<frozen ...> 等)は実ファイルではないため除外する
        if filename.startswith("<"):
            return None

        abs_filename = os.path.abspath(filename)

        if abs_filename.startswith(_CALLTRACER_PACKAGE_DIR):
            return None

        if not any(abs_filename.startswith(p) for p in self._include_paths):
            return None

        depth = _current_depth.get() + 1
        depth_token = _current_depth.set(depth)

        call_id = f"evt_{next(self._id_counter):05d}"
        self._event_bus.publish(
            session_id,
            {
                "id": call_id,
                "timestamp": time.time(),
                "source": "python",
                "type": "call",
                "depth": depth,
                "payload": {
                    "function": frame.f_code.co_name,
                    "file": filename,
                    "line": frame.f_lineno,
                    "args_summary": self._summarize_args(frame),
                },
            },
        )

        def local_trace(frame: FrameType, event: str, arg: Any):
            if event == "return":
                self._event_bus.publish(
                    session_id,
                    {
                        "id": f"{call_id}_ret",
                        "timestamp": time.time(),
                        "source": "python",
                        "type": "return",
                        "depth": depth,
                        "payload": {
                            "function": frame.f_code.co_name,
                            "call_id": call_id,
                        },
                    },
                )
                _current_depth.reset(depth_token)
            return local_trace

        return local_trace

    def _summarize_args(self, frame: FrameType) -> str:
        try:
            arg_names = frame.f_code.co_varnames[: frame.f_code.co_argcount]
            parts = []
            for name in arg_names:
                value = frame.f_locals.get(name, "?")
                text = repr(value)
                if len(text) > 40:
                    text = text[:37] + "..."
                parts.append(f"{name}={text}")
            return ", ".join(parts)
        except Exception:
            return ""