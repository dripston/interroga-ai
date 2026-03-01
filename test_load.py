import asyncio
import httpx
import json

async def test():
    url_load = "http://127.0.0.1:8000/game/load"
    
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(url_load, json={"mode": "text"})
        
        if r.status_code != 200:
            print("Failed to load case")
            return
            
        data = r.json()
        suspects = data.get('suspects', [])
        for s in suspects:
            print(f"- {s['name']}: {s.get('suspicious_behavior')}")

if __name__ == "__main__":
    asyncio.run(test())
