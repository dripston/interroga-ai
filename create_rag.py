import httpx
import json
import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SAMBANOVA_API_KEY = os.getenv("SAMBANOVA_API_KEY", "")
SAMBANOVA_URL = "https://api.sambanova.ai/v1/chat/completions"
MODEL = "DeepSeek-R1-0528"

OUTPUT_FILE = "playful_mysteries_100.json"

async def call_sambanova(prompt):
    """Call SambaNova API"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            SAMBANOVA_URL,
            headers={
                "Authorization": f"Bearer {SAMBANOVA_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": "You are a creative mystery writer. OUTPUT VALID JSON ONLY. You may think briefly to plan, but KEEP THINKING EXTREMELY SHORT (<200 words). Do not waste tokens on long outlines. Jump to the JSON output immediately after a brief thought."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.9,
                "max_tokens": 10000
            }
        )
        result = response.json()
        
        # Better error handling
        if 'choices' not in result:
            print(f"  ⚠️  API Response: {result}")
            raise Exception(f"API Error: {result.get('error', 'Unknown error')}")
        
        return result['choices'][0]['message']['content']

crime_scenarios = [
    # ═══════════════════════════════════════════════════════════
    # CULTURAL HERITAGE & REPATRIATION (15 scenarios)
    # ═══════════════════════════════════════════════════════════
    ("medium", "museum", "colonial-era manuscript stolen, proves family's freedom fighter legacy"),
    ("hard", "archive", "temple idol taken from British museum storage, descendant reclaiming heritage"),
    ("medium", "gallery", "Mughal miniature painting vanished, original artist's family involved"),
    ("hard", "library", "ancient Sanskrit texts missing, proves plagiarism by Western scholar"),
    ("expert", "palace", "royal crown jewels theft during heritage tour, family claim vs museum"),
    ("medium", "archaeological", "excavation artifacts disappear, tribal community reclaiming burial items"),
    ("hard", "monastery", "Buddhist scripture stolen, Chinese vs Indian ownership dispute"),
    ("medium", "fort", "historical weapons missing, Rajput family proving false British attribution"),
    ("hard", "university", "research proving caste-based land theft, documents destroyed"),
    ("expert", "auction", "stolen Nataraja statue repatriation, multiple countries claiming ownership"),
    ("medium", "temple", "donated freedom struggle medals missing, granddaughter retrieving them"),
    ("hard", "cultural", "tribal art exhibition sabotaged, appropriation vs appreciation debate"),
    ("medium", "heritage", "colonial architecture records altered, proving land grab history"),
    ("hard", "religious", "church relic stolen, Goan community vs Portuguese church dispute"),
    ("expert", "national", "independence era documents vanish, exposing political family's collaboration"),
    
    # ═══════════════════════════════════════════════════════════
    # CORPORATE CRIME & TECH SABOTAGE (15 scenarios)
    # ═══════════════════════════════════════════════════════════
    ("hard", "startup", "founder murdered during Series A pitch, IP theft + revenge"),
    ("expert", "tech", "AI model stolen, former employee proving they built it"),
    ("medium", "office", "product launch sabotaged, whistleblower exposing safety issues"),
    ("hard", "corporate", "CFO killed, uncovering Ponzi scheme affecting employees"),
    ("expert", "fintech", "blockchain code deleted, cryptocurrency fraud exposed"),
    ("medium", "agency", "ad campaign leaked to competitor, insider trading angle"),
    ("hard", "pharma", "clinical trial data manipulated, researcher exposing dangerous drug"),
    ("expert", "gaming", "unreleased game source code stolen, crunch culture revenge"),
    ("hard", "consulting", "client data breach, junior analyst framed by partner"),
    ("medium", "ecommerce", "seller ratings hacked, small business vs corporate giant"),
    ("hard", "crypto", "NFT art scam, artist proving work was stolen and minted"),
    ("expert", "cybersec", "zero-day exploit sold, ethical hacker vs black hat conflict"),
    ("medium", "saas", "customer database leaked, proving discrimination in hiring algorithm"),
    ("hard", "venture", "pitch deck stolen, female founder vs bro-culture investor"),
    ("expert", "deeptech", "quantum computing research sabotaged, international espionage"),
    
    # ═══════════════════════════════════════════════════════════
    # ACADEMIC FRAUD & RESEARCH THEFT (12 scenarios)
    # ═══════════════════════════════════════════════════════════
    ("medium", "university", "PhD thesis plagiarized, student's career destroyed by professor"),
    ("hard", "research", "lab data fabricated, junior researcher exposing senior's fraud"),
    ("expert", "medical", "clinical study results falsified, patient deaths covered up"),
    ("medium", "college", "entrance exam paper leaked, poor students vs coaching mafia"),
    ("hard", "institute", "IIT professor stealing student projects, selling to companies"),
    ("medium", "laboratory", "groundbreaking discovery stolen, woman scientist vs male colleague"),
    ("expert", "science", "Nobel-worthy research sabotaged, caste discrimination angle"),
    ("hard", "academic", "fake degrees sold to politicians, exposing education scam"),
    ("medium", "school", "board exam cheating ring, coaching center bribery"),
    ("hard", "publishing", "research journal editor manipulating peer review for bribes"),
    ("expert", "international", "student visa fraud network, dream vs deportation"),
    ("medium", "fellowship", "scholarship money embezzled by trust, underprivileged students suffer"),
    
    # ═══════════════════════════════════════════════════════════
    # FAMILY HONOR & DOMESTIC CRIME (12 scenarios)
    # ═══════════════════════════════════════════════════════════
    ("hard", "wedding", "dowry jewelry stolen, bride's brother avenging harassment"),
    ("expert", "family", "honor killing staged as accident, daughter's lover protecting her"),
    ("medium", "household", "inheritance will forged, illegitimate child claiming rights"),
    ("hard", "marriage", "domestic violence evidence destroyed, wife escaping abuse"),
    ("expert", "estate", "property papers burned, exposing grandfather's second family"),
    ("medium", "ceremony", "engagement broken, hidden caste certificate revealed"),
    ("hard", "dispute", "land deed stolen, proving village takeover by upper caste"),
    ("medium", "secret", "adoption papers missing, revealing baby swap scandal"),
    ("expert", "legacy", "DNA test results altered, contested inheritance of crores"),
    ("hard", "tradition", "ancestral recipe stolen, food business rivalry turns violent"),
    ("medium", "shame", "old photographs destroyed, hiding inter-religious marriage"),
    ("hard", "revenge", "family patriarch poisoned, exposing abuse of daughters-in-law"),
    
    # ═══════════════════════════════════════════════════════════
    # ENTERTAINMENT & FILM INDUSTRY (10 scenarios)
    # ═══════════════════════════════════════════════════════════
    ("hard", "film_set", "lead actor dies during intimate scene, MeToo revenge"),
    ("medium", "theatre", "opening night sabotaged, playwright vs plagiarist director"),
    ("expert", "bollywood", "casting couch evidence stolen, producer silencing victims"),
    ("hard", "music", "unreleased album leaked, ghost producer claiming credit"),
    ("medium", "comedy", "stand-up comedian's jokes stolen, copyright vs free speech"),
    ("hard", "reality_tv", "contestant murdered, exposing rigged voting scam"),
    ("medium", "radio", "podcast episode deleted, whistleblowing on celebrity abuse"),
    ("expert", "streaming", "web series script stolen, proving nepotism baby stole idea"),
    ("hard", "award", "jury bribed for film award, independent filmmaker exposing nexus"),
    ("medium", "festival", "documentary banned, proving government atrocities"),
    
    # ═══════════════════════════════════════════════════════════
    # MEDICAL & HEALTHCARE CRIME (10 scenarios)
    # ═══════════════════════════════════════════════════════════
    ("hard", "hospital", "patient records stolen, exposing organ trafficking ring"),
    ("expert", "clinic", "fertility doctor murdered, illegal surrogacy exploitation exposed"),
    ("medium", "pharmacy", "counterfeit medicine operation, whistleblower vs pharma lobby"),
    ("hard", "mental_health", "asylum patient files destroyed, forced electroshock torture hidden"),
    ("expert", "transplant", "kidney donation coerced, debt trap enslaving poor donors"),
    ("medium", "insurance", "health claim denied, proving medical negligence cover-up"),
    ("hard", "ayurveda", "traditional healer killed, corporate patent theft of tribal medicine"),
    ("medium", "covid", "vaccine certificate fraud, pandemic profiteering exposed"),
    ("expert", "ivf", "embryo switched at birth, baby trafficking scandal"),
    ("hard", "euthanasia", "mercy killing case, family vs medical ethics conflict"),
    
    # ═══════════════════════════════════════════════════════════
    # RELIGIOUS & SPIRITUAL CRIME (8 scenarios)
    # ═══════════════════════════════════════════════════════════
    ("medium", "temple", "donation money embezzled, priest vs trust chairman"),
    ("hard", "pilgrimage", "Tirupati laddu recipe stolen, commercial vs religious sanctity"),
    ("expert", "ashram", "guru murdered, exposing sexual abuse and financial fraud"),
    ("medium", "church", "charity funds diverted, bishop's lavish lifestyle revealed"),
    ("hard", "mosque", "waqf property documents forged, land grab by politicians"),
    ("medium", "gurudwara", "langar supplies poisoned, Hindu-Sikh tension investigation"),
    ("expert", "cult", "spiritual retreat turns deadly, brainwashing vs voluntary devotion"),
    ("hard", "conversion", "forced conversion alleged, love jihad vs interfaith marriage"),
    
    # ═══════════════════════════════════════════════════════════
    # ENVIRONMENTAL & SOCIAL JUSTICE (8 scenarios)
    # ═══════════════════════════════════════════════════════════
    ("hard", "protest", "activist killed, exposing mining company's illegal operations"),
    ("expert", "tribal", "forest land documents destroyed, Adivasi displacement evidence"),
    ("medium", "ngo", "charity funds stolen, exposing white savior scam"),
    ("hard", "pollution", "water quality reports altered, cancer cluster cover-up"),
    ("medium", "wildlife", "tiger poaching evidence destroyed, forest officer vs mafia"),
    ("expert", "dam", "displacement compensation stolen, Narmada Bachao movement angle"),
    ("hard", "slum", "demolition documents forged, poor vs builder-politician nexus"),
    ("medium", "farmer", "loan waiver list manipulated, suicide epidemic cover-up"),
    
    # ═══════════════════════════════════════════════════════════
    # POLITICAL & CORRUPTION (8 scenarios)
    # ═══════════════════════════════════════════════════════════
    ("expert", "election", "EVM tampering alleged, opposition leader vs ruling party"),
    ("hard", "municipal", "tender documents stolen, exposing kickback scheme"),
    ("medium", "police", "evidence room theft, protecting politician's criminal son"),
    ("expert", "parliament", "bill draft leaked, exposing corporate lobbyist influence"),
    ("hard", "ministry", "subsidy list altered, benefiting minister's relatives"),
    ("medium", "panchayat", "village funds embezzled, sarpanch vs gram sabha"),
    ("hard", "judiciary", "court files missing, judge bribed in land dispute case"),
    ("expert", "bureaucracy", "IAS officer's report destroyed, exposing scam worth thousands of crores"),
    
    # ═══════════════════════════════════════════════════════════
    # LUXURY & HIGH SOCIETY (5 scenarios)
    # ═══════════════════════════════════════════════════════════
    ("medium", "resort", "guest murdered at Goa resort, Russian mafia vs local police"),
    ("hard", "yacht", "billionaire's party turns deadly, inheritance conspiracy"),
    ("expert", "polo", "royal family scandal, illegitimate heir claiming throne"),
    ("medium", "golf", "club membership fraud, exposing caste-based exclusion"),
    ("hard", "cruise", "diamond necklace stolen, insurance scam on high seas"),
    
    # ═══════════════════════════════════════════════════════════
    # UNCONVENTIONAL & PSYCHOLOGICAL (7 scenarios)
    # ═══════════════════════════════════════════════════════════
    ("expert", "deepfake", "revenge porn using AI, victim vs tech-savvy stalker"),
    ("hard", "gaslighting", "wife's sanity questioned, husband stealing her business"),
    ("medium", "catfish", "dating app scam, lonely hearts vs romance fraudster"),
    ("expert", "identity", "Aadhaar theft leading to loan fraud, victim proving innocence"),
    ("hard", "stalking", "celebrity harassed, obsessed fan vs security failure"),
    ("medium", "cyberbully", "teenager's suicide, anonymous Instagram account exposed"),
    ("expert", "dark_web", "hitman hired on dark web, crypto trail investigation"),
]


base_prompt = """Generate a PRODUCTION-QUALITY detective mystery case set in India.

Difficulty: {difficulty}
Theme: {theme}
Crime: {crime}

CINEMATIC STORYTELLING REQUIREMENTS:
{cinematic_rules}

CRITICAL JSON RULES:
- Use single quotes inside JSON string values (e.g., "text": "He said 'hello'")
- Make it {tone}
- {complexity}
- Must be solvable through logical deduction
- Include red herrings and misdirection

DIVERSITY RULES (IMPORTANT):
- AVOID common names like Vikram, Priya, Arjun, Meera - use UNIQUE regional names (Tamil, Bengali, Marathi, Punjabi, Kashmiri, Gujarati, etc.)
- VARY alibis creatively - no "working alone" or "at protest" - use specific, culturally rich alibis
- SET story in diverse Indian regions: Chennai, Mumbai, Jaipur, Lucknow, Guwahati, Kochi, Chandigarh, Bhopal, Hyderabad - NOT always Kolkata/Delhi

YOU MUST respond with ONLY valid JSON, no other text. NO code blocks, NO explanations:
{{
  "title": "The Case of...",
  "difficulty": "{difficulty}",
  "setting": "Rich, atmospheric Indian location with sensory details",
  "crime": "Specific crime with emotional/cultural significance",
  "victim": "Person/institution - may have moral complexity",
  "suspects": [
    {{
      "name": "Indian name (culturally authentic)",
      "age": 19-60,
      "role": "student/professor/staff/activist/official",
      "personality": ["Complex", "Memorable", "Layered", "Real"],
      "motive": "DEEP personal reason - not just greed",
      "alibi": "Their claim (verifiable or not)",
      "alibi_verified": true/false,
      "alibi_sources": ["Evidence/witnesses for alibi"],
      "secret": "Hidden truth that adds depth",
      "suspicious_behavior": "Why they seem guilty",
      "emotional_state": "Complex emotion",
      "knowledge_level": "What they know",
      "backstory": "2-3 sentences explaining their character"
    }}
  ],
  "evidence": [
    {{
      "type": "physical/digital/witness/financial",
      "description": "Detailed description - NO smoking guns",
      "location": "Where found",
      "significance": "What it reveals",
      "misleading": true/false
    }}
  ],
  "timeline": ["Timestamped events - NO gaps >30min"],
  "red_herrings": ["False leads that feel real"],
  "solution": {{
    "culprit": "Who did it (unexpected, sympathetic)",
    "method": "Step-by-step how they did it",
    "motive": "TRUE motive (matches suspect motive)",
    "proof": "Combination of 3-4 subtle pieces",
    "how_to_solve": "Logical deduction path"
  }}
}}"""

difficulty_configs = {
    "medium": {
        "tone": "engaging with emotional complexity",
        "complexity": "Multiple suspects with layered motives, 3-4 red herrings",
        "cinematic_rules": """- Morally complex victim (not pure good/evil)
- Culprit should be sympathetic (we understand why)
- Deep Indian cultural context (caste/religion/regional tensions)
- At least 2-3 meaningful relationships driving the plot
- Motive must be PERSONAL (family honor, revenge, protection)
- Include 3-4 'surprising reveals' that recontextualize evidence"""
    },
    "hard": {
        "tone": "serious with high emotional stakes",
        "complexity": "Layered mystery with moral ambiguity, unreliable witnesses",
        "cinematic_rules": """- Netflix-worthy: high stakes, cultural depth, moral dilemmas
- Victim has dark secrets that justify (but don't excuse) the crime
- Culprit's action feels tragically inevitable given backstory
- Integrate caste/gender/colonial legacy as core plot drivers
- 5-6 'holy shit' moments (betrayals, hidden connections, revelations)
- Relationships must create emotional tension and drive decisions
- Ending should pose a moral question to the player"""
    },
    "expert": {
        "tone": "cinematic thriller with impossible moral choices",
        "complexity": "Multi-layered puzzle with competing narratives and deep cultural themes",
        "cinematic_rules": """- Production-level storytelling: unforgettable, culturally profound
- Crime reveals systemic corruption or historical injustice
- Multiple victims, accomplices, and moral gray areas
- Culprit's action exposes institutional evil (player sympathizes)
- 7+ revelations that completely shift understanding
- Ending forces player to choose between competing moral goods
- Cultural context is CENTRAL - story couldn't happen elsewhere
- Every character has rich backstory explaining their choices"""
    }
}

def load_existing_cases():
    """Load existing cases and identify which need regeneration"""
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"📂 Loaded {len(data)} entries from {OUTPUT_FILE}")
                
                # Separate successful cases from errors
                successful = [c for c in data if "case" in c or "raw_response" in c]
                errors = [c for c in data if "error" in c]
                
                print(f"  ✅ Successful: {len(successful)}")
                print(f"  ❌ Errors: {len(errors)}")
                
                return data, errors
        except:
            print(f"⚠️  Error reading {OUTPUT_FILE}, starting fresh")
            return [], []
    else:
        print(f"📝 No existing file found, starting fresh")
        return [], []

def save_cases(cases):
    """Save cases to file immediately"""
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)

async def generate_all_cases():
    """Generate all 100 cases, regenerating failed ones"""
    
    # Load existing
    all_cases, error_cases = load_existing_cases()
    
    # Create a dict of case_id -> case for easy lookup
    cases_dict = {case['id']: case for case in all_cases}
    
    # Find which cases need to be generated
    to_generate = []
    for i, (difficulty, theme, crime) in enumerate(crime_scenarios, 1):
        case_data = cases_dict.get(i, {})
        if i not in cases_dict or 'error' in case_data or case_data.get('parse_error'):
            to_generate.append(i)
    
    print(f"\n🎯 Total cases needed: {len(crime_scenarios)}")
    print(f"✅ Already completed: {len(crime_scenarios) - len(to_generate)}")
    print(f"⏳ Need to generate: {len(to_generate)}")
    
    if len(error_cases) > 0:
        print(f"\n🔄 Will retry {len(error_cases)} failed cases")
    
    if not to_generate:
        print("\n🎉 All cases already generated!")
        return all_cases
    
    print(f"\n📝 Generating cases: {to_generate}\n")
    
    # Generate missing cases
    for case_id in to_generate:
        i = case_id - 1  # Convert to 0-indexed
        difficulty, theme, crime = crime_scenarios[i]
        config = difficulty_configs[difficulty]
        
        prompt = base_prompt.format(
            difficulty=difficulty,
            theme=theme,
            crime=crime,
            tone=config["tone"],
            complexity=config["complexity"],
            cinematic_rules=config["cinematic_rules"]
        )
        
        print(f"\n[{case_id}/100] Generating {difficulty.upper()} case:")
        print(f"  Theme: {theme}")
        print(f"  Crime: {crime}")
        
        try:
            response = await call_sambanova(prompt)
            
            # Try to parse JSON
            try:
                clean_response = response.strip()
                
                # DeepSeek-R1 wraps in <think> tags - extract everything after
                if "<think>" in clean_response:
                    # Find where thinking ends and JSON starts
                    # Look for JSON start - either { or ```
                    think_end = clean_response.find("</think>")
                    if think_end != -1:
                        clean_response = clean_response[think_end + 8:].strip()
                
                # Remove code blocks if present
                if clean_response.startswith("```"):
                    clean_response = clean_response.split("```")[1]
                    if clean_response.startswith("json"):
                        clean_response = clean_response[4:]
                
                clean_response = clean_response.strip()
                
                parsed = json.loads(clean_response)
                
                case_data = {
                    "id": case_id,
                    "difficulty": difficulty,
                    "theme": theme,
                    "crime_type": crime,
                    "generated_at": datetime.now().isoformat(),
                    "case": parsed
                }
            except json.JSONDecodeError:
                print("  ⚠️  JSON parse failed, saving raw response")
                case_data = {
                    "id": case_id,
                    "difficulty": difficulty,
                    "theme": theme,
                    "crime_type": crime,
                    "generated_at": datetime.now().isoformat(),
                    "raw_response": response,
                    "parse_error": True
                }
            
            # Update the case in dict
            cases_dict[case_id] = case_data
            
            # Save immediately
            sorted_cases = [cases_dict[i] for i in sorted(cases_dict.keys())]
            save_cases(sorted_cases)
            print(f"  ✅ Case #{case_id} generated and saved!")
            
            await asyncio.sleep(3)  # Longer delay to avoid rate limits
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            
            cases_dict[case_id] = {
                "id": case_id,
                "difficulty": difficulty,
                "theme": theme,
                "crime_type": crime,
                "error": str(e),
                "generated_at": datetime.now().isoformat()
            }
            
            sorted_cases = [cases_dict[i] for i in sorted(cases_dict.keys())]
            save_cases(sorted_cases)
            
            if "rate" in str(e).lower() or "limit" in str(e).lower():
                print(f"\n⚠️  Hit rate limit. Stopping.")
                print(f"💾 Progress saved! Run again to continue.")
                break
            
            await asyncio.sleep(5)
    
    final_cases = [cases_dict[i] for i in sorted(cases_dict.keys())]
    print(f"\n🎉 Done! Total cases: {len(final_cases)}")
    return final_cases

if __name__ == "__main__":
    print("🚀 Mystery Case Generator (Resume Mode)")
    print(f"📊 Model: {MODEL}\n")
    
    asyncio.run(generate_all_cases())