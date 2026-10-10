from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from graph.guardrails import input_guard, output_guard, route_after_input
from graph.nodes import (
    TOOLS,
    answer,
    ask_report,
    ask_symptoms,
    ingest,
    route_after_answer,
    route_after_understand,
    understand,
)
from graph.state import AgentState

_memory = MemorySaver()
_graph = None


def build():
    graph = StateGraph(AgentState)
    graph.add_node("input_guard", input_guard)
    graph.add_node("understand", understand)
    graph.add_node("ask_symptoms", ask_symptoms)
    graph.add_node("ask_report", ask_report)
    graph.add_node("ingest", ingest)
    graph.add_node("answer", answer)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_node("output_guard", output_guard)

    graph.add_edge(START, "input_guard")
    graph.add_conditional_edges(
        "input_guard",
        route_after_input,
        {"understand": "understand", "end": END},
    )
    graph.add_conditional_edges(
        "understand",
        route_after_understand,
        {
            "ingest": "ingest",
            "ask_symptoms": "ask_symptoms",
            "ask_report": "ask_report",
            "answer": "answer",
        },
    )
    graph.add_edge("ask_symptoms", "output_guard")
    graph.add_edge("ask_report", "output_guard")
    graph.add_edge("output_guard", END)
    graph.add_edge("ingest", "answer")
    graph.add_conditional_edges(
        "answer",
        route_after_answer,
        {"tools": "tools", "end": "output_guard"},
    )
    graph.add_edge("tools", "answer")
    return graph.compile(checkpointer=_memory)


def get_graph():
    global _graph
    if _graph is None:
        _graph = build()
    return _graph
