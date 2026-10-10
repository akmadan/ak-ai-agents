# Medical Assistant (LangGraph)

Multi-turn medical assistant that clarifies symptoms, indexes an uploaded report into local ChromaDB, and answers from that report plus public web search. Llama is called through LiteLLM on Groq.

The assistant explains what is in the uploaded report and in public sources. It does not diagnose, prescribe, or invent values that were not retrieved. Every answer asks you to confirm with a clinician. Chest pain, trouble breathing, stroke signs, and severe bleeding get an urgent-care prompt.

## Setup

Python 3.11 or newer is required.

```bash
cd medical_assistant_langgraph
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

- `GROQ_API_KEY` — Groq key, used by LiteLLM
- `TAVILY_API_KEY` — web search
- `LLM` — defaults to `groq/llama-3.3-70b-versatile`

## Run

```bash
streamlit run app.py
```

Use the sidebar to upload a PDF or text report. The next message indexes it for that browser session and replaces any earlier report from the same session. Reports stay on this machine under `chroma_data/` and `uploads/`.

## How a turn works

1. An input guardrail checks the message. Questions outside health, symptoms, and medical reports are refused. Prompt injection is refused. Messages about suicide or self-harm stop with a short 988 notice and are not answered with methods.
2. The graph updates a short symptom summary and decides whether the question is about this person's report or general information.
3. Thin symptom descriptions get at most two follow-up questions.
4. Questions about the user's own results ask for an upload when nothing is indexed yet. General questions can be answered from the web without a file.
5. A new upload is chunked, embedded with local `all-MiniLM-L6-v2`, and stored in Chroma before the answer.
6. The answer node may search the report and the web. Report evidence is preferred. Web results are labeled as general information.
7. An output guardrail checks the draft. A reply that answers a non-health question, diagnoses, prescribes a drug or dose, or gives harmful instructions is replaced with a refusal. Other replies keep the clinician disclaimer.
