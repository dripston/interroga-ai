import requests

# Set up your endpoint and API key
url = "https://api.sambanova.ai/v1/chat/completions"
headers = {
    "Authorization": "Bearer c31d4323-2af1-4e51-a9b8-41c63ade6fba",
    "Content-Type": "application/json"
}
payload = {
    "model": "DeepSeek-R1-0528",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 50
}

# Make the request
response = requests.post(url, headers=headers, json=payload)

# Check if request was successful
if response.status_code == 200:
    # Access rate limit info from headers (correct header names)
    print("=== RPM (Requests Per Minute) ===")
    print(f"Limit: {response.headers.get('x-ratelimit-limit-requests')}")
    print(f"Remaining: {response.headers.get('x-ratelimit-remaining-requests')}")
    print(f"Reset (epoch): {response.headers.get('x-ratelimit-reset-requests')}")
    
    print("\n=== RPD (Requests Per Day) ===")
    print(f"Limit: {response.headers.get('x-ratelimit-limit-requests-day')}")
    print(f"Remaining: {response.headers.get('x-ratelimit-remaining-requests-day')}")
    print(f"Reset (epoch): {response.headers.get('x-ratelimit-reset-requests-day')}")
    
    # Optional: print all headers to see what's available
    print("\n=== All Response Headers ===")
    for key, value in response.headers.items():
        print(f"{key}: {value}")
else:
    print(f"Error: {response.status_code}, {response.text}")