import asyncio
import httpx
import json

async def test():
    case_id = "1771875157"
    url = f"http://127.0.0.1:8000/game/{case_id}/submit"
    
    # We will submit a partially correct answer to see if Qwen critiques it
    payload = {
        "culprit_name": "Vikram Mehta",
        "motive": "He was mad about his brother Arjun",
        "method": "He poisoned her water bottle before the stream",
        "evidence": ["Water bottle"]
    }
    
    print(f"Submitting to {url}...")
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            resp = await client.post(url, json=payload)
            print(f"Status: {resp.status_code}")
            print(json.dumps(resp.json(), indent=2))
        except Exception as e:
            print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())
