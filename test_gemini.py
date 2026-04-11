import os
from google import genai
from dotenv import load_dotenv

load_dotenv(".env")
# Print API key presence
print("API KEY FOUND:", "GEMINI_API_KEY" in os.environ)

client = genai.Client(api_key = os.getenv("GEMINI_API_KEY"))

print("\nAvailable Models:\n")

for m in client.models.list():
    print(m.name)