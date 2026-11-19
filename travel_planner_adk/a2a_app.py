"""A2A server for the travel planner.

Other agents call this process with the Agent2Agent protocol. The planner
runs inside this process. Sessions and tasks stay in memory.

A2A_HOST, A2A_PUBLIC_PORT, and A2A_PROTOCOL are the address written on the
agent card. A2A_BIND_HOST and A2A_PORT are where this process listens. Set
the public values when this server is reached through another hostname.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / "travel_planner" / ".env")

from google.adk.a2a.utils.agent_to_a2a import to_a2a

from travel_planner.agent import root_agent

bind_host = os.getenv("A2A_BIND_HOST", "0.0.0.0")
bind_port = int(os.getenv("A2A_PORT") or os.getenv("PORT") or "8001")
public_host = os.getenv("A2A_HOST", "localhost")
public_port = int(os.getenv("A2A_PUBLIC_PORT") or str(bind_port))
protocol = os.getenv("A2A_PROTOCOL", "http")

a2a_app = to_a2a(
    root_agent,
    host=public_host,
    port=public_port,
    protocol=protocol,
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(a2a_app, host=bind_host, port=bind_port)
