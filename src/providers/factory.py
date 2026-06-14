from providers.base import ChatProvider,EmbeddingProvider
from providers.ollama import Ollama
from providers.openai_compat import OpenAICompat
def create_chat_provider(settings) -> ChatProvider:
   match settings.llm_provider:
      case "openai":
         return OpenAICompat(settings.llm_provider, settings.llm_base_url, settings.llm_api_key, settings.llm_model)
      case "ollama":
         return Ollama(settings.llm_provider, settings.llm_base_url, settings.llm_api_key, settings.llm_model)
      case _:
         raise ValueError(f"Invalid LLM provider: {settings.llm_provider}")
def create_embedding_provider(settings) -> EmbeddingProvider:
   match settings.embed_provider:
      case "ollama":
         return Ollama(settings.embed_provider, settings.embed_base_url, settings.llm_api_key, settings.embed_model)
      case _:
         raise ValueError(f"Invalid embedding provider: {settings.embed_provider}")