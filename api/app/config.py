"""Configuração da aplicação — variáveis de ambiente lidas do .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""
    supabase_db_url: str = ""   # usado só pelo migration runner

    storage_bucket: str = "sas-uploads"

    cors_allow_origins: str = "http://localhost:5173"

    # LLM (insights estatísticos do ciclo). Sem chave → módulo degrada
    # graciosamente e a UI esconde o painel.
    openai_api_key: str = ""
    openai_modelo_insights: str = "gpt-4o-mini"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
