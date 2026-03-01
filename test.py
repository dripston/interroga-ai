#!/usr/bin/env python3
"""
Simple connectivity + health test for SambaNova Chat API
"""

import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

SAMBANOVA_API_KEY = os.getenv("SAMBANOVA_API_KEY", "")
SAMBANOVA_URL = "https://api.sambanova.ai/v1/chat/completions"
MODEL = "DeepSeek-R1-0528"


def test_sambanova():
    headers = {
        "Authorization": f"Bearer {SAMBANOVA_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": "Reply with: OK"}
        ],
        "max_tokens": 5
    }

    print("🔍 Checking SambaNova API status...")
    start = time.time()

    try:
        response = requests.post(
            SAMBANOVA_URL,
            headers=headers,
            json=payload,
            timeout=30
        )

        duration = round(time.time() - start, 2)

        print(f"\n📡 Status Code: {response.status_code}")
        print(f"⏱ Response Time: {duration}s")

        if response.status_code == 200:
            print("✅ API is UP and responding.")
            print("\n📝 Response Preview:")
            print(response.json())
        elif response.status_code == 401:
            print("❌ Unauthorized – Check API key.")
        elif response.status_code == 429:
            print("⚠️ Rate limit hit.")
        elif response.status_code >= 500:
            print("💥 Server error – API might be down.")
        else:
            print("⚠️ Unexpected response:")
            print(response.text[:300])

    except requests.exceptions.ConnectTimeout:
        print("❌ Connection timed out.")
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect – API may be down or blocked.")
    except Exception as e:
        print(f"💥 Unexpected error: {e}")


if __name__ == "__main__":
    test_sambanova()