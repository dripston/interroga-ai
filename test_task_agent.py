import asyncio
import json
from task_agent import TaskAgent

async def test_agent():
    print("Starting Stricter Task Agent Verification...")
    agent = TaskAgent()
    
    # 1. Test Help (Should show strictness)
    print("\n--- TEST: Help ---")
    resp = await agent.execute("help")
    print(resp)
    
    # 2. Test Broad Alibi Query (SHOULD FAIL)
    print("\n--- TEST: Broad Alibi Query (Expect Rejection) ---")
    resp = await agent.execute("Verify Priya's alibi")
    print(resp)
    
    # 3. Test Semi-Broad Location Query (SHOULD FAIL)
    print("\n--- TEST: Semi-Broad Location (Expect Rejection) ---")
    resp = await agent.execute("Check the whole library for resources")
    print(resp)
    
    # 4. Test Targeted Specific Query (SHOULD PASS)
    print("\n--- TEST: Targeted Specific Query (Expect Success) ---")
    # This should match alibi_source_6 (Priya's security logs)
    resp = await agent.execute("Check Priya's security logs")
    print(resp)

    
    # 5. Test Analytical Tool (SHOULD FAIL/REJECT)
    print("\n--- TEST: Forbidden Tool: Timeline (Expect Rejection) ---")
    resp = await agent.execute("Show me the timeline")
    print(resp)

if __name__ == "__main__":
    asyncio.run(test_agent())


