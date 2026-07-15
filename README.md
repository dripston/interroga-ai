# AI Detective — Interrogation Room

An immersive, browser-based noir detective game powered by a multi-agent system. Players interrogate suspects in real-time using text or voice to gather evidence, solve a dynamically generated murder mystery, and submit a case file to the Judge for evaluation.

---

## 🚀 Key Features

* **LangGraph Multi-Agent Orchestration**: Separate, stateful LLM agents represent individual suspects, a detective partner (Task Agent), and the Judge.
* **Interactive Voice Interrogation**: Real-time speech-to-text (STT) and text-to-speech (TTS) streaming using Sarvam AI.
* **Smart Voice Activity Detection (VAD)**: Browser-level audio energy analysis (RMS) handles recording windows and automatically sends base64 payloads to the backend upon silence detection.
* **Dynamic Case Generation**: Leverages structured LLM story generation to create a unique mystery dossier at the start of each game session (including victim details, timeline, setting, and suspects with specialized memory databases).
* **Judge Scoring Engine**: Evaluates the player's final accusation board (Who, Why, How) using strict marking rubrics and provides a detailed *Thinking Skills Report* and scoring analysis.

---

## 🛠️ Technology Stack

* **Frontend**: Vanilla JavaScript (ES Modules), HTML5 (Web Audio API), CSS3 (Noir theme with scanlines, fog, typewriter effects), Vite 6.
* **Backend**: Python 3.10+, FastAPI (REST + WebSockets), LangGraph, LangChain, Groq (Llama 3.1), HuggingFace (embeddings), FAISS (vector database for suspect knowledge retrieval).

---

## 📁 Repository Structure

```
ai-detective-game/
├── frontend/                 # Vite dev server + Vanilla JS client
│   ├── assets/               # Local sprites, audio, and styles
│   ├── public/               # Static assets
│   ├── index.html            # Main game layout
│   ├── main.js               # Game loop, WebAudio VAD, and API client
│   └── vite.config.js        # Vite config with backend API proxying
└── backend/                  # FastAPI web server
    ├── game_agents/          # System prompts, memories, and identity files
    ├── server.py             # App entrypoint and WebSocket routing
    ├── story_generator.py    # LLM case generator
    └── requirements.txt      # Python dependencies
```

---

## ⚙️ Getting Started

### 1. Prerequisites
* **Node.js** (v18+)
* **Python** (3.10+)
* **API Keys**:
  * **Groq API Key** (for Llama 3.1 LLM orchestration)
  * **Sarvam API Key** (required for Voice Mode STT/TTS services)

### 2. Backend Setup
1. Navigate to the backend folder:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file in the `backend/` folder:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   SARVAM_API_KEY=your_sarvam_api_key_here
   ```
5. Launch the FastAPI server:
   ```bash
   python server.py
   ```
   The backend will run on **`http://localhost:8000`**.

### 3. Frontend Setup
1. Open a new terminal and navigate to the frontend folder:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run dev
   ```
   Open **`http://localhost:5000`** in your browser to enter the precinct!

---

## 🎮 Gameplay Guide
1. **Case Briefing**: Select your mode (Text or Voice), language, and difficulty. Listen to/read the initial briefing from the database.
2. **Interrogate Suspects**: Click on suspects in the lineup to question them. 
   * *Voice Mode*: Speak naturally. The browser automatically streams your voice when you stop speaking.
   * *Text Mode*: Type your questions.
3. **Investigate (Task Agent)**: Ask your detective partner to gather digital logs, check CCTV feeds, or research background details.
4. **File Verdict**: Submit your theory to the Judge specifying **Who** did it, **Why** (motive), and **How** (method). You will receive an detailed report card and final score.
