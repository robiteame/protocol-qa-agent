import sys
from pathlib import Path

# Add src/ to sys.path so "core" and other packages are importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import json

import httpx
from core.config import Settings
from providers.openai_compat import OpenAICompat

settings = Settings()

base_url = settings.llm_base_url
api_key = settings.llm_api_key
model = settings.llm_model

embed_base_url = settings.embed_base_url
embed_model = settings.embed_model

def check_provider():
    # try:
    #     url = f"{base_url}/chat/completions"
    #     print(f"Connecting to: {url}")
    #     print(f"Model: {model}")
    #     response = httpx.post(
    #         url,
    #         headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    #         json={"model": model, "messages": [{"role": "user", "content": "你好"}]},
    #         timeout=30,
    #     )
    #     print(f"Status: {response.status_code}")
    #     print(f"Response: {response.json()}")
    # except httpx.RequestError as e:
    #     print(f"An error occurred while trying to connect to the provider: {e}")
    message = []
    message.append({"role": "user", "content": "你好"})
    print(OpenAICompat().chat(message))
    return
def check_provider_stream():
    try:
        url = f"{base_url}/chat/completions"
        with httpx.stream(
            "POST",
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model,"stream": True, "messages": [{"role": "user", "content": "你好"}]},
            timeout=30,
        ) as response:
               for line in response.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[len("data: "):]
                    if data.strip() == "[DONE]":
                        break
                    chunk = json.loads(data)
                    if not chunk.get("choices"):
                        continue
                    content = chunk["choices"][0].get("delta", {}).get("content", "")
                    if content:
                        print(content, end="", flush=True)

    except httpx.RequestError as e:
        print(f"An error occurred while trying to connect to the provider: {e}")
        return   

def check_embed_provider():
    url = embed_base_url+"/api/embeddings";
    print(f"Connecting to: {url}")
    try:
        response = httpx.post(
            url,
            json={"model": embed_model, "prompt": "测试这个向量模型是否可用"},
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except httpx.RequestError as e:
        print(f"An error occurred while trying to connect to the provider: {e}")
        return          


if __name__ == "__main__":
    print("Checking provider...")
    check_provider()