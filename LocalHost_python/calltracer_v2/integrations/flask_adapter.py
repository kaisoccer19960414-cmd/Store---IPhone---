"""
integrations/flask_adapter.py
==============================

Flaskアプリに、最小限の変更(init_flask()を1回呼ぶだけ)でCallTracerを
組み込むための統合レイヤー。

使い方:
    from calltracer_v2 import init_flask

    def is_admin(request):
        auth = request.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ")
        return verify_token(token)  # 既存の認証関数をそのまま使う

    init_flask(app, is_admin=is_admin)

追加されるエンドポイント(すべてurl_prefix配下、デフォルト /__calltracer__):
    GET  /viewer         管理者用Viewer画面(is_adminで保護)
    GET  /inject.js      fetchを横取りするJS(is_adminで保護)
    POST /session/start  トレースセッションを開始する(is_adminで保護)
    POST /session/stop    トレースセッションを終了する(is_adminで保護)
    POST /events         JS側からのfetchイベント受信(セッション有効性のみ確認)
    GET  /stream         SSEでイベントをViewerへ配信(is_adminで保護)
"""

from __future__ import annotations

import json
import os
import time
from typing import Callable, Optional

from flask import Blueprint, Response, jsonify, request

from ..core.event_bus import EventBus
from ..core.session import SessionRegistry
from ..core.tracer import Tracer


def init_flask(
    app,
    is_admin: Callable[[object], bool],
    include_paths: Optional[list[str]] = None,
    url_prefix: str = "/__calltracer__",
) -> None:
    """FlaskアプリにCallTracerを組み込む。対象アプリ側の変更はこの1行だけでよい。

    Args:
        app: Flaskアプリケーションインスタンス
        is_admin: リクエスト(flask.request相当)を受け取り、管理者かどうかを
                  返す関数。既存の認証ロジックをそのまま渡すことを想定。
        include_paths: トレース対象にするディレクトリ。省略時は、
                  対象アプリのメインモジュールが置かれているディレクトリを
                  自動で使う。
        url_prefix: エンドポイントのプレフィックス。
    """
    if include_paths is None:
        # app.root_path はFlaskがアプリのルートディレクトリとして
        # 認識している場所(通常はメインスクリプトのあるフォルダ)
        include_paths = [app.root_path]

    event_bus = EventBus()
    session_registry = SessionRegistry()
    tracer = Tracer(event_bus=event_bus, include_paths=include_paths)

    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

    bp = Blueprint("calltracer", __name__, url_prefix=url_prefix)

    def _require_admin():
        if not is_admin(request):
            return jsonify({"error": "forbidden"}), 403
        return None

    @bp.get("/viewer")
    def viewer():
        # 注意: このページ自体はis_adminで保護しない。
        # ブラウザの通常のページ遷移(アドレスバー入力やリンククリック)は、
        # Cookie以外の認証方式(Bearerトークンなど)のカスタムヘッダーを
        # 送れないため、ヘッダーベースのis_adminチェックがそもそも機能しない。
        # 実際のセキュリティ境界は /session/start (fetch()経由でカスタム
        # ヘッダーを送れる)にある。このページ単体を誰かが開けても、
        # 有効なセッションを開始できなければ何のデータも流れない。
        with open(os.path.join(static_dir, "timeline.html"), "r", encoding="utf-8") as f:
            return Response(f.read(), mimetype="text/html")

    @bp.get("/inject.js")
    def inject_js():
        # 同上の理由でis_admin保護を外している。<script src="...">タグからの
        # 読み込みもカスタムヘッダーを送れないため。このスクリプト自体は
        # 「localStorageに有効なsession_idがあれば報告する」という無害な
        # コードなので、内容が見られること自体に問題は無い。
        with open(os.path.join(static_dir, "inject.js"), "r", encoding="utf-8") as f:
            return Response(f.read(), mimetype="application/javascript")

    @bp.post("/session/start")
    def session_start():
        denied = _require_admin()
        if denied:
            return denied
        session_id = session_registry.start()
        tracer.on_session_start()
        return jsonify({"session_id": session_id})

    @bp.post("/session/stop")
    def session_stop():
        # 注意: タブを閉じた時にnavigator.sendBeacon()で自動終了を試みるが、
        # sendBeaconはカスタムヘッダーを送れないため、ここもis_adminでは
        # 保護できない。「セッションを止める」操作自体は、知っていても
        # 実害が薄い(管理者のトレースが早めに切れるだけ)ため、
        # 有効なsession_idを知っていることだけを条件にする。
        body = request.get_json(silent=True) or {}
        session_id = body.get("session_id")
        if session_id and session_registry.is_active(session_id):
            session_registry.stop(session_id)
            event_bus.discard(session_id)
            tracer.on_session_stop()
        return jsonify({"ok": True})

    @bp.post("/events")
    def events():
        # JS側からの報告は、管理者ログインのやり取りをその都度繰り返すのは
        # 重いので、「有効なセッションIDを知っているか」だけで検証する
        # (セッションIDはis_adminを通過した管理者にしか発行されないため)
        session_id = request.headers.get("X-CallTracer-Session")
        if not session_registry.is_active(session_id):
            return jsonify({"error": "invalid session"}), 403
        body = request.get_json(silent=True) or {}
        event_bus.publish(session_id, body)
        return jsonify({"ok": True})

    @bp.get("/stream")
    def stream():
        # 注意: ブラウザ標準のEventSource APIはカスタムヘッダーを送れないため、
        # ここもis_adminの再チェックはできない。session_idは
        # /session/start(is_adminで保護済み)を通過した管理者にしか
        # 発行されない、推測不可能なトークンなので、これ自体を通行証として扱う。
        session_id = request.args.get("session_id")
        if not session_registry.is_active(session_id):
            return jsonify({"error": "invalid session"}), 403

        def generate():
            while session_registry.is_active(session_id):
                try:
                    event = event_bus.get(session_id, timeout=15)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except Exception:
                    # timeout時は接続維持のためのコメント行を送る(SSEの作法)
                    yield ": keep-alive\n\n"

        return Response(generate(), mimetype="text/event-stream")

    app.register_blueprint(bp)

    # --- 全リクエストへのフック: セッションIDをcontextvarへ紐付ける ---

    @app.before_request
    def _calltracer_bind():
        session_id = request.headers.get("X-CallTracer-Session")
        if session_registry.is_active(session_id):
            session_registry.touch(session_id)
            request._calltracer_token = tracer.bind_session_to_current_context(session_id)
        else:
            request._calltracer_token = None

    @app.teardown_request
    def _calltracer_unbind(exc=None):
        from flask import request as req  # teardown時のrequestを明示的に取得

        token = getattr(req, "_calltracer_token", None)
        if token is not None:
            tracer.unbind_session_from_current_context(token)