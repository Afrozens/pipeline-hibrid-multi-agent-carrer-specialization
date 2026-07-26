from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path, override=True)


class Settings(BaseSettings):
    APP_NAME: str = "Career Path Advisor"
    DEBUG: bool = False

    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "career_advisor"
    DATABASE_URI: str = ""

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_EXTRACTOR_MODEL: str = "gpt-4o-mini"

    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "career-path-advisor"

    ACCESS_KEY_ID: str = ""
    SECRET_ACCESS_KEY: str = ""
    BUCKET_NAME: str = ""
    S3_ENDPOINT_URL: str = ""

    ENCRYPTION_KEY: str = ""

    @property
    def database_uri(self) -> str:
        if self.DATABASE_URI:
            return self.DATABASE_URI
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def langgraph_database_uri(self) -> str:
        uri = self.database_uri
        if uri.startswith("postgresql+"):
            return "postgresql://" + uri.split("://", 1)[1]
        return uri


@lru_cache()
def get_settings() -> Settings:
    return Settings()
