"""A2A entrypoint for running the agent as a kagent BYO agent.

kagent talks to BYO agents over A2A, so this wraps the same root_agent that
server.py serves with KAgentApp instead of the Agent Runtime HTTP contract.
"""

import os

from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from kagent.adk import KAgentApp
from medical_assistant.agent import root_agent

agent_card = AgentCard(
    name="medical_assistant",
    description="Answers general health questions with input and output guardrails.",
    url="http://localhost:8080",
    version="0.1.0",
    capabilities=AgentCapabilities(streaming=False),
    defaultInputModes=["text"],
    defaultOutputModes=["text"],
    skills=[
        AgentSkill(
            id="general-health-qa",
            name="General health Q&A",
            description="Answers general health questions; does not diagnose or prescribe.",
            tags=["health", "medical"],
        )
    ],
)

# The controller resolves sessions by "<namespace>__NS__<agent_name>"; kagent
# injects KAGENT_NAMESPACE and KAGENT_NAME into every BYO pod.
APP_NAME = "{}__NS__{}".format(
    os.getenv("KAGENT_NAMESPACE", "kagent"),
    os.getenv("KAGENT_NAME", "medical-assistant").replace("-", "_"),
)

kagent_app = KAgentApp(
    root_agent_factory=lambda: root_agent,
    agent_card=agent_card,
    kagent_url=os.getenv(
        "KAGENT_URL", "http://kagent-controller.kagent.svc.cluster.local:8083"
    ),
    app_name=APP_NAME,
)

app = kagent_app.build()
