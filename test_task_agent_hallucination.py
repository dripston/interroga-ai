import asyncio
import json
from task_agent import TaskAgent

async def test_task_agent_logic():
    print("Starting Task Agent Hallucination Verification...")
    
    agent = TaskAgent()
    
    # Test Case 1: Checking alibi logs (Should NOT mention Alex or Eclipse)
    print("\nQ: Check Dev Patel's tool usage logs")
    resp1 = await agent.execute("Check Dev Patel's tool usage logs")
    print(f"A: {resp1}")
    
    # Test Case 2: Checking a specific location (Should be factual)
    print("\nQ: Check security logs for toll booth")
    resp2 = await agent.execute("Check security logs for toll booth")
    print(f"A: {resp2}")
    
    # Test Case 3: Checking business partners (Should match correctly)
    print("\nQ: Check Toronto business partners")
    resp3 = await agent.execute("Check Toronto business partners")
    print(f"A: {resp3}")

if __name__ == "__main__":
    asyncio.run(test_task_agent_logic())
