"""Configuração da aplicação — variáveis de ambiente lidas do .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Default é "production" de PROPÓSITO: esquecer a variável no deploy tem
    # que falhar fechado. Com "dev" como default, um container sem APP_ENV
    # subia com o segredo de JWT publicado neste repositório e a senha demo —
    # e o guard de main.py nem rodava (docs/14 §4.1).
    # Desenvolvimento declara APP_ENV=dev explicitamente (api/.env,
    # docker-compose.yml), então nada muda localmente.
    app_env: str = "production"

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""
    supabase_db_url: str = ""   # usado só pelo migration runner

    # --- Modo local (docker compose) -------------------------------------
    # Preenchidas → o backend fala com o PostgREST/filesystem locais em vez do
    # Supabase hospedado. Vazias → comportamento original. Ver
    # app/supabase_client.py, app/storage.py e docker-compose.yml.
    postgrest_url: str = ""
    postgrest_token: str = ""   # JWT do PostgREST; vazio = papel anônimo (só dev)
    storage_dir: str = ""       # diretório do Storage local

    # Endereço público da API — usado para montar a URL de download do Storage
    # local. Precisa ser o host que o browser enxerga, não o do container.
    api_base_url: str = "http://localhost:8000"

    storage_bucket: str = "sas-uploads"

    cors_allow_origins: str = "http://localhost:5173"

    # Auth JWT
    jwt_secret_key: str = "dev-secret-change-in-production"

    # Autosserviço de primeiro acesso do aluno. DESLIGADO por default.
    #
    # O fluxo /auth/primeiro-acesso serve de "primeiro acesso" E de "esqueci
    # minha senha", e valida só matrícula + e-mail — sem prova de posse de
    # nenhum dos dois. Matrícula é o SIS User ID do Canvas, que circula em
    # lista de chamada; o e-mail é institucional e derivável do nome. Quem
    # souber os dois toma a conta na hora, e o dono só descobre quando não
    # conseguir mais entrar (docs/14 §10).
    #
    # Com isto desligado, quem provisiona acesso é a coordenação
    # (scripts/criar_acesso.py) e o vetor deixa de existir. Religar só faz
    # sentido depois que o fluxo mandar um código de uso único para o e-mail
    # do Canvas — e aí ele depende do envio de e-mail, hoje adiado.
    primeiro_acesso_autosservico: bool = False

    # Credenciais do coordenador (demo — substituir por tabela de usuários futuramente)
    coordenador_email: str = "leonardobruno@aridesa.com"
    coordenador_senha: str = "tioleo123"

    # LLM (insights estatísticos do ciclo). Sem chave → módulo degrada
    # graciosamente e a UI esconde o painel.
    openai_api_key: str = ""
    openai_modelo_insights: str = "gpt-4o-mini"

    # Modelo do chat da COORDENAÇÃO, explícito e barato por default.
    #
    # Antes era inferido de `openai_modelo_insights`: se o valor contivesse
    # "mini", o código concluía que não era "potente" e caía num fallback para
    # gpt-4o. A lógica estava invertida na prática — configurar o modelo barato
    # era justamente o que ligava o caro. E o caro custa 16x mais por token:
    # uma thread de 5 mensagens sai por US$ 0,55 em gpt-4o contra US$ 0,033 no
    # mini, e um coordenador com 20 mensagens/dia gastava mais que 175 alunos
    # somados (docs/14 §6.4).
    openai_modelo_coordenador: str = "gpt-4o-mini"

    # Teto de uso do chat POR USUÁRIO. Não existia nada: nem rate limit, nem
    # max_tokens, nem leitura dos tokens_in/tokens_out que já eram gravados em
    # chat_mensagem. Com o chat aberto para ~900 alunos, não havia nada entre
    # um script em loop e a fatura — no pior caso medido, US$ 379 numa hora
    # (docs/14 §6.4).
    #
    # 20 mensagens/hora é folgado para uma pessoa e apertado para um robô.
    # 300 mil tokens/dia ≈ 30 mensagens de aluno mediano, ou ~US$ 0,05/dia no
    # gpt-4o-mini — o que dá um teto previsível para a conta mensal.
    chat_limite_mensagens_hora: int = 20
    chat_limite_tokens_dia: int = 300_000

    # Canvas LMS — sincronização direta (canvas_sync/). Ver docs/08-integracao-canvas.md.
    canvas_base_url: str = ""
    canvas_api_token: str = ""
    canvas_account_id: str = "1"                # conta "Colégio Ari de Sá"
    canvas_ano_vigente: str = ""                # vazio = auto-detecta (maior ano encontrado)
    canvas_sync_lookback_minutos: str = "20"    # janela do graded_since no sync incremental

    # Canvas como provedor de identidade — OAuth2 por redirect (docs/18 §4.2).
    # É OUTRA credencial, não o token acima: o token autentica o SAS *como o
    # Admin*; a Developer Key é o cadastro do SAS como aplicativo, para o
    # aluno entrar com a conta DELE. Criada em Admin → Developer Keys, com a
    # redirect URI igual a `canvas_oauth_redirect_uri`. Vazio = SSO desligado
    # e a tela de login não oferece o botão.
    canvas_client_id: str = ""
    canvas_client_secret: str = ""
    canvas_oauth_redirect_uri: str = "http://localhost:8080/auth/canvas/callback"

    # E-mail via AWS SES (motor de lembretes, app/lembretes/). Sem credencial →
    # agendar COM lembrete devolve 422; o resto do sistema não muda.
    # Ver docs/12-plano-p2-motor-lembretes.md §2 (remetente precisa estar
    # verificado no SES; em sandbox, o destinatário também).
    aws_ses_regiao: str = "us-east-1"
    aws_ses_access_key_id: str = ""
    aws_ses_secret_access_key: str = ""
    email_remetente: str = ""

    # Rede de segurança de desenvolvimento (docs/13 §1, §4.5). Preenchida →
    # TODO envio vai pra este endereço, com o destinatário real no assunto.
    # É o que impede um curl de teste virar 873 e-mails reais.
    email_destinatario_teste: str = ""

    # Configuration set do SES — é o que faz bounce/complaint chegarem no SNS
    # (docs/13 §4.6). Vazio → envia igual, sem telemetria de rejeição.
    email_configuration_set: str = ""

    # --- Lembrete de aluno (P3, docs/13-plano-p3-lembrete-aluno.md) -------
    # Desligado por default: ligar é decisão, não default de deploy. Off → a
    # varredura da véspera é no-op e nenhum disparo de aluno é materializado.
    lembrete_aluno_ativo: bool = False
    lembrete_aluno_hora: str = "18:00"        # véspera, BRT — hora fixa (§1)
    email_envios_por_segundo: float = 5.0     # espaçamento entre envios em lote
    lembretes_orcamento_segundos: int = 240   # teto de duração de uma rodada
    email_teto_diario: int = 150              # sandbox do SES corta em 200/24h

    # Webhook de eventos do SES (SNS → app/routes/email_eventos.py). O SNS não
    # manda header customizado: a autenticação é o token no path + o ARN
    # conferido contra o tópico esperado.
    ses_sns_topic_arn: str = ""
    ses_webhook_token: str = ""

    # HMAC do link de descadastro do rodapé. Vazio → cai no jwt_secret_key.
    lembrete_token_secret: str = ""

    # Segredo compartilhado com o scheduler da AWS (header X-Scheduler-Secret).
    # Mesmo valor do parâmetro SSM /sas/scheduler/secret — ver infra/README.md.
    scheduler_secret: str = ""

    @property
    def segredo_lembrete(self) -> str:
        """Chave do HMAC do descadastro — dedicada se houver, senão a do JWT."""
        return self.lembrete_token_secret or self.jwt_secret_key

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
