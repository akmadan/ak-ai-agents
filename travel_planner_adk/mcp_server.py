"""MCP server for the travel planner, packaged for AgentCore Runtime.

The planner runs inside this process. An MCP client sends one request string
and receives the planner's final reply.

AgentCore Runtime expects an MCP container to listen on 0.0.0.0:8000 at /mcp
and to run stateless. Set MCP_TRANSPORT=stdio only for a local client that
launches this script itself.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / "travel_planner" / ".env")

from google.adk.tools.mcp_tool import to_mcp_server
from starlette.requests import Request
from starlette.responses import JSONResponse

from travel_planner.agent import root_agent

server = to_mcp_server(
    root_agent,
    name="travel_planner",
    instructions=(
        "Plans a trip. Pass the traveler's request as the tool argument. "
        "The planner delegates to destination, itinerary, and budget specialists."
    ),
)


@server.custom_route("/ping", methods=["GET"])
async def ping(request: Request) -> JSONResponse:
    return JSONResponse({"status": "Healthy"})


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    if transport == "stdio":
        server.run(transport="stdio")
        return
    if transport != "streamable-http":
        raise SystemExit(
            "MCP_TRANSPORT must be 'streamable-http' or 'stdio', "
            f"got {transport!r}."
        )
    server.run(
        transport="streamable-http",
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_PORT") or os.getenv("PORT") or "8000"),
        streamable_http_path=os.getenv("MCP_PATH", "/mcp"),
        stateless_http=True,
    )


if __name__ == "__main__":
    main()
