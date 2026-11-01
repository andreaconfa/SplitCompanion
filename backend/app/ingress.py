"""Supervisor-only Ingress boundary; never enabled by a client-supplied header."""

from http.cookies import SimpleCookie
import re

from starlette.responses import JSONResponse
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

INGRESS_PORT = 8099
SUPERVISOR_IP = "172.30.32.2"
PREFIX = re.compile(r"/api/hassio_ingress/[A-Za-z0-9_-]{1,256}")
HOST = re.compile(r"(?:[A-Za-z0-9.-]+|\[[A-Fa-f0-9:]+\])(?::[0-9]{1,5})?")
COOKIE_NAMES = {
    "split_session": "split_ingress_session",
    "split_push_device": "split_ingress_push_device",
}


class IngressApp:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)
        if scope["type"] != "http":
            await send({"type": "websocket.close", "code": 1008})
            return
        if not scope.get("client") or scope["client"][0] != SUPERVISOR_IP:
            return await JSONResponse({"detail": "Forbidden"}, status_code=403)(
                scope, receive, send
            )
        # Duplicate routing headers are ambiguous and must fail closed.
        headers = {}
        for key, value in scope["headers"]:
            key = key.lower()
            if key in headers and key in (
                b"x-ingress-path",
                b"x-forwarded-host",
                b"x-forwarded-proto",
            ):
                return await JSONResponse({"detail": "Invalid ingress headers"}, status_code=400)(
                    scope, receive, send
                )
            headers[key] = value.decode("latin-1")
        prefix = headers.get(b"x-ingress-path", "")
        host = headers.get(b"x-forwarded-host", "")
        scheme = headers.get(b"x-forwarded-proto", "")
        if (
            not PREFIX.fullmatch(prefix)
            or not HOST.fullmatch(host)
            or scheme not in ("http", "https")
        ):
            return await JSONResponse({"detail": "Invalid ingress headers"}, status_code=400)(
                scope, receive, send
            )
        scope = dict(scope)
        scope["split_ingress"] = prefix
        scope["root_path"] = prefix
        scope["scheme"] = scheme
        # Only the Ingress-specific cookie names enter normal account authentication.
        incoming = SimpleCookie()
        incoming.load(headers.get(b"cookie", ""))
        cookies = "; ".join(
            f"{name}={incoming[ingress_name].coded_value}"
            for name, ingress_name in COOKIE_NAMES.items()
            if ingress_name in incoming
        )
        scope["headers"] = [
            (key, value)
            for key, value in scope["headers"]
            if key.lower() not in (b"host", b"cookie")
        ]
        scope["headers"] += [
            (b"host", host.encode("ascii")),
            (b"cookie", cookies.encode("latin-1")),
        ]

        async def ingress_send(message):
            if message["type"] == "http.response.start":
                message = dict(message)
                rewritten = []
                for key, value in message["headers"]:
                    if key.lower() == b"set-cookie":
                        cookie = SimpleCookie()
                        cookie.load(value.decode("latin-1"))
                        for name, morsel in cookie.items():
                            if name in COOKIE_NAMES:
                                scoped = SimpleCookie()
                                scoped[COOKIE_NAMES[name]] = morsel.value
                                target = scoped[COOKIE_NAMES[name]]
                                for attribute, setting in morsel.items():
                                    if setting:
                                        target[attribute] = setting
                                target["path"] = prefix + "/"
                                target["secure"] = scheme == "https"
                                value = target.OutputString().encode("latin-1")
                    rewritten.append((key, value))
                message["headers"] = rewritten
            await send(message)

        await self.app(scope, receive, ingress_send)


class HomeAssistantApp:
    """Dispatch by local socket before any forwarded-header interpretation."""

    def __init__(self, app, trusted_proxy_ips):
        self.app = app
        self.ingress = IngressApp(app)
        self.direct = ProxyHeadersMiddleware(app, trusted_hosts=trusted_proxy_ips)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)
        target = (
            self.ingress if scope.get("server", (None, None))[1] == INGRESS_PORT else self.direct
        )
        await target(scope, receive, send)
