"""Application settings, loaded from the environment (12-factor style)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str = "bookshelf"
    postgres_password: str = "bookshelf"
    postgres_db: str = "bookshelf"
    postgres_host: str = "db"
    postgres_port: int = 5432
    database_url: str | None = None

    api_title: str = "My Bookshelf API"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    per_visitor_libraries: bool = False
    seed_library_path: str = "sample-data/seed_library.json"

    library_max_idle_days: int = 30
    max_libraries: int = 1000
    max_books_per_library: int = 5000
    max_request_bytes: int = 25 * 1024 * 1024

    google_books_api_key: str | None = None
    enrichment_provider: str = "google_books"
    enrichment_timeout_seconds: float = 10.0
    enrichment_delay_seconds: float = 0.2

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            for prefix in ("postgresql://", "postgres://"):
                if self.database_url.startswith(prefix):
                    return "postgresql+psycopg://" + self.database_url[len(prefix) :]
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
