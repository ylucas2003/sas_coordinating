"""Aplicação FastAPI. Ponto de entrada do backend.

Rodar localmente:
    uvicorn app.main:app --reload --port 8000

OpenAPI: http://localhost:8000/docs
"""

import os
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .canvas_sync import rotas as canvas_sync_rotas
from .chat import rotas as chat_rotas
from .config import get_settings
from .observabilidade import (
    configurar_logging,
    handler_erro_nao_tratado,
    middleware_request_id,
)
from .supabase_client import get_supabase
from .routes import (
    alertas,
    alunos,
    arquivos,
    auth,
    ciclos,
    dimensoes,
    disparos,
    email_eventos,
    me,
    notas,
    simulados,
    uploads,
)


def _validar_configuracao(settings) -> None:
    """Recusa subir com configuração insegura. Ver docs/14 §4.1.

    Roda SEMPRE. Os defaults de desenvolvimento só passam quando APP_ENV é
    explicitamente "dev" ou "test" — e como o default de `app_env` agora é
    "production" (config.py), esquecer a variável falha fechado.

    Compara contra vazio além do valor-sentinela: `COORDENADOR_SENHA=` (declarada
    sem valor) é o erro mais comum de painel de plataforma, e passava na
    comparação por igualdade — autenticando com senha vazia.

    POSTGREST_TOKEN de propósito NÃO é exigido: nesta topologia o PostgREST não
    tem porta publicada e só a API o alcança (infra/vps/docker-compose.yml).
    Quem contém o acesso é a rede, não um token.
    """
    if settings.app_env in ("dev", "test"):
        return

    problemas: list[str] = []

    if not settings.jwt_secret_key or settings.jwt_secret_key == "dev-secret-change-in-production":
        problemas.append("JWT_SECRET_KEY vazia ou no default de dev (valor público no repositório)")
    elif len(settings.jwt_secret_key) < 32:
        problemas.append("JWT_SECRET_KEY curta demais — use ao menos 32 caracteres")

    if not settings.coordenador_senha or settings.coordenador_senha == "tioleo123":
        problemas.append("COORDENADOR_SENHA vazia ou no default demo")

    if not settings.scheduler_secret:
        problemas.append("SCHEDULER_SECRET vazia — os 4 jobs agendados devolveriam 503 em silêncio")

    # `segredo_lembrete` (config.py) cai na JWT_SECRET_KEY quando esta está
    # vazia. O token do link de descadastro é HMAC(segredo, e-mail) truncado em
    # 64 bits, e vai por e-mail em claro para centenas de alunos — ou seja, o
    # segredo de SESSÃO viraria um oráculo distribuído por e-mail. Só é exigido
    # com o lembrete ligado, que é quando esses links passam a existir.
    if settings.lembrete_aluno_ativo and not settings.lembrete_token_secret:
        problemas.append(
            "LEMBRETE_TOKEN_SECRET vazia com LEMBRETE_ALUNO_ATIVO=true — o link de "
            "descadastro seria assinado com a JWT_SECRET_KEY e enviado por e-mail"
        )

    if settings.email_destinatario_teste:
        problemas.append(
            "EMAIL_DESTINATARIO_TESTE preenchida — TODO e-mail de aluno seria "
            "redirecionado para um endereço só"
        )

    if settings.storage_dir and "localhost" in settings.api_base_url:
        problemas.append(
            "API_BASE_URL aponta para localhost — o link de download do aluno "
            "apontaria para a máquina dele"
        )

    if any("localhost" in origem for origem in settings.cors_origins_list):
        problemas.append("CORS_ALLOW_ORIGINS contém localhost")

    if problemas:
        raise RuntimeError(
            f"Configuração insegura para APP_ENV={settings.app_env}:\n  - "
            + "\n  - ".join(problemas)
            + "\n\nCorrija as variáveis, ou declare APP_ENV=dev se for ambiente local."
        )


def create_app() -> FastAPI:
    settings = get_settings()
    _validar_configuracao(settings)
    configurar_logging()
    # Fora de dev, a superfície da API não é publicada: /docs e /openapi.json
    # entregam as ~50 rotas e os schemas de corpo a qualquer visitante
    # (docs/14 §5). O nginx de produção também bloqueia esses caminhos — as
    # duas camadas são de propósito: a do nginx protege mesmo com a API
    # exposta por engano, esta protege mesmo sem o nginx na frente.
    _dev = settings.app_env in ("dev", "test")
    app = FastAPI(
        title="SAS · API",
        description="Backend da interface de coordenação ITM do Colégio Ari de Sá.",
        version="0.0.1",
        docs_url="/docs" if _dev else None,
        redoc_url="/redoc" if _dev else None,
        openapi_url="/openapi.json" if _dev else None,
    )

    app.middleware("http")(middleware_request_id)
    app.add_exception_handler(Exception, handler_erro_nao_tratado)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(alertas.router)
    app.include_router(alunos.router)
    app.include_router(simulados.router)
    app.include_router(notas.router)
    app.include_router(ciclos.router)
    app.include_router(dimensoes.router)
    app.include_router(uploads.router)
    if settings.storage_dir:
        # Só faz sentido com o Storage local; no modo Supabase o download vai
        # direto pro bucket. Ver app/routes/arquivos.py.
        app.include_router(arquivos.router)
    app.include_router(chat_rotas.router)
    app.include_router(canvas_sync_rotas.router)
    app.include_router(disparos.router)
    # O webhook do SNS é o único endpoint público que não dá para proteger por
    # header custom nem por VPN — quem chama é a AWS. A verificação de
    # assinatura ainda não existe e o handler faz GET cego na SubscribeURL
    # (docs/14 §4.2). Enquanto o envio de e-mail está desligado (decisão de
    # 21/08, docs/15 §2), o router não é registrado: o SSRF deixa de ter
    # superfície em vez de ser remendado. Ligar o e-mail = preencher
    # SES_WEBHOOK_TOKEN, e aí a verificação de assinatura vira pré-requisito.
    if settings.ses_webhook_token:
        app.include_router(email_eventos.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        # LIVENESS: "o processo está de pé?". É o que o healthcheck do Docker
        # consulta, então NÃO pode depender do banco nem do agendador — senão
        # um cron parado faria o container reiniciar em loop, o que não
        # conserta nada.
        #
        # Sem `env`: o campo era sondável sem autenticação e dizia a qualquer
        # visitante se o guard de configuração estava ativo (docs/14 §4.1).
        return {"status": "ok"}

    @app.get("/health/ready", tags=["meta"])
    async def health_ready():
        """READINESS: "o sistema está fazendo o trabalho dele?".

        Existe por causa do modo de falha mais provável de toda a migração: o
        agendador parar de disparar. Nesse cenário a API responde 200 em tudo,
        o /health diz ok, e os dados simplesmente congelam — o coordenador só
        percebe dias depois, ao notar que as notas do último simulado não
        apareceram (docs/14 §5, ops).

        Duas checagens: o PostgREST responde, e existe sincronização com
        sucesso na janela esperada. Devolve 503 quando algo está degradado,
        para que um monitor externo consiga alertar.
        """
        problemas: list[str] = []
        detalhe: dict = {}

        try:
            cliente = get_supabase()
            cliente.table("materia").select("id").limit(1).execute()
            detalhe["banco"] = "ok"
        except Exception as exc:  # noqa: BLE001
            detalhe["banco"] = "falhou"
            problemas.append(f"banco inacessível: {type(exc).__name__}")

        # 30 min = 6x o intervalo do sync incremental (5 min). Tolera uma
        # rodada longa ou uma indisponibilidade curta do Canvas sem alarme
        # falso, e ainda detecta cron parado no mesmo turno de trabalho.
        limite_min = int(os.environ.get("SYNC_ALERTA_MINUTOS", "30"))
        if "banco" in detalhe and detalhe["banco"] == "ok":
            try:
                resp = (
                    get_supabase()
                    .table("canvas_sync_execucao")
                    .select("finalizado_em, status")
                    .eq("status", "sucesso")
                    .order("finalizado_em", desc=True)
                    .limit(1)
                    .execute()
                )
                linhas = resp.data or []
                if not linhas:
                    problemas.append("nenhuma sincronização com sucesso registrada")
                    detalhe["ultimo_sync"] = None
                else:
                    quando = datetime.fromisoformat(
                        str(linhas[0]["finalizado_em"]).replace("Z", "+00:00")
                    )
                    idade = datetime.now(timezone.utc) - quando
                    detalhe["ultimo_sync"] = quando.isoformat()
                    detalhe["ha_minutos"] = int(idade.total_seconds() // 60)
                    if idade > timedelta(minutes=limite_min):
                        problemas.append(
                            f"sem sync bem-sucedido há {detalhe['ha_minutos']} min "
                            f"(limite {limite_min})"
                        )
            except Exception as exc:  # noqa: BLE001
                problemas.append(f"não consegui ler o histórico de sync: {type(exc).__name__}")

        if problemas:
            return JSONResponse(
                status_code=503,
                content={"status": "degradado", "problemas": problemas, **detalhe},
            )
        return {"status": "ok", **detalhe}

    return app


app = create_app()
