"""Configuração do MCP da coordenação — env `MCP_*` — e o guard de boot dele.

Classe própria, e não campos novos em `app/config.py`, porque são DOIS
leitores com necessidades opostas: a API lê daqui o que a tela de Conexões
de IA precisa (`habilitado`, `emissao_so_administrador`, `url_publica`) e o
que o authorization server do OAuth precisa (`emissor_oauth`, `url_do_app`,
as validades e os tetos, inclusive os do código por e-mail —
routes/oauth_mcp.py, Fase 3), e o processo do MCP lê o resto. O guard também é próprio: o de `app/main.py`
exige JWT_SECRET_KEY, COORDENADOR_SENHA e SCHEDULER_SECRET — segredos que o
MCP NÃO pode ter. Aqui é o contrário: o guard recusa subir se algum deles
estiver no ambiente, porque é o sintoma de `env_file: .env` vazando para o
container (docs/43 §5.2).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from ..config import Settings

#: O default de `Settings.jwt_secret_key` (app/config.py). Qualquer outro
#: valor no processo do MCP quer dizer que o segredo de sessão da API chegou
#: aqui — com ele, o MCP assinaria sessão de coordenação na API.
_JWT_DE_DEV = "dev-secret-change-in-production"
_SENHA_DEMO = "tioleo123"

_HOSTS_LOCAIS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})  # noqa: S104 — lista de recusa, não bind


class ConfiguracaoMcp(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_", env_file=".env", extra="ignore")

    #: O portão de LGPD do docs/43 §5.4. Fora de dev/test o processo NÃO sobe
    #: sem `true` explícito: ligar o MCP manda dado de menor a um provedor de
    #: fora, e isso é decisão, não default de deploy. A API lê o mesmo campo
    #: para dizer à tela se há servidor para onde apontar a IA.
    habilitado: bool = False

    #: O endereço que a IA configura, com o caminho: https://portalsas.online/mcp.
    #: Dele saem o host aceito no header `Host` e o recurso do RFC 9728.
    url_publica: str = ""

    #: Quem conecta uma IA ao SAS: administrador E coordenador, cada um em nome
    #: da própria conta — DECISÃO DO DONO EM 26/10 (de 24/10 até ali, só o
    #: administrador). O administrador continua vendo e revogando todas as
    #: conexões (routes/mcp_tokens.py). `true` volta ao "só o administrador",
    #: que vale para emitir, para aprovar a conexão OAuth E para USAR: o MCP
    #: recusa a chamada de token cuja conta não é, na tabela e agora,
    #: administradora (`servidor._pode_consultar`). A API e o MCP leem cada um o
    #: seu ambiente, e os dois precisam do mesmo valor. O descompasso que DÓI
    #: é religar a regra só na API, onde mora a tela: ela passa a dizer "só o
    #: administrador" e recusa emitir, mas o MCP, sem a chave, continua
    #: servindo os tokens pessoais que coordenadores já tinham — por até 90
    #: dias, com o nome dos alunos (revisão de 26/10). O contrário falha
    #: fechado: a tela emite um token que o MCP recusa. Por isso os dois
    #: processos escrevem no log, ao subir, o valor que valeu
    #: (`registrar_no_log`): a conferência é comparar as duas linhas.
    emissao_so_administrador: bool = False

    #: O MCP devolve o NOME do aluno — DECISÃO DO DONO EM 26/10 (era a
    #: matrícula, "Aluno 2026001"). O pseudonimizador fica como opção: `false`
    #: volta a trocar o nome pela matrícula (`pseudonimo.py`) e tira do
    #: catálogo as tools que só servem com o nome
    #: (`catalogo.SO_COM_NOME_DO_ALUNO`). Os tetos de minimização valem nos dois
    #: modos (`teto_de_linhas`). ⚠️ Nome de aluno é dado de ADOLESCENTE indo a
    #: um provedor de IA de fora da escola: pede a base legal do art. 14 da LGPD
    #: (tratamento no melhor interesse do adolescente), registrada antes de o
    #: MCP subir em produção — é o portão do docs/43 §5.4 (`habilitado`).
    mostrar_nome_do_aluno: bool = True

    #: Chamadas de tool por minuto, por token. Em memória: vale porque o MCP é
    #: UM processo (o mesmo raciocínio do limite de login em routes/auth.py).
    limite_por_minuto: int = Field(default=120, gt=0)

    #: Tokens no formato do SAS recusados por minuto, POR IP, antes de o MCP
    #: parar de perguntar ao banco por aquele IP (`app.FalhasDeTokenPorIp`).
    #: O formato é público e cada token custa uma ida à RPC no pool de 3 do
    #: postgrest_mcp — o mesmo das tools. Cliente legítimo erra token uma ou
    #: duas vezes, não vinte.
    falhas_de_token_por_minuto: int = Field(default=20, gt=0)

    #: Requisições por minuto, por token, de QUALQUER método — initialize,
    #: tools/list, prompts/*, ping —, cada uma conferida pela RPC no mesmo
    #: pool das tools (`app.RequisicoesPorToken`). O dobro do limite de
    #: tools/call: quem só consulta bate antes no de cima, que responde com a
    #: mensagem ao modelo e uma linha de auditoria; este é o teto de quem
    #: martela o resto, e responde 429 sem ir ao banco.
    requisicoes_por_minuto: int = Field(default=240, gt=0)

    #: Teto dos parâmetros de limite (`limite`, `k`) de toda tool exposta —
    #: minimização, LGPD art. 6º, III. As tools não têm teto próprio
    #: (`listar_alunos` aceitava `limite=1000`).
    teto_de_linhas: int = Field(default=50, gt=0)

    #: Validade do token pessoal emitido pela tela. 0 = não expira. Um token
    #: esquecido num notebook é acesso à base de menores até alguém lembrar de
    #: revogar; vencer sozinho é o lado seguro do esquecimento.
    validade_do_token_dias: int = Field(default=90, ge=0)

    #: Valores aceitos no header `Host` (proteção de DNS rebinding do SDK),
    #: separados por vírgula; `host:*` aceita qualquer porta. Vazio = o host
    #: de `url_publica`, e em dev/test também localhost e 127.0.0.1.
    hosts_permitidos: str = ""

    #: Valores aceitos no header `Origin`, separados por vírgula. Vazio = só
    #: requisição SEM Origin (Claude Code, mcp-remote e os conectores falam de
    #: servidor, não de browser). Origin de browser fora da lista leva 403.
    origens_permitidas: str = ""

    #: `forwarded_allow_ips` do uvicorn: de quem o X-Forwarded-For é aceito.
    #: Em produção só o nginx alcança o MCP, como a API (infra/vps), e aí
    #: `*` é o certo; sem isso a auditoria grava o IP do nginx.
    ips_do_proxy: str = "127.0.0.1"

    #: Fase 3 (OAuth): o authorization server, que mora NA API. Vazio = sem
    #: OAuth — o MCP não publica o metadado do RFC 9728, para não mandar o
    #: cliente procurar um servidor de autorização que não existe.
    #:
    #: É o `issuer` do RFC 8414: a URL da API vista de FORA, com o caminho —
    #: https://portalsas.online/api. Os DOIS processos leem este valor, cada um
    #: no seu ambiente: a API publica com ele o metadado e os endpoints
    #: (`{emissor}/oauth/token`…), e o MCP o anuncia em `authorization_servers`
    #: do RFC 9728. Os dois textos têm de ser IDÊNTICOS — o cliente compara, e
    #: uma barra a mais já o faz descartar o metadado (RFC 8414 §3.3). Por isso
    #: ninguém lê o campo cru: lê `emissor`, que tira a barra final.
    emissor_oauth: str = ""

    #: A raiz do SAS no browser (https://portalsas.online), onde mora a tela de
    #: consentimento — rota React, não página da API (docs/43 §5.3). O
    #: /oauth/authorize manda a coordenadora para `{url_do_app}/conectar-ia?pedido=<id>`.
    url_do_app: str = ""

    #: Quanto vale o access token que o OAuth emite (uma linha de `token_mcp`
    #: com origem `oauth`). Curto de propósito: é ele que viaja a cada chamada
    #: e fica nos logs do provedor; o que dura é o refresh, que só vai ao
    #: /oauth/token.
    validade_do_acesso_oauth_minutos: int = Field(default=60, gt=0, le=24 * 60)

    #: Quanto vale a CONEXÃO OAuth, contada da APROVAÇÃO. O refresh gira a cada
    #: uso (o velho morre), mas o novo herda o prazo do velho: no fim dele a
    #: coordenadora aprova de novo. Um prazo que se renovasse com o uso seria
    #: acesso sem fim à base de menores — o mesmo motivo de o token pessoal
    #: vencer sozinho (`validade_do_token_dias`).
    validade_do_refresh_oauth_dias: int = Field(default=30, gt=0, le=365)

    #: Tetos por IP nas portas ABERTAS do OAuth, em memória (a API é um
    #: processo só — UVICORN_WORKERS=1, CLAUDE.md armadilha 5). O cadastro
    #: dinâmico (RFC 7591) não pede credencial: sem teto, qualquer um enche
    #: `oauth_cliente_mcp`. O /oauth/token e o /oauth/revoke dividem o segundo;
    #: o /oauth/authorize, que grava pedido, tem o dele com o mesmo número.
    #: Um conector de verdade cadastra uma vez e troca token uma vez por hora.
    oauth_cadastros_por_hora: int = Field(default=20, gt=0)
    oauth_tentativas_por_minuto: int = Field(default=60, gt=0)

    #: Cadastros por hora NO TOTAL, de todos os IPs, contados no banco. O teto
    #: por IP de cima limita um endereço; com muitos, `oauth_cliente_mcp`
    #: crescia sem limite — cada cadastro é uma linha de até ~16 KiB, no banco
    #: dos alunos (revisão final de 26/10). A casa conecta poucos apps, e cada
    #: um cadastra uma vez. Com a faxina abaixo, o pior caso fica em
    #: 30 × 24 × 7 ≈ 5 mil linhas (~80 MB), em vez de sem fim.
    oauth_cadastros_por_hora_no_total: int = Field(default=30, gt=0)

    #: Dias que um cliente cadastrado e NUNCA usado — nenhum pedido, nenhuma
    #: conexão — fica no banco antes de o próprio /oauth/register o apagar
    #: (`routes/oauth_mcp.FAXINA_DOS_CLIENTES`). O conector de verdade
    #: cadastra e manda ao /authorize no mesmo minuto; o que passou uma semana
    #: sem um pedido é lixo, ou é de um app que se cadastra de novo.
    oauth_dias_do_cliente_sem_uso: int = Field(default=7, gt=0)

    #: Pedidos do /oauth/authorize ABERTOS (nem decididos, nem vencidos) ao
    #: mesmo tempo, por app e no total. O /authorize é anônimo e cada pedido é
    #: uma linha de `oauth_pedido_mcp`, de até ~4 KB que quem pede escolhe: o
    #: teto por IP acima limita a VELOCIDADE, não o volume, e um IP sozinho
    #: gravava ~375 MB/dia no banco dos alunos (revisão de segurança de 25/10).
    #: A coordenadora que conecta um app abre UM pedido; dez é folga para quem
    #: tenta de novo, e duzentos, a casa inteira ao mesmo tempo — ~1 MB no pior
    #: caso. Os vencidos sem decisão o próprio /authorize apaga
    #: (`routes/oauth_mcp.FaxinaDosPedidos`).
    oauth_pedidos_abertos_por_cliente: int = Field(default=10, gt=0)
    oauth_pedidos_abertos_no_total: int = Field(default=200, gt=0)

    #: Os tetos do código que aprova a conexão OAuth, enviado ao e-mail da
    #: conta de IA (decisão de 26/10, routes/oauth_mcp.py). Em memória, como os
    #: de cima, e contados para QUALQUER e-mail digitado — cadastrado ou não —,
    #: senão o próprio 429 contaria quais estão cadastrados. Cada código aceita
    #: 5 tentativas (`emails_ia.TENTATIVAS_POR_CODIGO`), então é o teto POR
    #: E-MAIL que limita o chute: 10 códigos por dia são 50 chutes num milhão.
    #: Quem conecta pede um código por app, dois se errar o e-mail.
    oauth_codigos_por_pedido: int = Field(default=5, gt=0)
    oauth_codigos_por_email_por_dia: int = Field(default=10, gt=0)
    oauth_codigos_por_ip_por_hora: int = Field(default=20, gt=0)

    @property
    def emissor(self) -> str:
        """O `issuer` como a API o publica e o MCP o anuncia: sem barra final."""
        return self.emissor_oauth.strip().rstrip("/")

    @property
    def recurso(self) -> str:
        """O identificador do recurso protegido (RFC 8707, RFC 9728): a URL
        pública do MCP sem barra final — a forma que a especificação do MCP
        recomenda e a que o cliente manda em `resource`."""
        return self.url_publica.strip().rstrip("/")

    @property
    def oauth_ligado(self) -> bool:
        """Há OAuth neste ambiente: emissor, recurso e tela de consentimento."""
        return bool(self.emissor and self.recurso and self.url_do_app.strip())

    @property
    def lista_de_origens(self) -> list[str]:
        return _separar(self.origens_permitidas)

    def lista_de_hosts(self, app_env: str) -> list[str]:
        """Os hosts aceitos. Lista vazia recusa tudo com 421 — falha fechada."""
        explicitos = _separar(self.hosts_permitidos)
        if explicitos:
            return explicitos
        hosts: list[str] = []
        partes = urlsplit(self.url_publica) if self.url_publica else None
        if partes is not None and partes.netloc:
            hosts.append(partes.netloc.rsplit("@", 1)[-1])
        if app_env in ("dev", "test"):
            hosts += ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"]
        return hosts


def _separar(texto: str) -> list[str]:
    return [p.strip() for p in texto.split(",") if p.strip()]


@lru_cache
def get_configuracao_mcp() -> ConfiguracaoMcp:
    return ConfiguracaoMcp()


Processo = Literal["api", "mcp"]


def registrar_no_log(config: ConfiguracaoMcp, processo: Processo) -> None:
    """Uma linha INFO por chave que a API e o MCP leem CADA UM do seu ambiente
    e que decide quem vê o quê: o valor EFETIVO, depois de default e `.env`.

    A divergência não dá erro em lugar nenhum — a tela aprova o que o MCP
    recusa, ou afirma um corte que o MCP não fez (`emissao_so_administrador`).
    Com as duas linhas no log, quem sobe o deploy compara uma com a outra.
    Só booleanos: nada de URL, host ou segredo aqui.
    """
    log = logging.getLogger("sas.mcp.configuracao")
    log.info(
        "%s: MCP_EMISSAO_SO_ADMINISTRADOR=%s (valor efetivo)",
        processo, "true" if config.emissao_so_administrador else "false",
    )
    log.info(
        "%s: MCP_MOSTRAR_NOME_DO_ALUNO=%s (valor efetivo)",
        processo, "true" if config.mostrar_nome_do_aluno else "false",
    )


Modo = Literal["http", "stdio"]


def validar_configuracao_do_mcp(config: ConfiguracaoMcp, settings: Settings, modo: Modo = "http") -> None:
    """Recusa subir o MCP com configuração insegura — o par do guard de main.py.

    Pula em dev/test, como o de lá. Fora deles junta TODOS os problemas e
    levanta um RuntimeError com a lista, para o deploy mostrar tudo de uma vez.
    """
    if settings.app_env in ("dev", "test"):
        return

    problemas: list[str] = []

    if not config.habilitado:
        problemas.append(
            "MCP_HABILITADO não é true — o portão de LGPD (docs/43 §5.4) é decisão "
            "explícita, não default de deploy"
        )

    if modo == "stdio":
        # No stdio o processo roda na máquina de QUEM CHAMA: o pseudônimo, o
        # teto e o limite seriam lidos do ambiente dele, e o acesso ao dado é
        # o anônimo do postgrest_mcp — que teria de estar alcançável de lá, e
        # aí entregaria a lista branca sem token nenhum. O token só rotularia
        # a auditoria. Fora de dev, o Claude Desktop conecta pelo `mcp-remote`
        # sobre o HTTP (docs/43 §5.3), com os controles do lado do servidor.
        problemas.append(
            "--stdio só em dev/test — em produção a IA conecta pelo HTTP "
            "(`mcp-remote` no Claude Desktop), onde os controles são do servidor"
        )

    # O dado. O MCP só pode falar com o PostgREST DELE, cujo anônimo é o
    # sas_mcp: o da API tem o sas_service, com acesso total (docs/43 §5.2).
    # O nome do host é só o aviso rápido, sem rede: `postgrest.`, o nome do
    # container e o IP passam por ele. Quem garante é a sonda de privilégio
    # do boot (`dados.exigir_papel_restrito`).
    if not settings.postgrest_url:
        problemas.append("POSTGREST_URL vazia — aponte para o postgrest_mcp")
    elif (urlsplit(settings.postgrest_url).hostname or "").rstrip(".") == "postgrest":
        problemas.append(
            "POSTGREST_URL aponta para o `postgrest` da API, cujo papel anônimo é o "
            "sas_service (acesso total) — use o postgrest_mcp"
        )
    if settings.postgrest_token:
        # O postgrest_mcp não tem PGRST_JWT_SECRET, então recusa todo Bearer.
        # Um token aqui só funciona contra OUTRO PostgREST — e um JWT com
        # role=sas_service tiraria o MCP do papel restrito.
        problemas.append(
            "POSTGREST_TOKEN preenchido — o postgrest_mcp não aceita JWT; token aqui é "
            "sinal de que o processo aponta para outro PostgREST"
        )

    vazados = segredos_da_api_no_ambiente(settings)
    if vazados:
        problemas.append(
            "segredos da API no ambiente do MCP (" + ", ".join(vazados) + ") — o "
            "serviço não pode ter env_file com o .env da API"
        )

    if modo == "http":
        problemas += _problemas_da_url(config.url_publica)
        if not config.lista_de_hosts(settings.app_env):
            problemas.append("nenhum host permitido — defina MCP_URL_PUBLICA ou MCP_HOSTS_PERMITIDOS")
        # O MCP anuncia o emissor no RFC 9728: um emissor em http mandaria o
        # conector trocar código e refresh em claro.
        problemas += problemas_do_emissor(config, settings.app_env)

    if problemas:
        raise RuntimeError(
            f"Configuração insegura do MCP para APP_ENV={settings.app_env}:\n  - "
            + "\n  - ".join(problemas)
            + "\n\nCorrija as variáveis, ou declare APP_ENV=dev se for ambiente local."
        )


def _problemas_da_url(url: str) -> list[str]:
    if not url:
        return ["MCP_URL_PUBLICA vazia — é o endereço que a IA configura e o host aceito"]
    partes = urlsplit(url)
    problemas: list[str] = []
    if partes.scheme != "https":
        problemas.append("MCP_URL_PUBLICA sem https — o token pessoal viajaria em claro")
    host = (partes.hostname or "").lower()
    if not host or host in _HOSTS_LOCAIS or host.endswith(".localhost"):
        problemas.append("MCP_URL_PUBLICA aponta para localhost")
    return problemas


def _https_de_fora(nome: str, url: str) -> list[str]:
    partes = urlsplit(url)
    problemas: list[str] = []
    if partes.scheme != "https":
        problemas.append(f"{nome} sem https — código, token e refresh do OAuth viajariam em claro")
    host = (partes.hostname or "").lower()
    if not host or host in _HOSTS_LOCAIS or host.endswith(".localhost"):
        problemas.append(f"{nome} aponta para localhost")
    return problemas


def problemas_do_emissor(config: ConfiguracaoMcp, app_env: str) -> list[str]:
    """O que torna o `issuer` inválido. Vazia = ok, ou OAuth desligado.

    Query e fragmento valem em qualquer ambiente: o RFC 8414 §2 os proíbe no
    issuer, e o cliente monta o endereço do metadado inserindo o caminho
    dele. https e "não é localhost", só fora de dev/test, como o resto deste
    guard.
    """
    if not config.emissor:
        return []
    partes = urlsplit(config.emissor)
    problemas: list[str] = []
    if partes.query or partes.fragment:
        problemas.append("MCP_EMISSOR_OAUTH com query ou fragmento — o RFC 8414 §2 os proíbe no issuer")
    if not partes.scheme or not partes.hostname:
        problemas.append("MCP_EMISSOR_OAUTH não é uma URL absoluta")
    if app_env not in ("dev", "test"):
        problemas += _https_de_fora("MCP_EMISSOR_OAUTH", config.emissor)
    return problemas


def problemas_do_oauth(config: ConfiguracaoMcp, app_env: str) -> list[str]:
    """O que impede a API de servir o OAuth com segurança. Vazia = pode.

    Quem chama é `routes/oauth_mcp.py`, a cada requisição: com problema, o
    OAuth fica DESLIGADO (404, como se não existisse) e o motivo vai para o
    log. Falha fechada sem derrubar a API — o guard de boot dela (main.py) é
    de outro dono e não conhece o MCP.
    """
    if not config.emissor:
        return []
    problemas = problemas_do_emissor(config, app_env)
    if not config.recurso:
        problemas.append("MCP_URL_PUBLICA vazia — sem ela não há recurso para o OAuth proteger")
    if not config.url_do_app.strip():
        problemas.append("MCP_URL_DO_APP vazia — o /oauth/authorize não teria para onde mandar a coordenadora")
    elif app_env not in ("dev", "test"):
        problemas += _https_de_fora("MCP_URL_DO_APP", config.url_do_app.strip())
    return problemas


def segredos_da_api_no_ambiente(settings: Settings) -> list[str]:
    """Os segredos da API que estão preenchidos neste processo, pelo NOME.

    Nenhum deles serve ao MCP. Achar um é achar o `.env` da API no ambiente —
    e o que importa nele não é a OpenAI: é a JWT_SECRET_KEY, que assina sessão
    de coordenação, e as credenciais que escrevem no Canvas e na AWS.
    """
    vazados: list[str] = []
    if settings.jwt_secret_key and settings.jwt_secret_key != _JWT_DE_DEV:
        vazados.append("JWT_SECRET_KEY")
    if settings.coordenador_senha and settings.coordenador_senha != _SENHA_DEMO:
        vazados.append("COORDENADOR_SENHA")
    for nome, valor in (
        ("SCHEDULER_SECRET", settings.scheduler_secret),
        ("SUPABASE_SERVICE_KEY", settings.supabase_service_key),
        ("OPENAI_API_KEY", settings.openai_api_key),
        ("CANVAS_API_TOKEN", settings.canvas_api_token),
        ("CANVAS_CLIENT_SECRET", settings.canvas_client_secret),
        ("AWS_SECRET_ACCESS_KEY", settings.aws_secret_access_key),
        ("AWS_SES_SECRET_ACCESS_KEY", settings.aws_ses_secret_access_key),
        ("LEMBRETE_TOKEN_SECRET", settings.lembrete_token_secret),
        ("YOUTUBE_CLIENT_SECRET", settings.youtube_client_secret),
        ("YOUTUBE_REFRESH_TOKEN", settings.youtube_refresh_token),
    ):
        if valor:
            vazados.append(nome)
    return vazados
