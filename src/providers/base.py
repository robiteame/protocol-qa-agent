from abc import ABC, abstractmethod
from core.errors import ProviderError
from typing import Iterator
import functools
import time

def retry(num_times=3, delay=1):
    def decorator(func):

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal delay
            for i in range(num_times):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if i == num_times - 1:
                        raise ProviderError(e)
                    delay *= 2
                    time.sleep(delay)
                    print(f"第{i + 1}次重试 {func.__name__}方法 在 {delay} 秒后重试...")
        return wrapper
    return decorator

class ChatProvider(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], *, temperature: float = 0.2,
             json_mode: bool = False) -> str:
        """messages 为 OpenAI 风格 [{role, content}, ...]，返回助手文本。
        json_mode=True 时尽力让模型输出 JSON（openai兼容用 response_format，
        ollama 用 format=json；不支持时靠 prompt 约束）。"""

    @abstractmethod
    def stream_chat(self, messages: list[dict], *, temperature: float = 0.2,
                    json_mode: bool = False) -> Iterator[str]:
        """流式返回，逐块 yield 助手文本。"""

class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量向量化。实现内部要处理分批（如每批≤16条）。"""

