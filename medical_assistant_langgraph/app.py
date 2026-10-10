import os
import uuid
from pathlib import Path

_SKIP_WATCH_PREFIXES = ("transformers", "torch", "sentence_transformers", "chromadb")


def _skip_lazy_transformer_modules() -> None:
    """Do not let Streamlit import Transformers compatibility modules.

    Uploading a PDF loads Transformers. Its `*_fast` aliases have no real file,
    and reading `__path__` imports image models that require torchvision.
    """
    try:
        from streamlit.watcher import local_sources_watcher as watcher
    except Exception:
        return

    original = watcher.get_module_paths

    def get_module_paths(module):
        module_dict = getattr(module, "__dict__", {})
        name = module_dict.get("__name__", "")
        if name.startswith(_SKIP_WATCH_PREFIXES):
            file = module_dict.get("__file__")
            if isinstance(file, str) and os.path.isfile(file):
                return {os.path.realpath(file)}
            return set()
        return original(module)

    watcher.get_module_paths = get_module_paths


_skip_lazy_transformer_modules()

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

from config import DISCLAIMER, UPLOADS_DIR, missing_keys
from graph.builder import get_graph
from graph.nodes import message_text
from rag.store import delete_session

st.set_page_config(page_title="Medical Assistant")
st.title("Medical Assistant")
st.caption(DISCLAIMER)

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "pending_path" not in st.session_state:
    st.session_state.pending_path = None
if "last_error" not in st.session_state:
    st.session_state.last_error = None

graph = get_graph()
config = {"configurable": {"thread_id": st.session_state.thread_id}, "recursion_limit": 20}


def snapshot_values() -> dict:
    snapshot = graph.get_state(config)
    return snapshot.values or {}


def _meta_line(fields: dict) -> str:
    parts = []
    model = fields.get("model")
    if model:
        parts.append(f"model: {model}")
    elif fields.get("models"):
        parts.append("model: " + ", ".join(fields["models"]))
    prompt_tokens = fields.get("prompt_tokens", fields.get("input_tokens", 0))
    completion_tokens = fields.get("completion_tokens", fields.get("output_tokens", 0))
    total_tokens = fields.get("total_tokens", prompt_tokens + completion_tokens)
    parts.append(f"prompt_tokens: {prompt_tokens}")
    parts.append(f"completion_tokens: {completion_tokens}")
    parts.append(f"total_tokens: {total_tokens}")
    parts.append(f"latency_ms: {fields.get('latency_ms', 0)}")
    cost = fields.get("response_cost")
    if isinstance(cost, (int, float)):
        parts.append(f"response_cost: {cost:.6f}")
    if fields.get("decision"):
        parts.append(f"decision: {fields['decision']}")
    if fields.get("reason"):
        parts.append(f"reason: {fields['reason']}")
    return " · ".join(parts)


def render_turn_metadata(message: AIMessage) -> None:
    turn = (message.response_metadata or {}).get("turn") or {}
    calls = turn.get("calls") or []
    if not calls and not turn:
        return
    st.caption(_meta_line(turn))
    with st.expander("Run details"):
        for call in calls:
            st.write(f"{call.get('step')}: {_meta_line(call)}")


with st.sidebar:
    st.header("Report")
    uploaded = st.file_uploader("Upload a PDF or text report", type=["pdf", "txt"])
    if uploaded is not None:
        signature = (uploaded.name, uploaded.size)
        if signature != st.session_state.get("upload_sig"):
            session_dir = UPLOADS_DIR / st.session_state.thread_id
            session_dir.mkdir(parents=True, exist_ok=True)
            destination = session_dir / Path(uploaded.name).name
            destination.write_bytes(uploaded.getvalue())
            st.session_state.pending_path = str(destination)
            st.session_state.upload_sig = signature

    values = snapshot_values()
    if values.get("report_indexed"):
        st.success("Report indexed")
    else:
        st.info("No report indexed")
    if st.session_state.pending_path:
        st.write("Report saved. It will be indexed with your next message.")
    if values.get("symptoms"):
        st.subheader("Symptoms")
        st.write(values["symptoms"])

    missing = missing_keys()
    if missing:
        st.warning("Missing env: " + ", ".join(missing))

    if st.button("New conversation"):
        delete_session(st.session_state.thread_id)
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.pending_path = None
        st.session_state.upload_sig = None
        st.rerun()

values = snapshot_values()
visible = False
for message in values.get("messages") or []:
    if isinstance(message, HumanMessage):
        with st.chat_message("user"):
            st.markdown(message_text(message.content))
        visible = True
    elif isinstance(message, AIMessage) and message.content and not message.tool_calls:
        with st.chat_message("assistant"):
            st.markdown(message_text(message.content))
            render_turn_metadata(message)
        visible = True

if not visible:
    with st.chat_message("assistant"):
        st.markdown(
            "Tell me what you're feeling, or ask a general medical question. "
            "If you have a report, upload the PDF or text file in the sidebar "
            "and I will answer from that document."
        )

if st.session_state.last_error:
    st.error(st.session_state.last_error)

prompt = st.chat_input("Describe your symptoms or ask about your report")
if prompt:
    payload = {
        "messages": [HumanMessage(content=prompt)],
        "session_id": st.session_state.thread_id,
    }
    if st.session_state.pending_path:
        payload["pending_report_path"] = st.session_state.pending_path
    if not values:
        payload.update(
            {
                "symptoms": "",
                "symptom_questions_asked": 0,
                "report_indexed": False,
                "needs_personal_report": False,
                "symptoms_sufficient": False,
                "red_flag": False,
                "ingest_note": "",
            }
        )
    try:
        with st.spinner("Thinking..."):
            graph.invoke(payload, config=config)
    except Exception as exc:
        st.session_state.last_error = str(exc)
    else:
        st.session_state.last_error = None
        st.session_state.pending_path = None
    st.rerun()
