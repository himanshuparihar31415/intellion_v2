from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://intellion:intellion@localhost:5432/intellion"
    anthropic_api_key: str = ""
    openai_api_key: str = ""  # for embeddings via text-embedding-3-small

    # Exploration
    exploration_token_budget_per_day: int = 100_000
    dedup_similarity_threshold: float = 0.92

    # Reasoning
    reasoning_max_subgraph_nodes: int = 50
    reasoning_traversal_depth: int = 5

    # Decay
    decay_human_daily_rate: float = 0.2   # % per day after decay_start_days
    decay_test_daily_rate: float = 0.1
    decay_exploration_daily_rate: float = 0.5
    decay_document_daily_rate: float = 0.3

    debug: bool = False


settings = Settings()
