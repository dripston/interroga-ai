import sys
import io
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

import time
import asyncio
from task_agent import TaskAgent

async def test():
    t = TaskAgent()
    
    print("Testing Action query...")
    start = time.time()
    res = await t.execute('check the corridor cctv')
    print(f"Action took: {time.time() - start:.2f} seconds")
    
    print("\nTesting Question query...")
    start = time.time()
    res = await t.execute('what do you think about Aarohi?')
    print(f"Question took: {time.time() - start:.2f} seconds")

asyncio.run(test())
