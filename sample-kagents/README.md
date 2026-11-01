# Sample kagents

Two folders:

- `declarative/` — agents described in YAML. kagent runs them.
- `byo/` — agents you build and package yourself. kagent runs your image.

# Declarative Agent Examples

## Travel planner

`declarative/travel-planner-declarative-agent/` is a travel planner for the `akshit-madan` namespace.

It talks to the user, then asks three helpers: where to go, the day-by-day plan, and whether the trip fits the budget. Destination ideas come from the saved place list. Web facts come from Tavily.

Two copies of the same agents:

- `sandbox/` — try it here first.
- `production/` — apply this when you want it running for real.

### Files

- `secret.yaml` — Gemini key and Tavily key. Replace `REPLACE_ME` before you apply. `TAVILY_AUTHORIZATION` must look like `Bearer tvly-...`.
- `modelconfig.yaml` — Gemini model those agents use.
- `prompts.yaml` — what the planner and the three helpers are told to do.
- `tavily.yaml` — web search.
- `place-catalog/` — the saved place list, served as a `search_destinations` tool.
- `sandbox/agents.yaml` — the planner and three helpers, sandbox copy.
- `production/agents.yaml` — the same agents, production copy.

### Run

Build the place catalog image with Docker pointed at Colima:

```bash
docker build -t travel-place-catalog:sandbox \
  sample-kagents/declarative/travel-planner-declarative-agent/place-catalog
```

Fill in `secret.yaml`, then:

```bash
kubectl apply -f sample-kagents/declarative/travel-planner-declarative-agent/secret.yaml
kubectl apply -f sample-kagents/declarative/travel-planner-declarative-agent/modelconfig.yaml
kubectl apply -f sample-kagents/declarative/travel-planner-declarative-agent/prompts.yaml
kubectl apply -f sample-kagents/declarative/travel-planner-declarative-agent/tavily.yaml
kubectl apply -f sample-kagents/declarative/travel-planner-declarative-agent/place-catalog/mcpserver.yaml
kubectl apply -f sample-kagents/declarative/travel-planner-declarative-agent/sandbox/agents.yaml
```

Chat with `travel-planner` in `akshit-madan`. When that looks right:

```bash
kubectl apply -f sample-kagents/declarative/travel-planner-declarative-agent/production/agents.yaml
```
---

# BYO Agent Examples

## Travel planner

`byo/travel-planner-byo-agent/` is the same travel planner, packaged as your own image. The planner code is in `travel_planner/`. kagent talks to that image.

Two copies:

- `sandbox/` — try it here first.
- `production/` — apply this when you want it running for real.

### Files

- `travel_planner/` — the planner, the three helpers, the place list, and web search.
- `kagent_app.py` — the entrypoint kagent calls.
- `requirements.txt` — Python packages for that image.
- `Dockerfile` — builds the image.
- `secret.yaml` — Gemini key and Tavily key. Replace `REPLACE_ME` before you apply.
- `sandbox/agent.yaml` — sandbox copy.
- `production/agent.yaml` — production copy.

### Run

Build the image with Docker pointed at Colima:

```bash
docker build -t travel-planner-byo:sandbox \
  sample-kagents/byo/travel-planner-byo-agent
```

Fill in `secret.yaml`, then:

```bash
kubectl apply -f sample-kagents/byo/travel-planner-byo-agent/secret.yaml
kubectl apply -f sample-kagents/byo/travel-planner-byo-agent/sandbox/agent.yaml
```

Chat with `travel-planner` in `akshit-madan`. When that looks right:

```bash
kubectl apply -f sample-kagents/byo/travel-planner-byo-agent/production/agent.yaml
```
