from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    # LLM
    llm_provider: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str

    # Embedding
    embed_provider: str
    embed_base_url: str
    embed_model: str

    # Data root
    data_dir: str

    # Chunking & retrieval
    chunk_max_tokens: int
    retrieval_top_k: int
    fusion_top_n: int
    agent_max_rounds: int
    tree_max_depth: int
    tree_max_select: int

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

