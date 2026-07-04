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

    # Auth JWT
    jwt_secret_key: str = "dev-secret-change-in-production"

    # Credenciais do coordenador (demo — substituir por tabela de usuários futuramente)
    coordenador_email: str = "leonardobruno@aridesa.com"
    coordenador_senha: str = "tioleo123"

    # LLM (insights estatísticos do ciclo). Sem chave → módulo degrada
    # graciosamente e a UI esconde o painel.
    openai_api_key: str = ""
    openai_modelo_insights: str = "gpt-4o-mini"

    # Canvas LMS — sincronização direta (canvas_sync/). Ver docs/08-integracao-canvas.md.
    canvas_base_url: str = ""
    canvas_api_token: str = ""
    canvas_account_id: str = "1"                # conta "Colégio Ari de Sá"
    canvas_ano_vigente: str = ""                # vazio = auto-detecta (maior ano encontrado)
    canvas_sync_lookback_minutos: str = "20"    # janela do graded_since no sync incremental

    # Segredo compartilhado com o scheduler da AWS (header X-Scheduler-Secret).
    # Mesmo valor do parâmetro SSM /sas/scheduler/secret — ver infra/README.md.
    scheduler_secret: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
