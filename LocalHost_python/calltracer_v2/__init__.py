"""
calltracer_v2
=============

対象アプリのコード変更を最小限に抑えた、本番常設用のデバッグツール。

使い方(Flask):
    from calltracer_v2 import init_flask
    init_flask(app, is_admin=my_is_admin_func)

使い方(FastAPI):
    from calltracer_v2 import init_fastapi
    init_fastapi(app, is_admin=my_is_admin_func)
"""

from .integrations.flask_adapter import init_flask

__all__ = ["init_flask"]

try:
    from .integrations.fastapi_adapter import init_fastapi  # noqa: F401

    __all__.append("init_fastapi")
except ImportError:
    # starlette/fastapiが無い環境でも、Flask側だけは使えるようにしておく
    pass