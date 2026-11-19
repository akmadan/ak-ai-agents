"""A2A server for the travel planner, packaged for AgentCore Runtime.

Other agents call this process with the Agent2Agent protocol. The planner
runs inside this process. Sessions and tasks stay in memory, so the server
runs as a stateless container.

AgentCore Runtime expects an A2A container to listen on 0.0.0.0:9000 at /
and serves the agent card at /.well-known/agent-card.json.

A2A_PUBLIC_URL, or AGENTCORE_RUNTIME_URL when AgentCore sets it, replaces the
localhost address inside the agent card. Routes stay on this process.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / "travel_planner" / ".env")

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from travel_planner.agent import root_agent

bind_host = os.getenv("A2A_BIND_HOST", "0.0.0.0")
bind_port = int(os.getenv("A2A_PORT") or os.getenv("PORT") or "9000")
public_host = os.getenv("A2A_HOST", "localhost")
public_port = int(os.getenv("A2A_PUBLIC_PORT") or str(bind_port))
protocol = os.getenv("A2A_PROTOCOL", "http")

a2a_app = to_a2a(
    root_agent,
    host=public_host,
    port=public_port,
    protocol=protocol,
)


async def ping(request: Request) -> JSONResponse:
    return JSONResponse({"status": "Healthy"})


a2a_app.router.routes.append(Route("/ping", ping, methods=["GET"]))


def _public_a2a_url() -> str | None:
    value = os.getenv("A2A_PUBLIC_URL") or os.getenv("AGENTCORE_RUNTIME_URL")
    return value.rstrip("/") if value else None


class AgentCardUrlMiddleware:
    """Rewrite the card's advertised URL without moving the local routes."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        public_url = _public_a2a_url()
        if (
            scope["type"] != "http"
            or scope.get("method") != "GET"
            or scope.get("path") != "/.well-known/agent-card.json"
            or not public_url
        ):
            await self.app(scope, receive, send)
            return

        status_code = 200
        response_headers: list[tuple[bytes, bytes]] = []
        body = bytearray()

        async def capture(message):
            nonlocal status_code, response_headers
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = list(message.get("headers", []))
            elif message["type"] == "http.response.body":
                body.extend(message.get("body", b""))

        await self.app(scope, receive, capture)
        if status_code != 200 or not body:
            await send({
                "type": "http.response.start",
                "status": status_code,
                "headers": response_headers,
            })
            await send({"type": "http.response.body", "body": bytes(body)})
            return

        card = json.loads(body)
        for interface in card.get("supportedInterfaces") or []:
            if isinstance(interface, dict) and "url" in interface:
                interface["url"] = public_url
        if "url" in card:
            card["url"] = public_url
        payload = json.dumps(card).encode()
        headers = [
            (name, value)
            for name, value in response_headers
            if name.lower() not in {b"content-length", b"etag"}
        ]
        headers.append((b"content-length", str(len(payload)).encode()))
        await send({"type": "http.response.start", "status": 200, "headers": headers})
        await send({"type": "http.response.body", "body": payload})


a2a_app.add_middleware(AgentCardUrlMiddleware)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(a2a_app, host=bind_host, port=bind_port)
