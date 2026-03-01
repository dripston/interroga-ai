import asyncio
import httpx

async def test():
    url_load = "http://127.0.0.1:8000/game/load"
    
    async with httpx.AsyncClient(timeout=120) as client:
        print("Loading latest Case...")
        r = await client.post(url_load, json={"mode": "text"})
        print(f"Load Status: {r.status_code}")
        
        if r.status_code != 200:
            print("Failed to load case")
            return
            
        case_id = r.json().get('case_id')
        print(f"Loaded Case ID: {case_id}")
        
        url_task = f"http://127.0.0.1:8000/game/{case_id}/task"
        
        print("\n--- Test 1: Broad Query (Should Ask For Specifics) ---")
        res1 = await client.post(url_task, json={"command": "Check the CCTV everywhere."})
        print(f"[Status {res1.status_code}] result: {res1.json().get('result')}")

        print("\n--- Test 2: Specific Evidence Check (Should Say Nothing Found & Suggest Follow-up) ---")
        res2 = await client.post(url_task, json={"command": "Are there any forensic neurological scans of Meera?"})
        print(f"[Status {res2.status_code}] result: {res2.json().get('result')}")
        
        print("\n--- Test 3: Opinion/Guidance (Should Answer Safely) ---")
        res3 = await client.post(url_task, json={"command": "What do you think is going on?"})
        print(f"[Status {res3.status_code}] result: {res3.json().get('result')}")

if __name__ == "__main__":
    asyncio.run(test())
