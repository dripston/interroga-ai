#!/usr/bin/env python3
"""
GraphRAG Agent - Generates memory folders for all agents from case JSON
- Suspect agents (one per suspect)
- Task agent (executes user commands)
- Detective briefing (case introduction)
- Investigatable sources (evidence, logs, witnesses)
"""

import httpx
import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"



# ═══════════════════════════════════════════════════════════════
# LLM CLIENT
# ═══════════════════════════════════════════════════════════════

class OpenRouterClient:
    
    @staticmethod
    async def call(prompt: str, temperature: float = 0.7, max_tokens: int = 4000) -> str:
        try:
            from dotenv import load_dotenv
            import os
            load_dotenv(override=True)
            groq_key = os.getenv("GROQ_API_KEY", "")
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    GROQ_URL,
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": MODEL,
                        "messages": [
                            {"role": "system", "content": "Think briefly (under 100 words) then output the requested content directly."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if 'choices' in result and len(result['choices']) > 0:
                        return result['choices'][0]['message']['content']
                    else:
                        print(f"❌ Groq: Invalid response format")
                        return ""
                else:
                    print(f"❌ Groq: HTTP {response.status_code} - {response.text[:200]}")
                    return ""
                    
        except Exception as e:
            print(f"❌ Groq: {str(e)}")
            return ""

# ═══════════════════════════════════════════════════════════════
# GRAPHRAG AGENT
# ═══════════════════════════════════════════════════════════════

class GraphRAGAgent:
    
    def __init__(self, case_data: Dict):
        self.case = case_data.get('case', case_data)
        self.case_id = case_data.get('id', int(datetime.now().timestamp()))
        self.generated_at = case_data.get('generated_at', datetime.now().isoformat())
        self.agents_dir = Path(f"./game_agents_{self.case_id}")
        self.agents_dir.mkdir(exist_ok=True)
        
    async def generate_all_agents(self):
        print(f"\n🧠 GraphRAG Agent: Analyzing case and generating agent memories...")
        print(f"{'='*70}\n")
        
        await self._generate_detective_briefing()
        await self._generate_truth_graph()
        await self._generate_suspect_agents()
        await self._generate_task_agent()
        await self._generate_investigatable_sources()
        await self._categorize_evidence_by_layers()
        await self._generate_hint_system()
        
        print(f"\n{'='*70}")
        print(f"✅ All agent folders generated successfully!")
        print(f"{'='*70}\n")
        
        return {
            "success": True,
            "suspects_count": len(self.case['suspects']),
            "agents_directory": str(self.agents_dir)
        }
    
    # ═══════════════════════════════════════════════════════════════
    # DETECTIVE BRIEFING
    # ═══════════════════════════════════════════════════════════════
    
    async def _generate_detective_briefing(self):
        print(f"📋 Generating detective briefing...")
        
        prompt = f"""Write a fast-paced, dramatic case intro for a detective mystery. Second person ("You are called to...").
        
CASE: {self.case['title']}
Setting: {json.dumps(self.case['setting'])}
Crime: {json.dumps(self.case['crime'])}
Victim: {json.dumps(self.case['victim'])}
Reporting Time: The crime was reported around {self.case.get('timeline', [{'time': 'an unknown time'}])[-1].get('time', 'recently')}

STRUCTURE (in this order):
1. paragraph 1: Set the scene with rich, atmospheric sensory detail about the location and explicitly mention the Reporting Time.
2. paragraph 2: WHO is the victim — full name, role, why they matter, their public persona vs any quiet whispers.
3. paragraph 3: WHAT happened — the incident, obvious cause of death, and WHY it's suspicious (what doesn't add up).
4. End the final paragraph with exactly this sentence: "Five suspects have been identified."

RULES:
- Length: Around 150 to 200 words (3-4 short paragraphs).
- DO NOT leak any timeline events other than the reporting time.
- Focus purely on the victim and the immediate incident.
- Do NOT list suspects or evidence.
- No bullet points — flowing, punchy, dramatic prose only."""

        briefing_text = await OpenRouterClient.call(prompt, temperature=0.8, max_tokens=2000)
        
        briefing_dir = self.agents_dir / "detective_briefing"
        briefing_dir.mkdir(exist_ok=True)
        
        briefing_data = {
            "case_title": self.case['title'],
            "difficulty": self.case.get('difficulty', 'medium'),
            "setting": self.case['setting'],
            "briefing_text": briefing_text,
            "initial_information": {
                "crime": self.case['crime'],
                "victim": self.case['victim'],
                "time_window": self.case.get('time_window', '') or (self.case['timeline'][0]['time'] + ' - ' + self.case['timeline'][-1]['time'] if self.case.get('timeline') else 'Unknown'),
                "location": self.case['setting']
            },
            "suspects_overview": [
                {
                    "name": s['name'],
                    "role": s['role'],
                    "age": s['age']
                } for s in self.case['suspects']
            ],
            "evidence_count": len(self.case.get('evidence', [])),
            "generated_at": datetime.now().isoformat()
        }
        
        with open(briefing_dir / 'briefing.json', 'w', encoding='utf-8') as f:
            json.dump(briefing_data, f, indent=2, ensure_ascii=False)
        
        with open(briefing_dir / 'briefing.txt', 'w', encoding='utf-8') as f:
            f.write(f"{self.case['title']}\n")
            f.write(f"{'='*70}\n\n")
            f.write(briefing_text)
            f.write(f"\n\n{'='*70}\n")
            f.write("SUSPECT PROFILES:\n")
            f.write("-" * 30 + "\n")
            for suspect in self.case['suspects']:
                f.write(f"\n{suspect['name']}\n")
                f.write(f"Role: {suspect['role']}\n")
                f.write(f"Age: {suspect['age']}\n")
                if suspect.get('background'):
                    f.write(f"Background: {suspect['background']}\n")
            f.write(f"\n{'='*70}\n")
            f.write(f"Total Suspects: {len(self.case['suspects'])}\n")
            f.write(f"Evidence pieces: {len(self.case.get('evidence', []))}\n")
        
        print(f"  ✅ Detective briefing created")

    # ═══════════════════════════════════════════════════════════════
    # TRUTH GRAPH
    # ═══════════════════════════════════════════════════════════════

    async def _generate_truth_graph(self):
        print(f"🕸️ Generating truth graph...")
        
        prompt = f"""You are generating the absolute TRUTH GRAPH for a murder mystery.
This will be used by a Judge AI to score a player's final deduction.

CASE DATA:
{json.dumps(self.case, indent=2)}

Create a pure JSON object (no markdown, no backticks, just raw curly braces) with this exact schema:
{{
  "actual_culprit": "Name of the killer",
  "actual_motive": "Deep explanation of exactly why they did it",
  "actual_method": "Step-by-step of exactly how the murder was physically carried out",
  "timeline_of_truth": [
    {{"time": "08:00 PM", "event": "What ACTUALLY happened behind closed doors"}},
    ...
  ],
  "crucial_evidence": [
    "List of 3-4 specific clues the player MUST find to prove the case"
  ],
  "red_herrings": [
    "List of 2 false trails the player is meant to fall for"
  ],
  "hidden_suspect_secrets": {{
    "Suspect 1 Name": "Their biggest secret they are hiding (even if innocent)",
    "Suspect 2 Name": "..."
  }}
}}

Output ONLY the raw JSON object."""

        graph_json_str = await OpenRouterClient.call(prompt, temperature=0.2, max_tokens=3000)
        
        try:
            # Clean possible markdown formatting
            clean_str = graph_json_str.strip()
            if clean_str.startswith("```json"):
                clean_str = clean_str[7:]
            if clean_str.endswith("```"):
                clean_str = clean_str[:-3]
                
            truth_graph = json.loads(clean_str.strip())
            
            with open(self.agents_dir / 'truth_graph.json', 'w', encoding='utf-8') as f:
                json.dump(truth_graph, f, indent=2, ensure_ascii=False)
                
            print(f"  ✅ Truth graph created")
        except Exception as e:
            print(f"  ❌ Failed to parse Truth Graph JSON: {e}")
            # Fallback dumb graph
            with open(self.agents_dir / 'truth_graph.json', 'w', encoding='utf-8') as f:
                json.dump({"error": "Failed to parse", "raw": graph_json_str}, f, indent=2)
    
    # ═══════════════════════════════════════════════════════════════
    # SUSPECT AGENTS
    # ═══════════════════════════════════════════════════════════════
    
    async def _generate_suspect_agents(self):
        print(f"\n👥 Generating suspect agent memories...")
        
        for suspect in self.case['suspects']:
            suspect_name = suspect['name']
            suspect_dir = self.agents_dir / f"suspect_{suspect_name.lower().replace(' ', '_')}"
            suspect_dir.mkdir(exist_ok=True)
            
            print(f"  🔨 Creating: {suspect_name}...")
            
            await self._create_suspect_identity(suspect_dir, suspect)
            await self._create_suspect_knowledge(suspect_dir, suspect)
            await self._create_suspect_beliefs(suspect_dir, suspect)
            await self._create_suspect_memories(suspect_dir, suspect)
            await self._create_suspect_relationships(suspect_dir, suspect)
            self._create_suspect_conversation_state(suspect_dir, suspect)
            
            print(f"    ✅ {suspect_name} complete")
    
    async def _create_suspect_identity(self, suspect_dir: Path, suspect: Dict):
        is_culprit = suspect['name'] == self.case['solution']['culprit']
        character_type = suspect.get('character_type', 'young-male')
        
        VOICE_MAP = {
            'young-female': ['kavya', 'suhani', 'ritu'],
            'old-female': ['pooja', 'shruti', 'kavitha'],
            'young-male': ['rehan', 'tarun', 'sunny'],
            'old-male': ['aditya', 'mani', 'rohan'],
        }
        import random
        voices = VOICE_MAP.get(character_type, ['rehan', 'tarun', 'sunny'])
        assigned_voice = random.choice(voices)
        
        voice_profile = await self._generate_character_voice(suspect, is_culprit)
        voice_profile['voice_id'] = assigned_voice
        
        identity = {
            "name": suspect['name'],
            "age": suspect['age'],
            "role": suspect['role'],
            "character_type": character_type,
            "personality": suspect['personality'],
            "emotional_state": suspect.get('emotional_state', 'neutral'),
            "backstory": suspect.get('backstory', ''),
            "is_culprit": is_culprit,
            "connection_to_victim": suspect.get('relationship_to_victim', 'Known'),
            "character_voice": voice_profile
        }
        
        with open(suspect_dir / 'identity.json', 'w', encoding='utf-8') as f:
            json.dump(identity, f, indent=2, ensure_ascii=False)
    
    async def _generate_character_voice(self, suspect: Dict, is_culprit: bool) -> Dict:
        personality_str = ', '.join(suspect['personality'])
        
        prompt = f"""You are designing a CHARACTER for a detective game. This character will be INTERROGATED by a player.

Name: {suspect['name']}
Age: {suspect['age']}
Role: {suspect['role']}
Personality Traits: {personality_str}
Emotional State: {suspect.get('emotional_state', 'neutral')}
Backstory: {suspect.get('backstory', 'Unknown')}
Is Culprit: {is_culprit}

IMPORTANT: This character needs to feel like a REAL PERSON being questioned at a police station. They should have a DISTINCT vibe that's immediately recognizable.

Pick ONE dominant archetype for this character (based on personality and backstory) from these options:
- THE FUNNY ONE: Cracks jokes, uses humor to deflect, makes the detective laugh.
- THE RUDE ONE: Short-tempered, prickly, "Do I look like I care?", gets heated fast.
- THE SCARED ONE: Nervous wreck, stutters, overthinks everything. Defensiveness born of fear.
- THE SARCASTIC ONE: Eye-rolls, dry wit, passive-aggressive. "Oh wow, great question."
- THE CHILL ONE: Too calm, unbothered, almost suspiciously relaxed.
- THE DRAMATIC ONE: Over-the-top reactions, gasps, "HOW DARE YOU!", makes everything about their tragedy.
- THE STREET-SMART ONE: Knows the system, asks for lawyers, "I know my rights", negotiates.
- THE ANXIOUS ONE: Fidgety, talks too much, volunteers useless details to cover nervousness.
- THE ARROGANT ONE: Looks down on the detective, "Do you know who I am?", high-status attitude.

Generate their voice profile in JSON:
{{
  "archetype": "one of the archetypes above",
  "speaking_style": "How they talk — formality level, vocabulary, sentence length",
  "speech_patterns": ["5-7 signature SHORT phrases they'd say during interrogation"],
  "emotional_tells": {{
    "when_lying": "specific behavioral description",
    "when_truthful": "specific behavioral description", 
    "under_pressure": "specific behavioral description"
  }},
  "conversational_tendencies": ["3-4 habits like 'changes subject when cornered', 'answers questions with questions'"],
  "body_language_notes": "physical mannerisms during interrogation",
  "humor_style": "what kind of humor if any — sarcastic, nervous jokes, dark humor, none",
  "voice_id": "will be assigned automatically based on character type"
}}

Make speech_patterns SHORT (under 10 words each) and natural. No accents or slang.

JSON only:"""

        response = await OpenRouterClient.call(prompt, temperature=0.8, max_tokens=1000)
        
        try:
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            return json.loads(response.strip())
        except:
            return {
                "archetype": "THE SARCASTIC ONE",
                "speaking_style": "Casual with dry wit",
                "speech_patterns": ["Sure, whatever you say.", "Are we done here?", "That's your job, detective."],
                "emotional_tells": {"when_lying": "talks faster", "when_truthful": "makes eye contact", "under_pressure": "gets sarcastic"},
                "conversational_tendencies": ["deflects with humor", "answers questions with questions"],
                "body_language_notes": "arms crossed, eyebrow raised",
                "humor_style": "dry sarcasm",
                "voice_id": "rehan"
            }
            
    async def _covert_to_first_person(self, text: str, suspect_name: str, suspect_role: str) -> str:
        if not text or text.lower() in ["none", "unknown", "n/a"]:
            return text
            
        prompt = f"""Rewrite the following secret into the FIRST PERSON ("I", "my", "mine").
The character is {suspect_name}, who is a {suspect_role}.
Keep the exact same meaning, just change the pronouns/perspective.
Do not add any details.

SECRET TO REWRITE:
{text}

REWRITTEN IN FIRST PERSON:"""

        response = await OpenRouterClient.call(prompt, temperature=0.3, max_tokens=150)
        if response and response.strip():
            return response.strip()
        return text
    
    async def _create_suspect_knowledge(self, suspect_dir: Path, suspect: Dict):
        is_culprit = suspect['name'] == self.case['solution']['culprit']
        
        crime = self.case.get('crime', {})
        crime_what = crime.get('what_happened', 'something happened')
        crime_hidden = crime.get('hidden_truth', '')
        
        victim = self.case.get('victim', {})
        victim_name = victim.get('name', 'the victim')
        victim_role = victim.get('role', 'unknown')
        victim_age = victim.get('age', '')
        victim_public = victim.get('public_image', '')
        victim_private = victim.get('private_reality', '')
        victim_connection = victim.get('connection_to_culprit', '')
        
        timeline = self.case.get('timeline', [])
        if timeline:
            last_event = timeline[-1]
            time_of_incident = last_event.get('time', 'unknown')
            incident_summary = f"At {time_of_incident}, {victim_name} was found. Police are investigating."
        else:
            time_of_incident = self.case.get('time_window', 'unknown')
            incident_summary = f"The incident happened during {time_of_incident}."
        
        knowledge = {
            "my_role": f"I am a {suspect['role']}",
            "my_workplace": self.case.get('setting', 'this location'),
            "what_i_know_about_crime": crime_what,
            "what_i_know_about_victim": f"{victim_name}, {victim_age}, {victim_role}. {victim_public}.",
            "victim_private_reality": victim_private,
            "when_it_happened": incident_summary,
            "time_of_incident": time_of_incident,
            "my_alibi": suspect['alibi'],
            "my_secret": await self._covert_to_first_person(suspect['secret'], suspect['name'], suspect['role']),
            "my_access_level": suspect.get('knowledge_level', 'Standard access'),
            "what_i_can_access": self._extract_access_info(suspect)
        }
        
        if is_culprit:
            knowledge["hidden_truth"] = crime_hidden
            knowledge["connection_to_victim"] = victim_connection
        
        with open(suspect_dir / 'knowledge.json', 'w', encoding='utf-8') as f:
            json.dump(knowledge, f, indent=2, ensure_ascii=False)
    
    async def _create_suspect_beliefs(self, suspect_dir: Path, suspect: Dict):
        is_culprit = suspect['name'] == self.case['solution']['culprit']
        
        if is_culprit:
            beliefs = {
                "about_the_crime": "I know exactly what happened because I did it",
                "about_getting_caught": "I need to be careful with my answers",
                "my_cover_story": suspect['alibi'],
                "why_i_did_it": suspect['motive'],
                "how_i_justify_it": self._extract_moral_justification(suspect),
                "about_other_suspects": "They might suspect me, or they might suspect each other",
                "if_asked_about_my_behavior": suspect.get('suspicious_behavior', 'I acted normally')
            }
        else:
            beliefs = {
                "about_the_crime": "I believe someone did this but I don't know who",
                "about_my_innocence": "I know I didn't do it",
                "why_i_might_look_suspicious": suspect.get('suspicious_behavior', 'I have nothing to hide'),
                "my_explanation_for_suspicious_behavior": self._generate_innocent_explanation(suspect),
                "what_i_think_about_other_suspects": self._generate_beliefs_about_others(suspect),
                "my_theories_about_what_happened": self._generate_theories(suspect),
                "how_i_feel_about_being_questioned": "I want to help but I'm also worried about being wrongly accused"
            }
        
        with open(suspect_dir / 'beliefs.json', 'w', encoding='utf-8') as f:
            json.dump(beliefs, f, indent=2, ensure_ascii=False)
    
    async def _create_suspect_memories(self, suspect_dir: Path, suspect: Dict):
        memories = {
            "what_i_remember_from_that_day": [],
            "what_i_observed": [],
            "who_i_interacted_with": [],
            "sensory_details_i_remember": []
        }
        
        for event in self.case.get('timeline', []):
            witnessed_by = event.get('witnessed_by', [])
            
            is_witness = False
            for witness in witnessed_by:
                if isinstance(witness, str):
                    if (witness == suspect['name'] or 
                        suspect['name'].lower() in witness.lower() or
                        witness.lower() in suspect['name'].lower() or
                        any(word in witness.lower() for word in suspect['name'].lower().split())):
                        is_witness = True
                        break
            
            if is_witness:
                memories['what_i_remember_from_that_day'].append({
                    "time": event['time'],
                    "what_i_saw": event['event'],
                    "my_thoughts_at_the_time": self._generate_first_person_perspective(suspect, event),
                    "others_who_were_there": [w for w in witnessed_by if isinstance(w, str) and w != suspect['name']]
                })
        
        for evidence in self.case.get('evidence', []):
            if suspect['name'] in evidence.get('mentioned_by', []):
                memories['what_i_observed'].append({
                    "what_i_noticed": evidence['description'],
                    "where_i_saw_it": evidence.get('location', 'unknown'),
                    "when_i_noticed_it": "during that timeframe",
                    "what_i_thought_about_it": evidence.get('significance', 'I wasn\'t sure what it meant')
                })
        
        memories['sensory_details_i_remember'] = await self._generate_sensory_memories(suspect)
        
        with open(suspect_dir / 'memories.json', 'w', encoding='utf-8') as f:
            json.dump(memories, f, indent=2, ensure_ascii=False)
    
    async def _generate_sensory_memories(self, suspect: Dict) -> List[str]:
        prompt = f"""Generate 3-4 sensory details (sights, sounds, smells, feelings) that {suspect['name']}, a {suspect['role']}, would remember from the day of the crime at {self.case.get('setting', 'the location')}.

Write in FIRST PERSON ("I remember...", "I noticed...", "I felt...").
Make them atmospheric and specific to the setting. Return as JSON array of strings.

Setting: {self.case.get('setting', 'unknown')}
Character role: {suspect['role']}

JSON array only:"""

        response = await OpenRouterClient.call(prompt, temperature=0.8, max_tokens=300)
        
        try:
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            return json.loads(response.strip())
        except:
            return [
                "I remember the atmosphere was tense that day",
                "I noticed things seemed normal at first",
                "I felt something was off but couldn't place it"
            ]
    
    async def _create_suspect_relationships(self, suspect_dir: Path, suspect: Dict):
        relationships = {}
        
        for rel in self.case.get('relationships', []):
            if suspect['name'] in [rel.get('person_a'), rel.get('person_b'), rel.get('from'), rel.get('to')]:
                # Support both 'person_a/b' and 'from/to' field names
                person_a = rel.get('person_a') or rel.get('from', '')
                person_b = rel.get('person_b') or rel.get('to', '')
                other_person = person_b if person_a == suspect['name'] else person_a
                
                if rel.get('person_a') or rel.get('from', '') == suspect['name']:
                    what_i_know = rel.get('what_a_knows_about_b', '')
                else:
                    what_i_know = rel.get('what_b_knows_about_a', '')
                
                relationships[other_person] = {
                    "relationship_type": rel['relationship_type'],
                    "how_close_we_are": rel.get('strength', rel.get('dynamics', 'unknown')),
                    "is_this_public_knowledge": rel.get('public_knowledge', True),
                    "how_i_would_describe_our_relationship": rel.get('description', rel.get('relationship', '')),
                    "what_i_know_about_them": what_i_know,
                    "our_recent_interaction": rel.get('recent_interaction', ''),
                    "the_tension_between_us": rel.get('emotional_tension', rel.get('dynamics', '')),
                    "how_i_feel_about_them": self._generate_first_person_feeling(suspect, other_person, rel),
                    "how_much_i_trust_them": self._calculate_trust_level(rel)
                }
        
        with open(suspect_dir / 'relationships.json', 'w', encoding='utf-8') as f:
            json.dump(relationships, f, indent=2, ensure_ascii=False)
    
    def _create_suspect_conversation_state(self, suspect_dir: Path, suspect: Dict):
        state = {
            "questions_asked_count": 0,
            "questions_history": [],
            "information_revealed": [],
            "lies_told": [],
            "emotional_reactions": [],
            "topics_discussed": [],
            "willingness_to_talk": {
                "about_alibi": "willing" if suspect['alibi_verified'] else "defensive",
                "about_secret": "very_reluctant",
                "about_relationships": "cautious",
                "about_motive": "evasive" if suspect.get('motive') else "open",
                "about_crime": "concerned" if not suspect.get('alibi_verified') else "cooperative"
            },
            "stress_level": 0,
            "consistency_check": {
                "alibi_told_consistently": True,
                "story_changed": False,
                "contradictions": []
            }
        }
        
        with open(suspect_dir / 'conversation_state.json', 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    
    # ═══════════════════════════════════════════════════════════════
    # TASK AGENT
    # ═══════════════════════════════════════════════════════════════
    
    async def _generate_task_agent(self):
        print(f"\n🤖 Generating task agent memory...")
        
        task_dir = self.agents_dir / "task_agent"
        task_dir.mkdir(exist_ok=True)
        
        task_identity = {
            "agent_type": "task_executor",
            "role": "Execute user commands and coordinate investigation",
            "capabilities": [
                "Check CCTV footage",
                "Review digital logs",
                "Examine physical evidence",
                "Interview non-suspect witnesses",
                "Check security records",
                "Analyze timeline",
                "Find contradictions",
                "Route suspect interviews to GraphRAG"
            ],
            "personality": "Efficient, analytical, helpful detective assistant",
            "response_style": "Clear, factual, evidence-based",
            "limitations": [
                "Cannot interview suspects directly (routes to GraphRAG)",
                "Only handles physical investigation and non-suspect witnesses",
                "Reports findings objectively without speculation"
            ]
        }
        
        with open(task_dir / 'identity.json', 'w', encoding='utf-8') as f:
            json.dump(task_identity, f, indent=2, ensure_ascii=False)
        
        crime_safe = {
            "type": self.case['crime'].get('type', ''),
            "what_happened": self.case['crime'].get('what_happened', ''),
        }
        victim_safe = {
            "name": self.case['victim'].get('name', ''),
            "age": self.case['victim'].get('age', ''),
            "role": self.case['victim'].get('role', ''),
            "public_image": self.case['victim'].get('public_image', ''),
        }
        task_knowledge = {
            "case_title": self.case['title'],
            "case_difficulty": self.case.get('difficulty', 'medium'),
            "setting": self.case['setting'],
            "crime": crime_safe,
            "victim": victim_safe,
            "time_window": self.case.get('time_window', '') or (self.case['timeline'][0]['time'] + ' - ' + self.case['timeline'][-1]['time'] if self.case.get('timeline') else 'Unknown'),
            "all_suspects": [
                {
                    "name": s['name'],
                    "role": s['role'],
                    "age": s['age'],
                    "alibi_verified": s['alibi_verified']
                } for s in self.case['suspects']
            ],
            "timeline": self.case.get('timeline', []),
            "available_actions": [
                "check_cctv [location]",
                "review_logs [system/type]",
                "check_phone_records [person]",
                "examine_forensics [item]",
                "inspect_item [item_id]"
            ]
        }
        
        with open(task_dir / 'knowledge.json', 'w', encoding='utf-8') as f:
            json.dump(task_knowledge, f, indent=2, ensure_ascii=False)
        
        investigation_state = {
            "investigation_started_at": None,
            "sources_investigated": [],
            "evidence_examined": [],
            "witnesses_interviewed": [],
            "contradictions_found": [],
            "current_focus": "initial_investigation",
            "progress_percentage": 0
        }
        
        with open(task_dir / 'investigation_state.json', 'w', encoding='utf-8') as f:
            json.dump(investigation_state, f, indent=2, ensure_ascii=False)
        
        print(f"  ✅ Task agent complete")
    
    # ═══════════════════════════════════════════════════════════════
    # INVESTIGATABLE SOURCES — THE ONLY THING THAT CHANGED
    # ═══════════════════════════════════════════════════════════════
    
    async def _generate_investigatable_sources(self):
        print(f"\n🔍 Generating investigatable sources for task agent...")
        
        investigatable_sources = []
        source_id_counter = 1
        
        # ── 1. EVIDENCE ──
        for evidence in self.case.get('evidence', []):
            keywords = []
            if evidence.get('location_found'): keywords.append(evidence['location_found'].lower())
            if evidence.get('location'): keywords.append(evidence['location'].lower())
            if evidence.get('type'): keywords.append(evidence['type'].lower())
            if evidence.get('evidence_id'): keywords.append(evidence['evidence_id'].lower())
            
            desc = evidence.get('description', '').lower()
            important_words = ["audio", "log", "file", "phone", "blood", "fingerprint", "weapon",
                               "knife", "gun", "poison", "toxin", "adrenaline", "report", "cardiac"]
            for word in important_words:
                if word in desc:
                    keywords.append(word)

            # ── CLEAN FINDINGS for evidence ──
            evidence_findings = (
                f"Forensic report on: {evidence.get('description', 'unknown item')}. "
                f"Found at: {evidence.get('location_found', evidence.get('location', 'unknown'))}. "
                f"Significance: {evidence.get('significance', 'Under analysis')}."
            )

            investigatable_sources.append({
                "id": f"evidence_{source_id_counter}",
                "source_type": "evidence",
                "evidence_type": evidence['type'],
                "query_keywords": [k for k in keywords if k and k != "evidence"],
                "description": evidence['description'],
                "location": evidence.get('location_found', evidence.get('location', 'unknown')),
                "discovered_through": evidence.get('task_agent_method', evidence.get('discovered_through', 'investigation')),
                "significance": evidence.get('significance', ''),
                "misleading": evidence.get('misleading', False),
                "mentioned_by": evidence.get('mentioned_by', []),
                "investigated": False,
                "findings": evidence_findings
            })
            source_id_counter += 1

        # ── 2. ALIBI SOURCES ──
        for suspect in self.case['suspects']:
            suspect_name = suspect['name']
            alibi_sources = suspect.get('alibi_sources', [])
            is_verified = suspect.get('alibi_verified', True)
            
            for source_desc in alibi_sources:
                source_lower = source_desc.lower()
                
                # Classify source type
                if any(w in source_lower for w in ['cctv', 'camera', 'footage', 'video']):
                    source_type = 'cctv_footage'
                elif any(w in source_lower for w in ['log', 'digital', 'timestamp', 'computer', 'phone', 'login', 'data']):
                    source_type = 'digital_log'
                elif any(w in source_lower for w in ['witness', 'saw', 'recalls', 'remember', 'volunteer', 'worker', 'shopkeeper', 'vendor']):
                    source_type = 'witness_testimony'
                elif any(w in source_lower for w in ['guard', 'security', 'patrol']):
                    source_type = 'security_record'
                elif any(w in source_lower for w in ['boot', 'print', 'physical', 'trace']):
                    source_type = 'physical_trace'
                else:
                    source_type = 'other_verification'
                
                # Extract location keywords
                location_words = [
                    "barn", "house", "office", "lab", "gurudwara", "temple", "church",
                    "parking", "gate", "entrance", "hallway", "corridor", "kitchen",
                    "washroom", "bathroom", "garden", "field", "warehouse", "store",
                    "road", "highway", "toll", "station", "market", "shop", "clinic",
                    "hospital", "school", "college", "farm", "compound", "lobby",
                    "rooftop", "terrace", "balcony", "courtyard", "ghat", "river",
                    "ashram", "temple", "shrine", "pier", "dock", "bridge"
                ]
                location_keywords = [w for w in location_words if w in source_lower]
                
                # Build keywords
                keywords = [
                    source_type.replace('_', ' ').split()[-1],
                    suspect_name.lower().split()[0],
                    suspect_name.lower()
                ]
                keywords.extend(location_keywords)
                
                # Also pull location words from alibi text
                alibi_text = suspect.get('alibi', '').lower()
                for word in location_words:
                    if word in alibi_text and word not in keywords:
                        keywords.append(word)

                # Extract nouns from description
                desc_words = source_lower.replace(',', ' ').replace('.', ' ').split()
                important_nouns = ["gps", "phone", "email", "truck", "car", "driver", "assistant",
                                   "priest", "neighbor", "receipt", "bill", "ticket", "record",
                                   "harvester", "container", "sample", "login", "data", "souvenir",
                                   "shopkeeper", "vendor", "boatman", "priest", "devotee"]
                for noun in important_nouns:
                    if noun in desc_words:
                        keywords.append(noun)

                # ── CLEAN FINDINGS — the actual fix ──
                timeline = self.case.get('timeline', [])
                if timeline:
                    crime_time = timeline[-1].get('time', 'unknown')
                    if is_verified:
                        check_time = timeline[0].get('time', crime_time) if len(timeline) > 1 else crime_time
                        findings_text = (
                            f"Checked {source_desc} for {suspect_name}. "
                            f"Timestamp: {check_time}."
                        )
                    else:
                        mid_idx = len(timeline) // 2
                        suspicious_time = timeline[mid_idx].get('time', crime_time)
                        findings_text = (
                            f"Checked {source_desc} for {suspect_name}. "
                            f"Timestamp: {suspicious_time}."
                        )
                else:
                    findings_text = f"Checked {source_desc} for {suspect_name}."

                investigatable_sources.append({
                    "id": f"alibi_source_{source_id_counter}",
                    "source_type": source_type,
                    "query_keywords": [k for k in keywords if k],
                    "related_to_suspect": suspect_name,
                    "alibi_verified": is_verified,
                    "description": f"{source_desc} for {suspect_name}",
                    "investigated": False,
                    "findings": findings_text
                })
                source_id_counter += 1

        # ── 3. NON-SUSPECT WITNESSES FROM TIMELINE ──
        suspect_names = [s['name'] for s in self.case['suspects']]
        
        for event in self.case.get('timeline', []):
            witnessed_by = event.get('witnessed_by', [])
            
            for witness in witnessed_by:
                if witness in suspect_names:
                    continue
                if not isinstance(witness, str):
                    continue
                if witness.lower() in ['all', 'circumstantial', 'evidence', 'digital log', 'none', 'cctv timestamp', 'boot prints']:
                    continue
                if any(name.lower() in witness.lower() for name in suspect_names):
                    continue
                
                investigatable_sources.append({
                    "id": f"witness_{source_id_counter}",
                    "source_type": "witness_testimony",
                    "query_keywords": ["witness", witness.lower(), "testimony", "interview"],
                    "witness_name": witness,
                    "witnessed_event": event['event'],
                    "witnessed_time": event['time'],
                    "description": f"{witness} witnessed: {event['event']} at {event['time']}",
                    "investigated": False,
                    "findings": f"Spoke with {witness}. They recall: {event['event']} at {event['time']}."
                })
                source_id_counter += 1

        # ── 4. CONVERSATION REVEALS ──
        for reveal in self.case.get('conversation_reveals', []):
            revealer = reveal.get('revealer', '')
            if revealer in suspect_names:
                continue
            
            investigatable_sources.append({
                "id": f"info_{source_id_counter}",
                "source_type": "witness_testimony",
                "witness_name": revealer,
                "about": reveal.get('about', ''),
                "information": reveal.get('information', ''),
                "trigger_question": reveal.get('trigger_question', ''),
                "importance": reveal.get('importance', 'unknown'),
                "description": f"{revealer} can reveal: {reveal.get('information', '')}",
                "investigated": False,
                "findings": f"Spoke with {revealer}. They revealed: {reveal.get('information', 'Nothing significant at this time.')}."
            })
            source_id_counter += 1
        
        # ── SAVE ──
        task_dir = self.agents_dir / "task_agent"
        
        investigatable_data = {
            "total_sources": len(investigatable_sources),
            "sources_by_type": {
                "evidence": len([s for s in investigatable_sources if s['source_type'] == 'evidence']),
                "cctv_footage": len([s for s in investigatable_sources if s['source_type'] == 'cctv_footage']),
                "digital_log": len([s for s in investigatable_sources if s['source_type'] == 'digital_log']),
                "witness_testimony": len([s for s in investigatable_sources if s['source_type'] == 'witness_testimony']),
                "security_record": len([s for s in investigatable_sources if s['source_type'] == 'security_record']),
                "physical_trace": len([s for s in investigatable_sources if s['source_type'] == 'physical_trace'])
            },
            "sources": investigatable_sources
        }
        
        with open(task_dir / 'investigatable_sources.json', 'w', encoding='utf-8') as f:
            json.dump(investigatable_data, f, indent=2, ensure_ascii=False)
        
        print(f"  ✅ {len(investigatable_sources)} investigatable sources created")
        print(f"     - Evidence: {investigatable_data['sources_by_type']['evidence']}")
        print(f"     - CCTV Footage: {investigatable_data['sources_by_type']['cctv_footage']}")
        print(f"     - Digital Logs: {investigatable_data['sources_by_type']['digital_log']}")
        print(f"     - Witnesses: {investigatable_data['sources_by_type']['witness_testimony']}")
        print(f"     - Security Records: {investigatable_data['sources_by_type']['security_record']}")
        print(f"     - Physical Traces: {investigatable_data['sources_by_type']['physical_trace']}")
    
    # ═══════════════════════════════════════════════════════════════
    # EVIDENCE LAYERS
    # ═══════════════════════════════════════════════════════════════
    
    async def _categorize_evidence_by_layers(self):
        print(f"  📊 Categorizing evidence into investigation layers...")
        
        task_dir = self.agents_dir / "task_agent"
        culprit_name = self.case['solution']['culprit']
        
        red_herring_name = None
        for s in self.case['suspects']:
            if not s['alibi_verified'] and s['name'] != culprit_name:
                red_herring_name = s['name']
                break
        
        layers = {
            "layer_1_surface": {
                "description": "Obvious evidence that seems to point to culprit",
                "evidence_ids": [],
                "reveals_to_player": "Initial investigation"
            },
            "layer_2_misdirection": {
                "description": "Evidence that creates doubt and points to red herring",
                "evidence_ids": [],
                "reveals_to_player": "After interrogating suspects"
            },
            "layer_3_breakthrough": {
                "description": "Deep evidence that exposes the truth",
                "evidence_ids": [],
                "reveals_to_player": "Requires cross-referencing multiple sources"
            }
        }
        
        for evidence in self.case.get('evidence', []):
            description = evidence.get('description', '').upper()
            
            if 'LAYER 1' in description or evidence.get('layer_1_interpretation'):
                layers['layer_1_surface']['evidence_ids'].append({
                    "type": evidence.get('type', 'Physical Evidence'),
                    "description_vague": f"Evidence found at {evidence.get('location_found', evidence.get('location', 'scene'))}",
                    "full_description": evidence.get('description', ''),
                    "points_to": culprit_name
                })
            elif 'LAYER 2' in description or evidence.get('layer_2_alternative'):
                layers['layer_2_misdirection']['evidence_ids'].append({
                    "type": evidence.get('type', 'Alibi Evidence'),
                    "description_vague": f"Information about {evidence.get('who_it_implicates', 'suspect')}",
                    "full_description": evidence.get('description', ''),
                    "misleads_to": red_herring_name or "other suspects"
                })
            elif 'LAYER 3' in description or evidence.get('layer_3_truth'):
                layers['layer_3_breakthrough']['evidence_ids'].append({
                    "type": evidence.get('type', 'Digital Trace'),
                    "description_vague": "Hidden connection found",
                    "full_description": evidence.get('description', ''),
                    "requires": "Cross-reference analysis"
                })
            else:
                layers['layer_1_surface']['evidence_ids'].append({
                    "type": evidence.get('type', 'Evidence'),
                    "description_vague": "Uncategorized evidence",
                    "full_description": evidence.get('description', ''),
                    "points_to": "Unknown"
                })
        
        for suspect in self.case['suspects']:
            if suspect['name'] == culprit_name:
                for source in suspect.get('alibi_sources', []):
                    layers['layer_3_breakthrough']['evidence_ids'].append({
                        "type": "alibi_verification",
                        "related_to": culprit_name,
                        "source": source,
                        "requires": "Check for inconsistencies in alibi"
                    })
        
        accomplice_data = self.case.get('accomplice') or self.case.get('solution', {}).get('accomplice')
        if accomplice_data:
            accomplice = accomplice_data if isinstance(accomplice_data, dict) else {'name': accomplice_data}
            layers['layer_3_breakthrough']['evidence_ids'].append({
                "type": "accomplice_evidence",
                "accomplice_name": accomplice.get('name', 'Unknown'),
                "evidence_type": accomplice.get('evidence_of_involvement', 'Financial/digital records'),
                "requires": "Deep investigation into financial/digital records"
            })
        
        with open(task_dir / 'evidence_layers.json', 'w', encoding='utf-8') as f:
            json.dump(layers, f, indent=2, ensure_ascii=False)
        
        print(f"     - Layer 1 (Surface): {len(layers['layer_1_surface']['evidence_ids'])} items")
        print(f"     - Layer 2 (Misdirection): {len(layers['layer_2_misdirection']['evidence_ids'])} items")
        print(f"     - Layer 3 (Breakthrough): {len(layers['layer_3_breakthrough']['evidence_ids'])} items")

    # ═══════════════════════════════════════════════════════════════
    # HINT SYSTEM
    # ═══════════════════════════════════════════════════════════════

    async def _generate_hint_system(self):
        print(f"  💡 Generating hint system...")
        
        task_dir = self.agents_dir / "task_agent"
        culprit_name = self.case['solution']['culprit']
        
        hints = {
            "hint_triggers": {
                "stuck_at_start": {
                    "after_rounds": 3,
                    "condition": "player_hasnt_investigated_evidence",
                    "hint": "You should start by examining the physical evidence collected from the scene.",
                    "suggests": ["Examine evidence", "List available evidence"]
                },
                "stuck_with_obvious_suspect": {
                    "after_rounds": 5,
                    "condition": "player_suspects_culprit_but_hasnt_checked_alibi",
                    "hint": "Have you verified the suspects' alibis? CCTV footage, witness statements, and security logs might be available.",
                    "suggests": ["Check CCTV footage", "Review alibis", "Interview witnesses"]
                },
                "fooled_by_alibi": {
                    "after_rounds": 8,
                    "condition": "player_ruled_out_culprit",
                    "hint": f"{culprit_name}'s alibi seems solid, but evidence can be fabricated. Can you verify its authenticity?",
                    "suggests": ["Check CCTV metadata", "Cross-reference with weather data", "Verify timestamps"]
                },
                "found_flaw_need_accomplice": {
                    "after_rounds": 11,
                    "condition": "player_found_alibi_flaw",
                    "hint": f"You've found a flaw in {culprit_name}'s alibi. Someone must have helped them fake it.",
                    "suggests": ["Review financial records", "Check who had access to security systems"]
                },
                "almost_solved": {
                    "after_rounds": 13,
                    "condition": "player_has_most_evidence",
                    "hint": "You have most of the pieces. Who had motive, means, and opportunity?",
                    "suggests": ["Review all findings", "Connect the dots", "Identify accomplice"]
                }
            },
            "progressive_unlocks": {
                "after_viewing_evidence": ["Technical analysis", "Cross-reference tool"],
                "after_viewing_cctv": ["Metadata analysis", "Weather cross-reference", "Timestamp verification"],
                "after_finding_contradiction": ["Deep investigation mode", "Financial records access"],
                "after_suspecting_someone": ["Subject-specific financial records", "Subject-specific communications"]
            }
        }
        
        with open(task_dir / 'hint_system.json', 'w', encoding='utf-8') as f:
            json.dump(hints, f, indent=2, ensure_ascii=False)
        
        print(f"     ✅ Hint system created")
    
    # ═══════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════
    
    def _extract_access_info(self, suspect: Dict) -> List[str]:
        role = suspect['role'].lower()
        
        if any(w in role for w in ['curator', 'director', 'manager', 'head']):
            return ["Full building access", "Security system knowledge", "Keys to restricted areas"]
        elif any(w in role for w in ['security', 'guard']):
            return ["Security office", "CCTV systems", "Patrol routes", "Emergency protocols"]
        elif any(w in role for w in ['professor', 'teacher', 'priest', 'pandit']):
            return ["Office", "Classrooms", "Faculty areas", "Some archives"]
        elif any(w in role for w in ['student', 'intern', 'assistant', 'helper']):
            return ["Common areas", "Assigned workspace", "Public sections"]
        elif any(w in role for w in ['tech', 'it', 'architect', 'engineer']):
            return ["Technical areas", "Computer systems", "Building plans"]
        else:
            return ["Standard access for my role"]
    
    def _extract_moral_justification(self, suspect: Dict) -> str:
        motive = suspect.get('motive', '').lower()
        if any(w in motive for w in ['family', 'honor', 'child', 'daughter', 'son']):
            return "I did this for my family — they would understand"
        elif any(w in motive for w in ['justice', 'wrong', 'betrayal', 'stolen']):
            return "This was about righting a historical wrong"
        elif 'protect' in motive:
            return "I was protecting someone I care about deeply"
        else:
            return "I had no choice given the circumstances"
    
    def _generate_beliefs_about_others(self, suspect: Dict) -> Dict:
        beliefs = {}
        for other in self.case['suspects']:
            if other['name'] != suspect['name']:
                if not other['alibi_verified']:
                    beliefs[other['name']] = "Their alibi seems weak — they could be suspicious"
                else:
                    beliefs[other['name']] = "They have a solid alibi — probably innocent"
        return beliefs
    
    def _generate_theories(self, suspect: Dict) -> List[str]:
        return [
            "Whoever did this must have had inside knowledge",
            "The timing was too perfect to be random",
            "Someone with access to the area could have done it",
            "There might be more to this than it appears"
        ]
    
    def _generate_first_person_perspective(self, suspect: Dict, event: Dict) -> str:
        return f"I remember being there when {event['event']} at {event['time']}"
    
    def _generate_innocent_explanation(self, suspect: Dict) -> str:
        behavior = suspect.get('suspicious_behavior', '')
        if behavior and behavior.lower() not in ['none', 'minimal', '']:
            return f"I understand why my behavior ({behavior}) might look suspicious, but there's an innocent explanation"
        return "I have nothing to hide and I'm happy to explain anything"
    
    def _generate_first_person_feeling(self, suspect: Dict, other_person: str, rel: Dict) -> str:
        rel_type = rel.get('relationship_type', 'professional')
        strength = rel.get('strength', rel.get('dynamics', 'neutral'))
        
        feelings_map = {
            'family': f"They're my family — our bond is {strength}",
            'romance': f"I have feelings for them — our relationship is {strength}",
            'deep_friendship': f"We're close friends — I trust them",
            'mentorship': f"We have a mentor/student dynamic",
            'betrayal': f"They betrayed my trust — I feel deeply hurt",
            'rivalry': f"We're rivals — there's real tension between us",
            'professional': f"We have a professional relationship"
        }
        
        return feelings_map.get(rel_type, f"We have a {rel_type} relationship")
    
    def _calculate_trust_level(self, rel: Dict) -> str:
        rel_type = rel.get('relationship_type', '')
        strength = rel.get('strength', rel.get('dynamics', ''))
        
        if rel_type in ['family', 'deep_friendship'] and 'close' in str(strength):
            return "very_high"
        elif rel_type == 'romance' and 'close' in str(strength):
            return "extremely_high"
        elif rel_type == 'betrayal':
            return "broken"
        elif 'strained' in str(strength):
            return "low"
        elif 'complicated' in str(strength):
            return "uncertain"
        else:
            return "moderate"

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

async def main():
    if len(sys.argv) < 2:
        print("❌ Usage: python graphrag_agent.py <case_file.json>")
        sys.exit(1)
    
    case_file = sys.argv[1]
    
    if not Path(case_file).exists():
        print(f"❌ Case file not found: {case_file}")
        sys.exit(1)
    
    try:
        print(f"📂 Loading case: {case_file}")
        with open(case_file, 'r', encoding='utf-8') as f:
            case_data = json.load(f)
        
        graphrag = GraphRAGAgent(case_data)
        result = await graphrag.generate_all_agents()
        
        if result['success']:
            print(f"\n{'='*70}")
            print(f"✅ SUCCESS!")
            print(f"📁 Agents directory: {result['agents_directory']}")
            print(f"👥 Suspect agents: {result['suspects_count']}")
            print(f"🤖 Task agent: Created")
            print(f"📋 Detective briefing: Created")
            print(f"🔍 Investigatable sources: Created")
            print(f"{'='*70}\n")
        
    except Exception as e:
        print(f"\n💥 Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())