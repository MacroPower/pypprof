from starlette.responses import Response
from starlette.requests import Request
from starlette.types import ASGIApp
from fastapi import FastAPI

from .net_http import profile


def register_pprof_handlers(app: FastAPI):
    app.add_route("/debug/profile", handle_profile)
    return


def handle_profile(request: Request) -> Response:
    p = profile()
    headers = {
        "Content-Type": "application/octet-stream",
        "Content-Disposition": 'attachment; filename="profile"',
    }
    return Response(p, headers=headers)
