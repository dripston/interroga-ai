import asyncio
import json
from custom_voice_agent import SuspectMemoryLoader, OpenRouterClient

async def test_suspect_prompts():
    print("Starting Suspect Agent Logic Verification...")
    
    # We'll use a real suspect folder from the game_agents directory
    # I'll pick 'Vikram Oberoi' as he's the culprit in the current generated case
    suspect_name = "Arjun Malhotra"
    
    try:
        loader = SuspectMemoryLoader(suspect_name)
        system_prompt = loader.build_system_prompt()
        
        print(f"\n--- Testing Suspect: {suspect_name} (Culprit) ---")
        
        # Test Case 1: General Question (Brevity & No Emotion Check)
        print("\nQ: What were you doing last night?")
        prompt1 = f"{system_prompt}\n\nDETECTIVE: What were you doing last night?\n\nSUSPECT RESPONSE:"
        resp1 = await OpenRouterClient.call(prompt1, temperature=0.8, max_tokens=50)
        print(f"A: {resp1.strip()}")
        if "(" in resp1 or ")" in resp1:
            print("❌ FAILED: Response contains parentheses/emotion tags")
        else:
            print("✅ SUCCESS: No emotion tags found")
        
        # Test Case 2: Alibi Confirmation (Rejection Check)
        print("\nQ: Who can confirm you were at the office?")
        prompt2 = f"{system_prompt}\n\nDETECTIVE: Who can confirm you were at the office?\n\nSUSPECT RESPONSE:"
        resp2 = await OpenRouterClient.call(prompt2, temperature=0.8, max_tokens=50)
        print(f"A: {resp2.strip()}")

        # Test Case 3: Accusation (Push Back Check)
        print("\nQ: I think you killed Rajan.")
        prompt3 = f"{system_prompt}\n\nDETECTIVE: I think you killed Rajan.\n\nSUSPECT RESPONSE:"
        resp3 = await OpenRouterClient.call(prompt3, temperature=0.8, max_tokens=50)
        print(f"A: {resp3.strip()}")

    except Exception as e:
        print(f"❌ Error during test: {e}")

if __name__ == "__main__":
    asyncio.run(test_suspect_prompts())
