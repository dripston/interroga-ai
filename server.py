"""
FastAPI Backend for AI Detective Game
LangGraph-powered orchestration with REST + WebSocket endpoints
"""
import sys
import os

# Fix Windows cp1252 encoding — emoji prints in imported modules crash without this
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import asyncio
import base64
import json
import logging
import re
import time
import uuid
import wave
import io
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx

# ═══════════════════════════════════════════════════════════════
# ENV / API KEYS
# ═══════════════════════════════════════════════════════════════

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("detective-api")


# ═══════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ═══════════════════════════════════════════════════════════════

# -- Create Game --
class CreateGameRequest(BaseModel):
    difficulty: str = "easy"
    language: str = "en-IN"
    mode: str = "text"  # "text" or "voice"

class SuspectProfile(BaseModel):
    name: str
    role: str
    age: int
    personality: list[str]
    character_type: str
    voice_id: str
    frontend_character_id: str
    suspicious_behavior: Optional[str] = None

class CreateGameResponse(BaseModel):
    case_id: str
    title: str
    briefing_text: str
    briefing_audio_b64: Optional[str] = None
    suspects: list[SuspectProfile]
    language: str
    mode: str
    questions_per_suspect: int = 20
    setting: dict
    victim: dict
    time_window: str

# -- Interrogation (Text) --
class InterrogateRequest(BaseModel):
    suspect_name: str
    message: str

class InterrogateResponse(BaseModel):
    response: str
    response_english: str
    questions_remaining: int
    questions_used: int

# -- Punch --
class PunchRequest(BaseModel):
    suspect_name: str
    action: str  # "punch", "slap", etc.

class PunchResponse(BaseModel):
    reaction: str
    reaction_english: str
    audio_b64: Optional[str] = None

# -- Task Agent --
class TaskRequest(BaseModel):
    command: str

class TaskResponse(BaseModel):
    result: str
    questions_remaining: int
    questions_used: int

# -- Submit Solution --
class SubmitRequest(BaseModel):
    who: str   # The suspect the player accuses as the culprit
    why: str   # The motive the player believes drove the crime
    how: str   # The method the player believes was used

class SubmitResponse(BaseModel):
    correct: bool
    actual_culprit: str
    motive: str
    method: str
    key_evidence: list[str]
    summary: str
    
    # JUDGE EVALUATION FIELDS
    score: int = Field(default=0, description="Score out of 100 — strict rubric: Who(25) + Why(50) + How(25). If Who is wrong, score=0.")
    who_score: int = Field(default=0, description="Points for correct culprit identification (0 or 25)")
    why_score: int = Field(default=0, description="Points for motive accuracy (0-50)")
    how_score: int = Field(default=0, description="Points for method accuracy (0-25)")
    marking_schema: str = Field(default="", description="Breakdown of points awarded per axis")
    thinking_skills_report: str = Field(default="", description="Concise critique of the player's investigation strategy referencing transcript actions")
    analysis: str = Field(default="", description="Detailed narrative of truth vs player's claims")

# -- Game State --
class GameStateResponse(BaseModel):
    case_id: str
    title: str
    difficulty: str
    language: str
    mode: str
    phase: str
    suspects: list[dict]
    questions_asked: dict
    task_questions_used: int


# ═══════════════════════════════════════════════════════════════
# CHARACTER MAPPING — suspect character_type → frontend model
# ═══════════════════════════════════════════════════════════════

CHARACTER_SLOTS = {
    "young-male":   ["character_1", "character_2"],
    "young-female": ["character_3", "character_4"],
    "old-male":     ["character_5", "character_6"],
    "old-female":   ["character_7", "character_8"],
}


# ═══════════════════════════════════════════════════════════════
# SUPPORTED LANGUAGES
# ═══════════════════════════════════════════════════════════════

SUPPORTED_LANGUAGES = {
    "en-IN": "English",
    "hi-IN": "Hindi",
    "bn-IN": "Bengali",
    "ta-IN": "Tamil",
    "te-IN": "Telugu",
    "mr-IN": "Marathi",
    "kn-IN": "Kannada",
    "ml-IN": "Malayalam",
    "gu-IN": "Gujarati",
    "pa-IN": "Punjabi",
    "od-IN": "Odia",
}


# ═══════════════════════════════════════════════════════════════
# VOICE SERVICES (from custom_voice_agent.py)
# ═══════════════════════════════════════════════════════════════

class SarvamSTT:
    def __init__(self, api_key: str, client: httpx.AsyncClient = None):
        self.api_key = api_key
        self.client = client or httpx.AsyncClient(timeout=30.0)

    async def transcribe(self, audio_bytes: bytes) -> tuple[str, str]:
        if not audio_bytes:
            return "", "unknown"
        try:
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes(audio_bytes)
            response = await self.client.post(
                "https://api.sarvam.ai/speech-to-text",
                headers={"api-subscription-key": self.api_key},
                files={'file': ('audio.wav', wav_buffer.getvalue(), 'audio/wav')},
                data={'language_code': 'unknown', 'model': 'saarika:v2.5'}
            )
            response.raise_for_status()
            result = response.json()
            return result.get("transcript", ""), result.get("language_code", "unknown")
        except Exception as e:
            logger.error(f"STT error: {e}")
            return "", "unknown"


class SarvamTTS:
    def __init__(self, api_key: str, speaker: str = "rehan", target_lang: str = "en-IN", client: httpx.AsyncClient = None):
        self.api_key = api_key
        self.speaker = speaker
        self.target_lang = target_lang
        self.client = client or httpx.AsyncClient(timeout=30.0)

    async def synthesize(self, text: str) -> Optional[bytes]:
        text = clean_text_for_tts(text)
        if not text or len(text.strip()) < 2:
            return None
            
        try:
            response = await self.client.post(
                "https://api.sarvam.ai/text-to-speech",
                headers={
                    "api-subscription-key": self.api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "inputs": [text],
                    "target_language_code": self.target_lang,
                    "speaker": self.speaker,
                    "model": "bulbul:v3",
                    "speech_sample_rate": 22050,
                    "enable_preprocessing": True
                }
            )
            response.raise_for_status()
            data = response.json()
            if "audios" in data and data["audios"]:
                return base64.b64decode(data["audios"][0])
        except Exception as e:
            logger.error(f"TTS error: {e}")
        return None


class SarvamTranslate:
    def __init__(self, api_key: str, client: httpx.AsyncClient = None):
        self.api_key = api_key
        self.client = client or httpx.AsyncClient(timeout=30.0)

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        if not text.strip() or source_lang == target_lang:
            return text
        try:
            response = await self.client.post(
                "https://api.sarvam.ai/translate",
                headers={
                    "api-subscription-key": self.api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "input": text,
                    "source_language_code": source_lang,
                    "target_language_code": target_lang,
                    "model": "mayura:v1",
                    "mode": "modern-colloquial"
                }
            )
            response.raise_for_status()
            return response.json().get("translated_text", text)
        except Exception as e:
            logger.error(f"Translate error: {e}")
            return text


def clean_text_for_tts(text: str) -> str:
    """Removes markdown and standardizes phrasing for TTS & Frontend display."""
    if not text:
        return ""
        
    import re
    
    # 1. Remove all decorative borders
    text = re.sub(r'={3,}', '', text)
    text = re.sub(r'-{3,}', '', text)
    
    # 2. Convert "X-year-old" to words to prevent weird TTS reading
    def replace_age(match):
        age_str = match.group(1)
        try:
            age = int(age_str)
            tens_map = {2: 'twenty', 3: 'thirty', 4: 'forty', 5: 'fifty', 6: 'sixty', 7: 'seventy'}
            ones_map = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven', 8: 'eight', 9: 'nine'}
            if 20 <= age <= 79:
                tens = age // 10
                ones = age % 10
                if ones == 0:
                    word_age = tens_map[tens]
                else:
                    word_age = f"{tens_map[tens]} {ones_map[ones]}"
                return f"{word_age} year old"
        except:
            pass
        return f"{age_str} year old"
        
    text = re.sub(r'(\d+)-year-old', replace_age, text)
    
    # 3. Reformat Suspect Profiles block into natural sentences
    def reformat_suspect(match):
        name = match.group(1).strip()
        role = match.group(2).strip()
        age_str = match.group(3).strip()
        return f"{name}, aged {age_str}, whose role is {role}."
        
    text = re.sub(r'([A-Za-z\s\']+?)\nRole:\s*(.+?)\nAge:\s*(\d+)', reformat_suspect, text)
    
    # 4. Strip leftover artifacts
    text = text.replace('SUSPECT PROFILES:', 'The suspects are as follows.')
    text = re.sub(r'Total Suspects:\s*\d+', '', text)
    text = re.sub(r'Evidence pieces:\s*\d+', '', text)
    text = re.sub(r'\([^)]*\)', '', text).strip()
    text = re.sub(r'\[[^\]]*\]', '', text).strip()
    text = re.sub(r'\*[^*]*\*', '', text).strip()
    
    # 5. Collapse extra whitespace
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r' \s+', ' ', text).strip()

    return text


# ═══════════════════════════════════════════════════════════════
# LLM HELPERS (from custom_voice_agent.py)
# ═══════════════════════════════════════════════════════════════

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage


def build_chat_messages(system_prompt: str, suspect_name: str, conversation_history: list, user_input: str) -> list:
    chat_messages = [SystemMessage(content=system_prompt)]
    for msg in conversation_history[-10:]:
        if msg['role'] == 'user':
            chat_messages.append(HumanMessage(content=msg['content']))
        elif msg['role'] == 'assistant':
            chat_messages.append(AIMessage(content=msg['content']))
    chat_messages.append(SystemMessage(
        content=f"REMINDER: You are {suspect_name}. Concise 2-3 sentence response. NO brackets. NO prefixes. Just speak with strong character voice."
    ))
    return chat_messages


def clean_response(text: str, suspect_name: str) -> str:
    if not text:
        return ""
    prefixes = [f"{suspect_name}:", "SUSPECT:", "SUSPECT RESPONSE:", "AI:", "Assistant:"]
    for prefix in prefixes:
        if text.upper().startswith(prefix.upper()):
            text = text[len(prefix):].strip()
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'\[[^\]]*\]', '', text)
    text = re.sub(r'\*[^*]*\*', '', text)
    return text.strip()


async def call_llm(system_prompt: str, suspect_name: str, conversation_history: list, user_input: str) -> str:
    chat_messages = build_chat_messages(system_prompt, suspect_name, conversation_history, user_input)
    llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.85, max_tokens=180)
    response_msg = await llm.ainvoke(chat_messages)
    return clean_response(response_msg.content.strip(), suspect_name)


# ═══════════════════════════════════════════════════════════════
# SUSPECT MEMORY LOADER (from custom_voice_agent.py)
# ═══════════════════════════════════════════════════════════════

class SuspectMemoryLoader:
    """Loads a suspect's memory folder and builds system prompt."""

    def __init__(self, suspect_name: str, agents_dir: Path = None):
        self.suspect_name = suspect_name
        base = agents_dir or Path("game_agents")
        self.suspect_dir = base / f"suspect_{suspect_name.lower().replace(' ', '_')}"

        if not self.suspect_dir.exists():
            raise FileNotFoundError(f"Suspect folder not found: {self.suspect_dir}")

        self.identity = self._load_json('identity.json')
        self.knowledge = self._load_json('knowledge.json')
        self.beliefs = self._load_json('beliefs.json')
        self.memories = self._load_json('memories.json')
        self.relationships = self._load_json('relationships.json')
        self.conversation_state = self._load_json('conversation_state.json')
        self.chat_history = self._load_json('chat_history.json', default=[])

    def _load_json(self, filename: str, default=None):
        if default is None:
            default = {}
        filepath = self.suspect_dir / filename
        if not filepath.exists():
            return default
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return default

    def save_chat_history(self, history: list):
        filepath = self.suspect_dir / 'chat_history.json'
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

    def build_system_prompt(self) -> str:
        rel_context = ""
        if self.relationships:
            rel_context = "\n\nMY RELATIONSHIPS:\n"
            for person, rel_info in self.relationships.items():
                rel_context += f"- {person}: {rel_info.get('how_i_would_describe_our_relationship', '')}\n"
                rel_context += f"  How I feel: {rel_info.get('how_i_feel_about_them', '')}\n"
                rel_context += f"  What I know: {rel_info.get('what_i_know_about_them', '')}\n"

        memory_context = ""
        if self.memories.get('what_i_remember_from_that_day'):
            memory_context = "\n\nWHAT I REMEMBER FROM THAT DAY:\n"
            for mem in self.memories['what_i_remember_from_that_day']:
                memory_context += f"- {mem['time']}: {mem['what_i_saw']}\n"
                memory_context += f"  My thoughts: {mem['my_thoughts_at_the_time']}\n"

        observation_context = ""
        if self.memories.get('what_i_observed'):
            observation_context = "\n\nTHINGS I NOTICED:\n"
            for obs in self.memories['what_i_observed']:
                observation_context += f"- {obs['what_i_noticed']} (at {obs['where_i_saw_it']})\n"

        voice = self.identity.get('character_voice', {})
        archetype = voice.get('archetype', 'THE NEUTRAL ONE')
        speaking_style = voice.get('speaking_style', 'Natural conversational style')
        speech_patterns = voice.get('speech_patterns', [])

        archetype_instructions = {
            "THE FUNNY ONE": "Use humor to deflect tension. Crack jokes, use puns, and don't take the detective seriously.",
            "THE RUDE ONE": "Be prickly, impatient, and direct. You hate being questioned.",
            "THE SCARED ONE": "Be nervous, jumpy, and defensive. Overthink questions.",
            "THE SARCASTIC ONE": "Heavy eye-rolling, dry wit, and passive-aggressive answers.",
            "THE CHILL ONE": "Too calm. Unbothered. Suspiciously relaxed.",
            "THE DRAMATIC ONE": "Over-the-top reactions. Gasp, be offended, make everything about your tragedy.",
            "THE STREET-SMART ONE": "Know your rights. Be calculating. Negotiate."
        }.get(archetype, "Be a unique personality based on your backstory and traits.")

        prompt = f"""You ARE {self.identity['name']}. NO meta-talk. NO "Assistant:". You must fully embody your character's personality and speak naturally.NO bracketed actions like (sighs) or (pausing).

CORE IDENTITY:
- Archetype: {archetype}
- Traits: {', '.join(self.identity['personality'])}
- Speaking Style: {speaking_style}
- Instruction: {archetype_instructions}

MY STORY: {self.identity.get('backstory', '')}
MY ALIBI: {self.knowledge.get('my_alibi', '')}
MY SECRET: {self.knowledge.get('my_secret', '')}

{rel_context}{memory_context}{observation_context}

STRICT RESPONSE RULES:
1. NO BRACKETS OR ASTERISKS. Do NOT describe your actions or emotions in brackets like [angry] or *sighs*.
2. SHOW, DON'T TELL. Instead of writing (sighs), start your sentence with "Ugh..." or "Look...". Show emotion through your actual words, pacing, and tone!
3. NO PREFIXES. Do NOT start with "SUSPECT:" or "{self.identity['name']}:". Just speak directly.
4. BE YOUR ARCHETYPE. If you are angry, use aggressive words. If you are funny, be sarcastic. Make your personality blindingly obvious from the first word.
5. LENGTH: Concise 2-3 sentences (roughly 60-70 words max). Do not yap.
6. ENGLISH ONLY. Natural spoken English. No foreign words or slang.
7. STICK TO THE ALIBI. If caught, react defensively or emotionally based on your persona.

Phrases You Use:
{chr(10).join(f"- {p}" for p in speech_patterns)}

Now, respond to the detective. STAY IN CHARACTER.
"""
        return prompt


# ═══════════════════════════════════════════════════════════════
# GAME SESSION
# ═══════════════════════════════════════════════════════════════

class GameSession:
    """Holds all state for one game instance."""

    def __init__(self, case_id: str, case_data: dict, difficulty: str, language: str, mode: str):
        self.case_id = case_id
        self.case_data = case_data
        self.difficulty = difficulty
        self.language = language
        self.mode = mode
        self.phase = "BRIEFING"  # BRIEFING → INVESTIGATION → SOLVED → END
        self.created_at = datetime.now()

        # Per-suspect state
        case = case_data.get('case', case_data)
        self.suspects_data = case.get('suspects', [])
        self.suspect_names = [s['name'] for s in self.suspects_data]
        self.questions_asked: Dict[str, int] = {s['name']: 0 for s in self.suspects_data}
        self.conversation_histories: Dict[str, list] = {s['name']: [] for s in self.suspects_data}

        # Suspect memory loaders + system prompts
        self.suspect_loaders: Dict[str, SuspectMemoryLoader] = {}
        self.suspect_prompts: Dict[str, str] = {}
        agents_dir = Path(f"game_agents_{case_id}")
        for s in self.suspects_data:
            try:
                loader = SuspectMemoryLoader(s['name'], agents_dir)
                self.suspect_loaders[s['name']] = loader
                self.suspect_prompts[s['name']] = loader.build_system_prompt()
                if loader.chat_history:
                    self.conversation_histories[s['name']] = list(loader.chat_history)
            except FileNotFoundError:
                logger.warning(f"No memory folder for {s['name']}")

        # Task agent
        self.task_questions_used = 0
        self.task_agent = None
        self.task_agent_history: list = []  # Chronological log of player queries + Task Agent responses
        try:
            from task_agent import TaskAgent
            self.task_agent = TaskAgent(case_id)
        except Exception as e:
            logger.warning(f"Task agent init failed: {e}")

        # Voice services (only if voice mode)
        self.http_client: Optional[httpx.AsyncClient] = None
        self.stt: Optional[SarvamSTT] = None
        self.translator: Optional[SarvamTranslate] = None
        
        # New: Use standalone voice agent
        self.interrogation_agents = {}

        sarvam_key = os.getenv("SARVAM_API_KEY", "")
        if not sarvam_key:
            logger.error("❌ SARVAM_API_KEY missing - Voice features disabled")

        if sarvam_key:
            self.http_client = httpx.AsyncClient(timeout=30.0)
            self.translator = SarvamTranslate(sarvam_key, client=self.http_client)
            
            # Interactive Voice features — ONLY initialized if mode="voice"
            if mode == "voice":
                self.stt = SarvamSTT(sarvam_key, client=self.http_client)
                from custom_voice_agent import InterrogationAgent
                
                for s in self.suspects_data:
                    name = s['name']
                    loader = self.suspect_loaders.get(name)
                    voice_id = "rehan"
                    if loader:
                        voice_id = loader.identity.get('character_voice', {}).get('voice_id', 'rehan')
                        
                    agent = InterrogationAgent(
                        suspect_name=name,
                        system_prompt=self.suspect_prompts.get(name, ""),
                        sarvam_api_key=sarvam_key,
                        speaker=voice_id,
                        user_lang=language,
                        loader=loader
                    )
                    self.interrogation_agents[name] = agent
            
            elif mode == "text":
                from custom_voice_agent import TextModeAgent
                for s in self.suspects_data:
                    name = s['name']
                    loader = self.suspect_loaders.get(name)
                    agent = TextModeAgent(
                        suspect_name=name,
                        system_prompt=self.suspect_prompts.get(name, ""),
                        limit=20,
                        loader=loader
                    )
                    self.interrogation_agents[name] = agent

    def get_remaining(self, suspect_name: str) -> int:
        limit = 60 if self.mode == "voice" else 20
        return limit - self.questions_asked.get(suspect_name, 0)

    async def cleanup(self):
        if self.http_client:
            await self.http_client.aclose()
        for agent in getattr(self, 'interrogation_agents', {}).values():
            if hasattr(agent, '_http_client'):
                await agent._http_client.aclose()


# ═══════════════════════════════════════════════════════════════
# IN-MEMORY GAME STORE
# ═══════════════════════════════════════════════════════════════

game_sessions: Dict[str, GameSession] = {}


def get_session(case_id: str) -> GameSession:
    if case_id not in game_sessions:
        raise HTTPException(status_code=404, detail=f"Game session '{case_id}' not found")
    return game_sessions[case_id]


# ═══════════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════════

app = FastAPI(
    title="AI Detective Game API",
    description="LangGraph-powered mystery investigation backend",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════
# ENDPOINT: Create Game
# ═══════════════════════════════════════════════════════════════

@app.post("/game/create", response_model=CreateGameResponse)
async def create_game(req: CreateGameRequest):
    """Generate a new mystery case → return briefing + suspects."""
    logger.info(f"🎲 Creating game: difficulty={req.difficulty}, lang={req.language}, mode={req.mode}")

    if req.language == "en":
        req.language = "en-IN"
    if req.language == "hi":
        req.language = "hi-IN"

    if req.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, f"Unsupported language: {req.language}")
    if req.mode not in ("text", "voice"):
        raise HTTPException(400, f"Mode must be 'text' or 'voice'")

    # 1. Generate case
    from story_generator import generate_case
    case_data = await generate_case(req.difficulty)
    if not case_data:
        raise HTTPException(500, "Case generation failed")

    case = case_data.get('case', case_data)
    case_id = str(case_data.get('id', uuid.uuid4().hex[:8]))

    # 2. Process through GraphRAG (generate agent memory folders)
    from graphrag_agent import GraphRAGAgent
    graphrag = GraphRAGAgent(case_data)
    await graphrag.generate_all_agents()

    # 3. Create game session
    session = GameSession(case_id, case_data, req.difficulty, req.language, req.mode)
    game_sessions[case_id] = session
    session.phase = "INVESTIGATION"

    # 4. Build briefing
    briefing_path = Path(f"game_agents_{case_id}/detective_briefing/briefing.txt")
    if briefing_path.exists():
        briefing_text = briefing_path.read_text(encoding='utf-8')
    else:
        briefing_text = f"A crime has occurred: {case.get('crime', {}).get('what_happened', 'Unknown')}. Investigate."

    # Intercept and clean text for frontend and audio
    briefing_text = clean_text_for_tts(briefing_text)

    # 5. Briefing audio (now handled by frontend streaming)
    briefing_audio_b64 = None

    # 6. Map suspects to frontend characters
    slot_counters = {k: 0 for k in CHARACTER_SLOTS}
    suspect_profiles = []
    for s in case['suspects']:
        ctype = s.get('character_type', 'young-male')
        slots = CHARACTER_SLOTS.get(ctype, ["character_1", "character_2"])
        idx = slot_counters.get(ctype, 0)
        frontend_id = slots[idx % len(slots)]
        slot_counters[ctype] = idx + 1

        voice_id = "rehan"
        if s['name'] in session.suspect_loaders:
            voice_id = session.suspect_loaders[s['name']].identity.get('character_voice', {}).get('voice_id', 'rehan')

        suspect_profiles.append(SuspectProfile(
            name=s['name'],
            role=s['role'],
            age=s['age'],
            personality=s.get('personality', []),
            character_type=ctype,
            voice_id=voice_id,
            frontend_character_id=frontend_id,
            suspicious_behavior=s.get('suspicious_behavior'),
        ))

    # 7. Build time window
    timeline = case.get('timeline', [])
    time_window = ""
    if timeline:
        time_window = f"{timeline[0].get('time', '?')} - {timeline[-1].get('time', '?')}"

    return CreateGameResponse(
        case_id=case_id,
        title=case.get('title', 'Mystery Case'),
        briefing_text=briefing_text,
        briefing_audio_b64=briefing_audio_b64,
        suspects=suspect_profiles,
        language=req.language,
        mode=req.mode,
        questions_per_suspect=20,
        setting=case.get('setting', {}),
        victim={k: v for k, v in case.get('victim', {}).items() if k != 'connection_to_culprit'},
        time_window=time_window,
    )


# ═══════════════════════════════════════════════════════════════
# ENDPOINT: Load Existing Game (for testing with pre-generated agents)
# ═══════════════════════════════════════════════════════════════

class LoadGameRequest(BaseModel):
    case_file: str = ""  # path to case JSON, or empty for latest
    language: str = "en-IN"
    mode: str = "text"

@app.post("/game/load", response_model=CreateGameResponse)
async def load_game(req: LoadGameRequest):
    """Load an existing case file into a game session (skips generation)."""
    
    if req.language == "en":
        req.language = "en-IN"
    if req.language == "hi":
        req.language = "hi-IN"
    
    # Find case file
    if req.case_file:
        case_path = Path(req.case_file)
    else:
        # Find latest case file by modification time, not alphabetically
        import os
        case_files = sorted(Path(".").glob("game_case_v2_*.json"), key=os.path.getmtime, reverse=True)
        if not case_files:
            raise HTTPException(404, "No case files found")
        case_path = case_files[0]
    
    if not case_path.exists():
        raise HTTPException(404, f"Case file not found: {case_path}")
    
    with open(case_path, 'r', encoding='utf-8') as f:
        case_data = json.load(f)
    
    case = case_data.get('case', case_data)
    case_id = str(case_data.get('id', uuid.uuid4().hex[:8]))
    
    session = GameSession(case_id, case_data, case.get('difficulty', 'easy'), req.language, req.mode)
    game_sessions[case_id] = session
    session.phase = "INVESTIGATION"
    
    # Briefing
    briefing_path = Path(f"game_agents_{case_id}/detective_briefing/briefing.txt")
    briefing_text = briefing_path.read_text(encoding='utf-8') if briefing_path.exists() else "No briefing available."
    
    # Intercept and clean text for frontend and audio
    briefing_text = clean_text_for_tts(briefing_text)
    
    # Briefing audio (now handled by frontend streaming)
    briefing_audio_b64 = None
    
    # Suspect profiles
    slot_counters = {k: 0 for k in CHARACTER_SLOTS}
    suspect_profiles = []
    for s in case['suspects']:
        ctype = s.get('character_type', 'young-male')
        slots = CHARACTER_SLOTS.get(ctype, ["character_1", "character_2"])
        idx = slot_counters.get(ctype, 0)
        frontend_id = slots[idx % len(slots)]
        slot_counters[ctype] = idx + 1
        
        voice_id = "rehan"
        if s['name'] in session.suspect_loaders:
            voice_id = session.suspect_loaders[s['name']].identity.get('character_voice', {}).get('voice_id', 'rehan')
        
        suspect_profiles.append(SuspectProfile(
            name=s['name'], role=s['role'], age=s['age'],
            personality=s.get('personality', []), character_type=ctype,
            voice_id=voice_id, frontend_character_id=frontend_id,
            suspicious_behavior=s.get('suspicious_behavior'),
        ))
        
    # SHUFFLE SUSPECTS! So the culprit isn't always the first one in the UI.
    import random
    random.shuffle(suspect_profiles)
    
    timeline = case.get('timeline', [])
    time_window = f"{timeline[0].get('time', '?')} - {timeline[-1].get('time', '?')}" if timeline else ""
    
    logger.info(f"Loaded game {case_id} from {case_path}")
    
    response = CreateGameResponse(
        case_id=case_id, title=case.get('title', 'Mystery Case'),
        briefing_text=briefing_text, briefing_audio_b64=briefing_audio_b64,
        suspects=suspect_profiles, language=req.language, mode=req.mode,
        questions_per_suspect=20, setting=case.get('setting', {}),
        victim={k: v for k, v in case.get('victim', {}).items() if k != 'connection_to_culprit'},
        time_window=time_window,
    )
    
    # Debug logging for frontend integration
    logger.info(f"==== SENDING TO FRONTEND ====\n{response.model_dump_json(indent=2)}\n=============================")
    
    return response


# ═══════════════════════════════════════════════════════════════
# ENDPOINT: Get Game State
# ═══════════════════════════════════════════════════════════════

@app.get("/game/{case_id}", response_model=GameStateResponse)
async def get_game_state(case_id: str):
    session = get_session(case_id)
    case = session.case_data.get('case', session.case_data)
    return GameStateResponse(
        case_id=session.case_id,
        title=case.get('title', ''),
        difficulty=session.difficulty,
        language=session.language,
        mode=session.mode,
        phase=session.phase,
        suspects=[
            {"name": s['name'], "role": s['role'], "questions_used": session.questions_asked.get(s['name'], 0), "questions_remaining": session.get_remaining(s['name'])}
            for s in session.suspects_data
        ],
        questions_asked=session.questions_asked,
        task_questions_used=session.task_questions_used,
    )


# ═══════════════════════════════════════════════════════════════
# ENDPOINT: Text Interrogation
# ═══════════════════════════════════════════════════════════════

@app.post("/game/{case_id}/interrogate", response_model=InterrogateResponse)
async def interrogate_text(case_id: str, req: InterrogateRequest):
    session = get_session(case_id)

    if req.suspect_name not in session.suspect_prompts:
        raise HTTPException(400, f"Unknown suspect: {req.suspect_name}")
    if session.get_remaining(req.suspect_name) <= 0:
        raise HTTPException(400, f"No questions remaining for {req.suspect_name}")

    # Translate user message to English if non-English
    english_msg = req.message
    if session.language != "en-IN" and session.translator:
        english_msg = await session.translator.translate(req.message, session.language, "en-IN")

    session.questions_asked[req.suspect_name] += 1
    
    # LLM call (always in English)
    agent = session.interrogation_agents[req.suspect_name]
    agent.conversation_history = session.conversation_histories[req.suspect_name]
    
    if hasattr(agent, 'generate_response'):
        response_en = await agent.generate_response(english_msg)
    else:
        # Fallback for voice mode InterrogationAgent being called from text endpoint
        from custom_voice_agent import call_llm
        agent.conversation_history.append({"role": "user", "content": english_msg})
        response_en = await call_llm(
            agent.system_prompt, agent.suspect_name,
            agent.conversation_history, english_msg
        )
        agent.conversation_history.append({"role": "assistant", "content": response_en})
        if agent.loader:
            agent.loader.save_chat_history(agent.conversation_history)

    # Translate response to user's language
    response_user = response_en
    if session.language != "en-IN" and session.translator:
        response_user = await session.translator.translate(response_en, "en-IN", session.language)

    return InterrogateResponse(
        response=response_user,
        response_english=response_en,
        questions_remaining=session.get_remaining(req.suspect_name),
        questions_used=session.questions_asked[req.suspect_name],
    )


# ═══════════════════════════════════════════════════════════════
# ENDPOINT: Punch
# ═══════════════════════════════════════════════════════════════

@app.post("/game/{case_id}/punch", response_model=PunchResponse)
async def punch_suspect(case_id: str, req: PunchRequest):
    session = get_session(case_id)

    if req.suspect_name not in session.suspect_prompts:
        raise HTTPException(400, f"Unknown suspect: {req.suspect_name}")

    agent = session.interrogation_agents[req.suspect_name]
    agent.conversation_history = session.conversation_histories[req.suspect_name]
    
    if hasattr(agent, 'generate_response'):
        reaction_en = await agent.generate_response(f"punch {req.action}")
    else:
        # Fallback for voice mode InterrogationAgent
        from custom_voice_agent import OpenRouterClient, clean_response
        punch_prompt = f"""Continue this interrogation. The detective just physically intimidated you: "punch {req.action}"

You are {req.suspect_name}. React in character. MAX 15 WORDS. No brackets, no actions, no prefixes. Just your spoken reaction.

PREVIOUS CONTEXT:
{chr(10).join(f"{m['role'].upper()}: {m['content']}" for m in agent.conversation_history[-6:])}

YOUR REACTION:"""
        reaction_en = await OpenRouterClient.call(punch_prompt, temperature=0.9, max_tokens=100)
        reaction_en = clean_response(reaction_en.strip(), agent.suspect_name)
        
        agent.conversation_history.append({"role": "user", "content": f"*punch {req.action}*"})
        agent.conversation_history.append({"role": "assistant", "content": reaction_en})
        if agent.loader:
            agent.loader.save_chat_history(agent.conversation_history)

    # Translate reaction
    reaction_user = reaction_en
    if session.language != "en-IN" and session.translator:
        reaction_user = await session.translator.translate(reaction_en, "en-IN", session.language)

    # TTS for voice mode
    audio_b64 = None
    if session.mode == "voice" and req.suspect_name in getattr(session, 'interrogation_agents', {}):
        agent = session.interrogation_agents[req.suspect_name]
        audio_bytes = await agent.tts.synthesize(reaction_user)
        if audio_bytes:
            audio_b64 = base64.b64encode(audio_bytes).decode()

    return PunchResponse(
        reaction=reaction_user,
        reaction_english=reaction_en,
        audio_b64=audio_b64,
    )


# ═══════════════════════════════════════════════════════════════
# ENDPOINT: Task Agent
# ═══════════════════════════════════════════════════════════════

@app.post("/game/{case_id}/task", response_model=TaskResponse)
async def task_agent_query(case_id: str, req: TaskRequest):
    session = get_session(case_id)

    if not session.task_agent:
        raise HTTPException(500, "Task agent not available")
    if session.task_questions_used >= 20:
        raise HTTPException(400, "Task agent question limit reached")

    session.task_questions_used += 1

    # Translate command to English if needed
    command_en = req.command
    if session.language != "en-IN" and session.translator:
        command_en = await session.translator.translate(req.command, session.language, "en-IN")

    # Inject live chat histories so the partner LLM knows what we've asked
    session.task_agent.live_histories = session.conversation_histories
    result = await session.task_agent.execute(command_en)

    # Log the interaction for the Judge's context
    session.task_agent_history.append({
        "query": command_en,
        "response": result
    })

    # Translate result back
    result_user = result
    if session.language != "en-IN" and session.translator:
        result_user = await session.translator.translate(result, "en-IN", session.language)

    return TaskResponse(
        result=result_user,
        questions_remaining=20 - session.task_questions_used,
        questions_used=session.task_questions_used,
    )


# ═══════════════════════════════════════════════════════════════
# SAMBANOVA JUDGE AGENT
# ═══════════════════════════════════════════════════════════════

class JudgeAgent:
    def __init__(self):
        self.api_key = os.getenv("SAMBANOVA_API_KEY", "")
        # Fallback to standard 72B if the user doesn't provide the "235b" model string
        self.model = os.getenv("SAMBANOVA_MODEL", "Qwen3-235B")
        self.url = "https://api.sambanova.ai/v1/chat/completions"

    async def evaluate(self, session: GameSession, req: SubmitRequest) -> dict:
        if not self.api_key:
            logger.warning("SambaNova API key missing, using fallback evaluator")
            return self._fallback_eval(session, req)
            
        case = session.case_data.get('case', session.case_data)
        
        # Load Truth Graph
        truth_graph = {}
        try:
            tg_path = Path(f"./game_agents_{session.case_id}/truth_graph.json")
            if tg_path.exists():
                with open(tg_path, 'r', encoding='utf-8') as f:
                    truth_graph = json.load(f)
            
            # If empty or missing, build it directly from game session data
            if not truth_graph:
                evidence_list = case.get("solution", {}).get("evidence", [])
                expanded_evidence = []
                for ev in evidence_list:
                    if isinstance(ev, str) and ev.startswith("EV"):
                        for e_obj in case.get("evidence", []):
                            if e_obj.get("id") == ev:
                                expanded_evidence.append(e_obj.get("description", ev))
                    else:
                        expanded_evidence.append(str(ev))
                        
                truth_graph = {
                    "culprit": case.get("solution", {}).get("culprit", "Unknown"),
                    "motive": case.get("solution", {}).get("motive", "Unknown"),
                    "method": case.get("solution", {}).get("method", "Unknown"),
                    "evidence": expanded_evidence,
                    "hidden_truth": case.get("crime", {}).get("hidden_truth", "Unknown")
                }
        except Exception as e:
            logger.error(f"Failed to load truth graph: {e}")

        # ── Compile Suspect Interview Transcripts ──
        full_transcript = []
        for suspect, history in session.conversation_histories.items():
            if len(history) > 1:  # Ignore just the system prompt
                full_transcript.append(f"\n--- INTERVIEWS WITH {suspect.upper()} ---")
                for msg in history:
                    if msg['role'] != 'system':
                        full_transcript.append(f"{msg['role'].upper()}: {msg['content']}")
        
        interview_str = "\n".join(full_transcript)
        if not interview_str.strip():
            interview_str = "(The detective did not interrogate any suspects.)"

        # ── Compile Task Agent Investigation Log ──
        task_log_parts = []
        if session.task_agent_history:
            task_log_parts.append("\n--- TASK AGENT INVESTIGATION LOG ---")
            for i, entry in enumerate(session.task_agent_history, 1):
                task_log_parts.append(f"QUERY #{i}: {entry['query']}")
                task_log_parts.append(f"RESULT #{i}: {entry['response']}")
        task_log_str = "\n".join(task_log_parts)
        if not task_log_str.strip():
            task_log_str = "(The detective did not use the Task Agent to investigate evidence.)"

        # ── Combined Transcript ──
        combined_transcript = f"{interview_str}\n\n{task_log_str}"
        
        # Log that we are sending the transcript to the judge
        logger.info(f"Judge received transcript: {len(combined_transcript)} characters")

        prompt = f"""You are the MASTER DETECTIVE JUDGE for a murder mystery game. A junior detective has submitted their final accusation. You must evaluate it against the absolute truth using a STRICT 100-point rubric.

=== SCORING RUBRIC (100 POINTS TOTAL) ===
1. WHO — 25 points: Did the player correctly identify the culprit?
   - 25 points if the accused name matches the actual culprit (case-insensitive, partial name match allowed).
   - 0 points if wrong.

2. WHY — 50 points: Did the player correctly identify the motive?
   - 40-50 points: Motive is essentially correct, captures the core reason.
   - 20-39 points: Partially correct — right theme but missing key details or nuance.
   - 1-19 points: Vaguely related but fundamentally wrong.
   - 0 points: Completely wrong or nonsensical.

3. HOW — 25 points: Did the player correctly identify the method/means of the crime?
   - 20-25 points: Method is essentially correct.
   - 10-19 points: Partially correct — right category but wrong specifics.
   - 1-9 points: Vaguely related.
   - 0 points: Completely wrong.

*** ZERO-SUM RULE: If WHO is WRONG (0 points), the TOTAL SCORE is automatically 0 regardless of WHY and HOW scores. ***

=== THE ABSOLUTE TRUTH ===
{json.dumps(truth_graph, indent=2)}

=== SUBMITTED BY YOU (THE PLAYER) ===
Who (Accused Culprit): {req.who}
Why (Asserted Motive): {req.why}
How (Asserted Method): {req.how}

=== YOUR FULL INVESTIGATION TRANSCRIPT ===
{combined_transcript}

=== YOUR TASK ===
You must produce a JSON object with the following exact keys. The output must be valid JSON only, with no additional text or markdown.

{{
    "correct": boolean,
    "who_score": integer (0 or 25),
    "why_score": integer (0 to 50),
    "how_score": integer (0 to 25),
    "score": integer (0 to 100 — sum of above, but 0 if who_score is 0),
    "marking_schema": "Line-by-line breakdown, e.g. WHO: +25 Correct culprit | WHY: +35 Partial motive | HOW: +20 Correct method",
    "thinking_skills_report": "A 2-4 sentence personalized roadmap of their investigation addressing the user directly as 'you' (NEVER use 'the player'). You MUST physically quote specific, exact words/sentences the user said to the suspects or the task agent. E.g., 'When you asked Anil, \"why were you in the basement\", you showed good intuition, but you completely ignored Priya's contradictory statement about the wrench.' Make it sound highly observant, impressive, and tailored to their exact chat history.",
    "analysis": "A detailed narrative (3-5 paragraphs) comparing the truth timeline to your (the user's) claims. Address the user directly as 'you' (e.g., 'You claimed the motive was...'). Highlight key moments in the transcript where you showed good deduction or missed crucial clues. Explain how your theory matches or diverges from the truth. Include the actual culprit, motive, and method, and explain why your who/why/how were right or wrong.",
    "actual_culprit": "string",
    "motive": "string",
    "method": "string",
    "key_evidence": ["list", "of", "strings"]
}}

Note: The fields actual_culprit, motive, method, key_evidence must be extracted from the truth graph. Even if your accusation was wrong, you must provide the correct truth values.

Make the thinking_skills_report highly personalized and cite direct quotes from the user's transcript to show you were paying close attention. The analysis should be a thorough walkthrough of your investigation journey, pointing out your strengths and weaknesses directly to you.
"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    self.url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 3000
                    }
                )
                response.raise_for_status()
                content = response.json()['choices'][0]['message']['content']
                
                # Cleanup JSON
                clean_str = content.strip()
                if clean_str.startswith("```json"):
                    clean_str = clean_str[7:]
                if clean_str.startswith("```"):
                    clean_str = clean_str[3:]
                if clean_str.endswith("```"):
                    clean_str = clean_str[:-3]
                
                result = json.loads(clean_str.strip())
                
                # Enforce zero-sum rule on our side as a safety net
                if result.get('who_score', 0) == 0:
                    result['score'] = 0
                    result['correct'] = False
                
                # Ensure truth fields are present (fallback if judge omitted them)
                if 'actual_culprit' not in result:
                    result['actual_culprit'] = truth_graph.get('culprit', 'Unknown')
                if 'motive' not in result:
                    result['motive'] = truth_graph.get('motive', 'Unknown')
                if 'method' not in result:
                    result['method'] = truth_graph.get('method', 'Unknown')
                if 'key_evidence' not in result:
                    result['key_evidence'] = truth_graph.get('evidence', [])
                
                return result
                
        except Exception as e:
            logger.error(f"SambaNova eval failed: {e}")
            return self._fallback_eval(session, req)

    def _fallback_eval(self, session: GameSession, req: SubmitRequest) -> dict:
        """Offline fallback when SambaNova is unavailable."""
        case = session.case_data.get('case', session.case_data)
        solution = case.get('solution', {})
        actual_culprit = solution.get('culprit', '')
        who_correct = req.who.strip().lower() in actual_culprit.lower() or actual_culprit.lower() in req.who.strip().lower()
        who_score = 25 if who_correct else 0
        # If who is wrong, total is 0 per zero-sum rule
        total_score = who_score if who_correct else 0
        return {
            "correct": who_correct,
            "who_score": who_score,
            "why_score": 0,
            "how_score": 0,
            "score": total_score,
            "marking_schema": f"WHO: {'+25 Correct' if who_correct else '+0 Wrong culprit (ZERO-SUM: total=0)'} | WHY: Not evaluated (fallback) | HOW: Not evaluated (fallback)",
            "thinking_skills_report": "Unable to connect to Judge AI. Only culprit name was checked.",
            "analysis": f"Fallback evaluation. Actual culprit: {actual_culprit}. {'You identified the correct person.' if who_correct else 'Wrong culprit — score is 0.'}",
            "actual_culprit": actual_culprit,
            "motive": solution.get('motive', 'Unknown'),
            "method": solution.get('method', 'Unknown'),
            "key_evidence": solution.get('evidence', [])
        }


# ═══════════════════════════════════════════════════════════════
# ENDPOINT: Submit Solution
# ═══════════════════════════════════════════════════════════════

@app.post("/game/{case_id}/submit", response_model=SubmitResponse)
async def submit_solution(case_id: str, req: SubmitRequest):
    session = get_session(case_id)
    
    logger.info(f"⚖️ ACCUSATION SUBMITTED for {case_id}:")
    logger.info(f"   - WHO: {req.who}")
    logger.info(f"   - WHY: {req.why}")
    logger.info(f"   - HOW: {req.how}")
    logger.info(f"Raw Request JSON:\n{req.model_dump_json(indent=2)}")

    judge = JudgeAgent()
    eval_result = await judge.evaluate(session, req)
    
    # ---- DETERMINISTIC CULPRIT OVERRIDE ----
    case = session.case_data.get('case', session.case_data)
    solution = case.get('solution', {})
    actual_culprit = solution.get('culprit', '')
    
    # Normalize and compare (case-insensitive, partial match)
    def names_match(a, b):
        a = a.strip().lower()
        b = b.strip().lower()
        return a in b or b in a

    if names_match(req.who, actual_culprit):
        # Override who_score to 25 if it's not already
        if eval_result.get('who_score', 0) != 25:
            eval_result['who_score'] = 25
            
            # Recalculate total score (zero-sum rule: if who=25, total = why + how)
            why = eval_result.get('why_score', 0)
            how = eval_result.get('how_score', 0)
            eval_result['score'] = why + how
            # Update marking_schema to reflect the override
            eval_result['marking_schema'] = (
                f"WHO: +25 Correct culprit (overridden from judge) | "
                f"WHY: {why}/50 | HOW: {how}/25"
            )
        
        # Always ensure correct is True if the user guessed the right person
        eval_result['correct'] = True
    # ----------------------------------------
    
    session.phase = "SOLVED"
    
    # Grab static truth fallback data just in case the LLM misses fields
    case = session.case_data.get('case', session.case_data)
    solution = case.get('solution', {})
    
    response_obj = SubmitResponse(
        correct=eval_result.get('correct', False),
        actual_culprit=eval_result.get('actual_culprit', solution.get('culprit', 'Unknown')),
        motive=eval_result.get('motive', solution.get('motive', 'Unknown')),
        method=eval_result.get('method', solution.get('method', 'Unknown')),
        key_evidence=eval_result.get('key_evidence', solution.get('evidence', [])),
        summary="Verdict Reached by AI Judge.",
        score=eval_result.get('score', 0),
        who_score=eval_result.get('who_score', 0),
        why_score=eval_result.get('why_score', 0),
        how_score=eval_result.get('how_score', 0),
        marking_schema=eval_result.get('marking_schema', ''),
        thinking_skills_report=eval_result.get('thinking_skills_report', ''),
        analysis=eval_result.get('analysis', '')
    )

    logger.info(f"📊 VERDICT for {case_id}:")
    logger.info(f"   - TOTAL SCORE: {response_obj.score}")
    logger.info(f"   - BREAKDOWN: {response_obj.marking_schema}")
    logger.info(f"   - CRITIQUE: {response_obj.thinking_skills_report}")
    logger.info(f"Raw Response JSON:\n{response_obj.model_dump_json(indent=2)}")

    return response_obj





# ═══════════════════════════════════════════════════════════════
# WEBSOCKET: Voice Interrogation (streaming)
# ═══════════════════════════════════════════════════════════════

@app.websocket("/game/{case_id}/interrogate/voice")
async def voice_interrogate_ws(websocket: WebSocket, case_id: str):
    await websocket.accept()

    try:
        session = game_sessions.get(case_id)
        if not session:
            await websocket.send_json({"type": "error", "message": "Game session not found"})
            await websocket.close()
            return

        if session.mode != "voice":
            await websocket.send_json({"type": "error", "message": "Game is in text mode"})
            await websocket.close()
            return

        while True:
            # Wait for audio from client
            data = await websocket.receive_json()

            if data.get("type") == "audio":
                suspect_name = data.get("suspect_name", "")
                audio_b64 = data.get("data", "")

                if not suspect_name or suspect_name not in session.suspect_prompts:
                    await websocket.send_json({"type": "error", "message": f"Unknown suspect: {suspect_name}"})
                    continue

                if session.get_remaining(suspect_name) <= 0:
                    await websocket.send_json({"type": "error", "message": f"No questions remaining for {suspect_name}"})
                    continue

                # Decode audio
                try:
                    if "," in audio_b64:
                        audio_b64 = audio_b64.split(",")[1]
                    audio_bytes = base64.b64decode(audio_b64)
                except Exception:
                    await websocket.send_json({"type": "error", "message": "Invalid audio data"})
                    continue

                # Stream STT → LLM → TTS → WebSocket using custom_voice_agent
                agent = session.interrogation_agents[suspect_name]
                # Sync history in case of previous text-mode turns
                agent.conversation_history = session.conversation_histories[suspect_name]
                
                full_text = ""
                has_transcript = False
                
                async for event in agent.stream_response(audio_bytes):
                    if event["type"] == "transcript":
                        has_transcript = True
                        session.questions_asked[suspect_name] += 1
                        
                    elif event["type"] == "error":
                        await websocket.send_json(event)
                        continue
                        
                    elif event["type"] == "audio_chunk":
                        if event.get("data"):
                            event["data"] = base64.b64encode(event["data"]).decode()
                        else:
                            event["data"] = ""
                        full_text += event.get("sentence", "") + " "
                    
                    await websocket.send_json(event)

                if has_transcript:
                    await websocket.send_json({
                        "type": "response_complete",
                        "full_text": full_text.strip(),
                        "questions_remaining": session.get_remaining(suspect_name),
                        "questions_used": session.questions_asked[suspect_name],
                    })

            elif data.get("type") == "close":
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for game {case_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# HEALTH + STARTUP
# ═══════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {"status": "ok", "games_active": len(game_sessions)}


@app.on_event("shutdown")
async def shutdown():
    for session in game_sessions.values():
        await session.cleanup()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)