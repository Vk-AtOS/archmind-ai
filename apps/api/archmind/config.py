from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings, loaded from environment (prefix ARCHMIND_) or .env. See .env.example."""

    model_config = SettingsConfigDict(env_prefix="ARCHMIND_", env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+psycopg://archmind:archmind@localhost:55432/archmind"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "archmind"
    # ADR-006: deterministic mock provider by default; real providers are opt-in.
    llm_provider: str = "mock"


settings = Settings()
