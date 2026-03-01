import asyncio
import json
from pathlib import Path
from custom_voice_agent import SuspectMemoryLoader, TextModeAgent

async def test_persistence():
    suspect_name = "Rajat Kapoor"
    loader = SuspectMemoryLoader(suspect_name)
    
    # Check if history is loaded
    print(f"Loaded history: {len(loader.chat_history)} messages")
    for msg in loader.chat_history:
        print(f"  {msg['role']}: {msg['content']}")
        
    system_prompt = loader.build_system_prompt()
    agent = TextModeAgent(suspect_name, system_prompt, limit=20, loader=loader)
    
    # Check if agent's history includes the loaded messages
    # The first message is system prompt, then the history
    print(f"Agent history length: {len(agent.conversation_history)}")
    
    if len(agent.conversation_history) > 1:
        print("✅ Persistence test passed: History loaded into agent.")
    else:
        print("❌ Persistence test failed: History not loaded into agent.")

if __name__ == "__main__":
    asyncio.run(test_persistence())
