"""
Project:   edgestream-api
File:      edgestream/services/middleware.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

import uuid
import re
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.datastructures import MutableHeaders

ID_HEADERS = ["x-request-id", "x-correlation-id"]

VALID_ID_RE = re.compile(r"^[a-zA-Z0-9-]{1,64}$")


class CorrelationIdMiddleware:
    """
    ASGI Middleware that ensures every request has a unique Correlation ID.
    This ID is propagated through the request state and returned in response headers.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = MutableHeaders(scope=scope)
        request_id = None

        for header_name in ID_HEADERS:
            existing_id = headers.get(header_name)
            if existing_id and VALID_ID_RE.match(existing_id):
                request_id = existing_id
                break

        if not request_id:
            request_id = str(uuid.uuid4())

        if "state" not in scope:
            scope["state"] = {}

        scope["state"]["correlation_id"] = request_id
        scope["state"]["request_id"] = request_id

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                if not response_headers.get("X-Correlation-ID"):
                    response_headers.append("X-Correlation-ID", request_id)
            await send(message)

        await self.app(scope, receive, send_wrapper)
