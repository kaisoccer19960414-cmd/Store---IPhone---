"""
integrations/fastapi_adapter.py
=================================

FastAPI(Starlette)アプリに、最小限の変更(init_fastapi()を1回呼ぶだけ)で
CallTracerを組み込むための統合レイヤー。Flask版(flask_adapter.py)と
設計・エンドポイント構成は完全に対をなす。

使い方:
    from calltracer_v2 import init_fastapi

    def is_admin(request):
        auth = request.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ")
        return verify_token(token)

    init_fastapi(app, is_admin=is_admin)

注意:
- contextvarsは、Starletteが各リクエストを独立したasyncio Taskとして
  実行するため、非同期(async def)のエンドポイントでも同時並行リクエスト間で
  正しく分離される(Flask/WSGIのスレッド分離と同じ理屈が、asyncioの
  Task分離でもそのまま成り立つ)。
- このモジュールは fastapi が無い環境ではimportエラーになるが、
  calltracer_v2/__init__.py側でtry/exceptにより吸収され、
  Flask側だけは問題なく使えるようになっている。
"""

from __future__ import annotations

import os
from typing import Awaitable, Callable, Optional, Union

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from starlette.routing import Route

from ..core.event_bus import EventBus
from ..core.session import SessionRegistry
from ..core.tracer import Tracer

IsAdminFunc = Callable[[Request], Union[bool, Awaitable[bool]]]


async def _maybe_await(value):
    """is_adminが同期関数(bool)でも非同期関数(コルーチン)でも、
    どちらでも受け付けられるようにするための小さなヘルパー。"""
    if hasattr(value, "__await__"):
        return await value
    return value


def init_fastapi(
    app: Starlette,
    is_admin: IsAdminFunc,
    include_paths: Optional[list[str]] = None,
    url_prefix: str = "/__calltracer__",
) -> None:
    """FastAPI/StarletteアプリにCallTracerを組み込む。

    Args:
        app: FastAPI(Starlette)アプリケーションインスタンス
        is_admin: Requestを受け取り、管理者かどうかを返す関数
                  (同期関数・async関数のどちらでもよい)。
        include_paths: トレース対象にするディレクトリ。省略時はカレント
                  ディレクトリ(対象アプリの起動場所)を使う。
        url_prefix: エンドポイントのプレフィックス。
    """
    if include_paths is None:
        include_paths = [os.getcwd()]

    event_bus = EventBus()
    session_registry = SessionRegistry()
    tracer = Tracer(event_bus=event_bus, include_paths=include_paths)

    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

    async def viewer(request: Request) -> Response:
        # Flask版と同じ理由(ページ遷移・script/EventSourceはカスタム
        # ヘッダーを送れない)で、ここはis_adminによる保護をしない。
        with open(os.path.join(static_dir, "timeline.html"), "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())

    async def inject_js(request: Request) -> Response:
        with open(os.path.join(static_dir, "inject.js"), "r", encoding="utf-8") as f:
            return PlainTextResponse(f.read(), media_type="application/javascript")

    async def session_start(request: Request) -> Response:
        if not await _maybe_await(is_admin(request)):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        session_id = session_registry.start()
        tracer.on_session_start()
        return JSONResponse({"session_id": session_id})

    async def session_stop(request: Request) -> Response:
        # Flask版と同じ理由(sendBeaconの制約)でis_admin保護はしない
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        session_id = body.get("session_id")
        if session_id and session_registry.is_active(session_id):
            session_registry.stop(session_id)
            event_bus.discard(session_id)
            tracer.on_session_stop()
        return JSONResponse({"ok": True})

    async def events(request: Request) -> Response:
        session_id = request.headers.get("X-CallTracer-Session")
        if not session_registry.is_active(session_id):
            return JSONResponse({"error": "invalid session"}, status_code=403)
        try:
            body = await request.json()
        except Exception:
            body = {}
        event_bus.publish(session_id, body)
        return JSONResponse({"ok": True})

    async def poll(request: Request) -> Response:
        # Flask版と同じ理由(Gunicorn等のsyncワーカーが長時間ブロックする
        # 接続を誤検知して強制終了する問題)で、SSEではなくポーリング方式にする。
        # FastAPI/Uvicornの非同期ワーカーであればSSEも問題なく動く可能性が
        # 高いが、Flask/Gunicorn構成と実装を共通化しておくため、こちらも
        # 同じポーリング方式に統一する。
        session_id = request.query_params.get("session_id")
        if not session_registry.is_active(session_id):
            return JSONResponse({"error": "invalid session"}, status_code=403)
        session_registry.touch(session_id)
        events = event_bus.drain_nowait(session_id)
        return JSONResponse({"events": events})

    prefix = url_prefix.rstrip("/")
    app.router.routes.extend(
        [
            Route(f"{prefix}/viewer", viewer, methods=["GET"]),
            Route(f"{prefix}/inject.js", inject_js, methods=["GET"]),
            Route(f"{prefix}/session/start", session_start, methods=["POST"]),
            Route(f"{prefix}/session/stop", session_stop, methods=["POST"]),
            Route(f"{prefix}/events", events, methods=["POST"]),
            Route(f"{prefix}/poll", poll, methods=["GET"]),
        ]
    )

    @app.middleware("http")
    async def _calltracer_middleware(request: Request, call_next):
        session_id = request.headers.get("X-CallTracer-Session")
        token = None
        request_token = None
        if session_registry.is_active(session_id):
            session_registry.touch(session_id)
            token = tracer.bind_session_to_current_context(session_id)
            request_id = request.headers.get("X-CallTracer-Request-Id")
            if request_id:
                request_token = tracer.bind_request_id_to_current_context(request_id)
        try:
            response = await call_next(request)
        finally:
            if token is not None:
                tracer.unbind_session_from_current_context(token)
            if request_token is not None:
                tracer.unbind_request_id_from_current_context(request_token)
        return response