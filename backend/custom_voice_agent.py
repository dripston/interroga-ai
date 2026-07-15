"""
Standalone Voice Agent for Detective Interrogation
Uses suspect agent memory folders for authentic responses
"""
import asyncio
import logging
import time
import base64
import json
import wave
import io
import re
from typing import Optional
from collections import deque
import httpx
import numpy as np
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("interrogation-agent")

# Load API keys from .env
import os
from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage


# ═══════════════════════════════════════════════════════════════
# LLM CLIENT (for punch mechanic + text mode)
# ═══════════════════════════════════════════════════════════════

class OpenRouterClient:
    @staticmethod
    async def call(prompt: str, temperature: float = 0.7, max_tokens: int = 4000) -> str:
        try:
            llm = ChatGroq(model="llama-3.1-8b-instant", temperature=temperature, max_tokens=max_tokens)
            response = await llm.ainvoke(prompt)
            return response.content
        except Exception as e:
            print(f"❌ Groq: {str(e)}")
            return ""


class RateLimiter:
    def __init__(self, max_calls: int = 10, per_seconds: int = 60):
        self.max_calls = max_calls
        self.window = per_seconds
        self.calls = deque()
    
    def can_call(self) -> bool:
        now = time.time()
        while self.calls and now - self.calls[0] > self.window:
            self.calls.popleft()
        return len(self.calls) < self.max_calls
    
    def record_call(self):
        self.calls.append(time.time())
        logger.info(f"⏱️  Rate limit: {len(self.calls)}/{self.max_calls} calls")


class LanguageDetector:
    ENGLISH_CODES = {'en', 'en-in', 'en-us', 'en-gb', 'english'}
    
    @classmethod
    def is_english(cls, language_code: str) -> bool:
        return language_code.lower() in cls.ENGLISH_CODES or language_code.lower().startswith('en')


# ═══════════════════════════════════════════════════════════════
# SUSPECT MEMORY LOADER
# ═══════════════════════════════════════════════════════════════

class SuspectMemoryLoader:
    def __init__(self, suspect_name: str, case_id: str = None):
        self.suspect_name = suspect_name
        
        if case_id:
            base_dir = Path(f"game_agents_{case_id}")
        else:
            import os
            dirs = [d for d in os.listdir('.') if d.startswith('game_agents_')]
            if dirs:
                latest_dir = max(dirs, key=os.path.getmtime)
                base_dir = Path(f"./{latest_dir}")
            else:
                base_dir = Path("game_agents")
                
        self.suspect_dir = base_dir / f"suspect_{suspect_name.lower().replace(' ', '_')}"
        
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
            except:
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
            "THE FUNNY ONE": "Use humor to deflect tension. Crack jokes, use puns, and don't take the detective seriously. Be likeable but elusive.",
            "THE RUDE ONE": "Be prickly, impatient, and direct. You hate being questioned. Pissed off by dumb questions. 'Do I look like I have time for this?'",
            "THE SCARED ONE": "Be nervous, jumpy, and defensive. Overthink questions. Stutter slightly if pressured. You are terrified of being blamed.",
            "THE SARCASTIC ONE": "Heavy eye-rolling, dry wit, and passive-aggressive answers. 'Oh wow, great question detective. Truly a master at work.'",
            "THE CHILL ONE": "Too calm. Unbothered. Suspiciously relaxed. Treat it like a casual chat. 'Whatever, man.'",
            "THE DRAMATIC ONE": "Over-the-top reactions. Gasp, be offended, make everything about your personal tragedy. 'HOW DARE YOU ACCUSE ME!'",
            "THE STREET-SMART ONE": "Know your rights. Be calculating. Negotiate. 'I'll tell you what I saw, but what's in it for me?'"
        }.get(archetype, "Be a unique personality based on your backstory and traits.")
        
        prompt = f"""You ARE {self.identity['name']}. NO meta-talk. NO "Assistant:". NO "SUSPECT:". NO bracketed actions like (sighs) or (pausing).

CORE IDENTITY:
- Archetype: {archetype}
- Traits: {', '.join(self.identity['personality'])}
- Speaking Style: {speaking_style}
- Instruction: {archetype_instructions}

MY STORY: {self.identity.get('backstory', '')}
MY ALIBI: {self.knowledge.get('my_alibi', '')}
MY SECRET: {self.knowledge.get('my_secret', '')}

WHAT I KNOW ABOUT THE CRIME: {self.knowledge.get('what_i_know_about_crime', '')}
WHAT I KNOW ABOUT THE VICTIM: {self.knowledge.get('what_i_know_about_victim', '')}

{rel_context}{memory_context}{observation_context}

STRICT RESPONSE RULES:
1. NO BRACKETS OR ASTERISKS. Do NOT describe your actions or emotions in brackets like [angry] or *sighs*.
2. SHOW, DON'T TELL. Instead of writing (sighs), start your sentence with "Ugh..." or "Look...". Show emotion through your actual words, pacing, and tone!
3. NO PREFIXES. Do NOT start with "SUSPECT:" or "{self.identity['name']}:". Just speak directly.
4. BE YOUR ARCHETYPE. If you are angry, use aggressive words. If you are funny, be sarcastic. Make your personality blindingly obvious from the first word.
5. LENGTH: Concise 2-3 sentences (roughly 60-70 words max). Do not yap.
6. ENGLISH ONLY. Natural spoken English. No foreign words or slang.
7. STICK TO THE ALIBI. If caught, react defensively or emotionally based on your persona.
8. DO NOT INVENT RELATIONSHIPS. If the detective asks about people or events you do NOT know about, deny knowing them. Do not improvise connections.

Phrases You Use:
{chr(10).join(f"- {p}" for p in speech_patterns)}

Now, respond to the detective. STAY IN CHARACTER.
"""
        return prompt


# ═══════════════════════════════════════════════════════════════
# SHARED HELPERS — used by BOTH text and voice mode
# ═══════════════════════════════════════════════════════════════

def build_chat_messages(system_prompt: str, suspect_name: str, conversation_history: list, user_input: str) -> list:
    chat_messages = [SystemMessage(content=system_prompt)]
    for msg in conversation_history[-10:]:
        if msg['role'] == 'user':
            chat_messages.append(HumanMessage(content=msg['content']))
        elif msg['role'] == 'assistant':
            chat_messages.append(AIMessage(content=msg['content']))
    chat_messages.append(HumanMessage(content=user_input))
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
    """Non-streaming LLM call — used by text mode."""
    chat_messages = build_chat_messages(system_prompt, suspect_name, conversation_history, user_input)
    llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.85, max_tokens=180)
    response_msg = await llm.ainvoke(chat_messages)
    return clean_response(response_msg.content.strip(), suspect_name)


# ═══════════════════════════════════════════════════════════════
# STT — REST with persistent client
# ═══════════════════════════════════════════════════════════════

class SarvamSTT:
    def __init__(self, api_key: str, client: httpx.AsyncClient = None):
        self.api_key = api_key
        self.client = client or httpx.AsyncClient(timeout=30.0)
    
    def _create_wav(self, audio_bytes: bytes) -> bytes:
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(audio_bytes)
        return wav_buffer.getvalue()
    
    async def transcribe(self, audio_bytes: bytes) -> tuple[str, str]:
        if not audio_bytes:
            return "", "unknown"
        try:
            # Log first 4 bytes to debug format issues
            logger.info(f"🔍 Audio format: first 4 bytes = {audio_bytes[:4].hex()}, size = {len(audio_bytes)}")

            # WebM from browser (EBML magic bytes)
            if audio_bytes[:4] == bytes([0x1a, 0x45, 0xdf, 0xa3]):
                file_tuple = ('audio.webm', audio_bytes, 'audio/webm')
                logger.info("📦 Format detected: WebM (browser)")
            # OGG from browser (some browsers use OGG)
            elif audio_bytes[:4] == b'OggS':
                file_tuple = ('audio.ogg', audio_bytes, 'audio/ogg')
                logger.info("📦 Format detected: OGG (browser)")
            # WAV — already a proper WAV file
            elif audio_bytes[:4] == b'RIFF':
                file_tuple = ('audio.wav', audio_bytes, 'audio/wav')
                logger.info("📦 Format detected: WAV")
            else:
                # Raw PCM from CLI PyAudio — wrap in WAV header
                wav_bytes = self._create_wav(audio_bytes)
                file_tuple = ('audio.wav', wav_bytes, 'audio/wav')
                logger.info("📦 Format detected: Raw PCM → wrapped as WAV (CLI)")

            response = await self.client.post(
                "https://api.sarvam.ai/speech-to-text",
                headers={"api-subscription-key": self.api_key},
                files={'file': file_tuple},
                data={'language_code': 'unknown', 'model': 'saarika:v2.5'}
            )
            response.raise_for_status()
            result = response.json()
            transcript = result.get("transcript", "")
            lang = result.get("language_code", "unknown")
            if transcript:
                logger.info(f"🎤 STT: '{transcript}' (lang: {lang})")
            return transcript, lang
        except Exception as e:
            logger.error(f"❌ STT error: {e}")
            return "", "unknown"


# ═══════════════════════════════════════════════════════════════
# TTS — REST with persistent client
# ═══════════════════════════════════════════════════════════════
def format_age_for_tts(text: str) -> str:
    """Convert '17-year-old' to 'seventeen year old' for better TTS parsing."""
    def replace_age(match):
        age_str = match.group(1)
        try:
            age = int(age_str)
            tens_map = {1: 'ten', 2: 'twenty', 3: 'thirty', 4: 'forty', 5: 'fifty', 6: 'sixty', 7: 'seventy', 8: 'eighty', 9: 'ninety'}
            ones_map = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven', 8: 'eight', 9: 'nine'}
            teens_map = {11: 'eleven', 12: 'twelve', 13: 'thirteen', 14: 'fourteen', 15: 'fifteen', 16: 'sixteen', 17: 'seventeen', 18: 'eighteen', 19: 'nineteen'}
            
            if 11 <= age <= 19:
                word_age = teens_map[age]
            elif 20 <= age <= 99:
                tens = age // 10
                ones = age % 10
                if ones == 0:
                    word_age = tens_map[tens]
                else:
                    word_age = f"{tens_map[tens]} {ones_map[ones]}"
            elif age == 10:
                word_age = "ten"
            else:
                return f"{age_str} year old"
                
            return f"{word_age} year old"
        except:
            pass
        return f"{age_str} year old"
        
    return re.sub(r'(\d+)-year-old', replace_age, text)


class SarvamTTS:
    def __init__(self, api_key: str, speaker: str = "rehan", target_lang: str = "en-IN", client: httpx.AsyncClient = None):
        self.api_key = api_key
        self.speaker = speaker
        self.target_lang = target_lang
        self.client = client or httpx.AsyncClient(timeout=30.0)
    
    async def synthesize(self, text: str) -> Optional[bytes]:
        if not text or len(text.strip()) < 2:
            return None
        text = re.sub(r'\([^)]*\)', '', text).strip()
        text = re.sub(r'\[[^\]]*\]', '', text).strip()
        text = re.sub(r'\*[^*]*\*', '', text).strip()
        text = format_age_for_tts(text)
        if not text:
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
                audio_bytes = base64.b64decode(data["audios"][0])
                logger.info(f"🔊 TTS: {len(audio_bytes)} bytes")
                return audio_bytes
        except Exception as e:
            logger.error(f"❌ TTS error: {e}")
        return None


class SarvamTranslate:
    """Translation via Sarvam mayura:v1 — supports 12 Indian languages + English"""
    
    def __init__(self, api_key: str, client: httpx.AsyncClient = None):
        self.api_key = api_key
        self.client = client or httpx.AsyncClient(timeout=30.0)
    
    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        if not text.strip():
            return text
        if source_lang == target_lang:
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
            result = response.json()
            translated = result.get("translated_text", text)
            logger.info(f"🌐 Translate [{source_lang}→{target_lang}]: '{text[:40]}' → '{translated[:40]}'")
            return translated
        except Exception as e:
            logger.error(f"❌ Translation error: {e}")
            return text


# Supported languages for voice mode
SUPPORTED_LANGUAGES = {
    '1': ('en-IN', 'English'),
    '2': ('hi-IN', 'Hindi'),
    '3': ('bn-IN', 'Bengali'),
    '4': ('ta-IN', 'Tamil'),
    '5': ('te-IN', 'Telugu'),
    '6': ('mr-IN', 'Marathi'),
    '7': ('kn-IN', 'Kannada'),
    '8': ('ml-IN', 'Malayalam'),
    '9': ('gu-IN', 'Gujarati'),
    '10': ('pa-IN', 'Punjabi'),
    '11': ('od-IN', 'Odia'),
}


# ═══════════════════════════════════════════════════════════════
# AUDIO HANDLER
# ═══════════════════════════════════════════════════════════════

class AudioHandler:
    def __init__(self):
        import pyaudio
        self.pyaudio = pyaudio.PyAudio()
        self.sample_rate = 16000
        self.stop_playback = False
    
    def record_audio(self, duration: float = 5.0) -> bytes:
        import pyaudio
        stream = self.pyaudio.open(
            format=pyaudio.paInt16, channels=1,
            rate=self.sample_rate, input=True, frames_per_buffer=1024
        )
        frames = []
        for _ in range(int(self.sample_rate / 1024 * duration)):
            frames.append(stream.read(1024, exception_on_overflow=False))
        stream.stop_stream()
        stream.close()
        return b''.join(frames)
    
    def record_until_silence(self, silence_timeout: float = 0.7, max_duration: float = 15.0, energy_threshold: int = 500) -> bytes:
        import struct
        import pyaudio
        CHUNK = 4800
        chunk_duration = CHUNK / self.sample_rate
        
        stream = self.pyaudio.open(
            format=pyaudio.paInt16, channels=1,
            rate=self.sample_rate, input=True, frames_per_buffer=CHUNK
        )
        
        frames = []
        speech_started = False
        silence_chunks = 0
        max_silence_chunks = int(silence_timeout / chunk_duration)
        max_chunks = int(max_duration / chunk_duration)
        wait_chunks = int(8.0 / chunk_duration)
        total_chunks = 0
        wait_count = 0
        
        try:
            while True:
                data = stream.read(CHUNK, exception_on_overflow=False)
                samples = struct.unpack(f'<{CHUNK}h', data)
                rms = int((sum(s * s for s in samples) / CHUNK) ** 0.5)
                is_speech = rms > energy_threshold
                
                if not speech_started:
                    if is_speech:
                        speech_started = True
                        frames.append(data)
                        total_chunks += 1
                        logger.info(f"🎙️ Speech detected (RMS: {rms})")
                    else:
                        wait_count += 1
                        if wait_count >= wait_chunks:
                            break
                else:
                    frames.append(data)
                    total_chunks += 1
                    if is_speech:
                        silence_chunks = 0
                    else:
                        silence_chunks += 1
                        if silence_chunks >= max_silence_chunks:
                            logger.info(f"🔇 Silence after {total_chunks * chunk_duration:.1f}s")
                            break
                    if total_chunks >= max_chunks:
                        break
        finally:
            stream.stop_stream()
            stream.close()
        
        return b''.join(frames)
    
    def play_audio(self, wav_bytes: bytes):
        try:
            with wave.open(io.BytesIO(wav_bytes), 'rb') as wav_file:
                sr = wav_file.getframerate()
                ch = wav_file.getnchannels()
                sw = wav_file.getsampwidth()
                audio_data = wav_file.readframes(wav_file.getnframes())
            
            stream = self.pyaudio.open(
                format=self.pyaudio.get_format_from_width(sw),
                channels=ch, rate=sr, output=True
            )
            for i in range(0, len(audio_data), 1024):
                if self.stop_playback:
                    self.stop_playback = False
                    break
                stream.write(audio_data[i:i+1024])
            stream.stop_stream()
            stream.close()
        except Exception as e:
            logger.error(f"❌ Playback error: {e}")
    
    def close(self):
        self.pyaudio.terminate()


# ═══════════════════════════════════════════════════════════════
# TEXT MODE AGENT
# ═══════════════════════════════════════════════════════════════

class TextModeAgent:
    def __init__(self, suspect_name: str, system_prompt: str, limit: int = 20, loader: SuspectMemoryLoader = None):
        self.suspect_name = suspect_name
        self.system_prompt = system_prompt
        self.limit = limit
        self.questions_used = 0
        self.loader = loader
        self.conversation_history = []
        if loader and loader.chat_history:
            self.conversation_history.extend(loader.chat_history)
    
    def _save_usage(self):
        try:
            with open("session_usage.json", "w") as f:
                json.dump({
                    "suspect_name": self.suspect_name,
                    "questions_used": self.questions_used,
                    "limit": self.limit,
                    "remaining": self.limit - self.questions_used
                }, f)
        except Exception as e:
            print(f"⚠️ Failed to save usage: {e}")

    async def generate_response(self, user_input: str) -> str:
        """Generates LLM response. Handles punch keywords and chat history saving."""
        punch_words = ['punch', 'slap', 'belt', 'hit', 'smack', 'kick', 'shove', 'grab', 'threaten']
        if any(word in user_input.lower() for word in punch_words):
            punch_prompt = f"""Continue this interrogation. The detective just physically intimidated you: "{user_input}"

You are {self.suspect_name}. React in character. MAX 15 WORDS. No brackets, no actions, no prefixes. Just your spoken reaction.

PREVIOUS CONTEXT:
{chr(10).join(f"{m['role'].upper()}: {m['content']}" for m in self.conversation_history[-6:])}

YOUR REACTION:"""
            
            reaction = await OpenRouterClient.call(punch_prompt, temperature=0.9, max_tokens=100)
            reaction = reaction.strip()
            if reaction.startswith("SUSPECT") or reaction.startswith(self.suspect_name):
                reaction = reaction.split(":", 1)[-1].strip()
            
            self.conversation_history.append({"role": "user", "content": f"*{user_input}*"})
            self.conversation_history.append({"role": "assistant", "content": reaction})
            if self.loader:
                self.loader.save_chat_history(self.conversation_history)
            return reaction
            
        self.conversation_history.append({"role": "user", "content": user_input})
        response = await call_llm(
            self.system_prompt, self.suspect_name,
            self.conversation_history, user_input
        )
        self.conversation_history.append({"role": "assistant", "content": response})
        if self.loader:
            self.loader.save_chat_history(self.conversation_history)
        return response

    async def start_chat(self):
        while True:
            try:
                if self.questions_used >= self.limit:
                    print(f"\n⏳ Session limit reached! ({self.limit} questions)")
                    self._save_usage()
                    break

                user_input = input("\n🕵️  Detective: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ['quit', 'exit', 'bye', 'back']:
                    print(f"\n👋 Goodbye! Thanks for interrogating {self.suspect_name}.")
                    self._save_usage()
                    break
                
                punch_words = ['punch', 'slap', 'belt', 'hit', 'smack', 'kick', 'shove', 'grab', 'threaten']
                is_punch = any(word in user_input.lower() for word in punch_words)
                if not is_punch:
                    self.questions_used += 1
                    
                response = await self.generate_response(user_input)
                
                if is_punch:
                    print(f"\n👊 *You {user_input.lower()} {self.suspect_name}*")
                
                print(f"\n👤 {self.suspect_name}: {response}")
                print(f"   (Questions remaining: {self.limit - self.questions_used})")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                self._save_usage()
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                continue


# ═══════════════════════════════════════════════════════════════
# VOICE MODE AGENT — shared httpx client, streaming LLM → TTS
# ═══════════════════════════════════════════════════════════════

class InterrogationAgent:
    def __init__(self, suspect_name: str, system_prompt: str, sarvam_api_key: str, speaker: str = "rehan", user_lang: str = "en-IN", loader: SuspectMemoryLoader = None):
        self.suspect_name = suspect_name
        self.system_prompt = system_prompt
        self.loader = loader
        self.user_lang = user_lang
        
        # Shared persistent HTTP client — connection pooling
        self._http_client = httpx.AsyncClient(timeout=30.0)
        self.stt = SarvamSTT(sarvam_api_key, client=self._http_client)
        self.tts = SarvamTTS(sarvam_api_key, speaker, target_lang=user_lang, client=self._http_client)
        self.translator = SarvamTranslate(sarvam_api_key, client=self._http_client)
        
        self.audio = AudioHandler()
        self.rate_limiter = RateLimiter(max_calls=10, per_seconds=60)
        self.running = False
        self.is_speaking = False
        
        self.conversation_history = []
        if loader and loader.chat_history:
            self.conversation_history.extend(loader.chat_history)
    
    async def start(self):
        self.running = True
        logger.info(f"🎭 {self.suspect_name} ready!")
        logger.info("💡 Speak naturally — I'll wait for you to finish")
        
        try:
            while self.running:
                if self.is_speaking:
                    audio_chunk = await asyncio.to_thread(self.audio.record_audio, 2.0)
                    transcript, lang = await self.stt.transcribe(audio_chunk)
                    if transcript and lang == self.user_lang:
                        logger.info("🛑 BARGE-IN!")
                        self.audio.stop_playback = True
                        await asyncio.sleep(0.2)
                        if self.rate_limiter.can_call():
                            self.rate_limiter.record_call()
                            await self._handle_user_input(transcript)
                else:
                    audio_chunk = await asyncio.to_thread(self.audio.record_until_silence)
                    if not audio_chunk:
                        continue
                    
                    if not self.rate_limiter.can_call():
                        logger.warning("⚠️  Rate limited")
                        continue
                    
                    self.rate_limiter.record_call()
                    await self._handle_user_input(audio_chunk)
                    
        except KeyboardInterrupt:
            logger.info("\n👋 Bye!")
        finally:
            self.audio.close()
            await self._http_client.aclose()
    
    async def stream_response(self, user_audio: bytes):
        """
        Async generator that yields events for sequential playback or WebSocket streaming.
        Accepts raw audio bytes (WebM from browser, PCM from CLI).
        """
        t_start = time.time()
        
        # STT — format auto-detected inside transcribe()
        transcript, lang = await self.stt.transcribe(user_audio)
        logger.info(f"⚡ STT: {time.time() - t_start:.2f}s — '{transcript}' ({lang})")
        
        if not transcript:
            yield {"type": "error", "message": "Could not transcribe audio"}
            return
            
        if lang != self.user_lang:
            yield {"type": "error", "message": f"Please speak in {self.user_lang} (detected: {lang})"}
            return
            
        yield {"type": "transcript", "text": transcript, "language": lang}
        
        user_text = transcript
        logger.info(f"💬 User: '{user_text}'")
        
        # ── PUNCH mechanic ──
        punch_words = ['punch', 'slap', 'belt', 'hit', 'smack', 'kick', 'shove', 'grab', 'threaten']
        if any(word in user_text.lower() for word in punch_words):
            punch_prompt = f"""Continue this interrogation. The detective just physically intimidated you: "{user_text}"

You are {self.suspect_name}. React in character. MAX 15 WORDS. No brackets, no actions, no prefixes. Just your spoken reaction.

PREVIOUS CONTEXT:
{chr(10).join(f"{m['role'].upper()}: {m['content']}" for m in self.conversation_history[-6:])}

YOUR REACTION:"""
            
            reaction = await OpenRouterClient.call(punch_prompt, temperature=0.9, max_tokens=100)
            reaction = clean_response(reaction.strip(), self.suspect_name)
            
            self.conversation_history.append({"role": "user", "content": f"*{user_text}*"})
            self.conversation_history.append({"role": "assistant", "content": reaction})
            if self.loader:
                self.loader.save_chat_history(self.conversation_history)
            
            logger.info(f"👊 Punch reaction: {reaction}")
            audio = await self.tts.synthesize(reaction)
            yield {"type": "audio_chunk", "sentence": reaction, "data": audio}
            return
        
        # Translate user speech to English if needed
        english_text = user_text
        if self.user_lang != "en-IN":
            english_text = await self.translator.translate(user_text, self.user_lang, "en-IN")
            logger.info(f"🌐 User (EN): '{english_text}'")
            yield {"type": "transcript_en", "text": english_text}
        
        # Add user turn (store English version for LLM context)
        self.conversation_history.append({"role": "user", "content": english_text})
        
        chat_messages = build_chat_messages(
            self.system_prompt, self.suspect_name,
            self.conversation_history, english_text
        )
        
        full_response = ""
        llm = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0.85,
            max_tokens=180,
            streaming=True
        )
        
        buffer = ""
        first_token = True
        first_tts = True
        
        async for chunk in llm.astream(chat_messages):
            content = chunk.content
            if not content:
                continue
            if first_token:
                logger.info(f"⚡ LLM first token: {time.time() - t_start:.2f}s")
                first_token = False
            buffer += content
            full_response += content

            # Aggressive chunking — fire TTS ASAP
            stripped = buffer.strip()
            word_count = len(stripped.split())
            should_fire = False
            
            if any(stripped.endswith(p) for p in ['.', '!', '?']) and len(stripped) > 5:
                should_fire = True
            elif any(stripped.endswith(p) for p in [',', ';', ':', '—', ' -']) and word_count >= 4:
                should_fire = True
            elif len(stripped) >= 50:
                should_fire = True
            
            if should_fire:
                text = clean_response(stripped, self.suspect_name)
                if text:
                    if self.user_lang != "en-IN":
                        text = await self.translator.translate(text, "en-IN", self.user_lang)
                    t_tts = time.time()
                    audio = await self.tts.synthesize(text)
                    if first_tts:
                        logger.info(f"⚡ First TTS done: {time.time() - t_start:.2f}s (TTS call: {time.time() - t_tts:.2f}s)")
                        first_tts = False
                    yield {"type": "audio_chunk", "sentence": text, "data": audio}
                buffer = ""
        
        # Flush remainder
        if buffer.strip():
            text = clean_response(buffer.strip(), self.suspect_name)
            if text:
                if self.user_lang != "en-IN":
                    text = await self.translator.translate(text, "en-IN", self.user_lang)
                audio = await self.tts.synthesize(text)
                yield {"type": "audio_chunk", "sentence": text, "data": audio}
        
        logger.info(f"⚡ Total turn: {time.time() - t_start:.2f}s")
        
        cleaned = clean_response(full_response, self.suspect_name)
        self.conversation_history.append({"role": "assistant", "content": cleaned})
        logger.info(f"🤖 LLM: {cleaned}")
        
        if self.loader:
            self.loader.save_chat_history(self.conversation_history)

    async def _handle_user_input(self, audio_chunk: bytes):
        """Standalone CLI handler: streams LLM chunks, queues audio, plays sequentially."""
        audio_queue = asyncio.Queue()
        
        async def tts_producer():
            async for event in self.stream_response(audio_chunk):
                if event["type"] == "audio_chunk" and event.get("data"):
                    await audio_queue.put(event["data"])
            await audio_queue.put(None)
            
        async def audio_consumer():
            while True:
                audio = await audio_queue.get()
                if audio is None:
                    break
                self.is_speaking = True
                await asyncio.to_thread(self.audio.play_audio, audio)
            self.is_speaking = False
            
        await asyncio.gather(tts_producer(), audio_consumer())


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

async def main():
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Suspect Voice/Text Agent')
    parser.add_argument('suspect_name', type=str, help='Name of the suspect')
    parser.add_argument('--limit', type=int, default=20, help='Question limit')
    parser.add_argument('--voice', action='store_true', help='Voice mode')
    parser.add_argument('--case_id', type=str, default=None, help='Specific case ID to load instead of the latest')
    args = parser.parse_args()
    
    suspect_name = args.suspect_name
    limit = args.limit
    
    try:
        loader = SuspectMemoryLoader(suspect_name, case_id=args.case_id)
    except FileNotFoundError:
        print(f"❌ Suspect '{suspect_name}' not found.")
        sys.exit(1)
    
    voice_id = loader.identity.get('character_voice', {}).get('voice_id', 'rehan')
    
    print(f"\n🎭 Loading suspect: {suspect_name}")
    print("=" * 70)
    print(f"📋 Name: {loader.identity['name']}")
    print(f"👤 Role: {loader.identity['role']}")
    print(f"🎭 Personality: {', '.join(loader.identity['personality'])}")
    print(f"🎤 Voice: {voice_id}")
    print("=" * 70)
    
    system_prompt = loader.build_system_prompt()
    
    if not args.voice:
        mode_choice = input("\n🎙️ Use Voice Mode? (y/n) [n]: ").strip().lower()
        if mode_choice == 'y':
            args.voice = True

    if args.voice:
        sarvam_key = os.getenv("SARVAM_API_KEY", "")
        if not sarvam_key:
            print("❌ SARVAM_API_KEY not set. Falling back to text mode.")
            args.voice = False
        else:
            print("\n🌐 Choose your language:")
            for key, (code, name) in SUPPORTED_LANGUAGES.items():
                print(f"  {key}. {name}")
            lang_choice = input("\nEnter choice [1]: ").strip() or '1'
            user_lang_code, user_lang_name = SUPPORTED_LANGUAGES.get(lang_choice, ('en-IN', 'English'))
            
            print(f"\n🎙️ Voice Mode: Interrogating {suspect_name}")
            print(f"🌐 Language: {user_lang_name}")
            print("💡 Speak naturally — I'll wait for you to finish")
            print("Press Ctrl+C to exit")
            print("=" * 50)
            
            agent = InterrogationAgent(
                suspect_name, system_prompt,
                sarvam_key, speaker=voice_id,
                user_lang=user_lang_code, loader=loader
            )
            await agent.start()
            return
    
    print(f"\n📝 Text Mode: Chatting with {suspect_name}")
    print(f"⏳ Questions remaining: {limit}")
    print("Type 'quit' to exit")
    print("=" * 50)
    
    agent = TextModeAgent(suspect_name, system_prompt, limit, loader)
    await agent.start_chat()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass