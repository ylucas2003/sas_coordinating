"""O app HTTP do MCP: Starlette com `/mcp` e `/health` (docs/43 §5.1).

  /mcp     Streamable HTTP, STATELESS e em JSON. Stateless porque as tools só
           leem e o MCP é um processo só: não há o que guardar entre
           requisições, e o modo sem sessão não é afetado pelos dois avisos
           de segurança de sessão do SDK (sessões sem limite; sessão aceitando
           credencial de outro principal). JSON porque nenhuma tool manda
           progresso — a resposta é uma só.
  /health  liveness, sem banco e sem token — é o HEALTHCHECK herdado da
           imagem da API (api/Dockerfile), que chama 127.0.0.1:8000/health.

As camadas de um POST /mcp, de fora para dentro:

  1. id de requisição (o mesmo middleware da API: X-Request-Id, linha de log);
  2. Bearer, SÓ na rota /mcp: `AutenticacaoDoMcp` com o `VerificadorDeToken`,
     que confere o sha256 do token pela RPC `mcp_conferir_token` A CADA
     requisição — sem cache, porque revogar promete que "a próxima consulta
     já é recusada". Só na rota porque cada token no formato custa uma ida
     ao banco: no app inteiro, /health e caminho inexistente também custavam
     (revisão de 24/10). E com dois tetos, os dois com 429 sem ir ao banco:
     o de tokens recusados por IP (`FalhasDeTokenPorIp`) e o de requisições
     por token, de qualquer método (`RequisicoesPorToken`);
  3. `RequireAuthMiddleware`: sem token válido, 401 com `WWW-Authenticate`;
  4. só POST: GET abriria um SSE que no modo stateless nunca fecha (o
     servidor não tem o que mandar por ele), e a especificação manda
     responder 405 a quem não oferece o stream;
  5. o transporte do SDK, com a proteção de DNS rebinding LIGADA — sem
     `TransportSecuritySettings` ela vem desligada (transport_security.py).

Fase 3 (OAuth): com `MCP_EMISSOR_OAUTH`, o app publica o metadado do RFC 9728
em DOIS caminhos — `/.well-known/oauth-protected-resource/mcp` (o do RFC 9728
§3.1, com o caminho do recurso inserido) e a raiz
`/.well-known/oauth-protected-resource` (para onde a especificação do MCP manda
o cliente que não acha o primeiro) — e o 401 passa a apontar para o primeiro no
`WWW-Authenticate` (`resource_metadata`). O documento é montado aqui, e não pelo
`create_protected_resource_routes` do SDK, por três motivos: o SDK publica um
caminho só, o `AnyHttpUrl` dele põe barra final num emissor sem caminho
(`https://portalsas.online/`), e o cliente compara `authorization_servers` com o
`issuer` do metadado da API letra por letra (RFC 8414 §3.3). As rotas do
authorization server moram na API (routes/oauth_mcp.py), não aqui; o access
token que ele emite é uma linha de `token_mcp`, conferida pela mesma RPC.
"""

from __future__ import annotations

import contextlib
import logging
import time
from collections import OrderedDict, deque
from collections.abc import AsyncIterator, Callable
from typing import Any
from urllib.parse import urlsplit

from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend, RequireAuthMiddleware
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.routes import cors_middleware
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.authentication import AuthCredentials, AuthenticationError, BaseUser
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import HTTPConnection, Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Route
from starlette.types import Receive, Scope, Send

from ..config import get_settings
from ..observabilidade import middleware_request_id
from ..supabase_client import criar_cliente_supabase
from . import tokens
from .configuracao import ConfiguracaoMcp, get_configuracao_mcp
from .dados import CriarCliente
from .servidor import ESCOPO_DE_LEITURA, acesso_da_identidade, conferir_em_thread, montar_servidor

log = logging.getLogger("sas.mcp.app")


class ConferenciaIndisponivel(AuthenticationError):
    """O banco não respondeu à conferência do token. Vira 503, não 401: um 401
    mandaria o cliente refazer a autenticação por um problema que é nosso."""


class TentativasDemais(AuthenticationError):
    """O IP passou do teto de tokens recusados. Vira 429, sem ir ao banco."""


class RequisicoesDemais(AuthenticationError):
    """O token passou do teto de requisições por minuto. Vira 429, sem ir ao banco."""


class FalhasDeTokenPorIp:
    """Quantos tokens no formato do SAS cada IP errou no último minuto.

    O formato é público (`sas_mcp_` + 43) e cada token nele custa uma thread e
    uma ida à RPC, no pool de 3 conexões do postgrest_mcp — o mesmo das tools.
    Sem teto, uma rajada de tokens inventados derruba as consultas de quem tem
    token de verdade (revisão de 24/10). Passado o teto, o IP fica um minuto
    sem chegar ao banco.

    ⚠️ Atrás do nginx, o IP só é o de quem chama com MCP_IPS_DO_PROXY certo.
    Errado, todo mundo tem o IP do nginx e o teto vira um balde só — o motivo
    de o login (routes/auth.py) chavear por ip:usuario. Aqui não há usuário
    antes do banco; o que impede o balde único de trancar todo mundo é a
    ISENÇÃO: token que o banco aceitou há pouco nunca é barrado. A isenção não
    é cache de conferência — ele continua sendo conferido a cada requisição, e
    revogar vale na hora. O limite de verdade, por IP real, é o do nginx.

    Em memória e sem trava pelo mesmo motivo do `LimitePorMinuto`: um processo
    só, e nenhum `await` entre ler e gravar.
    """

    JANELA_S = 60.0
    #: Por quanto tempo um token aceito fica isento do teto.
    ISENCAO_S = 3600.0
    #: Teto de memória: IPs (e tokens isentos) além disto saem pelo mais antigo.
    MAXIMO_DE_CHAVES = 10_000

    def __init__(self, por_minuto: int, *, relogio: Callable[[], float] = time.monotonic) -> None:
        self.por_minuto = por_minuto
        self._relogio = relogio
        self._falhas: OrderedDict[str, deque[float]] = OrderedDict()
        self._aceitos: OrderedDict[str, float] = OrderedDict()

    def _recentes(self, ip: str, agora: float) -> deque[float]:
        fila = self._falhas.pop(ip, None) or deque()
        while fila and fila[0] <= agora - self.JANELA_S:
            fila.popleft()
        return fila

    def barrado(self, ip: str, hash_do_token: str) -> bool:
        agora = self._relogio()
        aceito_em = self._aceitos.get(hash_do_token)
        if aceito_em is not None and agora - aceito_em < self.ISENCAO_S:
            return False
        if ip not in self._falhas:
            return False
        fila = self._recentes(ip, agora)
        if fila:
            self._falhas[ip] = fila
        return len(fila) >= self.por_minuto

    def recusado(self, ip: str, hash_do_token: str) -> bool:
        """Conta a recusa. True quando ela é a que fecha o teto (para logar uma vez só)."""
        agora = self._relogio()
        self._aceitos.pop(hash_do_token, None)
        fila = self._recentes(ip, agora)
        fila.append(agora)
        self._falhas[ip] = fila
        while len(self._falhas) > self.MAXIMO_DE_CHAVES:
            self._falhas.popitem(last=False)
        return len(fila) == self.por_minuto

    def aceito(self, hash_do_token: str) -> None:
        self._aceitos.pop(hash_do_token, None)
        self._aceitos[hash_do_token] = self._relogio()
        while len(self._aceitos) > self.MAXIMO_DE_CHAVES:
            self._aceitos.popitem(last=False)


class RequisicoesPorToken:
    """Quantas requisições cada token fez no último minuto, QUALQUER método.

    O `LimitePorMinuto` do servidor só conta tools/call. Todo o resto —
    initialize, tools/list, prompts/*, ping, o GET do SSE — também passa pela
    RPC `mcp_conferir_token`, no pool de 3 conexões do postgrest_mcp que as
    tools usam, e o token aceito fica isento do `FalhasDeTokenPorIp`: sem
    este teto, um cliente com token ocupava o pool à vontade e atrasava as
    consultas de todo mundo (revisão final de 26/10, 150 tools/list em 0,9 s).

    Conta ANTES da conferência, pelo hash do token, para a requisição barrada
    não chegar ao banco — e conta na mesma volta do event loop em que confere
    o teto, sem `await` no meio, para uma rajada simultânea não passar inteira.
    Token inventado também conta, e por isso o teto de memória: quem chega com
    token que não existe é assunto do `FalhasDeTokenPorIp`, por IP.

    Em memória e sem trava pelo mesmo motivo do `LimitePorMinuto`: um
    processo só, e nenhum `await` entre ler e gravar.
    """

    JANELA_S = 60.0
    #: Teto de memória: tokens além disto saem pelo mais antigo.
    MAXIMO_DE_CHAVES = 10_000

    def __init__(self, por_minuto: int, *, relogio: Callable[[], float] = time.monotonic) -> None:
        self.por_minuto = por_minuto
        self._relogio = relogio
        self._por_token: OrderedDict[str, deque[float]] = OrderedDict()

    def admitir(self, hash_do_token: str) -> bool:
        agora = self._relogio()
        fila = self._por_token.pop(hash_do_token, None) or deque()
        while fila and fila[0] <= agora - self.JANELA_S:
            fila.popleft()
        admitida = len(fila) < self.por_minuto
        if admitida:
            fila.append(agora)
        self._por_token[hash_do_token] = fila
        while len(self._por_token) > self.MAXIMO_DE_CHAVES:
            self._por_token.popitem(last=False)
        return admitida


def _token_do_cabecalho(conn: HTTPConnection) -> str | None:
    # O mesmo recorte do `BearerAuthBackend` do SDK: é este texto que ele
    # passa ao verificador, então é dele que sai o hash do teto.
    cabecalho = conn.headers.get("authorization")
    if not cabecalho or not cabecalho.lower().startswith("bearer "):
        return None
    return cabecalho[7:]


class AutenticacaoDoMcp(BearerAuthBackend):
    """O `BearerAuthBackend` do SDK com os dois tetos na frente da conferência:
    `FalhasDeTokenPorIp` (token recusado, por IP) e `RequisicoesPorToken`
    (toda requisição, por token)."""

    def __init__(
        self, verificador: VerificadorDeToken, falhas: FalhasDeTokenPorIp, requisicoes: RequisicoesPorToken
    ) -> None:
        super().__init__(verificador)
        self._falhas = falhas
        self._requisicoes = requisicoes

    async def authenticate(self, conn: HTTPConnection) -> tuple[AuthCredentials, BaseUser] | None:
        token = _token_do_cabecalho(conn)
        if token is None or not tokens.formato_valido(token):
            # Sem custo: fora do formato nem thread nem banco
            # (`conferir_em_thread`). O SDK devolve "sem usuário" → 401.
            return await super().authenticate(conn)
        ip = conn.client.host if conn.client else "-"
        hash_do_token = tokens.hash_do_token(token)
        if self._falhas.barrado(ip, hash_do_token):
            raise TentativasDemais("tokens recusados demais a partir deste IP")
        if not self._requisicoes.admitir(hash_do_token):
            raise RequisicoesDemais("requisições demais com este token")
        resultado = await super().authenticate(conn)
        if resultado is None:
            if self._falhas.recusado(ip, hash_do_token):
                # O IP no texto: o formatador da casa só escreve os extras
                # que conhece (observabilidade.py), e `ip` não é um deles.
                log.warning(
                    "IP %s passou de %d tokens recusados por minuto: fica sem conferência por um minuto",
                    ip,
                    self._falhas.por_minuto,
                )
        else:
            self._falhas.aceito(hash_do_token)
        return resultado


class VerificadorDeToken:
    """O `TokenVerifier` do SDK sobre `tokens.conferir` (docs/43 §5.3)."""

    def __init__(self, criar_cliente: CriarCliente = criar_cliente_supabase) -> None:
        self._criar_cliente = criar_cliente

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            identidade = await conferir_em_thread(token, self._criar_cliente)
        except Exception:
            log.warning("não consegui conferir o token do MCP", exc_info=True)
            raise ConferenciaIndisponivel("conferência de token indisponível") from None
        if identidade is None:
            return None
        return acesso_da_identidade(token, identidade)


def _quando_a_conferencia_falha(conn: HTTPConnection, exc: AuthenticationError) -> Response:
    if isinstance(exc, TentativasDemais):
        return JSONResponse(
            {
                "error": "too_many_requests",
                "error_description": "Tokens recusados demais a partir deste endereço. Espere um minuto.",
            },
            status_code=429,
            headers={"Retry-After": str(int(FalhasDeTokenPorIp.JANELA_S))},
        )
    if isinstance(exc, RequisicoesDemais):
        return JSONResponse(
            {
                "error": "too_many_requests",
                "error_description": "Requisições demais com esta conexão. Espere um minuto.",
            },
            status_code=429,
            headers={"Retry-After": str(int(RequisicoesPorToken.JANELA_S))},
        )
    return JSONResponse(
        {
            "error": "temporarily_unavailable",
            "error_description": "Não consegui conferir o token agora. Tente de novo em instantes.",
        },
        status_code=503,
        headers={"Retry-After": "30"},
    )


class _SoPost:
    """Só POST chega ao transporte; o resto leva 405 com `Allow: POST`.

    Classe, e não função: o Starlette trata endpoint função como
    request/response só de GET (starlette/routing.py) — o POST voltaria 405.
    """

    def __init__(self, gerente: StreamableHTTPSessionManager) -> None:
        self._gerente = gerente

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("method") != "POST":
            await Response(status_code=405, headers={"Allow": "POST"})(scope, receive, send)
            return
        await self._gerente.handle_request(scope, receive, send)


async def _saude(request: Request) -> JSONResponse:
    # LIVENESS, como o /health da API: sem banco, para um PostgREST fora do ar
    # não fazer o Docker reiniciar o MCP em laço — o que não consertaria nada.
    return JSONResponse({"status": "ok"})


# ─── RFC 9728: o metadado do recurso protegido ───────────────────────────

_RAIZ_DO_METADADO = "/.well-known/oauth-protected-resource"
NOME_DO_RECURSO = "SAS — coordenação"


def caminhos_do_metadado_do_recurso(recurso: str) -> list[str]:
    """Onde o metadado é servido: o do RFC 9728 §3.1 primeiro, a raiz depois.

    `https://portalsas.online/mcp` → `/.well-known/oauth-protected-resource/mcp`
    e `/.well-known/oauth-protected-resource`. Recurso sem caminho tem um só.
    """
    caminho = urlsplit(recurso).path.rstrip("/")
    return [_RAIZ_DO_METADADO + caminho, _RAIZ_DO_METADADO] if caminho else [_RAIZ_DO_METADADO]


def url_do_metadado_do_recurso(recurso: str) -> str:
    """A URL absoluta que o 401 anuncia em `resource_metadata` (RFC 9728 §5.1)."""
    partes = urlsplit(recurso)
    return f"{partes.scheme}://{partes.netloc}{caminhos_do_metadado_do_recurso(recurso)[0]}"


def metadado_do_recurso(config: ConfiguracaoMcp) -> dict[str, Any]:
    """O documento do RFC 9728, com as strings EXATAS de configuracao.py.

    `resource` é a URL pública do MCP — a mesma que o conector manda em
    `resource` (RFC 8707) e que o /oauth/authorize da API confere. E
    `authorization_servers` é `config.emissor`, o MESMO texto que a API
    publica como `issuer`: os dois processos leem MCP_EMISSOR_OAUTH, e a
    barra final sai nos dois pelo mesmo `emissor`.
    """
    return {
        "resource": config.recurso,
        "authorization_servers": [config.emissor],
        "scopes_supported": [ESCOPO_DE_LEITURA],
        "bearer_methods_supported": ["header"],
        "resource_name": NOME_DO_RECURSO,
    }


def _rotas_do_metadado_do_recurso(config: ConfiguracaoMcp) -> list[BaseRoute]:
    documento = metadado_do_recurso(config)

    async def _metadado(request: Request) -> JSONResponse:
        # Público e sem banco: é o que o cliente lê ANTES de ter token. CORS
        # aberto como no SDK, para cliente de browser (o MCP Inspector).
        return JSONResponse(documento, headers={"Cache-Control": "public, max-age=3600"})

    return [
        Route(caminho, endpoint=cors_middleware(_metadado, ["GET", "OPTIONS"]), methods=["GET", "OPTIONS"])
        for caminho in caminhos_do_metadado_do_recurso(config.recurso)
    ]


def montar_app(
    *,
    config: ConfiguracaoMcp | None = None,
    servidor: Server | None = None,
    criar_cliente: CriarCliente = criar_cliente_supabase,
    app_env: str | None = None,
) -> Starlette:
    """O app ASGI do MCP. Um gerente por app: o `run()` dele só abre uma vez."""
    config = config or get_configuracao_mcp()
    app_env = app_env or get_settings().app_env
    servidor = servidor or montar_servidor(config=config, criar_cliente=criar_cliente)

    gerente = StreamableHTTPSessionManager(
        app=servidor,
        stateless=True,
        json_response=True,
        security_settings=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=config.lista_de_hosts(app_env),
            allowed_origins=config.lista_de_origens,
        ),
    )

    rotas: list[BaseRoute] = [Route("/health", endpoint=_saude, methods=["GET"])]
    metadado: AnyHttpUrl | None = None
    if config.emissor and config.recurso:
        # Com o metadado publicado, o 401 do /mcp aponta para ele no
        # `WWW-Authenticate` (`resource_metadata`, RFC 9728 §5.1): é por ali
        # que o conector descobre o authorization server da API.
        metadado = AnyHttpUrl(url_do_metadado_do_recurso(config.recurso))
        rotas += _rotas_do_metadado_do_recurso(config)
    # A autenticação embrulha SÓ a rota /mcp: /health, o metadado do RFC 9728
    # e caminho inexistente não vão ao banco por token nenhum.
    autenticacao = AutenticacaoDoMcp(
        VerificadorDeToken(criar_cliente),
        FalhasDeTokenPorIp(config.falhas_de_token_por_minuto),
        RequisicoesPorToken(config.requisicoes_por_minuto),
    )
    rotas.append(
        Route(
            "/mcp",
            endpoint=AuthenticationMiddleware(
                RequireAuthMiddleware(_SoPost(gerente), [ESCOPO_DE_LEITURA], metadado),
                backend=autenticacao,
                on_error=_quando_a_conferencia_falha,
            ),
        )
    )

    @contextlib.asynccontextmanager
    async def ciclo_de_vida(_app: Starlette) -> AsyncIterator[None]:
        async with gerente.run():
            yield

    return Starlette(
        routes=rotas,
        middleware=[Middleware(BaseHTTPMiddleware, dispatch=middleware_request_id)],
        lifespan=ciclo_de_vida,
    )
