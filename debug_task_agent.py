
import asyncio
import sys
import json
from task_agent import TaskAgent

async def debug_task_agent():
    print("🔬 Initializing Task Agent...")
    try:
        agent = TaskAgent()
        print(f"✅ Loaded {len(agent.sources)} total sources.")
        print(f"📂 Evidence Layers loaded: {list(agent.memory.evidence_layers.keys()) if agent.memory.evidence_layers else 'None'}")
        
        print("\n🔍 Testing _get_accessible_sources(0)...")
        accessible = agent._get_accessible_sources(0)
        print(f"👉 Found {len(accessible)} accessible sources.")
        
        if not accessible:
            print("\n❌ Accessible sources is EMPTY. dumping raw sources for first 2 items:")
            for s in agent.sources[:2]:
                print(json.dumps(s, indent=2))
                
            print("\n❌ Dumping Evidence Layer 1:")
            if agent.memory.evidence_layers:
                 print(json.dumps(agent.memory.evidence_layers.get('layer_1_surface', {}), indent=2))
        else:
            for s in accessible:
                print(f"  - {s['id']}: {s.get('description_vague', 'No desc')}")

    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_task_agent())
