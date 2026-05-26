"""Aplicação FastAPI. Ponto de entrada do backend.

Rodar localmente:
    uvicorn app.main:app --reload --port 8000

OpenAPI: http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .chat import rotas as chat_rotas
from .config import get_settings
from .routes import alertas, alunos, ciclos, dimensoes, simulados, uploads


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SAS · API",
        description="Backend da interface de coordenação ITM do Colégio Ari de Sá.",
        version="0.0.1",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
    )

    app.include_router(alertas.router)
    app.include_router(alunos.router)
    app.include_router(simulados.router)
    app.include_router(ciclos.router)
    app.include_router(dimensoes.router)
    app.include_router(uploads.router)
    app.include_router(chat_rotas.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
