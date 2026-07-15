#!/usr/bin/env python3
"""
Task Agent - Two-Block System
Block 1: Companion LLM (questions/opinions)
Block 2: Source Lookup Engine (actions/investigations)
"""
import asyncio
import json
import copy
import sys
import io
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

import os
from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq

# ═══════════════════════════════════════════════════════════════
# LLM CLIENT
# ═══════════════════════════════════════════════════════════════

class OpenRouterClient:
    """Handles all LLM calls via Groq"""

    @staticmethod
    async def call(prompt: str, temperature: float = 0.7, max_tokens: int = 4000, model_name: str = "llama-3.1-8b-instant") -> str:
        try:
            llm = ChatGroq(model=model_name, temperature=temperature, max_tokens=max_tokens)
            response = await llm.ainvoke(prompt)
            return response.content
        except Exception as e:
            print(f"❌ Groq: {str(e)}")
            return ""

# ═══════════════════════════════════════════════════════════════
# TASK AGENT MEMORY LOADER
# ═══════════════════════════════════════════════════════════════

class TaskAgentMemory:
    """Loads task agent memory from game_agents/task_agent/"""

    def __init__(self, case_id: str = None):
        if case_id:
            self.agents_dir = Path(f"./game_agents_{case_id}")
        else:
            import os
            dirs = [d for d in os.listdir('.') if d.startswith('game_agents_')]
            if dirs:
                latest_dir = max(dirs, key=os.path.getmtime)
                self.agents_dir = Path(f"./{latest_dir}")
            else:
                self.agents_dir = Path("./game_agents")
        
        self.task_dir = self.agents_dir / "task_agent"

        if not self.task_dir.exists():
            raise FileNotFoundError(f"Task agent folder not found: {self.task_dir}")

        self.identity = self._load_json('identity.json')
        self.knowledge = self._load_json('knowledge.json')
        self.investigation_state = self._load_json('investigation_state.json')
        self.investigatable_sources = self._load_json('investigatable_sources.json')
        self.evidence_layers = self._load_json('evidence_layers.json')
        self.hint_system = self._load_json('hint_system.json')

    def _load_json(self, filename: str) -> dict:
        filepath = self.task_dir / filename
        if not filepath.exists():
            print(f"⚠️  Missing: {filename}")
            return {}
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_investigation_state(self):
        filepath = self.task_dir / 'investigation_state.json'
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.investigation_state, f, indent=2, ensure_ascii=False)

# ═══════════════════════════════════════════════════════════════
# TASK AGENT
# ═══════════════════════════════════════════════════════════════

class TaskAgent:

    def __init__(self, case_id: str = None):
        self.memory = TaskAgentMemory(case_id)
        self.sources = self.memory.investigatable_sources.get('sources', [])
        self.suspects = self.memory.knowledge.get('all_suspects', [])
        self.timeline = self.memory.knowledge.get('timeline', [])

        if not self.memory.investigation_state.get('investigation_started_at'):
            self.memory.investigation_state['investigation_started_at'] = datetime.now().isoformat()
            self.memory.save_investigation_state()

        self.live_histories = {} # Injected by server.py at runtime

    # ─────────────────────────────────────────────────────────────
    # ENTRY POINT
    # ─────────────────────────────────────────────────────────────

    async def execute(self, user_command: str) -> str:
        if user_command.lower() in ['help', 'h', '?']:
            return self._get_help_message()
            
        print("🧠 Calling Detective Partner LLM...")

        # Briefing text
        briefing_path = self.memory.agents_dir / "detective_briefing" / "briefing.json"
        briefing_text = "No briefing available."
        if briefing_path.exists():
            with open(briefing_path, 'r', encoding='utf-8') as f:
                briefing_data = json.load(f)
                briefing_text = briefing_data.get('briefing_text', briefing_data.get('briefing', briefing_text))

        # Formatting live chat histories (passed from Server)
        chats_text = ""
        if getattr(self, 'live_histories', None):
            all_chats = []
            for suspect, history in self.live_histories.items():
                if history and len(history) > 1:
                    formatted = f"--- {suspect.upper()} ---\n"
                    # Only take the last 4 user/assistant exchanges to keep context focused
                    for msg in history[-8:]:
                        if msg['role'] != 'system':
                            formatted += f"[{msg['role'].upper()}]: {msg['content']}\n"
                    all_chats.append(formatted)
            chats_text = "\n".join(all_chats)
        else:
            chats_text = "No suspects interrogated yet."

        # ── KEYWORD MATCHING: Only surface evidence that matches the user's query ──
        user_lower = user_command.lower()
        matched_evidence = []
        for s in self.sources:
            keywords = s.get('query_keywords', [])
            desc_lower = s.get('description', '').lower()
            source_type = s.get('source_type', '').lower()
            related_suspect = s.get('related_to_suspect', '').lower()
            witness_name = s.get('witness_name', '').lower()
            location = s.get('location', '').lower()
            
            # Check if any keyword, suspect name, source type, witness, or location matches
            hit = False
            for kw in keywords:
                if kw.lower() in user_lower:
                    hit = True
                    break
            if not hit and related_suspect and related_suspect in user_lower:
                hit = True
            if not hit and witness_name and witness_name in user_lower:
                hit = True
            if not hit and source_type in user_lower:
                hit = True
            if not hit and location and any(word in user_lower for word in location.split() if len(word) > 3):
                hit = True
            # Also check if any significant word from description matches
            if not hit:
                desc_words = [w for w in desc_lower.split() if len(w) > 4]
                for w in desc_words:
                    if w in user_lower:
                        hit = True
                        break
            
            if hit:
                matched_evidence.append(
                    f"- [ID: {s.get('id')}] TYPE: {s.get('source_type', 'Unknown')} | DESC: {s.get('description', 'Unknown')} | FINDINGS: {s.get('findings', 'No data')}"
                )

        # Build the evidence section: only matched items, or a "nothing found" note
        if matched_evidence:
            evidence_section = "MATCHED EVIDENCE FOR THIS QUERY:\n" + "\n".join(matched_evidence)
        else:
            evidence_section = "NO EVIDENCE MATCHED THIS QUERY. Nothing in the database relates to what the detective asked."

        # Build a menu of available source types (descriptions only, NO findings) so the agent can suggest
        available_sources_menu = "\n".join([
            f"- {s.get('source_type', '?').upper()}: {s.get('description', '?')} (Location: {s.get('location', s.get('related_to_suspect', 'N/A'))})"
            for s in self.sources
        ])

        system_prompt = f"""You are a gritty, sharp detective partner working this murder case with the user.

=== ABSOLUTE RULES — VIOLATING ANY OF THESE IS A CRITICAL FAILURE ===

1. ONLY ANSWER WHAT IS ASKED. If the detective says "Anil is suspicious" or makes a comment, respond with a SHORT opinion (1-2 sentences). Do NOT volunteer evidence, findings, or investigation results unless they EXPLICITLY ask you to check/look up/investigate something.

2. NEVER DUMP MULTIPLE PIECES OF EVIDENCE. If the detective asks to check ONE thing, give them ONE result. Do not list other findings, do not say "I also found..." or "Additionally...". ONE query = ONE answer.

3. If the detective asks a BROAD question like "check everything" or "what do we have", push back: "That's a lot of ground, partner. Give me something specific — a name, a location, a piece of evidence."

4. If the MATCHED EVIDENCE section below says "NO EVIDENCE MATCHED", tell them you couldn't find anything related to that. Then suggest ONE specific thing they could ask about instead (pick from the Available Sources menu).

5. NEVER reveal who the culprit is. NEVER say "the evidence points to X as the killer." You are a partner, not the judge.

6. NEVER mention the evidence database, source IDs, or that you have a list. Act like you're physically going to check things.

7. MAX 2-3 SENTENCES. No essays. No bullet points. No lists. Talk like a real detective partner.

8. If they ask for your OPINION on a suspect, give a brief cynical take based ONLY on what's in the chat transcripts. Do NOT reference evidence they haven't asked about.

=== END OF RULES ===

CASE BRIEFING (Background context only — do NOT recite this):
{briefing_text}

RECENT INTERROGATION NOTES (Context only — reference only if directly relevant):
{chats_text}

{evidence_section}

AVAILABLE SOURCES (For suggesting what to investigate — NEVER reveal findings from these):
{available_sources_menu}"""

        full_prompt = f"{system_prompt}\n\nDetective: \"{user_command}\"\n\nYour response (remember: ONLY answer what was asked, max 2-3 sentences):"

        response = await OpenRouterClient.call(
            full_prompt,
            temperature=0.3,
            max_tokens=200,
            model_name="llama-3.1-8b-instant"
        )
        return response.strip()

    # ─────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────

    def _clean_json_string(self, text: str) -> str:
        """Strip markdown code fences from LLM JSON responses"""
        text = text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].strip()
        return text

    def _get_help_message(self) -> str:
        return (
            "Detective, I'm your partner — I can give you my take on things, or actually go check evidence.\n"
            "Ask me opinions: 'What do you think about Vikram?' or 'Something feels off about her alibi.'\n"
            "Or send me to investigate: 'Check the barn CCTV', 'Examine Aarohi's phone logs', 'Look at the forensics report'."
        )


# ═══════════════════════════════════════════════════════════════
# INTERACTIVE MODE
# ═══════════════════════════════════════════════════════════════

async def interactive_mode():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=20, help='Question limit')
    parser.add_argument('--case-id', type=str, default=None, help='Case ID to load')
    args = parser.parse_args()
    limit = args.limit
    questions_used = 0

    try:
        agent = TaskAgent(case_id=args.case_id)
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("\n💡 Run graphrag_agent.py first to generate agent folders.")
        return

    print("\n" + "═" * 70)
    print("🔬 TASK AGENT — DETECTIVE PARTNER")
    print("═" * 70)
    print(f"\nReady. Case: {agent.memory.knowledge.get('case_title', 'Unknown')}")
    print(f"⏳ Questions remaining: {limit}")
    print(f"Type 'help' for examples or 'quit' to exit\n")
    print("═" * 70)

    def save_usage():
        try:
            with open("session_usage.json", "w") as f:
                json.dump({"questions_used": questions_used}, f)
        except:
            pass

    while True:
        try:
            if questions_used >= limit:
                print(f"\n⏳ Session limit reached! ({limit} questions used)")
                save_usage()
                break

            user_input = input("\n🕵️  Detective: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'q', 'back']:
                print("\nGood luck out there, Detective.")
                save_usage()
                break

            print()
            result = await agent.execute(user_input)
            questions_used += 1
            remaining = limit - questions_used

            print(f"🔬 Partner: {result}")
            print(f"\n   (Questions remaining: {remaining})")

        except KeyboardInterrupt:
            print("\n\nSession ended.")
            save_usage()
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

async def main():
    await interactive_mode()


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
    print("🔬 Task Agent - Two-Block System")
    print("═" * 70)
    asyncio.run(main())