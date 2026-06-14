from providers.base import ChatProvider, EmbeddingProvider, retry
from core.config import Settings
import json
from typing import Iterator

import httpx
class Ollama(ChatProvider, EmbeddingProvider):
    def __init__(self, provider, base_url, api_key, model):
        self.base_url = base_url
        self.model = model
        self.provider = provider
        self.api_key = api_key
    @retry(num_times=3, delay=1)
    def chat(self, messages: list[dict], *, temperature: float = 0.2,
             json_mode: bool = False) -> str:
        """invoke模式"""
        url = f"{self.base_url}/chat/completions"
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "messages": messages, "temperature": temperature, "stream": False},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def stream_chat(self, messages: list[dict], *, temperature: float = 0.2,
                    json_mode: bool = False) -> Iterator[str]:
        """stream模式，逐块返回内容"""
        url = f"{self.base_url}/chat/completions"
        with httpx.stream(
            "POST",
            url,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "stream": True, "messages": messages, "temperature": temperature},
            timeout=60,
        ) as response:
            response.raise_for_status()
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
                    yield content

    @retry(num_times=3, delay=1)
    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量向量化。Ollama /api/embeddings 每次只接受单个 prompt，
        需要逐条调用；响应格式为 {"embedding": [...]}。"""
        url = f"{self.base_url}/api/embeddings"
        embeddings = []
        for text in texts:
            response = httpx.post(
                url,
                json={"model": self.model, "prompt": text},
                timeout=60,
            )
            response.raise_for_status()
            embeddings.append(response.json()["embedding"])
        return embeddings