# AI Detective — Interrogation Room

An AI-powered noir detective game where players interrogate suspects, consult a detective partner, and submit a final accusation judged by an LLM rubric.

---

## What this project is

This repo is a full-stack game:

- **Frontend (Vite + Vanilla JS):** cinematic UI, suspect lineup, text/voice interrogation, verdict flow, PDF case report.
- **Backend (FastAPI):** case generation, agent-memory generation, suspect/task/judge orchestration, REST + WebSocket APIs.
- **AI system:** multiple specialized agents (suspects, task partner, judge) with per-case memory folders generated on demand.

---

## AI architecture (end-to-end)

At game start, the backend creates a fresh case and builds a per-case agent memory graph:

1. **Case Generator (`story_generator.py`)**
   - Uses RAG over `mystery_rag_index` (FAISS + MiniLM embeddings) for style/context seeding.
   - Calls OpenRouter models to produce strict JSON case files.
   - Writes `game_case_v2_<difficulty>_<timestamp>.json`.

2. **GraphRAG Builder (`graphrag_agent.py`)**
   - Creates `game_agents_<case_id>/`.
   - Generates:
     - detective briefing (`detective_briefing/briefing.{json,txt}`)
     - truth graph (`truth_graph.json`) for judge scoring
     - one folder per suspect (`identity`, `knowledge`, `beliefs`, `memories`, `relationships`, `conversation_state`)
     - task agent knowledge + investigatable sources + hint system

3. **Runtime Orchestrator (`server.py`)**
   - Creates an in-memory `GameSession` keyed by `case_id`.
   - Initializes suspect agents and task agent from generated memory files.
   - Serves REST and WebSocket endpoints used by the browser client.

4. **Interrogation Layer (`custom_voice_agent.py` + `task_agent.py`)**
   - **Suspect agents:** persona-constrained 2–3 sentence responses with saved chat history.
   - **Task agent:** detective partner that answers investigation requests by matching against generated evidence/source memory.
   - **Voice mode:** STT → LLM streaming → TTS chunk streaming with optional translation.

5. **Judge Layer (`JudgeAgent` in `server.py`)**
   - Scores final accusation with strict rubric:
     - WHO (25), WHY (50), HOW (25)
     - zero-sum rule if WHO is wrong
   - Uses full interrogation + task transcript context.
   - Returns score, critique, analysis, and ground-truth reveal.

---

## Runtime request flow

### A) Game creation

`Frontend /game/create` → `FastAPI create_game()`:

- generate case (or fallback default case)
- generate agent memory folders (or copy fallback static agents)
- create session + suspect profiles
- return briefing + suspects + metadata

### B) Text interrogation

`POST /game/{case_id}/interrogate`:

- validate suspect + question budget
- optional translate user text to English
- run suspect text agent response
- optional translate back to player language
- persist conversation history + question counts

### C) Voice interrogation (streaming)

`WS /game/{case_id}/interrogate/voice`:

- browser sends base64 WAV/WebM
- backend STT transcribes
- suspect LLM streams output
- backend streams TTS audio chunks + transcript events back over WS
- frontend queues chunks and animates live talking

### D) Detective partner queries

`POST /game/{case_id}/task`:

- routes to task agent
- task agent uses generated investigatable sources and live suspect chat histories
- returns concise partner-style response

### E) Final verdict

`POST /game/{case_id}/submit`:

- judge scores against truth graph + transcripts
- returns breakdown, narrative analysis, and actual solution

---

## Repository map (practical view)

```text
ai-detective-game/
├─ README.md
├─ package.json                      # root helper scripts
├─ frontend/
│  ├─ index.html                     # full game UI screens
│  ├─ main.js                        # game state, API calls, WS, VAD, verdict UI
│  ├─ style.css                      # noir visual system
│  ├─ imageHelper.js                 # padded image detector helper
│  ├─ vite.config.js                 # /game proxy -> localhost:8000
│  └─ assets/
│     ├─ audio/
│     └─ characters/
└─ backend/
   ├─ server.py                      # FastAPI app + all game endpoints
   ├─ story_generator.py             # LLM case generation with RAG context
   ├─ graphrag_agent.py              # memory folder generator per case
   ├─ custom_voice_agent.py          # suspect text/voice interrogation engine
   ├─ task_agent.py                  # detective partner logic
   ├─ langgraph_orchestrator.py      # CLI orchestrator (non-web flow)
   ├─ requirements.txt
   ├─ .env.example
   ├─ playful_mysteries_100.json     # source corpus for embedding index
   ├─ create_rag.py                  # rebuild FAISS index from corpus
   ├─ mystery_rag_index/             # generated FAISS index
   ├─ embedding_cache/               # local HF embedding cache
   ├─ game_case_v2_easy_default.json # fallback default case
   └─ game_agents/                   # static fallback memory set
```

---

## Environment variables

Create `backend/.env`:

```env
# Runtime LLM for suspect/task flows
GROQ_API_KEY=...

# Judge + case generation (OpenRouter in current code paths)
OPENROUTER_API_KEY=...

# Voice stack: STT/TTS/translation
SARVAM_API_KEY=...
```

`backend/.env.example` also contains `SAMBANOVA_API_KEY` for older/experimental scripts.

---

## Setup

## 1) Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python server.py
```

Backend runs on `http://localhost:8000`.

## 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5000` and proxies `/game` + WS requests to backend.

---

## API surface (backend)

- `POST /game/create` — generate a new playable case session
- `POST /game/load` — load existing generated case file
- `GET /game/{case_id}` — session state + remaining questions
- `POST /game/{case_id}/interrogate` — text interrogation
- `WS /game/{case_id}/interrogate/voice` — streaming voice interrogation
- `POST /game/{case_id}/punch` — intimidation/punch reaction event
- `POST /game/{case_id}/task` — detective partner query
- `POST /game/{case_id}/submit` — final accusation scoring
- `GET /health` — service health + active session count

---

## Gameplay model

- **Question budgets:** per suspect + separate task-agent budget.
- **Modes:** text or voice.
- **Language:** multilingual support in voice mode through translation pipeline.
- **Verdict scoring:** WHO/WHY/HOW with strict rubric and detailed post-game critique.

---

## Notes for contributors

- Generated runtime artifacts (`game_agents_*`, `game_case_v2_*`, caches) are intentionally ignored in git.
- The frontend is intentionally framework-free and stateful in a single `main.js` for rapid iteration.
- Most AI behavior is prompt-driven; key behavior constraints live in:
  - `custom_voice_agent.py` (suspect persona/response rules)
  - `task_agent.py` (partner behavior and evidence lookup constraints)
  - `server.py` judge prompt (scoring rubric + transcript-aware critique)

---

## Rebuilding the RAG index (optional)

If you change `playful_mysteries_100.json`:

```bash
cd backend
python create_rag.py
```

This regenerates `mystery_rag_index/`.

