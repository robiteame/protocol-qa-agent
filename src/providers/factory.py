from providers.base import ChatProvider,EmbeddingProvider
from providers.openai_compat import OpenAICompat
def create_chat_provider(settings) -> ChatProvider:
   if settings.llm_provider == "openai":
      return OpenAICompat()
   else:
      return ChatProvider(settings.llm_provider, settings.llm_base_url, settings.llm_api_key, settings.llm_model)

def create_embedding_provider(settings) -> EmbeddingProvider:
   return EmbeddingProvider(settings.embed_provider, settings.embed_base_url, settings.embed_model)