"""A2A entrypoint so kagent can run this travel planner."""

import os

from a2a.types import AgentCapabilities
from a2a.types import AgentCard
from a2a.types import AgentSkill

from kagent.adk import KAgentApp
from travel_planner.agent import root_agent

agent_card = AgentCard(
    name="travel_planner",
    description=(
        "Plans a trip by delegating to destination, itinerary, and budget "
        "specialists."
    ),
    url="http://localhost:8080",
    version="0.1.0",
    capabilities=AgentCapabilities(streaming=False),
    defaultInputModes=["text"],
    defaultOutputModes=["text"],
    skills=[
        AgentSkill(
            id="plan-trip",
            name="Plan a trip",
            description=(
                "Suggests destinations, writes a day-by-day plan, and checks "
                "the budget."
            ),
            tags=["travel"],
        )
    ],
)

APP_NAME = "{}__NS__{}".format(
    os.getenv("KAGENT_NAMESPACE", "akshit-madan"),
    os.getenv("KAGENT_NAME", "travel-planner").replace("-", "_"),
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
