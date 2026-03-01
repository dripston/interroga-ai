import json
from server import SuspectProfile, CreateGameResponse, load_game, LoadGameRequest
import asyncio

async def test():
    req = LoadGameRequest(mode="text")
    res = await load_game(req)
    for s in res.suspects:
        print(s.name, s.suspicious_behavior)

if __name__ == "__main__":
    asyncio.run(test())
