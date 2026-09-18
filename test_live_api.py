import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
headers = {'Content-Type': 'application/json'}

print(f"Fetching available models for key starting with: {api_key[:10]}...")
response = requests.get(url, headers=headers)
print(f"Status Code: {response.status_code}")
if response.status_code == 200:
    models = [m['name'] for m in response.json().get('models', [])]
    print(f"Available Models: {models}")
else:
    print(f"Response Body:\n{response.json()}")
