import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

HF_API_TOKEN = os.getenv("HF_API_TOKEN")
HF_MODEL = "mistralai/Mistral-7B-Instruct-v0.2"
HF_API_URL = f"https://huggingface.co/api/models./{HF_MODEL}"
_HEADERS = {"Authorization": f"Bearer {HF_API_TOKEN}"}

_HF_INTER_REQUEST_DELAY = 3
_hf_last_request_time = 0.0


def _format_messages_to_prompt(messages: list) -> str:
    prompt = "<s>"
    system_text = ""
    for msg in messages:
        role = type(msg).__name__
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        if role == "SystemMessage":
            system_text = content
        elif role == "HumanMessage":
            if system_text:
                prompt += f"[INST] {system_text}\n\n{content} [/INST]"
                system_text = ""
            else:
                prompt += f"[INST] {content} [/INST]"
        elif role == "AIMessage":
            prompt += f" {content} </s><s>"
    return prompt


def hf_invoke(messages: list, max_new_tokens: int = 200) -> str:
    global _hf_last_request_time

    now = time.time()
    wait = _HF_INTER_REQUEST_DELAY - (now - _hf_last_request_time)
    if wait > 0:
        print(f"[HF RateLimit] Waiting {wait:.1f}s...")
        time.sleep(wait)
    _hf_last_request_time = time.time()

    prompt = _format_messages_to_prompt(messages)
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max_new_tokens,
            "temperature": 0.7,
            "do_sample": True,
            "return_full_text": False,
        }
    }

    for attempt in range(3):
        response = requests.post(HF_API_URL, headers=_HEADERS, json=payload, timeout=60)

        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and result:
                return result[0].get("generated_text", "").strip()
            return str(result).strip()

        elif response.status_code == 503:
            wait_time = 20 * (attempt + 1)
            print(f"[HF] Model loading, waiting {wait_time}s... (attempt {attempt+1}/3)")
            time.sleep(wait_time)

        elif response.status_code == 429:
            print(f"[HF] Rate limited, waiting 30s...")
            time.sleep(30)

        else:
            print(f"[HF] Error {response.status_code}: {response.text[:200]}")
            break

    raise RuntimeError(f"HF API failed after 3 attempts. Last status: {response.status_code}")