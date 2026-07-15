"""
LangGraph Detective Game Orchestrator
Handles the complete game flow from difficulty selection to case solving
"""

import asyncio
import json
import random
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Import our existing modules
from story_generator import generate_case
from graphrag_agent import GraphRAGAgent



class GameState:
    """Tracks game state across sessions"""
    
    def __init__(self):
        self.difficulty = None
        self.case_file = None
        self.case_data = None
        self.current_suspect = None
        self.questions_asked = {}  # suspect_name: count
        self.task_agent_questions = 0
        self.game_started_at = None
        self.interrogation_history = []
    
    def start_new_game(self, difficulty: str, case_data: Dict):
        """Initialize new game state"""
        self.difficulty = difficulty
        self.case_file = None  # Not needed since we have case_data
        self.case_data = case_data
        
        # Shuffle suspects to prevent "first = culprit" predictability
        random.shuffle(self.case_data['suspects'])
        
        self.current_suspect = None
        self.questions_asked = {s['name']: 0 for s in self.case_data['suspects']}
        # Limits: 20 questions per suspect TOTAL, 20 questions for Task Agent TOTAL
        self.max_suspect_questions = 20 
        self.max_task_agent_questions = 20
        self.task_agent_questions = 0
        self.game_started_at = datetime.now().isoformat()
        self.interrogation_history = []
    
    def update_questions(self, suspect_name: str, used: int):
        """Update question count from usage file"""
        if suspect_name == "TASK_AGENT":
            self.task_agent_questions += used
        else:
            self.questions_asked[suspect_name] = self.questions_asked.get(suspect_name, 0) + used
    
    def get_remaining_questions(self, suspect_name: str) -> int:
        """Get remaining questions for suspect"""
        if suspect_name == "TASK_AGENT":
            return max(0, self.max_task_agent_questions - self.task_agent_questions)
        return max(0, self.max_suspect_questions - self.questions_asked.get(suspect_name, 0))


class DetectiveGameOrchestrator:
    """Main game orchestrator using LangGraph-style flow"""
    
    def __init__(self):
        self.state = GameState()
        self.graphrag_agent = None
        
    async def run_game(self):
        """Main game execution flow"""
        print("🎭 WELCOME TO DETECTIVE SIMULATOR 🕵️")
        print("=" * 50)
        
        # Step 1: Get difficulty or mode
        choice = await self._select_mode()
        
        if choice == "debug":
             print(f"\n🐞 Starting DEBUG MODE...")
             case_data = await self._load_existing_case()
             if not case_data:
                 print("❌ No cases found! Starting normal generation.")
                 choice = "medium" # fallback
        
        if choice != "debug":
             # NORMAL FLOW
             difficulty = choice
             
             # Step 2: Generate case
             print(f"\n🎲 Generating {difficulty.upper()} case...")
             case_data = await self._generate_case(difficulty)
             
             # Step 3: Process case through GraphRAG
             print("📊 Processing case data...")
             await self._process_case(case_data)
        
        # Step 4: Initialize game state
        self.state.start_new_game(choice if choice != "debug" else "medium", case_data)
        
        # Step 5: Show case introduction
        await self._show_case_introduction(case_data)
        
        # Step 6: Main interrogation loop
        await self._interrogation_loop()
        
        # Step 7: Final submission
        await self._submit_solution()
    
    async def _select_mode(self) -> str:
        """Get game mode/difficulty"""
        print("\nSelect Game Mode:")
        print("1. New Game - Easy")
        print("2. New Game - Medium")
        print("3. New Game - Hard")
        print("4. 🐞 Debug Mode (Load last case, skip generation)")
        
        while True:
            choice = input("\nEnter choice (1-4): ").strip()
            if choice == "1": return "easy"
            if choice == "2": return "medium"
            if choice == "3": return "hard"
            if choice == "4": return "debug"
            print("Please enter 1-4")

    async def _load_existing_case(self) -> Dict:
        """Load the most recent case file"""
        try:
            files = list(Path(".").glob("game_case_*.json"))
            if not files:
                return None
            
            # Get latest file
            latest_file = max(files, key=lambda f: f.stat().st_mtime)
            print(f"📂 Loading latest case: {latest_file.name}")
            
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Unwrap 'case' if present (new format)
                return data.get('case', data)
        except Exception as e:
            print(f"❌ Error loading case: {e}")
            return None
    
    async def _generate_case(self, difficulty: str) -> Dict:
        """Generate mystery case using story generator"""
        print("📝 Creating your mystery case...")
        print("   - Generating plot...")
        print("   - Creating suspects...")
        print("   - Setting up clues...")
        
        # generate_case returns the case data directly and saves to file
        case_data = await generate_case(difficulty)
        print("✅ Case generated and saved to file")
        # Unwrap 'case' if present
        return case_data.get('case', case_data)
    
    async def _process_case(self, case_data: Dict):
        """Process case through GraphRAG agent"""
        print("🤖 Initializing investigation agents...")
        print("   - Creating detective briefing...")
        print("   - Generating suspect profiles...")
        print("   - Setting up task agent...")
        
        # Process with GraphRAG
        self.graphrag_agent = GraphRAGAgent(case_data)
        await self.graphrag_agent.generate_all_agents()
        
        print("✅ Agents ready!")
    
    async def _show_case_introduction(self, case_data: Dict):
        """Display cinematic case intro using GraphRAG briefing"""
        
        case_id = case_data.get('id')
        if getattr(self, 'graphrag_agent', None) and hasattr(self.graphrag_agent, 'agents_dir'):
            briefing_path = self.graphrag_agent.agents_dir / "detective_briefing" / "briefing.txt"
        elif case_id:
            briefing_path = Path(f"game_agents_{case_id}/detective_briefing/briefing.txt")
        else:
            import os
            dirs = [d for d in os.listdir('.') if d.startswith('game_agents_')]
            if dirs:
                latest_dir = max(dirs, key=os.path.getmtime)
                briefing_path = Path(f"./{latest_dir}/detective_briefing/briefing.txt")
            else:
                briefing_path = Path("game_agents/detective_briefing/briefing.txt")
        
        print("\n")
        print("▓" * 60)
        print(f"  🎬  {case_data.get('title', 'CASE FILE').upper()}")
        print("▓" * 60)
        
        if briefing_path.exists():
            with open(briefing_path, 'r', encoding='utf-8') as f:
                briefing = f.read()
            print()
            for line in briefing.strip().split('\n'):
                print(f"  {line}")
            print()
        else:
            # Fallback if briefing wasn't generated
            setting = case_data.get('setting', {})
            crime = case_data.get('crime', {})
            victim = case_data.get('victim', {})
            location = setting.get('location', str(setting)) if isinstance(setting, dict) else str(setting)
            crime_desc = crime.get('what_happened', str(crime)) if isinstance(crime, dict) else str(crime)
            victim_name = victim.get('name', '?') if isinstance(victim, dict) else str(victim)
            print(f"\n  📍 {location}")
            print(f"  ⚖️  {crime_desc}")
            print(f"  👤 Victim: {victim_name}")
            print()
        
        # Show time of incident from timeline
        timeline = case_data.get('timeline', [])
        if timeline:
            last_event = timeline[-1]
            time_str = last_event.get('time', 'Unknown')
            event_str = last_event.get('event', '')
            print(f"  ⏰ TIME OF INCIDENT: {time_str} — {event_str}")
            print()
        
        # Suspect list — clean: just name, role, age
        print("─" * 60)
        print(f"  👥 SUSPECTS")
        print("─" * 60)
        for i, suspect in enumerate(case_data['suspects'], 1):
            print(f"  {i}. {suspect['name']}  —  {suspect['role']}, age {suspect['age']}")
        print()
        print("▓" * 60)
        print("  The investigation begins.")
        print("▓" * 60)
        print()
    
    async def _interrogation_loop(self):
        """Main interrogation loop"""
        print("\n" + "=" * 60)
        print("🕵️  INTERROGATION PHASE")
        print("=" * 60)
        print("You can interrogate suspects and the task agent.")
        print(f"Limits: {self.state.max_suspect_questions} questions per suspect, {self.state.max_task_agent_questions} for task agent")
        print("Type 'exit' to submit your answer anytime.")
        
        while True:
            # Show current status
            await self._show_interrogation_status()
            
            # Select who to interrogate
            target = await self._select_interrogation_target()
            
            if target == "EXIT":
                break
            elif target == "TASK_AGENT":
                await self._interrogate_task_agent()
            else:
                await self._interrogate_suspect(target)
    
    async def _show_interrogation_status(self):
        """Show current interrogation progress"""
        print(f"\n📊 PROGRESS:")
        print(f"Task Agent: {self.state.task_agent_questions}/{self.state.max_task_agent_questions} questions used")
        
        for suspect in self.state.case_data['suspects']:
            name = suspect['name']
            used = self.state.questions_asked.get(name, 0)
            remaining = self.state.get_remaining_questions(name)
            status = "🔴 FULL" if remaining == 0 else f"🟡 {remaining} left"
            print(f"{name}: {used}/{self.state.max_suspect_questions} questions used {status}")
    
    async def _select_interrogation_target(self) -> str:
        """Let user choose who to interrogate"""
        print(f"\nChoose who to interrogate:")
        print("0. Submit final answer (EXIT)")
        print("T. Task Agent")
        
        suspect_options = {}
        for i, suspect in enumerate(self.state.case_data['suspects'], 1):
            name = suspect['name']
            remaining = self.state.get_remaining_questions(name)
            status = "🔴" if remaining == 0 else "🟢"
            print(f"{i}. {status} {name} ({remaining} questions left)")
            suspect_options[str(i)] = name
        
        print("T. 🟢 Task Agent")
        
        while True:
            choice = input("\nEnter choice: ").strip().upper()
            
            if choice == "0" or choice == "EXIT":
                return "EXIT"
            elif choice == "T":
                if self.state.get_remaining_questions("TASK_AGENT") > 0:
                    return "TASK_AGENT"
                else:
                    print("❌ Task Agent question limit reached!")
            elif choice in suspect_options:
                suspect_name = suspect_options[choice]
                if self.state.get_remaining_questions(suspect_name) > 0:
                    return suspect_name
                else:
                    print(f"❌ {suspect_name} question limit reached!")
            else:
                print("Invalid choice. Please try again.")

    async def _read_usage_file(self) -> int:
        """Read session_usage.json to get questions used"""
        try:
            with open("session_usage.json", "r") as f:
                data = json.load(f)
                return data.get("questions_used", 0)
        except Exception:
            return 0  # Assume 0 if file missing or error
    
    async def _interrogate_suspect(self, suspect_name: str):
        """Launch custom voice agent for suspect interrogation"""
        remaining = self.state.get_remaining_questions(suspect_name)
        print(f"\n🗣️  INTERROGATING: {suspect_name}")
        print(f"Questions remaining: {remaining}")
        
        # Ask for mode
        while True:
            mode = input("Choose mode — [T]ext or [V]oice: ").strip().lower()
            if mode in ['t', 'text', 'v', 'voice']:
                break
            print("  Please enter T or V")
        
        use_voice = mode in ['v', 'voice']
        
        # Reset usage file before starting
        if Path("session_usage.json").exists():
            Path("session_usage.json").unlink()
            
        # Launch custom voice agent for this suspect
        import subprocess
        import sys
        
        try:
            # Launch the custom voice agent with the suspect name
            cmd = [sys.executable, "custom_voice_agent.py", suspect_name, "--limit", str(remaining)]
            if use_voice:
                cmd.append("--voice")
            process = subprocess.Popen(cmd)
            
            # Wait for the process to complete
            process.wait()
            
            # Update question count from file
            used = await self._read_usage_file()
            self.state.questions_asked[suspect_name] += used
            
        except Exception as e:
            print(f"❌ Error launching voice agent: {e}")
            # Fallback
            self.state.update_questions(suspect_name, 1)
        
        print(f"\n🔄 Returned from voice agent for {suspect_name}")
    
    async def _interrogate_task_agent(self):
        """Launch task agent for investigation"""
        remaining = self.state.get_remaining_questions("TASK_AGENT")
        print(f"\n🔬 LAUNCHING TASK AGENT")
        print(f"Questions remaining: {remaining}")
        print("(Type 'back' or 'quit' to return)")
        
        # Reset usage file before starting
        if Path("session_usage.json").exists():
            Path("session_usage.json").unlink()

        # Launch the task agent
        import subprocess
        import sys
        
        try:
            # Launch the task agent
            cmd = [sys.executable, "task_agent.py", "--limit", str(remaining)]
            process = subprocess.Popen(cmd)
            
            # Wait for the process to complete
            process.wait()
            
            # Update question count from file
            used = await self._read_usage_file()
            self.state.task_agent_questions += used
            
        except Exception as e:
            print(f"❌ Error launching task agent: {e}")
            # Fallback
            self.state.update_questions("TASK_AGENT", 1)
        
        print(f"\n🔄 Returned from task agent")
    
    async def _submit_solution(self):
        """Submit and verify final answer"""
        print("\n" + "=" * 60)
        print("🎯 FINAL SUBMISSION")
        print("=" * 60)
        
        # Show interrogation summary
        print(f"\n📊 INTERROGATION SUMMARY:")
        print(f"Total interrogation sessions: {sum(self.state.questions_asked.values()) + self.state.task_agent_questions}")
        print(f"Suspects interrogated: {len([s for s, count in self.state.questions_asked.items() if count > 0])}")
        
        # Get user's answer
        print(f"\nBased on your investigation, who do you think is the culprit?")
        for i, suspect in enumerate(self.state.case_data['suspects'], 1):
            print(f"{i}. {suspect['name']}")
        
        guessed_culprit = None
        while True:
            choice = input("\nEnter suspect number: ").strip()
            try:
                index = int(choice) - 1
                if 0 <= index < len(self.state.case_data['suspects']):
                    guessed_culprit = self.state.case_data['suspects'][index]['name']
                    break
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a number.")
        
        # Verify answer
        actual_culprit = self.state.case_data.get('solution', {}).get('culprit')
        print(f"\n📢 REVEALING THE TRUTH...")
        await asyncio.sleep(1)
        print(f"\n👉 Your Accusation: {guessed_culprit}")
        await asyncio.sleep(1)
        print(f"🕵️  The Real Culprit: {actual_culprit}")
        print()
        
        if guessed_culprit and guessed_culprit.lower() == actual_culprit.lower():
            print("═" * 60)
            print("  🎉 CONGRATULATIONS! YOU CRACKED THE CASE! 🏆")
            print("  You are a true master detective.")
            print("═" * 60)
        else:
            print("═" * 60)
            print("  ❌ INCORRECT. THE CULPRIT GOT AWAY.")
            print("  Better luck next time, detective.")
            print("═" * 60)
        
        # Show solution details
        print(f"\n📋 CASE FILE CLOSED:")
        solution = self.state.case_data.get('solution', {})
        print(f"  🔪 Motive: {solution.get('motive', 'Unknown')}")
        print(f"  🔧 Method: {solution.get('method', 'Unknown')}")
        
        evidence = solution.get('evidence', [])
        if evidence:
            print("\n  🔎 KEY EVIDENCE:")
            for item in evidence:
                print(f"    • {item}")
        
        print("\n" + "═" * 60)
        print("  Thanks for playing! 🕵️")
        print("═" * 60)


# Main execution
async def main():
    orchestrator = DetectiveGameOrchestrator()
    await orchestrator.run_game()


if __name__ == "__main__":
    asyncio.run(main())