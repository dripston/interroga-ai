#!/usr/bin/env python3
"""
Mystery Case Generator v2 - INTERESTING Edition
Generates logically consistent AND emotionally compelling mysteries
"""

import httpx
import random
import asyncio
import json
import sys
import os
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

load_dotenv()

# OpenRouter API Configuration
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "meta-llama/llama-3.3-70b-instruct:free"

CACHE_DIR = Path("./embedding_cache")
CACHE_DIR.mkdir(exist_ok=True)

print("📂 Loading RAG index...")
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    cache_folder=str(CACHE_DIR),
    model_kwargs={'device': 'cpu'}
)
vectorstore = FAISS.load_local(
    "mystery_rag_index",
    embeddings,
    allow_dangerous_deserialization=True
)
print("✅ RAG index loaded!")

MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "google/gemma-4-31b-it:free"
]

async def call_openrouter(prompt):
    """Call OpenRouter API with fallback models to handle 429 rate limits"""
    from dotenv import load_dotenv
    import os
    load_dotenv(override=True)
    api_key = os.getenv("OPENROUTER_API_KEY", "")

    for model_name in MODELS:
        print(f"🎲 Attempting case generation with model: {model_name}...")
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    OPENROUTER_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_name,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a structured JSON generator. Output ONLY valid JSON. No markdown. No code fences. No thinking. No explanation. No <think> blocks. Just the raw JSON object."
                            },
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.8,
                        "max_tokens": 6000
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    if 'choices' in result and len(result['choices']) > 0:
                        content = result['choices'][0]['message']['content']
                        if content.strip():
                            # Set global MODEL to this successful one so it's logged in metadata
                            global MODEL
                            MODEL = model_name
                            return content
                    print(f"⚠️ OpenRouter ({model_name}): Invalid/Empty response format")
                else:
                    print(f"⚠️ OpenRouter ({model_name}): HTTP {response.status_code} - {response.text[:200]}")

        except Exception as e:
            print(f"⚠️ OpenRouter ({model_name}) request error: {str(e)}")
        
        print("🔄 Trying next fallback model...")
    
    return ""

def clean_json_response(text):
    import re
    text = text.strip().replace("```json", "").replace("```", "")
    # Remove <think>...</think> blocks (just in case model ignores instruction)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    if '<think>' in text:
        text = text[:text.find('<think>')]
    text = text.strip()
    start, end = text.find('{'), text.rfind('}')
    if start == -1 or end == -1:
        raise ValueError("No valid JSON found")
    json_text = text[start:end+1]

    # Step 1: Remove trailing commas before } or ]
    json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)

    # Step 2: Try parsing as-is first
    try:
        json.loads(json_text)
        return json_text
    except json.JSONDecodeError:
        pass

    # Step 3: Fix unbalanced brackets/braces
    open_braces = json_text.count('{') - json_text.count('}')
    open_brackets = json_text.count('[') - json_text.count(']')

    if open_braces > 0 or open_brackets > 0:
        json_text = json_text.rstrip().rstrip(',')
        stack = []
        for ch in json_text:
            if ch in ('{', '['):
                stack.append('}' if ch == '{' else ']')
            elif ch in ('}', ']'):
                if stack and stack[-1] == ch:
                    stack.pop()
        json_text += ''.join(reversed(stack))

    # Step 4: Remove trailing commas again
    json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)

    # Step 5: Remove control characters except \n \r \t
    json_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', json_text)

    # Step 6: Try one more time
    try:
        json.loads(json_text)
        return json_text
    except json.JSONDecodeError:
        pass

    # Step 7: Nuclear option — patch around error position
    try:
        json.loads(json_text)
    except json.JSONDecodeError as e:
        pos = e.pos if hasattr(e, 'pos') else None
        if pos and 'Expecting' in str(e):
            for fix in [',', '}', '],', '},']:
                patched = json_text[:pos] + fix + json_text[pos:]
                patched = re.sub(r',(\s*[}\]])', r'\1', patched)
                try:
                    json.loads(patched)
                    print(f"  🔧 Auto-repaired JSON at position {pos}")
                    return patched
                except json.JSONDecodeError:
                    continue

    return json_text

def auto_fix_alibis(case):
    culprit = case.get('solution', {}).get('culprit')
    if culprit:
        for s in case.get('suspects', []):
            if s['name'] == culprit and s.get('alibi_verified'):
                print(f"⚠️  Auto-fixing: {culprit} alibi→false")
                s['alibi_verified'] = False
    return case

# ═══════════════════════════════════════════════════════════════
# BROAD DOMAIN POOLS — model inventss all specifics
# ═══════════════════════════════════════════════════════════════

WORLD_DOMAINS = [
    "entertainment and media (film, TV, music, influencers)",
    "academia and research (universities, labs, publishing)",
    "religion and spirituality (ashrams, temples, cults, pilgrimages)",
    "politics and governance (local elections, bureaucracy, dynasties)",
    "technology and startups (funding, IP theft, pivots)",
    "traditional crafts and heritage (artisans, auctions, preservation)",
    "agriculture and rural life (land rights, cooperatives, harvests)",
    "medicine and healthcare (hospitals, pharma, alternative medicine)",
    "finance and investment (VC, stock fraud, family wealth)",
    "sports and competition (cricket, kabaddi, athletics, coaching)",
    "journalism and activism (whistleblowers, media houses, NGOs)",
    "hospitality and luxury tourism (resorts, heritage hotels, cruises)",
    "military and paramilitary (retired officers, border towns, cantonment)",
    "legal and judiciary (courts, law firms, criminal networks)",
    "fashion and design (luxury brands, knockoffs, runway culture)",
]

CRIME_DOMAINS = [
    "poisoning — invent your own substance, delivery method, and disguise",
    "tech-enabled sabotage — invent your own device, software exploit, or digital manipulation",
    "staged accident — invent your own type, location, and cover mechanism",
    "theft escalating to murder — invent what was stolen and how the cover-up unraveled",
    "blackmail turned lethal — invent the secret, the leverage, and how it went too far",
    "identity fraud with fatal consequences — invent how the identity was used and what it cost",
    "smuggling with witness elimination — invent what was moved and how loose ends were tied",
    "slow invisible harm — invent a method that looked natural for weeks before detection",
]

MOTIVE_DOMAINS = [
    "stolen credit or intellectual property — invent the specific betrayal",
    "suppressed identity or secret past — invent what they were hiding and why",
    "family betrayal across generations — invent the wound and the reckoning",
    "revenge for a covered-up crime — invent what was buried and who buried it",
    "protection of someone else at any cost — invent who and what the threat was",
    "ideological obsession — invent the belief system and its fatal logic",
    "desperate preservation of power or status — invent what was at stake and who threatened it",
    "forbidden love with catastrophic fallout — invent the relationship and the impossible choice",
]

VICTIM_NAMES_POOL = [
    "Suresh", "Devika", "Nalini", "Cyrus", "Harish", "Lakshmi",
    "Farhan", "Zoya", "Vikram", "Padma", "Kabir", "Meera",
    "Arjun", "Priya", "Rajan", "Ananya", "Siddharth", "Noor",
    "Tara", "Aditya", "Rekha", "Sameer", "Kavya", "Deepak",
]

async def generate_case(difficulty="medium"):
    query = f"{difficulty} difficulty mystery Indian setting"
    similar_cases = vectorstore.similarity_search(query, k=2)
    examples = "\n---\n".join([f"EXAMPLE {i+1}:\n{d.page_content[:800]}" for i, d in enumerate(similar_cases)])

    # Pick broad domains — model invents all specifics
    forced_world = random.choice(WORLD_DOMAINS)
    forced_crime = random.choice(CRIME_DOMAINS)
    forced_motive = random.choice(MOTIVE_DOMAINS)
    forced_victim_name = random.choice(VICTIM_NAMES_POOL)

    print(f"  🎲 Domain: {forced_world[:40]}... | Crime: {forced_crime[:35]}...")

    prompt = f"""You are a master mystery writer. Generate an ORIGINAL detective case set in India as valid JSON. {difficulty} difficulty.

MANDATORY SEEDS — use these as creative direction, invent ALL specifics yourself:
- World/Domain: {forced_world}
- Crime category: {forced_crime}
- Motive theme: {forced_motive}
- Victim first name must be: {forced_victim_name}

STYLE REFERENCES (for tone only, do NOT copy plots):
{examples}

RULES:
- Setting: Pick ANY specific Indian location that fits the world domain. Be creative and specific.
- Victim: morally gray (public saint, private sinner). Their dark side must be relevant to the motive.
- 5 suspects: CULPRIT (likeable, fake/unverified alibi, deep personal motive), ACCOMPLICE (helped unknowingly or partially), RED HERRING (looks guilty but innocent, unverified alibi), WITNESS (has key clue but hiding something), OUTSIDER (provides outside perspective)
- CHARACTER TYPE: Each suspect MUST have "character_type" — exactly one of "young-male", "young-female", "old-male", "old-female". Age < 40 = young. Ensure a MIX across 5 suspects.
- NEVER use "None", "Unknown", or generic placeholders anywhere.
- Alibi sources: specific investigative leads only — named witnesses, specific CCTV IDs, digital log types, physical traces. Do NOT say "alibi is fake" — describe the raw observation only.
- For unverified alibis (culprit/red herring): source must be partial, tampered, or have a gap.
- 4 evidence items — mix physical, digital, forensic, testimonial. No smoking guns that directly name the culprit.
- Timeline: 6-8 events with specific times showing the crime window, each with witnessed_by field.
- 7 interrogation rounds building to a final twist.
- At least 3 relationships: mix family, romance, professional, rivalry.

OUTPUT THIS EXACT JSON STRUCTURE:
{{
"title": "Creative Case Title",
"difficulty": "{difficulty}",
"scenario": {{
    "crime_type": "specific invented method",
    "setting": "specific Indian location",
    "cultural_context": "social issue woven in",
    "why_unique": "what makes this case special"
}},
"setting": {{
    "location": "detailed location description",
    "atmosphere": "rich sensory details"
}},
"crime": {{
    "type": "category",
    "what_happened": "what appeared to happen",
    "hidden_truth": "what actually happened"
}},
"victim": {{
    "name": "Full Indian Name", "age": 45, "role": "position",
    "public_image": "how world sees them",
    "private_reality": "hidden dark side",
    "connection_to_culprit": "how connected"
}},
"suspects": [
    {{
    "type": "THE CULPRIT",
    "name": "Full Name", "age": 35, "role": "job",
    "character_type": "young-male|young-female|old-male|old-female",
    "personality": ["trait1", "trait2", "trait3"],
    "motive": "deep personal motive",
    "alibi": "detailed but ultimately unverified/fake", "alibi_verified": false,
    "alibi_sources": ["Specific partial/tampered source e.g. 'North corridor CCTV with 4-minute gap'"],
    "secret": "what they hide", "suspicious_behavior": "what looks guilty",
    "emotional_state": "state", "knowledge_level": "what they know",
    "backstory": "2-3 sentence background",
    "voice_cues": "how they speak under pressure"
    }},
    {{"type": "THE ACCOMPLICE", "name": "...", "age": 0, "role": "...", "character_type": "...", "personality": ["..."], "motive": "...", "alibi": "...", "alibi_verified": true, "alibi_sources": ["..."], "secret": "...", "suspicious_behavior": "...", "emotional_state": "...", "knowledge_level": "...", "backstory": "...", "voice_cues": "..."}},
    {{"type": "THE RED HERRING", "name": "...", "age": 0, "role": "...", "character_type": "...", "personality": ["..."], "motive": "...", "alibi": "...", "alibi_verified": false, "alibi_sources": ["..."], "secret": "...", "suspicious_behavior": "...", "emotional_state": "...", "knowledge_level": "...", "backstory": "...", "voice_cues": "..."}},
    {{"type": "THE WITNESS", "name": "...", "age": 0, "role": "...", "character_type": "...", "personality": ["..."], "motive": "...", "alibi": "...", "alibi_verified": true, "alibi_sources": ["..."], "secret": "...", "suspicious_behavior": "...", "emotional_state": "...", "knowledge_level": "...", "backstory": "...", "voice_cues": "..."}},
    {{"type": "THE OUTSIDER", "name": "...", "age": 0, "role": "...", "character_type": "...", "personality": ["..."], "motive": "...", "alibi": "...", "alibi_verified": true, "alibi_sources": ["..."], "secret": "...", "suspicious_behavior": "...", "emotional_state": "...", "knowledge_level": "...", "backstory": "...", "voice_cues": "..."}}
],
"relationships": [
    {{"from": "Name", "to": "Name", "relationship": "desc", "relationship_type": "family|romance|professional|rivalry|mentorship", "dynamics": "how they interact"}}
],
"evidence": [
    {{"id": "EV001", "type": "Physical|Digital|Forensic|Testimonial", "description": "what found", "location_found": "where", "significance": "what it suggests (not proves)", "task_agent_method": "how investigator discovers it"}}
],
"timeline": [
    {{"time": "6:00 PM", "event": "what happened", "witnessed_by": ["Name or role"]}}
],
"interrogation_path": {{
    "round_1": {{"suspect": "Name", "focus": "topic", "key_question": "...", "revelation": "..."}},
    "round_2": {{"suspect": "Name", "focus": "topic", "key_question": "...", "revelation": "..."}},
    "round_3": {{"suspect": "Name", "focus": "topic", "key_question": "...", "revelation": "..."}},
    "round_4": {{"suspect": "Name", "focus": "topic", "key_question": "...", "revelation": "..."}},
    "round_5": {{"suspect": "Name", "focus": "topic", "key_question": "...", "revelation": "..."}},
    "round_6": {{"suspect": "Name", "focus": "topic", "key_question": "...", "revelation": "..."}},
    "round_7": {{"suspect": "Name", "focus": "topic", "key_question": "...", "revelation": "FINAL TWIST"}}
}},
"solution": {{
    "culprit": "Exact suspect name",
    "accomplice": "Name or null",
    "motive": "the real motive",
    "method": "how they did it",
    "evidence": ["EV001", "EV002"]
}},
"moral_ending": {{
    "dilemma": "why arrest is hard",
    "arrest_consequences": "what happens if arrested",
    "release_consequences": "what happens if let go"
}}
}}

RESPOND WITH ONLY THE JSON. NO EXPLANATION. NO THINKING."""

    print(f"🎲 Generating {difficulty} case...")
    for attempt in range(3):
        try:
            response = await call_openrouter(prompt)
            debug_file = f"debug_v2_{difficulty}_{datetime.now().strftime('%H%M%S')}.txt"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response)
            print(f"  📝 Debug: {debug_file}")

            clean = clean_json_response(response)
            parsed = json.loads(clean)
            parsed = auto_fix_alibis(parsed)

            if all(k in parsed for k in ['title', 'suspects', 'evidence', 'solution']):
                print(f"  ✅ Valid JSON (attempt {attempt+1})")

                issues = []
                warnings = []

                unverified = sum(1 for s in parsed['suspects'] if not s.get('alibi_verified', True))
                if unverified < 2:
                    issues.append(f"Only {unverified} unverified alibis")

                SMOKING_GUNS = [
                    'uv trace', 'dna match', 'fingerprint match', 'employee id',
                    'dark web search', 'deleted search', 'browser history',
                    'confession', 'admits to', 'cctv shows culprit',
                    'caught on camera', 'recorded on', 'gps tracking',
                ]
                for e in parsed.get('evidence', []):
                    desc = e.get('description', '').lower()
                    if any(t in desc for t in SMOKING_GUNS):
                        issues.append(f"Smoking gun: {desc[:50]}...")
                        break

                culprit_name = parsed.get('solution', {}).get('culprit')
                culprit = next((s for s in parsed['suspects'] if s['name'] == culprit_name), None)
                if culprit:
                    personality = ' '.join(culprit.get('personality', [])).lower()
                    motive = culprit.get('motive', '').lower()

                    boring_traits = ['socially awkward', 'quiet', 'nervous', 'loner', 'introverted']
                    if any(trait in personality for trait in boring_traits):
                        warnings.append("Culprit has stereotypical 'quiet/awkward' personality")

                    boring_motives = ['medical bill', 'debt', 'financial', 'money', 'pay off', 'collector offered']
                    if any(motive_word in motive for motive_word in boring_motives):
                        warnings.append("Motive is generic financial desperation")

                personal_rels = [r for r in parsed.get('relationships', [])
                            if r.get('relationship_type') in ['family', 'romance', 'deep_friendship', 'mentorship']]
                if len(personal_rels) == 0:
                    warnings.append("No personal relationships (only professional)")

                has_backstory = any('backstory' in s for s in parsed['suspects'])
                if not has_backstory:
                    warnings.append("Suspects missing backstory field")

                VALID_TYPES = {'young-male', 'young-female', 'old-male', 'old-female'}
                for s in parsed['suspects']:
                    ct = s.get('character_type', '')
                    if ct not in VALID_TYPES:
                        age = s.get('age', 30)
                        age_prefix = 'young' if age < 40 else 'old'
                        name = s.get('name', '').split()[0].lower()
                        female_endings = ('a', 'i', 'ya', 'ni', 'ti', 'ka', 'na', 'ri', 'vi', 'hi')
                        gender = 'female' if name.endswith(female_endings) else 'male'
                        s['character_type'] = f"{age_prefix}-{gender}"
                        warnings.append(f"Auto-fixed character_type for {s['name']}: {s['character_type']}")

                if issues:
                    print(f"  ⚠️  Critical issues:")
                    for i in issues:
                        print(f"     - {i}")

                if warnings:
                    print(f"  ⚡ Storytelling warnings:")
                    for w in warnings:
                        print(f"     - {w}")

                output = {
                    "id": int(datetime.now().timestamp()),
                    "difficulty": difficulty,
                    "generated_at": datetime.now().isoformat(),
                    "model": MODEL,
                    "generator_version": "v2_interesting",
                    "case": parsed
                }

                filename = f"game_case_v2_{difficulty}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, "w", encoding='utf-8') as f:
                    json.dump(output, f, indent=2, ensure_ascii=False)

                print(f"\n✅ Case saved to: {filename}")
                return output

        except json.JSONDecodeError as e:
            print(f"  ❌ JSON error (attempt {attempt+1}): {e}")
            if attempt < 2:
                await asyncio.sleep(2)
        except Exception as e:
            print(f"  ❌ Error (attempt {attempt+1}): {e}")
            if attempt < 2:
                await asyncio.sleep(2)

    raise Exception("Failed after 3 attempts")

async def main():
    difficulty = sys.argv[1] if len(sys.argv) > 1 else "medium"
    if difficulty not in ["easy", "medium", "hard", "expert"]:
        print("❌ Use: easy, medium, hard, expert")
        return

    try:
        parsed = await generate_case(difficulty)

        print(f"\n{'='*70}")
        print(f"📊 Title: {parsed['title']}")
        setting = parsed.get('setting', {})
        setting_str = setting.get('location', str(setting)) if isinstance(setting, dict) else str(setting)
        print(f"🎭 Setting: {setting_str[:60]}...")
        print(f"🔍 Suspects: {len(parsed['suspects'])}")
        print(f"⚖️  Culprit: {parsed['solution']['culprit']}")

        culprit_name = parsed['solution']['culprit']
        culprit = next((s for s in parsed['suspects'] if s['name'] == culprit_name), None)
        if culprit:
            print(f"💭 Motive: {culprit.get('motive', 'N/A')[:60]}...")

        print(f"{'='*70}")
        print(f"\n🔍 VALIDATION:")
        print(f"{'='*70}")

        victim = parsed.get('victim', {})
        victim_name = victim.get('name', '') if isinstance(victim, dict) else str(victim)
        culprit_suspect = next((s for s in parsed['suspects'] if s['name'] == culprit_name), None)

        if culprit_suspect and culprit_suspect.get('alibi_verified'):
            print(f"❌ CRITICAL: Culprit has verified alibi!")
        else:
            print(f"✅ Culprit alibi unverified")

        if victim_name and culprit_name.lower() in victim_name.lower():
            print(f"❌ CRITICAL: Victim=Culprit!")
        else:
            print(f"✅ Victim ≠ Culprit")

        unverified = [s for s in parsed['suspects'] if not s.get('alibi_verified', True)]
        if len(unverified) >= 2:
            print(f"✅ {len(unverified)} unverified alibis")
        else:
            print(f"⚠️  Only {len(unverified)} unverified alibi")

        print(f"\n📖 STORYTELLING QUALITY:")
        print(f"{'='*70}")

        if culprit_suspect:
            personality = ' '.join(culprit_suspect.get('personality', [])).lower()
            if any(t in personality for t in ['socially awkward', 'quiet', 'nervous']):
                print(f"⚠️  Culprit has stereotypical personality")
            else:
                print(f"✅ Culprit has interesting personality")

        if culprit_suspect:
            motive = culprit_suspect.get('motive', '').lower()
            if any(m in motive for m in ['medical bill', 'debt', 'financial']):
                print(f"⚠️  Generic financial motive")
            else:
                print(f"✅ Deep personal motive")

        personal_rels = [r for r in parsed.get('relationships', [])
                    if r.get('relationship_type', '') in ['family', 'romance', 'deep_friendship', 'mentorship', 'betrayal']]
        if personal_rels:
            print(f"✅ {len(personal_rels)} personal relationship(s)")
        else:
            print(f"⚠️  No personal relationships tagged")

        has_backstory = sum(1 for s in parsed['suspects'] if s.get('backstory'))
        if has_backstory > 0:
            print(f"✅ {has_backstory} character(s) have backstory")
        else:
            print(f"⚠️  No character backstories")

        print(f"\n⚡ STRUCTURE CHECKS:")

        accomplice = parsed.get('solution', {}).get('accomplice')
        if accomplice:
            print(f"✅ Accomplice: {accomplice}")
        else:
            print(f"ℹ️  No accomplice specified")

        if 'interrogation_path' in parsed:
            print(f"✅ Interrogation path mapped")
        else:
            print(f"❌ Missing interrogation path")

        evidence_count = len(parsed.get('evidence', []))
        print(f"{'✅' if evidence_count >= 4 else '⚠️'}  {evidence_count} evidence items")

        has_twist = 'twist' in parsed.get('solution', {})
        print(f"{'✅' if has_twist else 'ℹ️ '} Plot twist {'present' if has_twist else 'not explicitly specified'}")

        print(f"{'='*70}")
        print(f"\n🎮 Case ready!")

    except Exception as e:
        print(f"\n💥 Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())