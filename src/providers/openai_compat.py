from providers.base import ChatProvider, retry
import httpx
import json
from typing import Iterator
from core.config import Settings

class OpenAICompat(ChatProvider):
    def __init__(self):
        setting = Settings()
        self.base_url = setting.llm_base_url
        self.api_key = setting.llm_api_key
        self.model = setting.llm_model

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
