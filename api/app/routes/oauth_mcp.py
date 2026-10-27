"""O authorization server do OAuth do MCP da coordenação (docs/43 §5.3, Fase 3).

Para os conectores do claude.ai e do ChatGPT, que não aceitam colar um token:
o conector se cadastra sozinho (RFC 7591), manda quem conecta aprovar NO SAS —
com o código enviado ao e-mail da conta de IA (decisão do dono, 26/10) — e
troca o código por um access token. O access token é UMA LINHA DE
`token_mcp` com origem `oauth` (0072): o MCP o confere pela mesma RPC do token
pessoal, sem saber que veio do OAuth, e a tela de Conexões de IA o lista e o
revoga como qualquer outro.

Por que FastAPI direto, e não as rotas do SDK (`mcp.server.auth`):
  1. a API não importa o SDK do MCP — puxaria o servidor inteiro para o
     processo dela (app/mcp/__init__.py); e
  2. as lacunas do SDK 1.30.0, verificadas no mapa de 24/10: "none" fora do
     metadado, `issuer` com barra final, /register recusando cliente sem
     `refresh_token`, /revoke exigindo `client_secret` de cliente público,
     Basic exigindo `client_id` no corpo — e uso único do código, rotação do
     refresh e amarração do `resource` deixados por conta de quem implementa.
  O que importa são os MUST dos RFCs, cada um com teste em tests/test_oauth_mcp.py.

As rotas:
  GET  /.well-known/oauth-authorization-server[/<caminho do emissor>]  RFC 8414
  POST /oauth/register    RFC 7591 — aberto (é o ponto), com teto por IP
  GET  /oauth/authorize   RFC 6749 §4.1, PKCE S256 (RFC 7636), resource (RFC 8707)
  POST /oauth/token       authorization_code; refresh_token com ROTAÇÃO
  POST /oauth/revoke      RFC 7009
  GET  /oauth/pedidos/{id}, POST …/codigo, POST …/aprovar, POST …/recusar — o
       consentimento, que a tela /conectar-ia do front chama. SEM sessão do
       SAS desde 26/10: o claude.ai e o ChatGPT abrem a tela no browser em que
       a IA está e não dizem de quem é a conta; quem aprova prova a POSSE do
       e-mail da conta de IA, cadastrado por um coordenador no card Conexões
       de IA (routes/mcp_emails_ia.py, app/mcp/emails_ia.py).

O caminho de uma conexão:
  /authorize grava um PEDIDO (10 min) e manda o browser para a tela →
  quem conecta digita o e-mail da conta de IA e recebe nele um código de 6
  dígitos → digita o código: o pedido é aprovado em nome do coordenador DONO
  do e-mail → CÓDIGO do RFC (só o hash, uso único, 10 min) →
  /token: uma linha de token_mcp (o access, 1 h) + um REFRESH →
  cada refresh troca o hash da MESMA linha de token_mcp e gira o refresh: o
  access e o refresh antigos morrem na hora. A linha de token_mcp é a CONEXÃO —
  revogá-la na tela derruba os dois, e a lista não ganha uma linha por hora.
  O refresh novo herda o prazo do velho: a conexão vale N dias da aprovação.

MCP_EMISSAO_SO_ADMINISTRADOR (desligado por padrão desde 26/10: administrador e
coordenador conectam) vale aqui como vale no MCP (`servidor._pode_consultar`):
ligado, o código só vai ao e-mail de administrador e só aprova em nome dele.
Ligado ou não, cada troca (código e refresh) reconfere na TABELA que a conta
ainda está ativa e, com a regra ligada, ainda é administradora — rebaixamento
que só valesse no fim da conexão não seria rebaixamento
(`auth.conta_ainda_e_administradora`).

Erros no formato do RFC 6749 §5.2 — `{"error", "error_description"}`, com a
descrição só em ASCII imprimível, porque o RFC proíbe o resto (`_ascii`). No
/authorize, NENHUM erro redireciona sozinho. `client_id` ou `redirect_uri`
ruim, porque o §4.1.2.1 proíbe (seria mandar o browser para um endereço que
ninguém conferiu). O resto, porque o /authorize é anônimo e o cadastro é
aberto: a `redirect_uri` "conferida" é a que o próprio app cadastrou, e um 302
de erro faria de portalsas.online um redirecionador para qualquer site — a
isca de phishing que o RFC 9700 §4.11.2 descreve ("MUST always authenticate
the user first [...] before redirecting"). O erro vira uma página que mostra o
host e oferece o link de volta, com o `state` e o `iss`; quem segue é a
pessoa. Só a resposta dada na tela de consentimento volta ao app: a
aprovação, que pede o código do e-mail, e a recusa, que a pessoa clica vendo o
host — a mesma escolha que o link de volta da página de erro já oferecia sem
login nenhum.

I/O: o consentimento e o metadado são rotas `def` (pool de threads); o
/codigo responde ANTES de procurar o e-mail, e o que depende dele roda numa
tarefa de fundo, depois da resposta (`_preparar_codigo`). As quatro portas do
protocolo são `async def` — leem o corpo cru com teto e aplicam o teto por IP
no loop, antes de gastar thread —, e todo acesso delas ao banco vai por
`asyncio.to_thread`: o event loop da API é um só (UVICORN_WORKERS=1,
api/CLAUDE.md).
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
import html
import ipaddress
import json
import logging
import re
import secrets
import threading
import time
import unicodedata
import uuid
from collections import OrderedDict, deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, unquote_plus, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from ..auditoria import registrar as auditar
from ..config import get_settings
from ..lembretes import email as email_ses
from ..mcp import emails_ia, tokens
from ..mcp.auditoria_mcp import ACAO_CONEXAO_EMITIDA, ACAO_CONEXAO_REVOGADA, CANAL, recurso_do_token
from ..mcp.configuracao import ConfiguracaoMcp, get_configuracao_mcp, problemas_do_oauth
from ..mcp.dados import cliente_novo
from ..supabase_client import criar_cliente_supabase, get_supabase

log = logging.getLogger("sas.oauth")

#: As portas abertas do protocolo: o RFC manda que sejam públicas.
router = APIRouter(tags=["oauth"])

#: O consentimento — também público desde 26/10 (decisão do dono): quem
#: aprova prova a posse do e-mail da conta de IA com o código enviado a ele, e
#: não a sessão do SAS, que o browser da IA muitas vezes nem tem. Sem guard de
#: sessão de propósito: com ele, voltaria a haver DUAS portas de aprovação.
router_consentimento = APIRouter(prefix="/oauth/pedidos", tags=["oauth"])

#: O único escopo do MCP — o MESMO texto de `app.mcp.servidor.ESCOPO_DE_LEITURA`
#: (um teste confere). Repetido aqui porque importar de lá puxaria o SDK.
ESCOPO = "sas.leitura"

ACAO_PEDIDO_APROVADO = "mcp_oauth_aprovado"
#: Não é mais gravada desde 26/10 — a recusa ficou anônima e vai só ao log
#: (`recusar_pedido`). O nome fica reservado: uma "recusa" na linha do tempo só
#: pode ter vindo de fora, e o gatilho da 0072 continua tendo de recusá-la
#: vinda do sas_mcp (scripts/verificar_papeis_do_mcp.py).
ACAO_PEDIDO_RECUSADO = "mcp_oauth_recusado"

METODOS_DE_AUTENTICACAO = ("none", "client_secret_basic", "client_secret_post")
CONCESSOES = ("authorization_code", "refresh_token")

VALIDADE_DO_PEDIDO = timedelta(minutes=10)
#: RFC 6749 §4.1.2: "A maximum authorization code lifetime of 10 minutes is RECOMMENDED".
VALIDADE_DO_CODIGO = timedelta(minutes=10)

#: O começo de todo refresh. Diferente do `sas_mcp_` do access de propósito:
#: um refresh apresentado como Bearer no MCP cai no formato antes do banco, e
#: um scanner de segredo distingue os dois.
PREFIXO_DO_REFRESH = "sas_rt_"
_FORMATO_DO_REFRESH = re.compile(r"sas_rt_[A-Za-z0-9_-]{43}")
_FORMATO_DO_PEDIDO = re.compile(r"[A-Za-z0-9_-]{43}")
#: O `client_id` é um uuid4 que a própria API gera. Fora disso, nem vai ao banco.
_FORMATO_DO_CLIENT_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
#: RFC 7636 §4.1 e §4.2: verificador e desafio são 43 a 128 "unreserved".
_FORMATO_PKCE = re.compile(r"[A-Za-z0-9._~-]{43,128}")

_TETO_DO_CORPO = 16 * 1024
_MAXIMO_DE_REDIRECTS = 10
_MAXIMO_DA_URI = 2000
_MAXIMO_DO_NOME = 100
_MAXIMO_DO_STATE = 2048
_HOSTS_DE_LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})
NOME_SEM_DECLARACAO = "App sem nome"
#: O teto de `token_mcp.nome` — o CHECK `token_mcp_nome_valido` da 0072.
_MAXIMO_DO_NOME_DA_CONEXAO = 80

#: O que o RFC 3986 §2 deixa numa URI — unreserved, reserved e o `%` com dois
#: hexadecimais —, menos o `#` (fragmento: RFC 6749 §3.1.2). Fora disto, o
#: browser (parser WHATWG) e o `urlsplit` leem a MESMA URI de jeitos
#: diferentes, e é o do browser que decide para onde o código vai: em
#: https://atacante.example\.claude.ai/cb, o Python vê o host
#: "atacante.example\.claude.ai" e o browser, que corta a autoridade também
#: em `\`, vai para atacante.example (revisão de segurança de 25/10).
_URI_DO_RFC_3986 = re.compile(r"(?:[A-Za-z0-9\-._~:/?\[\]@!$&'()*+,;=]|%[0-9A-Fa-f]{2})+")
#: A autoridade de uma volta: host e porta, nada mais, e ESCRITOS como o
#: browser os escreve (`URL.host`) — é esse texto que a tela mostra e confere
#: contra o destino, caractere por caractere. Sem usuário
#: (`https://claude.ai@evil.example` engana quem lê), sem `%` no host (o
#: browser o decodifica, e `claude%2eai` é claude.ai para ele), porta sem zero
#: à esquerda (`:0443` ele escreve 443) e IPv6 sem o IPv4 embutido (que ele
#: reescreve em hexadecimal: `[::ffff:127.0.0.1]` vira `[::ffff:7f00:1]`).
_AUTORIDADE = re.compile(r"(?P<host>\[[0-9A-Fa-f:]+\]|[A-Za-z0-9.-]+)(?::(?P<porta>[1-9][0-9]{0,4}))?")
#: A porta que o browser APAGA do host: `https://claude.ai:443/cb` é
#: "claude.ai" para ele, e a tela mostraria "claude.ai:443".
_PORTA_PADRAO = {"https": 443, "http": 80}
_ROTULO_DNS = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
#: O rótulo que o WHATWG lê como NÚMERO ("ends in a number checker"): no fim
#: do host, ele faz o browser ler o host inteiro como IPv4.
_ROTULO_NUMERICO = re.compile(r"[0-9]+|0x[0-9a-f]*")

#: RFC 6749 §5.1: toda resposta com token ou credencial leva os dois.
_SEM_CACHE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


# ─── Erros ───────────────────────────────────────────────────────────────


def _ascii(texto: str) -> str:
    """`error_description` só em %x20-21 / %x23-5B / %x5D-7E (RFC 6749 §4.1.2.1
    e §5.2; RFC 7591 §3.2.2 diz "ASCII"): imprimível, sem aspas nem barra
    invertida. As frases deste módulo são escritas em português e perdem o
    acento aqui — o resto da linha some."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return "".join(c for c in sem_acento if 0x20 <= ord(c) <= 0x7E and c not in '"\\')


class ErroOAuth(Exception):
    """Um erro no formato do RFC 6749 §5.2 (e do RFC 7591 §3.2.2, no cadastro)."""

    def __init__(
        self, erro: str, descricao: str, *, status: int = 400, cabecalhos: dict[str, str] | None = None
    ) -> None:
        super().__init__(erro)
        self.erro = erro
        self.descricao = descricao
        self.status = status
        self.cabecalhos = cabecalhos or {}

    def resposta(self) -> JSONResponse:
        return JSONResponse(
            {"error": self.erro, "error_description": _ascii(self.descricao)},
            status_code=self.status,
            headers={**_SEM_CACHE, **self.cabecalhos},
        )


def _cliente_invalido(via_basic: bool) -> ErroOAuth:
    # RFC 6749 §5.2: 401, e com `WWW-Authenticate` do esquema que o cliente
    # usou quando ele tentou pelo cabeçalho Authorization.
    return ErroOAuth(
        "invalid_client",
        "Cliente desconhecido ou credencial do cliente errada.",
        status=401,
        cabecalhos={"WWW-Authenticate": 'Basic realm="sas-oauth"'} if via_basic else None,
    )


class PedidoInvalido(Exception):
    """Erro do /authorize. Vira página (ou JSON) — NUNCA redirecionamento.

    `volta` é a `redirect_uri` com o erro (RFC 6749 §4.1.2.1), que a página
    oferece como link para a PESSOA seguir; só existe depois de conferidos o
    cliente e a redirect_uri. Sem ela (cliente ou endereço ruim), não há para
    onde voltar.
    """

    def __init__(
        self, erro: str, mensagem: str, *, status: int = 400, volta: str | None = None,
        cabecalhos: dict[str, str] | None = None,
    ) -> None:
        super().__init__(erro)
        self.erro = erro
        self.mensagem = mensagem
        self.status = status
        self.volta = volta
        self.cabecalhos = cabecalhos or {}


_PAGINA_DE_ERRO = """<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pedido de conexão inválido · SAS</title></head>
<body>
<main>
<h1>Este pedido de conexão não vale</h1>
<p>{mensagem}</p>
{orientacao}
<p><small>Código do erro: <code>{codigo}</code></small></p>
</main>
</body>
</html>
"""

_SEM_VOLTA = (
    "<p>Volte ao app de IA e comece a conexão de novo. Se o erro continuar, avise quem administra o SAS.</p>"
)

#: O host aparece duas vezes, e no texto do link: é para lá que a pessoa vai,
#: e quem escolheu esse endereço foi o app que se cadastrou, não o SAS.
_COM_VOLTA = """<p>Se foi você quem começou esta conexão agora, volte ao app pelo link abaixo, que leva o aviso \
do erro para <b>{host}</b>, e tente de novo. Se o erro continuar, avise quem administra o SAS.</p>
<p>Se você não pediu conexão nenhuma, feche esta aba e não siga o link.</p>
<p><a href="{href}" rel="noreferrer">Voltar para {host}</a></p>"""


def _pagina_de_erro(
    request: Request, erro: str, mensagem: str, *, status: int = 400, volta: str | None = None,
    cabecalhos: dict[str, str] | None = None,
) -> Response:
    """A resposta de todo erro do /authorize — ele nunca redireciona sozinho.

    Para a pessoa no browser, uma página em português, sem script, estilo nem
    nada de fora (a CSP do nginx e a regra de LGPD da armadilha 7), com o
    link de volta ao app quando há (`PedidoInvalido.volta`); para quem não
    pede HTML, o mesmo erro em JSON. Nenhum texto livre do pedido é ecoado:
    a página está em portalsas.online, e o que ela diz o SAS diz.
    """
    da_resposta = {
        **_SEM_CACHE, **(cabecalhos or {}), "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
    }
    if "text/html" not in request.headers.get("accept", ""):
        return JSONResponse(
            {"error": erro, "error_description": _ascii(mensagem)}, status_code=status, headers=da_resposta
        )
    orientacao = (
        _COM_VOLTA.format(host=html.escape(_host_de_volta(volta)), href=html.escape(volta))
        if volta else _SEM_VOLTA
    )
    corpo = _PAGINA_DE_ERRO.format(mensagem=html.escape(mensagem), orientacao=orientacao, codigo=html.escape(erro))
    return HTMLResponse(
        corpo,
        status_code=status,
        headers={**da_resposta, "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'"},
    )


# ─── Tempo, hash, PKCE ───────────────────────────────────────────────────


def _agora() -> datetime:
    return datetime.now(UTC)


def _instante(momento: datetime) -> str:
    """Todo instante que esta rota grava ou filtra, num formato só e com `Z`.

    `Z` e nunca `+00:00`: o `+` não é encodado na query string do PostgREST e
    viraria espaço (a armadilha do motor de lembretes,
    `lembretes/despachante._filtro_ts`). E um formato só porque o filtro
    `gt("expira_em", …)` compara com o que esta mesma rota escreveu.
    """
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _ler_instante(valor: Any) -> datetime | None:
    if not valor:
        return None
    try:
        momento = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


def _vencido(valor: Any, agora: datetime) -> bool:
    """Prazo ilegível conta como vencido: falha fechada."""
    fim = _ler_instante(valor)
    return fim is None or fim <= agora


def _sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def desafio_s256(verificador: str) -> str:
    """RFC 7636 §4.2: BASE64URL(SHA256(ASCII(code_verifier))), sem `=`."""
    digesto = hashlib.sha256(verificador.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digesto).rstrip(b"=").decode("ascii")


def _novo_refresh() -> tuple[str, str]:
    refresh = PREFIXO_DO_REFRESH + secrets.token_urlsafe(32)
    return refresh, _sha256(refresh)


# ─── Tetos por IP ────────────────────────────────────────────────────────


class TetoPorIp:
    """Tentativas por IP numa janela deslizante, EM MEMÓRIA.

    Vale porque a API é um processo só (UVICORN_WORKERS=1, CLAUDE.md armadilha
    5): com dois, cada um teria a sua contagem e o teto dobraria calado — o
    mesmo motivo do limite de login em routes/auth.py. O IP só é o de quem
    chama com o `--forwarded-allow-ips` da produção (infra/vps); errado, todo
    mundo vira o nginx e o teto vira um balde só — o que aqui só atrasa o
    conector, porque o teto não guarda nada além de contagem.

    Com trava: o teto é lido no event loop, mas nada impede uma rota `def`
    de usá-lo amanhã, do pool de threads.
    """

    #: Teto de memória: IPs além disto saem pelo mais antigo.
    MAXIMO_DE_CHAVES = 10_000

    def __init__(self, janela_s: float, *, relogio: Callable[[], float] = time.monotonic) -> None:
        self.janela_s = janela_s
        self._relogio = relogio
        self._por_ip: OrderedDict[str, deque[float]] = OrderedDict()
        self._trava = threading.Lock()

    def admitir(self, ip: str, maximo: int) -> bool:
        with self._trava:
            agora = self._relogio()
            fila = self._por_ip.pop(ip, None) or deque()
            while fila and fila[0] <= agora - self.janela_s:
                fila.popleft()
            admitida = len(fila) < maximo
            if admitida:
                fila.append(agora)
            self._por_ip[ip] = fila
            while len(self._por_ip) > self.MAXIMO_DE_CHAVES:
                self._por_ip.popitem(last=False)
            return admitida

    def limpar(self) -> None:
        with self._trava:
            self._por_ip.clear()


TETO_DO_CADASTRO = TetoPorIp(3600.0)
#: /oauth/token e /oauth/revoke: os dois são credencial de cliente contra o banco.
TETO_DO_TOKEN = TetoPorIp(60.0)
TETO_DO_AUTHORIZE = TetoPorIp(60.0)
#: As rotas do consentimento, que desde 26/10 são anônimas: ler o pedido,
#: aprovar e recusar dividem este (oauth_tentativas_por_minuto).
TETO_DO_CONSENTIMENTO = TetoPorIp(60.0)
#: Os três do /codigo. A chave não precisa ser IP: o por pedido conta pelo id
#: dele, e o por e-mail pelo sha256 do e-mail digitado — cadastrado ou não, ou
#: o 429 contaria quais estão (ConfiguracaoMcp.oauth_codigos_*). O por pedido
#: vive o que o pedido vive; o por e-mail, um dia.
TETO_DE_CODIGOS_POR_IP = TetoPorIp(3600.0)
TETO_DE_CODIGOS_POR_PEDIDO = TetoPorIp(600.0)
TETO_DE_CODIGOS_POR_EMAIL = TetoPorIp(86400.0)


class FaxinaDosPedidos:
    """Quando apagar os pedidos que venceram SEM decisão: no máximo uma vez por
    intervalo, de dentro do próprio /authorize (`_apagar_pedidos_vencidos`).

    É o /authorize que enche `oauth_pedido_mcp`, uma linha por pedido e sem
    login, e por isso é ele que a esvazia: um cron seria mais uma peça na VPS
    para uma tabela que só esta rota escreve. Pedido vencido e não decidido
    não responde nada (a tela o trata como inexistente, e nenhum código saiu
    dele); o que a 0073 guarda para sempre é o DECIDIDO, quem aprovou que app.

    Em memória, como os tetos acima: com dois processos, cada um faxinaria por
    si, o que só repete um DELETE inofensivo.
    """

    def __init__(self, intervalo_s: float, *, relogio: Callable[[], float] = time.monotonic) -> None:
        self.intervalo_s = intervalo_s
        self._relogio = relogio
        self._ultima: float | None = None
        self._trava = threading.Lock()

    def devida(self) -> bool:
        """Se já passou o intervalo. Passou: esta conta como a última."""
        with self._trava:
            agora = self._relogio()
            if self._ultima is not None and agora - self._ultima < self.intervalo_s:
                return False
            self._ultima = agora
            return True

    def limpar(self) -> None:
        with self._trava:
            self._ultima = None


FAXINA_DOS_PEDIDOS = FaxinaDosPedidos(60.0)
#: A mesma cadência, para os clientes cadastrados e NUNCA usados, de dentro do
#: /oauth/register — que é quem enche `oauth_cliente_mcp`
#: (`_apagar_clientes_sem_uso`). Uma vez por hora basta: o teto do total de
#: cadastros por hora é que segura a velocidade.
FAXINA_DOS_CLIENTES = FaxinaDosPedidos(3600.0)


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _limitar(teto: TetoPorIp, request: Request, maximo: int) -> None:
    if not teto.admitir(_ip(request) or "-", maximo):
        raise ErroOAuth(
            "too_many_requests",
            "Tentativas demais a partir deste endereço. Espere e tente de novo.",
            status=429,
            cabecalhos={"Retry-After": str(int(teto.janela_s))},
        )


# ─── Configuração ────────────────────────────────────────────────────────


def _config_ligada() -> ConfiguracaoMcp:
    """A configuração, se o OAuth está ligado E seguro; senão, 404.

    404, e não 503: sem OAuth configurado, estas rotas não existem neste
    ambiente — e o cliente que as procura cai no mesmo que cairia num SAS
    sem a Fase 3. Configurado de um jeito inseguro (emissor em http em
    produção…), também 404, com o motivo no log: o guard de boot da API é
    de outro dono e não conhece o MCP (`configuracao.problemas_do_oauth`).
    """
    config = get_configuracao_mcp()
    if not config.oauth_ligado:
        raise HTTPException(status_code=404)
    problemas = problemas_do_oauth(config, get_settings().app_env)
    if problemas:
        log.error("OAuth do MCP desligado por configuração insegura: %s", "; ".join(problemas))
        raise HTTPException(status_code=404)
    return config


# ─── Corpo da requisição ─────────────────────────────────────────────────


def _tipo_do_corpo(request: Request) -> str:
    return request.headers.get("content-type", "").split(";", 1)[0].strip().lower()


async def _corpo(request: Request) -> bytes:
    """O corpo cru, com teto. Lido à mão porque o formulário do starlette
    0.38.6 não limita o urlencoded (GHSA-82w8-qh3p-5jfq — mapa do SDK, risco 6),
    e /token e /revoke são portas abertas."""
    declarado = request.headers.get("content-length", "")
    if declarado.isdigit() and int(declarado) > _TETO_DO_CORPO:
        raise ErroOAuth("invalid_request", "Corpo grande demais.", status=413)
    partes: list[bytes] = []
    total = 0
    async for pedaco in request.stream():
        total += len(pedaco)
        if total > _TETO_DO_CORPO:
            raise ErroOAuth("invalid_request", "Corpo grande demais.", status=413)
        partes.append(pedaco)
    return b"".join(partes)


def _sem_repeticao(pares: Iterable[tuple[str, str]]) -> tuple[dict[str, str], list[str], set[str]]:
    """(campos, valores de `resource`, nomes repetidos).

    Vazio vale como ausente (RFC 6749 §3.1) — é o `client_secret=` que cliente
    público manda. Repetido é recusado por quem chama (§3.1 e §3.2), salvo
    `resource`, que o RFC 8707 §2 deixa vir mais de uma vez.
    """
    campos: dict[str, str] = {}
    recursos: list[str] = []
    repetidos: set[str] = set()
    for chave, valor in pares:
        if valor == "":
            continue
        if chave == "resource":
            recursos.append(valor)
            continue
        if chave in campos:
            repetidos.add(chave)
        campos[chave] = valor
    return campos, recursos, repetidos


async def _formulario(request: Request) -> tuple[dict[str, str], list[str]]:
    """O corpo `application/x-www-form-urlencoded` do /token e do /revoke
    (RFC 6749 §3.2, RFC 7009 §2.1)."""
    if _tipo_do_corpo(request) != "application/x-www-form-urlencoded":
        raise ErroOAuth(
            "invalid_request", "O corpo tem de ser application/x-www-form-urlencoded (RFC 6749 3.2)."
        )
    bruto = await _corpo(request)
    try:
        pares = parse_qsl(bruto.decode("utf-8"), keep_blank_values=True, max_num_fields=40)
    except (UnicodeDecodeError, ValueError):
        raise ErroOAuth("invalid_request", "Corpo ilegível.") from None
    campos, recursos, repetidos = _sem_repeticao(pares)
    if repetidos:
        raise ErroOAuth("invalid_request", f"Parâmetro repetido: {sorted(repetidos)[0][:40]} (RFC 6749 3.2).")
    return campos, recursos


# ─── O cliente OAuth ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class ClienteOAuth:
    client_id: str
    nome: str | None
    redirect_uris: tuple[str, ...]
    metodo: str
    concessoes: tuple[str, ...]
    hash_do_segredo: str | None

    @property
    def publico(self) -> bool:
        return self.metodo == "none"


@dataclass(frozen=True)
class Credenciais:
    client_id: str | None
    segredo: str | None
    via_basic: bool


_COLUNAS_DO_CLIENTE = (
    "client_id, client_secret_hash, client_name, redirect_uris, token_endpoint_auth_method, grant_types"
)


def _carregar_cliente(db: Any, client_id: str | None) -> ClienteOAuth | None:
    if not client_id or not _FORMATO_DO_CLIENT_ID.fullmatch(client_id):
        return None
    linhas = (
        db.table("oauth_cliente_mcp").select(_COLUNAS_DO_CLIENTE).eq("client_id", client_id).limit(1).execute().data
        or []
    )
    if not linhas:
        return None
    linha = linhas[0]
    return ClienteOAuth(
        client_id=str(linha["client_id"]),
        nome=linha.get("client_name") or None,
        redirect_uris=tuple(linha.get("redirect_uris") or ()),
        metodo=str(linha.get("token_endpoint_auth_method") or ""),
        concessoes=tuple(linha.get("grant_types") or ()),
        hash_do_segredo=linha.get("client_secret_hash"),
    )


def _credenciais(request: Request, campos: dict[str, str]) -> Credenciais:
    """Quem diz ser o cliente: pelo Basic OU pelo corpo (RFC 6749 §2.3.1).

    O confidencial pode usar qualquer dos dois, seja qual for o método que
    cadastrou — `client_secret_basic` e `client_secret_post` provam a mesma
    coisa, e há cliente que cadastra um e manda o outro. No Basic, o
    `client_id` no corpo é dispensado (o SDK o exigia — lacuna do mapa) e, se
    vier, tem de ser o mesmo. Os dois jeitos ao mesmo tempo, não (§2.3).
    """
    cabecalho = request.headers.get("authorization")
    if not cabecalho:
        return Credenciais(campos.get("client_id"), campos.get("client_secret"), False)
    esquema, _, valor = cabecalho.partition(" ")
    if esquema.lower() != "basic":
        raise _cliente_invalido(True)
    try:
        decodificado = base64.b64decode(valor.strip(), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        raise _cliente_invalido(True) from None
    usuario, separador, senha = decodificado.partition(":")
    if not separador:
        raise _cliente_invalido(True)
    # §2.3.1: id e segredo vão form-urlencoded ANTES do base64.
    client_id = unquote_plus(usuario)
    if "client_secret" in campos:
        raise ErroOAuth("invalid_request", "Autentique o cliente de um jeito só: Basic ou corpo (RFC 6749 2.3).")
    if campos.get("client_id") not in (None, client_id):
        raise _cliente_invalido(True)
    return Credenciais(client_id, unquote_plus(senha) or None, True)


def _cliente_autenticado(db: Any, cred: Credenciais) -> ClienteOAuth:
    cliente = _carregar_cliente(db, cred.client_id)
    if cliente is None:
        raise _cliente_invalido(cred.via_basic)
    if cliente.publico:
        # Cliente público não tem segredo: o que o prende é o PKCE e a
        # redirect_uri cadastrada. Segredo que ele mande não prova nada.
        return cliente
    if not cliente.hash_do_segredo or not cred.segredo:
        raise _cliente_invalido(cred.via_basic)
    if not hmac.compare_digest(_sha256(cred.segredo), cliente.hash_do_segredo):
        raise _cliente_invalido(cred.via_basic)
    return cliente


def _nome_declarado(cliente: ClienteOAuth | None) -> str:
    return (cliente.nome if cliente else None) or NOME_SEM_DECLARACAO


def _host_de_volta(redirect_uri: str) -> str:
    """O host (com porta) para onde o browser volta — o que a tela mostra e
    confere antes de seguir (web/src/dominio/conexoesDeIa.ts::destinoDaVolta).

    É o `URL.host` do browser, letra por letra, porque toda redirect_uri que
    chega aqui passou por `redirect_aceitavel`: ela recusa o que o browser
    leria diferente (a `\\` da revisão de 25/10) e o que ele ESCREVERIA
    diferente (porta padrão, zero à esquerda, IPv6 por extenso). Sobra o que
    os dois escrevem igual, a menos da caixa — e o browser também põe o host
    em minúscula."""
    partes = urlsplit(redirect_uri)
    return partes.netloc.rsplit("@", 1)[-1].lower()


# ─── redirect_uri ────────────────────────────────────────────────────────


def _rotulo_idn_legivel(rotulo: str) -> bool:
    """O rótulo `xn--…` é um nome internacional em punycode, e o browser o
    DECODIFICA (UTS 46) antes de aceitar a URL: o que não decodifica, ou dá
    nada ou só ASCII, ele recusa. `xn--zz` e `xn--abc-` são URL inválida para
    ele e host para o `urlsplit`. As tabelas de caractere permitido do UTS 46
    ficam com o browser: recusar ali só faz a volta não acontecer, e então
    ninguém recebe o código."""
    if not rotulo.startswith("xn--"):
        return True
    try:
        texto = rotulo[4:].encode("ascii").decode("punycode")
    except ValueError:  # UnicodeError é ValueError
        return False
    return bool(texto) and not texto.isascii()


def _host_legivel(host: str) -> bool:
    """Se o browser lê este host como o `urlsplit` o lê, e o escreve como ele
    está escrito — e então o que a tela mostra é o host que recebe o código.

    Três formas: IPv6 entre colchetes e já comprimido (o RFC 5952, que é o que
    o serializador WHATWG escreve: `[0:0:0:0:0:0:0:1]` ele mostra `[::1]`),
    IPv4 canônico e nome DNS de rótulos [a-z0-9-]. O resto o parser WHATWG
    REINTERPRETA. O último rótulo numérico faz dele um IPv4: `0x7f.1` e
    `2130706433` são 127.0.0.1, e `010.0.0.1`, lido em octal, é 8.0.0.1.
    Rótulo vazio ou com `_` não é host de volta de ninguém.
    """
    if host.startswith("["):
        literal = host[1:-1].lower()
        try:
            return ipaddress.IPv6Address(literal).compressed == literal
        except ValueError:
            return False
    try:
        # 3.9.5+: zero à esquerda é recusado, e é ele que o browser lê em octal.
        return str(ipaddress.IPv4Address(host)) == host
    except ValueError:
        pass
    rotulos = host.lower().removesuffix(".").split(".")
    if not all(_ROTULO_DNS.fullmatch(r) and _rotulo_idn_legivel(r) for r in rotulos):
        return False
    return _ROTULO_NUMERICO.fullmatch(rotulos[-1]) is None


def redirect_aceitavel(uri: Any) -> bool:
    """Se uma redirect_uri pode ser CADASTRADA — e usada.

    https para qualquer host, ou http SÓ de loopback — o app nativo (Claude
    Code, mcp-remote) recebe a volta numa porta local (RFC 8252 §7.3). Só os
    caracteres do RFC 3986 (o que deixa de fora acento, espaço, controle e a
    `\\` que engana a tela), sem fragmento (RFC 6749 §3.1.2), e a autoridade
    só com host e porta, num formato que o browser lê E escreve como está
    escrito (`_AUTORIDADE`, `_PORTA_PADRAO`, `_host_legivel`): o host que a
    tela mostra é o `URL.host` dele, letra por letra. Esquema próprio de app
    (`com.exemplo:/volta`) fica de fora: nenhum dos conectores da Fase 3
    precisa, e ele não tem host para a tela mostrar.
    """
    if not isinstance(uri, str) or not uri or len(uri) > _MAXIMO_DA_URI:
        return False
    if not _URI_DO_RFC_3986.fullmatch(uri):
        return False
    try:
        partes = urlsplit(uri)
    except ValueError:
        return False
    autoridade = _AUTORIDADE.fullmatch(partes.netloc)
    if autoridade is None or not _host_legivel(autoridade["host"]):
        return False
    porta = autoridade["porta"]
    if porta is not None and (int(porta) > 65535 or int(porta) == _PORTA_PADRAO.get(partes.scheme)):
        return False
    if partes.scheme == "https":
        return True
    return partes.scheme == "http" and (partes.hostname or "") in _HOSTS_DE_LOOPBACK


def redirect_registrada(pedida: str, registradas: Iterable[str]) -> bool:
    """A redirect_uri do /authorize contra as do cadastro.

    Comparação EXATA de texto (RFC 6749 §3.1.2.3; a "exact string matching"
    do OAuth 2.1), com a única exceção que o RFC 8252 §7.3 OBRIGA: no http de
    loopback, a PORTA pode mudar a cada pedido — o app nativo pede ao sistema
    uma porta livre na hora. Esquema, host, caminho e query continuam exatos.

    A regra do cadastro vale de novo aqui, ANTES da comparação: um cadastro
    gravado antes de ela endurecer (a `\\` da revisão de 25/10) não volta a
    servir só porque o texto bate.
    """
    if not redirect_aceitavel(pedida):
        return False
    registradas = tuple(registradas)
    if pedida in registradas:
        return True
    partes = urlsplit(pedida)
    host = (partes.hostname or "").lower()
    if partes.scheme != "http" or host not in _HOSTS_DE_LOOPBACK:
        return False
    for registrada in registradas:
        outra = urlsplit(registrada)
        if (
            outra.scheme == "http"
            and (outra.hostname or "").lower() == host
            and outra.path == partes.path
            and outra.query == partes.query
        ):
            return True
    return False


def _com_parametros(uri: str, **parametros: str | None) -> str:
    """A redirect_uri com os parâmetros da resposta, MANTENDO a query que ela
    já tinha (RFC 6749 §3.1.2: "MUST be retained")."""
    partes = urlsplit(uri)
    extra = urlencode({k: v for k, v in parametros.items() if v is not None})
    query = f"{partes.query}&{extra}" if partes.query else extra
    return urlunsplit((partes.scheme, partes.netloc, partes.path, query, ""))


# ─── resource (RFC 8707) ─────────────────────────────────────────────────


def _canonico(url: str) -> str | None:
    """A forma canônica de um identificador de recurso: esquema e host em
    minúscula, sem porta padrão, sem barra final, sem fragmento — a "canonical
    server URI" da especificação do MCP. None se nem é URL absoluta."""
    try:
        partes = urlsplit(url.strip())
        porta = partes.port
    except ValueError:
        return None
    if partes.scheme.lower() not in ("http", "https") or not partes.hostname or partes.fragment:
        return None
    esquema = partes.scheme.lower()
    host = partes.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    if porta is not None and (esquema, porta) not in (("https", 443), ("http", 80)):
        host = f"{host}:{porta}"
    return urlunsplit((esquema, host, partes.path.rstrip("/"), partes.query, ""))


def _conferir_recursos(recursos: list[str], config: ConfiguracaoMcp) -> str | None:
    """O `resource` pedido, que só pode ser o MCP. None quando não veio
    (é opcional); qualquer outro: `invalid_target` (RFC 8707 §2)."""
    if not recursos:
        return None
    esperado = _canonico(config.recurso)
    if esperado is None or any(_canonico(r) != esperado for r in recursos):
        raise ErroOAuth("invalid_target", "O resource pedido não é este servidor MCP (RFC 8707 2).")
    return config.recurso


# ─── A conta em nome de quem a conexão existe ────────────────────────────


def _conta_pode_conectar(db: Any, coordenador_id: str, config: ConfiguracaoMcp) -> bool:
    """A conta ainda pode ter a conexão AGORA? Ativa e, com a regra do
    administrador ligada, administradora — lido da tabela no /codigo (envia ou
    não), no /aprovar e a cada troca de código e de refresh, não do que valia
    na aprovação. Desde 26/10 é a ÚNICA régua de quem conecta: não há sessão
    do SAS no consentimento para conferir."""
    linhas = (
        db.table("usuario_coordenacao").select("papel, ativo").eq("id", coordenador_id).limit(1).execute().data
        or []
    )
    if not linhas or linhas[0].get("ativo") is not True:
        return False
    return not config.emissao_so_administrador or linhas[0].get("papel") == "administrador"


def _derrubar_conexao(
    db: Any, token_mcp_id: Any, *, motivo: str, ator_tipo: str, ator_id: str | None, ip: str | None
) -> None:
    """Revoga a CONEXÃO: a linha de token_mcp (o access) e todo refresh dela.

    É a resposta a todo sinal de vazamento — código reapresentado (RFC 6749
    §4.1.2), refresh girado reapresentado (RFC 9700 §4.14.2), refresh de um
    cliente na mão de outro — e a revogação que o próprio app pede (RFC 7009
    §2.1: revogar o refresh derruba o access da mesma concessão).
    `revogado_por` fica NULL: revogação automática não tem autor (0072).
    """
    if not token_mcp_id:
        return
    agora = _instante(_agora())
    revogadas = (
        db.table("token_mcp")
        .update({"revogado_em": agora})
        .eq("id", str(token_mcp_id))
        .is_("revogado_em", "null")
        .execute()
        .data
        or []
    )
    db.table("oauth_refresh_mcp").update({"revogado_em": agora}).eq("token_mcp_id", str(token_mcp_id)).is_(
        "revogado_em", "null"
    ).execute()
    if revogadas:
        auditar(
            db, ACAO_CONEXAO_REVOGADA, canal=CANAL,
            ator_tipo=ator_tipo, ator_id=ator_id,
            recurso=recurso_do_token(str(token_mcp_id)), ip=ip,
            detalhe={"nome": revogadas[0].get("nome"), "origem": "oauth", "motivo": motivo},
        )


def _resposta_de_token(acesso: str, expira: datetime, agora: datetime, refresh: str | None) -> dict[str, Any]:
    corpo: dict[str, Any] = {
        "access_token": acesso,
        "token_type": "Bearer",
        "expires_in": max(1, int((expira - agora).total_seconds())),
        # Sempre: o escopo concedido pode não ser o pedido (RFC 6749 §5.1).
        "scope": ESCOPO,
    }
    if refresh:
        corpo["refresh_token"] = refresh
    return corpo


# ─── Metadado (RFC 8414) ─────────────────────────────────────────────────


def metadado_do_servidor(config: ConfiguracaoMcp) -> dict[str, Any]:
    """O metadado do authorization server.

    `issuer` é `config.emissor` — sem a barra final que o `AnyHttpUrl` do SDK
    poria —, o MESMO texto que o MCP anuncia em `authorization_servers`: o
    cliente compara os dois, e o RFC 8414 §3.3 manda descartar o metadado se
    divergirem. Os endpoints são o emissor + o caminho da rota: o emissor É a
    API vista de fora (o nginx tira o `/api`).
    """
    emissor = config.emissor
    return {
        "issuer": emissor,
        "authorization_endpoint": f"{emissor}/oauth/authorize",
        "token_endpoint": f"{emissor}/oauth/token",
        "registration_endpoint": f"{emissor}/oauth/register",
        "revocation_endpoint": f"{emissor}/oauth/revoke",
        "scopes_supported": [ESCOPO],
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        "grant_types_supported": list(CONCESSOES),
        # "none" é o cliente público — o que o SDK deixava de fora (lacuna do mapa).
        "token_endpoint_auth_methods_supported": list(METODOS_DE_AUTENTICACAO),
        "revocation_endpoint_auth_methods_supported": list(METODOS_DE_AUTENTICACAO),
        # O cliente do MCP recusa seguir sem isto (especificação de autorização do MCP).
        "code_challenge_methods_supported": ["S256"],
        # RFC 9207: o `iss` na volta do /authorize, contra a confusão de servidores.
        "authorization_response_iss_parameter_supported": True,
    }


def _resposta_do_metadado(config: ConfiguracaoMcp) -> JSONResponse:
    return JSONResponse(metadado_do_servidor(config), headers={"Cache-Control": "public, max-age=300"})


@router.get("/.well-known/oauth-authorization-server")
def metadado_na_raiz() -> JSONResponse:
    """A raiz: para o cliente que procura pelo host da API, e para quem chega
    por `{emissor}/.well-known/…` (o nginx tira o `/api`)."""
    return _resposta_do_metadado(_config_ligada())


@router.get("/.well-known/oauth-authorization-server/{caminho:path}")
def metadado_com_o_caminho_do_emissor(caminho: str) -> JSONResponse:
    """O endereço do RFC 8414 §3.1 para emissor com caminho: o
    `/.well-known/oauth-authorization-server` entra ANTES do caminho —
    https://portalsas.online/.well-known/oauth-authorization-server/api.
    Só o caminho do emissor configurado; o resto é 404."""
    config = _config_ligada()
    do_emissor = urlsplit(config.emissor).path.strip("/")
    if not do_emissor or caminho.strip("/") != do_emissor:
        raise HTTPException(status_code=404)
    return _resposta_do_metadado(config)


# ─── /oauth/register (RFC 7591) ──────────────────────────────────────────


@dataclass(frozen=True)
class CadastroValido:
    redirect_uris: tuple[str, ...]
    metodo: str
    concessoes: tuple[str, ...]
    nome: str | None


#: Caracteres que não são de controle nem de formatação, e por isso passam
#: pelo filtro de categoria "C", mas DESENHAM EM BRANCO: o Braille vazio
#: (U+2800, categoria So) e os preenchimentos do hangul. Num nome declarado,
#: servem para fingir espaço ou empurrar o resto da linha para fora da tela —
#: "Claude (claude.ai)" seguido de 62 deles era um nome de 80 que escondia o
#: host de verdade (revisão de segurança de 25/10). Viram espaço e colapsam.
_DESENHAM_EM_BRANCO = str.maketrans(dict.fromkeys(map(chr, (0x2800, 0x3164, 0x115F, 0x1160, 0xFFA0)), " "))


def _texto_limpo(texto: str) -> str:
    """Sem caractere de controle, sem o que desenha em branco e com espaço
    colapsado: o nome declarado vai para a tela, para o log e para a
    auditoria."""
    sem_controle = "".join(
        c for c in texto.translate(_DESENHAM_EM_BRANCO) if not unicodedata.category(c).startswith("C")
    )
    return " ".join(sem_controle.split())


def validar_cadastro(meta: Any) -> CadastroValido:
    """O pedido de cadastro do RFC 7591 §2, regra por regra. Função pura.

    Os defaults são os do RFC: sem `token_endpoint_auth_method`,
    `client_secret_basic`; sem `grant_types`, só `authorization_code` — e,
    diferente do SDK, isso basta (o conector que não quer refresh não leva).
    Metadado que não entendemos é ignorado, como o §2 manda.
    """
    if not isinstance(meta, dict):
        raise ErroOAuth("invalid_client_metadata", "O corpo tem de ser um objeto JSON (RFC 7591 3.1).")

    uris = meta.get("redirect_uris")
    if not isinstance(uris, list) or not uris:
        raise ErroOAuth("invalid_redirect_uri", "redirect_uris é obrigatório para o authorization_code (RFC 7591 2).")
    if len(uris) > _MAXIMO_DE_REDIRECTS:
        raise ErroOAuth("invalid_redirect_uri", f"No máximo {_MAXIMO_DE_REDIRECTS} redirect_uris.")
    if not all(redirect_aceitavel(u) for u in uris):
        raise ErroOAuth(
            "invalid_redirect_uri",
            "Toda redirect_uri tem de ser https, ou http de loopback para app nativo (RFC 8252 7.3), "
            "só com caracteres do RFC 3986, sem fragmento nem usuário na autoridade, e com host e porta "
            "escritos como o navegador os escreve (sem a porta padrão, sem zero à esquerda, IPv6 comprimido).",
        )

    metodo = meta.get("token_endpoint_auth_method") or "client_secret_basic"
    if metodo not in METODOS_DE_AUTENTICACAO:
        raise ErroOAuth(
            "invalid_client_metadata",
            "token_endpoint_auth_method aceito: none, client_secret_basic ou client_secret_post.",
        )

    concessoes = meta.get("grant_types") or ["authorization_code"]
    if (
        not isinstance(concessoes, list)
        or not all(isinstance(c, str) and c in CONCESSOES for c in concessoes)
        or "authorization_code" not in concessoes
    ):
        raise ErroOAuth(
            "invalid_client_metadata",
            "grant_types aceito: authorization_code, com ou sem refresh_token.",
        )

    respostas = meta.get("response_types") or ["code"]
    if not isinstance(respostas, list) or set(respostas) != {"code"}:
        raise ErroOAuth("invalid_client_metadata", "response_types aceito: so code.")

    nome = meta.get("client_name")
    if nome is not None:
        if not isinstance(nome, str):
            raise ErroOAuth("invalid_client_metadata", "client_name tem de ser texto.")
        nome = _texto_limpo(nome)
        if len(nome) > _MAXIMO_DO_NOME:
            raise ErroOAuth("invalid_client_metadata", f"client_name com mais de {_MAXIMO_DO_NOME} caracteres.")

    return CadastroValido(
        redirect_uris=tuple(dict.fromkeys(uris)),
        metodo=metodo,
        concessoes=tuple(dict.fromkeys(concessoes)),
        nome=nome or None,
    )


#: Clientes por consulta da faxina: o `in.(…)` vai na URL do PostgREST, e cem
#: uuids são ~4 KB. O teto do total por hora põe bem menos que isto por rodada.
_LOTE_DA_FAXINA = 100


def _apagar_clientes_sem_uso(db: Any, agora: datetime, dias: int) -> None:
    """A faxina de `FAXINA_DOS_CLIENTES`: os clientes cadastrados há mais de
    `dias` que nunca foram usados.

    Nunca usado = nenhum pedido e nenhuma conexão. O pedido decidido fica para
    sempre (0073), e todo código, conexão OAuth e refresh nasce de um — por
    isso basta o pedido, e a conexão vai junto só por garantia. O vencido sem
    decisão a `FAXINA_DOS_PEDIDOS` já apagou: quem só abriu pedido e ninguém
    aprovou também é "nunca usado". A rede de segurança é a FK sem CASCADE da
    0073: cliente com história não se apaga — o DELETE falharia alto, e aqui
    só viraria um aviso no log e a próxima faxina tentaria de novo.

    O app que se cadastrou e não conectou em `dias` volta a se cadastrar — é o
    que o RFC 7591 prevê. Falhar aqui não derruba o cadastro de ninguém.
    """
    corte = _instante(agora - timedelta(days=dias))
    try:
        velhos = [
            linha["client_id"]
            for linha in db.table("oauth_cliente_mcp").select("client_id").lt("criado_em", corte).execute().data
            or []
        ]
        for inicio in range(0, len(velhos), _LOTE_DA_FAXINA):
            lote = velhos[inicio : inicio + _LOTE_DA_FAXINA]
            usados = {
                linha["client_id"]
                for linha in db.table("oauth_pedido_mcp").select("client_id").in_("client_id", lote).execute().data
                or []
            }
            usados |= {
                linha["oauth_cliente_id"]
                for linha in db.table("token_mcp")
                .select("oauth_cliente_id")
                .in_("oauth_cliente_id", lote)
                .execute()
                .data
                or []
            }
            sem_uso = [client_id for client_id in lote if client_id not in usados]
            if sem_uso:
                db.table("oauth_cliente_mcp").delete(returning="minimal").in_("client_id", sem_uso).lt(
                    "criado_em", corte
                ).execute()
                log.info("faxina do OAuth: %d cliente(s) sem uso apagado(s)", len(sem_uso))
    except Exception:  # manutenção: qualquer falha dela, o cadastro de quem conecta segue
        log.warning("faxina dos clientes do OAuth falhou; a próxima tenta de novo", exc_info=True)


def _cadastros_na_ultima_hora(db: Any, agora: datetime) -> int:
    """Quantos clientes nasceram na última hora, de qualquer IP — contados no
    BANCO, e não na memória: o teto do total vale também através de um deploy,
    que zeraria a contagem em memória a cada restart."""
    resposta = (
        db.table("oauth_cliente_mcp")
        .select("client_id", count="exact")
        .gte("criado_em", _instante(agora - timedelta(hours=1)))
        .limit(1)
        .execute()
    )
    return resposta.count or 0


def _gravar_cliente(cadastro: CadastroValido, config: ConfiguracaoMcp) -> dict[str, Any]:
    agora = _agora()
    db = get_supabase()
    if FAXINA_DOS_CLIENTES.devida():
        _apagar_clientes_sem_uso(db, agora, config.oauth_dias_do_cliente_sem_uso)
    # O teto por IP limita UM endereço; com muitos, a tabela crescia sem
    # limite — uma linha de até ~16 KiB por cadastro, no banco dos alunos
    # (revisão final de 26/10). Este é o da casa inteira. 503 e não 429: quem
    # chama não passou de nada; o servidor é que não aceita mais por ora.
    # Duas threads ao mesmo tempo podem passar as duas: o teto é de volume.
    if _cadastros_na_ultima_hora(db, agora) >= config.oauth_cadastros_por_hora_no_total:
        log.warning("OAuth: teto de %d cadastros por hora no total atingido", config.oauth_cadastros_por_hora_no_total)
        raise ErroOAuth(
            "temporarily_unavailable",
            "Cadastros demais na última hora. Tente de novo mais tarde.",
            status=503,
            cabecalhos={"Retry-After": str(int(TETO_DO_CADASTRO.janela_s))},
        )
    client_id = str(uuid.uuid4())
    segredo = None if cadastro.metodo == "none" else secrets.token_urlsafe(32)
    db.table("oauth_cliente_mcp").insert(
        {
            "client_id": client_id,
            "client_secret_hash": _sha256(segredo) if segredo else None,
            "client_name": cadastro.nome,
            "redirect_uris": list(cadastro.redirect_uris),
            "token_endpoint_auth_method": cadastro.metodo,
            "grant_types": list(cadastro.concessoes),
            "criado_em": _instante(agora),
        }
    ).execute()
    # Log e não auditoria: o cadastro é anônimo e aberto, e quem enche a
    # trilha à vontade a torna inútil. O que é ato de alguém — aprovar — é
    # auditado.
    log.info(
        "cliente OAuth cadastrado: %s, método %s, volta em %s",
        client_id, cadastro.metodo, ", ".join(sorted({_host_de_volta(u) for u in cadastro.redirect_uris})),
    )
    # RFC 7591 §3.2.1: TODO o metadado registrado, inclusive o que o servidor
    # decidiu (o escopo); o segredo, uma vez, com a validade (0 = não vence).
    resposta: dict[str, Any] = {
        "client_id": client_id,
        "client_id_issued_at": int(agora.timestamp()),
        "redirect_uris": list(cadastro.redirect_uris),
        "token_endpoint_auth_method": cadastro.metodo,
        "grant_types": list(cadastro.concessoes),
        "response_types": ["code"],
        "scope": ESCOPO,
    }
    if cadastro.nome:
        resposta["client_name"] = cadastro.nome
    if segredo:
        resposta["client_secret"] = segredo
        resposta["client_secret_expires_at"] = 0
    return resposta


@router.post("/oauth/register")
async def cadastrar_cliente(request: Request) -> Response:
    """O cadastro dinâmico (RFC 7591): aberto, como o claude.ai e o ChatGPT
    esperam — o que limita é o teto por IP, o do total por hora, a faxina dos
    nunca usados e o consentimento de quem aprova."""
    config = _config_ligada()
    try:
        _limitar(TETO_DO_CADASTRO, request, config.oauth_cadastros_por_hora)
        if _tipo_do_corpo(request) != "application/json":
            raise ErroOAuth("invalid_client_metadata", "O corpo tem de ser application/json (RFC 7591 3.1).")
        bruto = await _corpo(request)
        try:
            meta = json.loads(bruto)
        except (UnicodeDecodeError, ValueError, RecursionError):
            # RecursionError não é ValueError: `[[[[…` aninhado cabe nos 16 KiB
            # e estoura a pilha do decodificador — era 500 numa porta anônima.
            raise ErroOAuth("invalid_client_metadata", "JSON ilegível.") from None
        cadastro = validar_cadastro(meta)
        resposta = await asyncio.to_thread(_gravar_cliente, cadastro, config)
    except ErroOAuth as erro:
        return erro.resposta()
    return JSONResponse(resposta, status_code=201, headers=_SEM_CACHE)


# ─── /oauth/authorize (RFC 6749 §4.1) ────────────────────────────────────


#: Os parâmetros que o /authorize lê. Só o nome de um destes aparece no
#: aviso de parâmetro repetido: qualquer outro nome é texto livre de quem
#: montou o link, e a página de erro fala em nome do SAS ("Parâmetro
#: repetido: Sua senha venceu, entre em sas-login.example").
_PARAMETROS_DO_AUTHORIZE = frozenset({
    "response_type", "client_id", "redirect_uri", "scope", "state", "code_challenge", "code_challenge_method",
})


def _apagar_pedidos_vencidos(db: Any, agora: datetime) -> None:
    """A faxina de `FaxinaDosPedidos`: os pedidos vencidos que NÃO são história.

    São dois: o que venceu SEM decisão, e o RECUSADO. O decidido-APROVADO é a
    história (0073) — o código do RFC e o refresh apontam para ele por FK — e
    fica; por isso o segundo DELETE filtra `aprovado = False`, não
    `decidido_em IS NOT NULL`. O recusado é decidido, mas desde 26/10 a recusa é
    anônima e vai ao LOG, não à trilha, e nada nasce dele (nenhum código do RFC,
    nenhum refresh); os códigos por e-mail que porventura saíram dele vão junto,
    pelo único CASCADE da 0073.

    Sem apagar o recusado, ele escapava dos DOIS controles da revisão de 25/10 —
    esta faxina e o teto de abertos só olhavam `decidido_em IS NULL` —, e um
    atacante sem sessão gravava linhas permanentes de até ~4 KB em laço
    (authorize→recusar, um cliente só), sem teto de volume, no banco dos alunos:
    a reabertura do buraco de ~375 MB/dia que a 25/10 fechou (revisão de 26/10).

    `returning=minimal`: ela não precisa ver o que apagou. Falhar aqui não
    derruba quem está conectando; o teto continua valendo, e a próxima faxina
    tenta de novo.
    """
    try:
        db.table("oauth_pedido_mcp").delete(returning="minimal").is_("decidido_em", "null").lt(
            "expira_em", _instante(agora)
        ).execute()
        db.table("oauth_pedido_mcp").delete(returning="minimal").eq("aprovado", False).lt(
            "expira_em", _instante(agora)
        ).execute()
    except Exception:  # manutenção: qualquer falha dela, o pedido de quem conecta segue
        log.warning("faxina dos pedidos do OAuth falhou; a próxima tenta de novo", exc_info=True)


def _teto_de_pedidos_abertos(db: Any, client_id: str, config: ConfiguracaoMcp, agora: datetime) -> str | None:
    """Que teto de pedidos abertos este pedido estouraria: "total", "cliente"
    ou nenhum (`ConfiguracaoMcp.oauth_pedidos_abertos_*`).

    Uma consulta só: ela traz até `no_total` pedidos abertos e, quando não
    chega lá, traz TODOS — e a conta do cliente sai exata da mesma lista. Duas
    threads ao mesmo tempo podem passar as duas; o teto é de volume, e não
    precisa ser exato.
    """
    teto_total = config.oauth_pedidos_abertos_no_total
    abertos = (
        db.table("oauth_pedido_mcp")
        .select("client_id")
        .is_("decidido_em", "null")
        .gt("expira_em", _instante(agora))
        .limit(teto_total)
        .execute()
        .data
        or []
    )
    if len(abertos) >= teto_total:
        return "total"
    if sum(1 for p in abertos if p.get("client_id") == client_id) >= config.oauth_pedidos_abertos_por_cliente:
        return "cliente"
    return None


def _autorizar(itens: list[tuple[str, str]], config: ConfiguracaoMcp) -> str:
    """Valida o pedido, grava e devolve para onde mandar o browser: a tela de
    consentimento do SAS. Síncrono (banco).

    Todo erro é `PedidoInvalido`, e nenhum redireciona (o porquê está no
    docstring do módulo). Primeiro o que não tem para onde voltar (cliente e
    redirect_uri); conferidos os dois, o erro leva o link de volta ao app,
    com o `state` e o `iss`. O pedido só é gravado inteiro e válido.
    """
    campos, recursos, repetidos = _sem_repeticao(itens)
    if {"client_id", "redirect_uri"} & repetidos:
        raise PedidoInvalido("invalid_request", "O pedido veio com o app ou o endereço de volta repetidos.")
    client_id = campos.get("client_id")
    if not client_id:
        raise PedidoInvalido("invalid_request", "O pedido chegou sem dizer qual app está pedindo (client_id).")

    db = get_supabase()
    cliente = _carregar_cliente(db, client_id)
    if cliente is None:
        raise PedidoInvalido("invalid_client", "O app que pediu a conexão não está cadastrado no SAS.")

    pedida = campos.get("redirect_uri")
    explicita = pedida is not None
    if pedida is None:
        # RFC 6749 §3.1.2.3: sem redirect_uri só dá para seguir quando o
        # cadastro tem uma só — e ela ainda passa pela regra de hoje.
        if len(cliente.redirect_uris) != 1:
            raise PedidoInvalido("invalid_request", "O pedido não disse para onde voltar, e o app cadastrou mais de um endereço.")
        if not redirect_aceitavel(cliente.redirect_uris[0]):
            raise PedidoInvalido("invalid_request", "O endereço de volta que o app cadastrou não é aceito pelo SAS.")
        pedida = cliente.redirect_uris[0]
    elif not redirect_registrada(pedida, cliente.redirect_uris):
        raise PedidoInvalido("invalid_request", "O endereço de volta do pedido não é um dos que o app cadastrou.")

    state = campos.get("state")

    def de_volta(
        erro: str, descricao: str, *, status: int = 400, cabecalhos: dict[str, str] | None = None
    ) -> PedidoInvalido:
        volta = _com_parametros(pedida, error=erro, error_description=_ascii(descricao), state=state, iss=config.emissor)
        return PedidoInvalido(erro, descricao, status=status, volta=volta, cabecalhos=cabecalhos)

    if repetidos:
        conhecidos = sorted(repetidos & _PARAMETROS_DO_AUTHORIZE)
        raise de_volta("invalid_request", f"Parâmetro repetido{f': {conhecidos[0]}' if conhecidos else ''} (RFC 6749 3.1).")
    tipo = campos.get("response_type")
    if tipo is None:
        raise de_volta("invalid_request", "Falta response_type.")
    if tipo != "code":
        raise de_volta("unsupported_response_type", "Só response_type=code (RFC 6749 4.1).")
    if "authorization_code" not in cliente.concessoes:
        raise de_volta("unauthorized_client", "O app não cadastrou o grant authorization_code.")
    desafio = campos.get("code_challenge")
    if desafio is None:
        raise de_volta("invalid_request", "code_challenge é obrigatório: PKCE (RFC 7636 4.4.1).")
    if campos.get("code_challenge_method") != "S256":
        # Sem o método, o RFC 7636 §4.3 diz "plain" — e plain não é aceito.
        raise de_volta("invalid_request", "Só code_challenge_method=S256; plain não é aceito (RFC 7636 4.4.1).")
    if not _FORMATO_PKCE.fullmatch(desafio):
        raise de_volta("invalid_request", "code_challenge fora do formato do RFC 7636 4.2.")
    if state is not None and len(state) > _MAXIMO_DO_STATE:
        raise de_volta("invalid_request", f"state com mais de {_MAXIMO_DO_STATE} caracteres.")
    try:
        recurso = _conferir_recursos(recursos, config)
    except ErroOAuth as erro:
        raise de_volta(erro.erro, erro.descricao) from None

    agora = _agora()
    if FAXINA_DOS_PEDIDOS.devida():
        _apagar_pedidos_vencidos(db, agora)
    estourado = _teto_de_pedidos_abertos(db, cliente.client_id, config, agora)
    if estourado is not None:
        # temporarily_unavailable é o código do RFC 6749 §4.1.2.1 para "agora
        # não dá", e o que o app recebe se a pessoa seguir o link. Os abertos
        # vencem em 10 min: é o que vale esperar.
        espera = {"Retry-After": str(int(VALIDADE_DO_PEDIDO.total_seconds()))}
        if estourado == "total":
            raise de_volta(
                "temporarily_unavailable",
                "Há pedidos de conexão demais esperando resposta no SAS agora. Espere alguns minutos e tente de novo.",
                status=503, cabecalhos=espera,
            )
        raise de_volta(
            "temporarily_unavailable",
            "Este app já tem pedidos de conexão demais esperando resposta. Espere alguns minutos e tente de novo.",
            status=429, cabecalhos=espera,
        )

    # O escopo: só existe um. Pedido sem escopo, ou com outro, leva o
    # sas.leitura — o RFC 6749 §3.3 deixa o servidor ignorar o que não
    # concede, e a resposta do /token diz o que foi concedido.
    pedido_id = secrets.token_urlsafe(32)
    db.table("oauth_pedido_mcp").insert(
        {
            "id": pedido_id,
            "client_id": cliente.client_id,
            "redirect_uri": pedida,
            "redirect_uri_explicita": explicita,
            "code_challenge": desafio,
            "code_challenge_method": "S256",
            "state": state,
            "scope": ESCOPO,
            "resource": recurso,
            "criado_em": _instante(agora),
            "expira_em": _instante(agora + VALIDADE_DO_PEDIDO),
        }
    ).execute()
    return f"{config.url_do_app.strip().rstrip('/')}/conectar-ia?{urlencode({'pedido': pedido_id})}"


@router.get("/oauth/authorize")
async def autorizar(request: Request) -> Response:
    """Recebe o browser vindo do app, guarda o pedido e o manda para a tela de
    consentimento do SAS (`/conectar-ia?pedido=<id>`). Quem decide é a
    coordenadora, lá — esta rota não sabe quem ela é. Por isso o único 302
    daqui é para o próprio SAS: erro vira página (`_pagina_de_erro`)."""
    config = _config_ligada()
    if not TETO_DO_AUTHORIZE.admitir(_ip(request) or "-", config.oauth_tentativas_por_minuto):
        return _pagina_de_erro(
            request, "too_many_requests", "Pedidos demais a partir deste endereço. Espere um minuto.", status=429
        )
    try:
        destino = await asyncio.to_thread(_autorizar, list(request.query_params.multi_items()), config)
    except PedidoInvalido as erro:
        return _pagina_de_erro(
            request, erro.erro, erro.mensagem, status=erro.status, volta=erro.volta, cabecalhos=erro.cabecalhos
        )
    return RedirectResponse(destino, status_code=302, headers=_SEM_CACHE)


# ─── O consentimento (o contrato da tela /conectar-ia) ───────────────────
#
# Sem sessão do SAS desde 26/10 (decisão do dono). Quem aprova prova a POSSE
# do e-mail da conta de IA: o /codigo manda a ele um código de 6 dígitos, e o
# /aprovar com o código certo aprova em nome do coordenador DONO do e-mail.
# É a ÚNICA porta de aprovação — a de antes, pela sessão da coordenação, saiu.
#
# A regra que atravessa as quatro rotas: nada do que elas respondem — corpo,
# status, cabeçalho, tempo — depende de o e-mail digitado estar cadastrado.
# Por isso o /codigo responde antes de procurar o e-mail, grava a linha do
# código para QUALQUER e-mail (sem envio, quando não há cadastro que aprove), e
# o /aprovar faz o mesmo caminho nos dois casos até o código bater.


class ClienteDoPedido(BaseModel):
    #: O nome que o PRÓPRIO app declarou — não é conferido.
    nome: str
    #: O host para onde o browser volta: é ele que o SAS confere.
    redirectHost: str


class PedidoDeConexao(BaseModel):
    id: str
    cliente: ClienteDoPedido
    expiraEm: str


class RespostaAoPedido(BaseModel):
    redirecionarPara: str


#: O corpo vem de qualquer um: o teto vale antes de normalizar.
_MAXIMO_DO_EMAIL_DIGITADO = emails_ia.MAXIMO_DO_EMAIL + 64


class PedirCodigoBody(BaseModel):
    email: str = Field(max_length=_MAXIMO_DO_EMAIL_DIGITADO)


class CodigoPedido(BaseModel):
    #: Sempre true: a resposta não diz se o e-mail está cadastrado.
    enviado: bool


class AprovarPedidoBody(BaseModel):
    email: str = Field(max_length=_MAXIMO_DO_EMAIL_DIGITADO)
    codigo: str = Field(max_length=32)


_COLUNAS_DO_PEDIDO = (
    "id, client_id, redirect_uri, redirect_uri_explicita, code_challenge, state, resource, "
    "expira_em, decidido_em"
)

_PEDIDO_ENCERRADO = "Este pedido de conexão expirou, já foi respondido ou não existe."
#: A mesma frase para código errado, vencido, já usado, de outro pedido, de
#: outro e-mail, de e-mail sem cadastro e com as tentativas esgotadas: qualquer
#: diferença entre elas contaria a quem chuta o que acertou.
_CODIGO_RECUSADO = (
    "Código errado, vencido ou já usado. Confira o e-mail digitado e o código, ou peça um código novo."
)
_EMAIL_SEM_CADASTRO = (
    "Este e-mail não está mais cadastrado no SAS como e-mail de conta de IA. Cadastre-o de novo "
    "em Conexões de IA e peça um código novo."
)
_CONTA_SEM_PERMISSAO = (
    "A conta da coordenação dona deste e-mail não pode conectar uma IA ao SAS agora (conta desativada, "
    "ou sem o papel de administrador enquanto só ele conecta)."
)

_TABELA_DOS_CODIGOS = "oauth_codigo_por_email_mcp"
_TABELA_DOS_EMAILS = "email_conta_ia_mcp"


class RecusaDoConsentimento(Exception):
    """Um erro das rotas do consentimento, no corpo do contrato da tela."""

    def __init__(self, status: int, mensagem: str, *, cabecalhos: dict[str, str] | None = None) -> None:
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem
        self.cabecalhos = cabecalhos or {}

    def resposta(self) -> JSONResponse:
        # `erro` é o contrato da tela (/conectar-ia); `detail`, o mesmo texto
        # onde o cliente HTTP do front procura a frase do servidor
        # (web/src/servicos/http.ts), para o erro não virar "→ 400".
        return JSONResponse(
            {"erro": self.mensagem, "detail": self.mensagem},
            status_code=self.status,
            headers={**_SEM_CACHE, **self.cabecalhos},
        )


def _demais(teto: TetoPorIp, mensagem: str) -> RecusaDoConsentimento:
    return RecusaDoConsentimento(429, mensagem, cabecalhos={"Retry-After": str(int(teto.janela_s))})


def _limitar_consentimento(request: Request, config: ConfiguracaoMcp) -> None:
    if not TETO_DO_CONSENTIMENTO.admitir(_ip(request) or "-", config.oauth_tentativas_por_minuto):
        raise _demais(TETO_DO_CONSENTIMENTO, "Tentativas demais a partir deste endereço. Espere um minuto.")


def _chave_dos_codigos() -> bytes:
    """A chave do HMAC dos e-mails e códigos (app/mcp/emails_ia.chave_dos_hashes),
    da JWT_SECRET_KEY: só a API a tem — o guard do MCP recusa subir com ela."""
    return emails_ia.chave_dos_hashes(get_settings().jwt_secret_key)


def _resposta_sem_cache(corpo: BaseModel, *, status: int = 200) -> JSONResponse:
    """A volta com o código do RFC não pode ficar em cache nenhum (RFC 6749 §5.1
    vale para a credencial, e ela está na URL)."""
    return JSONResponse(corpo.model_dump(), status_code=status, headers=_SEM_CACHE)


def _pedido_aberto(db: Any, pedido_id: str, agora: datetime) -> dict | None:
    """O pedido, se ainda dá para respondê-lo. Inexistente, vencido e já
    decidido são o mesmo 404 para a tela: os três pedem a mesma ação —
    voltar ao app e começar de novo (dominio/conexoesDeIa.ts)."""
    if not _FORMATO_DO_PEDIDO.fullmatch(pedido_id or ""):
        return None
    linhas = (
        db.table("oauth_pedido_mcp").select(_COLUNAS_DO_PEDIDO).eq("id", pedido_id).limit(1).execute().data or []
    )
    if not linhas:
        return None
    pedido = linhas[0]
    if pedido.get("decidido_em") is not None or _vencido(pedido.get("expira_em"), agora):
        return None
    return pedido


def _decidir(db: Any, pedido_id: str, dono: str | None, aprovado: bool, agora: datetime) -> bool:
    """Grava a decisão — e só a primeira: UPDATE condicional, então duas abas
    respondendo ao mesmo tempo não geram dois códigos. `dono` é o coordenador
    em nome de quem a aprovação nasce; a recusa não tem autor (0073)."""
    decididos = (
        db.table("oauth_pedido_mcp")
        .update({"decidido_em": _instante(agora), "decidido_por": dono, "aprovado": aprovado})
        .eq("id", pedido_id)
        .is_("decidido_em", "null")
        .gt("expira_em", _instante(agora))
        .execute()
        .data
        or []
    )
    return bool(decididos)


@router_consentimento.get("/{pedido_id}", response_model=PedidoDeConexao)
def obter_pedido(pedido_id: str, request: Request) -> Response:
    """O que a tela mostra antes de alguém decidir: o app e o host de volta."""
    config = _config_ligada()
    try:
        _limitar_consentimento(request, config)
        db = get_supabase()
        pedido = _pedido_aberto(db, pedido_id, _agora())
        if pedido is None:
            raise RecusaDoConsentimento(404, _PEDIDO_ENCERRADO)
    except RecusaDoConsentimento as recusa:
        return recusa.resposta()
    cliente = _carregar_cliente(db, pedido["client_id"])
    expira = _ler_instante(pedido["expira_em"])
    return _resposta_sem_cache(
        PedidoDeConexao(
            id=pedido["id"],
            cliente=ClienteDoPedido(
                nome=_nome_declarado(cliente), redirectHost=_host_de_volta(pedido["redirect_uri"])
            ),
            expiraEm=_instante(expira) if expira else str(pedido["expira_em"]),
        )
    )


def _cadastro_que_aprova(db: Any, email: str, config: ConfiguracaoMcp) -> dict | None:
    """O cadastro ATIVO e CONFIRMADO do e-mail, se a conta dona dele pode
    conectar agora. O que só aguarda confirmação não recebe o código de
    aprovar: a posse da caixa ainda não foi provada, e um e-mail digitado
    errado no card mandaria o acesso da conta a quem a lê
    (routes/mcp_emails_ia.py, regra 0). Confirmado e ativo, há um só por
    e-mail (o índice da 0073); os que aguardam, de outras contas, não contam."""
    linhas = (
        db.table(_TABELA_DOS_EMAILS).select("id, usuario_coordenacao_id").eq("email", email)
        .is_("removido_em", "null").not_.is_("confirmado_em", "null").limit(1).execute().data
        or []
    )
    if not linhas or not _conta_pode_conectar(db, str(linhas[0]["usuario_coordenacao_id"]), config):
        return None
    return linhas[0]


def _enviar_codigo(email: str, codigo: str, host_de_volta: str) -> None:
    """Pelo SES do motor de lembretes (lembretes/email.py), o mesmo remetente
    e a mesma rede de EMAIL_DESTINATARIO_TESTE."""
    assunto, corpo = emails_ia.mensagem_do_codigo(codigo, host_de_volta)
    if email_ses.email_configurado():
        try:
            email_ses.enviar_email(destinatario=email, assunto=assunto, corpo=corpo)
        except Exception as erro:
            # O erro do SES carrega o ENDEREÇO no texto do botocore — o
            # MessageRejected de destinatário não verificado (o SES segue em
            # sandbox, docs/15), um hard bounce. Deixá-lo subir ao `log.exception`
            # de `_preparar_codigo` gravaria o e-mail INTEIRO no campo `excecao`
            # do log de produção (observabilidade._FormatadorJSON), contra a
            # máscara que o resto do módulo mantém de propósito (mascarar_email na
            # trilha e no log de dev). Ao log vão só o e-mail mascarado e o TIPO
            # do erro — nunca a mensagem, que é onde o endereço aparece.
            log.error(
                "[AÇÃO NECESSÁRIA] o SES recusou o envio do código de aprovação de uma conexão de IA "
                "para %s (%s)",
                emails_ia.mascarar_email(email), type(erro).__name__,
            )
        return
    if get_settings().app_env == "dev":
        # SÓ em dev, e só sem SES: é como se testa o fluxo na máquina. Em
        # qualquer outro ambiente o código NUNCA vai ao log — quem lesse o log
        # aprovaria conexão em nome de qualquer coordenador.
        log.warning(
            "[DEV] SES não configurado — o código de aprovação para %s é %s",
            emails_ia.mascarar_email(email), codigo,
        )
        return
    log.error(
        "[AÇÃO NECESSÁRIA] SES não configurado (AWS_SES_* e EMAIL_REMETENTE): o código de "
        "aprovação de uma conexão de IA não foi enviado"
    )


def _preparar_codigo(pedido_id: str, email: str, config: ConfiguracaoMcp) -> None:
    """A metade do /codigo que depende do e-mail, DEPOIS da resposta.

    Grava a linha do código para QUALQUER e-mail: com cadastro que aprova, ela
    aponta para ele e o código vai por e-mail; sem, fica sem cadastro e o
    código, que ninguém vê, não aprova nada. É a linha a mais ou a menos que
    contaria ao /aprovar quem está cadastrado.

    Tarefa de fundo, com cliente PostgREST próprio (api/CLAUDE.md: a cacheada
    divide a conexão HTTP/2 com as requisições). Falha aqui não volta a
    ninguém — a resposta já saiu —: vai ao log, e quem esperava o código pede
    outro.
    """
    try:
        with cliente_novo(criar_cliente_supabase) as db:
            agora = _agora()
            pedido = _pedido_aberto(db, pedido_id, agora)
            if pedido is None:
                return
            cadastro = _cadastro_que_aprova(db, email, config)
            chave = _chave_dos_codigos()
            hash_email = emails_ia.hash_do_email(chave, email)
            codigo = emails_ia.gerar_codigo()
            db.table(_TABELA_DOS_CODIGOS).insert(
                {
                    "pedido_id": pedido_id,
                    "hash_email": hash_email,
                    "email_conta_ia_id": str(cadastro["id"]) if cadastro else None,
                    "hash_codigo": emails_ia.hash_do_codigo(chave, pedido_id, hash_email, codigo),
                    "criado_em": _instante(agora),
                    "expira_em": _instante(agora + emails_ia.VALIDADE_DO_CODIGO),
                    "tentativas": 0,
                }
            ).execute()
            if cadastro is None:
                # Sem o e-mail nem o pedido: um aviso por pedido de código para
                # e-mail que não aprova — o que alguém digitou não vai ao log.
                log.info("código de aprovação pedido para e-mail sem cadastro que aprove: nada enviado")
                return
            _enviar_codigo(email, codigo, _host_de_volta(pedido["redirect_uri"]))
    except Exception:  # tarefa de fundo: a resposta já saiu, e o erro não pode sumir
        log.exception("[AÇÃO NECESSÁRIA] não consegui preparar o código de aprovação de uma conexão de IA")


@router_consentimento.post("/{pedido_id}/codigo", status_code=202, response_model=CodigoPedido)
def pedir_codigo(
    pedido_id: str, body: PedirCodigoBody, request: Request, tarefas: BackgroundTasks
) -> Response:
    """Manda o código de aprovação ao e-mail da conta de IA — se ele estiver
    cadastrado e a conta dona puder conectar. A resposta é a MESMA, e sai no
    mesmo tempo, nos dois casos: o que depende do e-mail roda depois dela
    (`_preparar_codigo`). Os três tetos contam qualquer e-mail digitado."""
    config = _config_ligada()
    email = emails_ia.normalizar_email(body.email)
    try:
        if not TETO_DE_CODIGOS_POR_IP.admitir(_ip(request) or "-", config.oauth_codigos_por_ip_por_hora):
            raise _demais(TETO_DE_CODIGOS_POR_IP, "Pedidos de código demais a partir deste endereço. Espere e tente de novo.")
        if _pedido_aberto(get_supabase(), pedido_id, _agora()) is None:
            raise RecusaDoConsentimento(404, _PEDIDO_ENCERRADO)
        if not TETO_DE_CODIGOS_POR_PEDIDO.admitir(pedido_id, config.oauth_codigos_por_pedido):
            raise _demais(
                TETO_DE_CODIGOS_POR_PEDIDO,
                "Códigos demais para este pedido. Volte ao app de IA e comece a conexão de novo.",
            )
        chave_do_teto = hashlib.sha256(email.encode()).hexdigest()
        if not TETO_DE_CODIGOS_POR_EMAIL.admitir(chave_do_teto, config.oauth_codigos_por_email_por_dia):
            raise _demais(TETO_DE_CODIGOS_POR_EMAIL, "Códigos demais para este e-mail hoje. Tente de novo amanhã.")
    except RecusaDoConsentimento as recusa:
        return recusa.resposta()
    tarefas.add_task(_preparar_codigo, pedido_id, email, config)
    return _resposta_sem_cache(CodigoPedido(enviado=True), status=202)


def _conferir_codigo(db: Any, pedido_id: str, hash_email: str, codigo: str, agora: datetime) -> dict:
    """A linha do código, se `codigo` é o certo — e ela vira usada; senão,
    a recusa genérica.

    Só a linha MAIS RECENTE de (pedido, e-mail) vale: pedir outro código mata o
    anterior, usado ou não. Cada conferência GASTA uma tentativa antes de
    comparar, num UPDATE condicional na contagem que leu: dez chutes ao mesmo
    tempo não viram dez comparações — só o que ganha a vez compara. O uso
    único é outro UPDATE condicional (`usado_em IS NULL`).
    """
    linhas = (
        db.table(_TABELA_DOS_CODIGOS)
        .select("id, email_conta_ia_id, hash_codigo, expira_em, tentativas, usado_em")
        .eq("pedido_id", pedido_id)
        .eq("hash_email", hash_email)
        .order("criado_em", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not linhas:
        raise RecusaDoConsentimento(400, _CODIGO_RECUSADO)
    linha = linhas[0]
    tentativas = int(linha.get("tentativas") or 0)
    if (
        linha.get("usado_em") is not None
        or _vencido(linha.get("expira_em"), agora)
        or tentativas >= emails_ia.TENTATIVAS_POR_CODIGO
    ):
        raise RecusaDoConsentimento(400, _CODIGO_RECUSADO)
    gasta = (
        db.table(_TABELA_DOS_CODIGOS)
        .update({"tentativas": tentativas + 1})
        .eq("id", str(linha["id"]))
        .eq("tentativas", tentativas)
        .is_("usado_em", "null")
        .execute()
        .data
        or []
    )
    esperado = emails_ia.hash_do_codigo(_chave_dos_codigos(), pedido_id, hash_email, codigo)
    if not gasta or not hmac.compare_digest(esperado, str(linha.get("hash_codigo") or "")):
        raise RecusaDoConsentimento(400, _CODIGO_RECUSADO)
    usada = (
        db.table(_TABELA_DOS_CODIGOS)
        .update({"usado_em": _instante(agora)})
        .eq("id", str(linha["id"]))
        .is_("usado_em", "null")
        .execute()
        .data
        or []
    )
    if not usada:
        raise RecusaDoConsentimento(400, _CODIGO_RECUSADO)
    return linha


def _dono_do_codigo(db: Any, linha: dict, email: str, config: ConfiguracaoMcp) -> dict:
    """O cadastro que recebeu o código, conferido AGORA: ainda ativo, ainda
    deste e-mail, e de conta que ainda pode conectar. Só quem acertou o código
    chega aqui — por isso as mensagens podem dizer o que houve."""
    email_id = linha.get("email_conta_ia_id")
    if not email_id:
        # O código de um e-mail sem cadastro: ninguém o recebeu.
        raise RecusaDoConsentimento(400, _CODIGO_RECUSADO)
    cadastros = (
        db.table(_TABELA_DOS_EMAILS).select("id, usuario_coordenacao_id, email, confirmado_em, removido_em")
        .eq("id", str(email_id)).limit(1).execute().data
        or []
    )
    if (
        not cadastros
        or cadastros[0].get("removido_em") is not None
        # Só o confirmado recebe o código (`_cadastro_que_aprova`); reconferir
        # aqui é a mesma régua do "removido", lida na hora.
        or cadastros[0].get("confirmado_em") is None
        or cadastros[0].get("email") != email
    ):
        raise RecusaDoConsentimento(400, _EMAIL_SEM_CADASTRO)
    if not _conta_pode_conectar(db, str(cadastros[0]["usuario_coordenacao_id"]), config):
        raise RecusaDoConsentimento(400, _CONTA_SEM_PERMISSAO)
    return cadastros[0]


@router_consentimento.post("/{pedido_id}/aprovar", response_model=RespostaAoPedido)
def aprovar_pedido(pedido_id: str, body: AprovarPedidoBody, request: Request) -> Response:
    """Aprova com o código que chegou ao e-mail: gera o código do RFC (uso
    único) e devolve para onde o browser volta.

    A conexão nasce em nome do coordenador DONO do e-mail — é essa conta que o
    MCP identifica em cada chamada. Não há outra porta: sem e-mail e código,
    nem a sessão de administrador aprova.
    """
    config = _config_ligada()
    try:
        _limitar_consentimento(request, config)
        db = get_supabase()
        agora = _agora()
        pedido = _pedido_aberto(db, pedido_id, agora)
        if pedido is None:
            raise RecusaDoConsentimento(404, _PEDIDO_ENCERRADO)
        email = emails_ia.normalizar_email(body.email)
        codigo_digitado = emails_ia.codigo_no_formato(body.codigo)
        if codigo_digitado is None:
            raise RecusaDoConsentimento(400, _CODIGO_RECUSADO)
        hash_email = emails_ia.hash_do_email(_chave_dos_codigos(), email)
        linha = _conferir_codigo(db, pedido_id, hash_email, codigo_digitado, agora)
        cadastro = _dono_do_codigo(db, linha, email, config)
        dono = str(cadastro["usuario_coordenacao_id"])
        if not _decidir(db, pedido_id, dono, True, agora):
            raise RecusaDoConsentimento(404, _PEDIDO_ENCERRADO)
    except RecusaDoConsentimento as recusa:
        return recusa.resposta()

    codigo = secrets.token_urlsafe(32)
    db.table("oauth_codigo_mcp").insert(
        {
            "hash_codigo": _sha256(codigo),
            "pedido_id": pedido_id,
            "usuario_coordenacao_id": dono,
            "criado_em": _instante(agora),
            "expira_em": _instante(agora + VALIDADE_DO_CODIGO),
        }
    ).execute()
    try:
        db.table(_TABELA_DOS_EMAILS).update({"ultimo_uso_em": _instante(agora)}).eq("id", str(cadastro["id"])).execute()
    except Exception:  # o "último uso" do card é informação, não acesso: não derruba a aprovação
        log.warning("não consegui gravar o último uso do e-mail da conta de IA", exc_info=True)
    cliente = _carregar_cliente(db, pedido["client_id"])
    auditar(
        db, ACAO_PEDIDO_APROVADO, canal=CANAL,
        ator_tipo="coordenador", ator_id=dono,
        recurso=f"oauth_cliente/{pedido['client_id']}", ip=_ip(request),
        # Quem, para onde e por qual e-mail — mascarado, com o id do cadastro;
        # nunca os códigos, o state nem o desafio.
        detalhe={
            "cliente": _nome_declarado(cliente)[:80],
            "redirectHost": _host_de_volta(pedido["redirect_uri"]),
            "email": emails_ia.mascarar_email(email),
            "emailIaId": str(cadastro["id"]),
        },
    )
    return _resposta_sem_cache(
        RespostaAoPedido(
            redirecionarPara=_com_parametros(
                pedido["redirect_uri"], code=codigo, state=pedido.get("state"), iss=config.emissor
            )
        )
    )


@router_consentimento.post("/{pedido_id}/recusar", response_model=RespostaAoPedido)
def recusar_pedido(pedido_id: str, request: Request) -> Response:
    """Recusa: o app recebe `access_denied` (RFC 6749 §4.1.2.1). Recusar não
    pede código nem sessão — tirar acesso nunca depende de poder dar acesso.

    Vai ao log, e não à trilha: anônimo, e quem enche a trilha à vontade a
    torna inútil (o motivo do cadastro). O pedido decidido guarda a recusa,
    sem autor (0073). A volta é a do link da página de erro do /authorize: a
    pessoa clica vendo o host.
    """
    config = _config_ligada()
    try:
        _limitar_consentimento(request, config)
        db = get_supabase()
        agora = _agora()
        pedido = _pedido_aberto(db, pedido_id, agora)
        if pedido is None or not _decidir(db, pedido_id, None, False, agora):
            raise RecusaDoConsentimento(404, _PEDIDO_ENCERRADO)
    except RecusaDoConsentimento as recusa:
        return recusa.resposta()
    log.info(
        "pedido de conexão OAuth recusado: cliente %s, volta em %s",
        pedido["client_id"], _host_de_volta(pedido["redirect_uri"]),
    )
    return _resposta_sem_cache(
        RespostaAoPedido(
            redirecionarPara=_com_parametros(
                pedido["redirect_uri"],
                error="access_denied",
                error_description=_ascii("O pedido de conexão foi recusado no SAS."),
                state=pedido.get("state"),
                iss=config.emissor,
            )
        )
    )


# ─── /oauth/token ────────────────────────────────────────────────────────

_CODIGO_INVALIDO = "Código de autorização inválido, vencido ou já usado."
_REFRESH_INVALIDO = "Refresh token inválido, vencido ou já usado."


def _nome_da_conexao(cliente: ClienteOAuth, redirect_uri: str) -> str:
    """O nome da linha de token_mcp: o que o app declarou e o host de volta —
    o nome sozinho não prova nada (qualquer um se cadastra como "Claude").

    O host vai INTEIRO no fim, e quem encolhe para caber nos 80 é o nome
    declarado. Cortar a frase toda no fim deixava o app decidir o que sobrava:
    um nome de 80 caracteres empurrava o host para fora, e a conexão de um
    app qualquer ficava igual à do Claude na lista de Conexões de IA, onde a
    administradora procura o que revogar (revisão de segurança de 25/10). Host
    maior que o nome inteiro (só no limite do DNS) perde o COMEÇO: o fim é o
    domínio que alguém registrou.
    """
    host = _host_de_volta(redirect_uri)
    if len(host) + 3 > _MAXIMO_DO_NOME_DA_CONEXAO:
        host = "…" + host[-(_MAXIMO_DO_NOME_DA_CONEXAO - 4):]
    sufixo = f" ({host})"
    declarado = _nome_declarado(cliente)[: _MAXIMO_DO_NOME_DA_CONEXAO - len(sufixo)].rstrip()
    return f"{declarado}{sufixo}".strip()


def _trocar_codigo(
    db: Any, cliente: ClienteOAuth, campos: dict[str, str], recurso: str | None, ip: str | None,
    config: ConfiguracaoMcp,
) -> dict[str, Any]:
    """authorization_code → access + refresh (RFC 6749 §4.1.3, RFC 7636 §4.6).

    Tudo que dá para conferir é conferido ANTES de gastar o código, e o gasto
    é um UPDATE condicional (`usado_em IS NULL`): de duas trocas simultâneas,
    só uma ganha. Código reapresentado depois de usado derruba a conexão que
    ele gerou (RFC 6749 §4.1.2: "SHOULD revoke").
    """
    codigo = campos.get("code")
    verificador = campos.get("code_verifier")
    if codigo is None:
        raise ErroOAuth("invalid_request", "Falta code.")
    if verificador is None:
        raise ErroOAuth("invalid_request", "Falta code_verifier: o PKCE é obrigatório (RFC 7636 4.5).")
    if not _FORMATO_PKCE.fullmatch(verificador):
        raise ErroOAuth("invalid_request", "code_verifier fora do formato do RFC 7636 4.1.")

    hash_codigo = _sha256(codigo)
    linhas = (
        db.table("oauth_codigo_mcp")
        .select("hash_codigo, pedido_id, usuario_coordenacao_id, expira_em, usado_em, token_mcp_id")
        .eq("hash_codigo", hash_codigo)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not linhas:
        raise ErroOAuth("invalid_grant", _CODIGO_INVALIDO)
    linha = linhas[0]
    if linha.get("usado_em") is not None:
        _derrubar_conexao(
            db, linha.get("token_mcp_id"), motivo="codigo_reapresentado", ator_tipo="sistema", ator_id=None, ip=ip
        )
        raise ErroOAuth("invalid_grant", _CODIGO_INVALIDO)

    pedidos = (
        db.table("oauth_pedido_mcp").select(_COLUNAS_DO_PEDIDO).eq("id", linha["pedido_id"]).limit(1).execute().data
        or []
    )
    agora = _agora()
    # O código foi emitido para ESTE cliente (§4.1.3) e ainda vale.
    if not pedidos or pedidos[0]["client_id"] != cliente.client_id or _vencido(linha.get("expira_em"), agora):
        raise ErroOAuth("invalid_grant", _CODIGO_INVALIDO)
    pedido = pedidos[0]

    enviada = campos.get("redirect_uri")
    if enviada is None and pedido.get("redirect_uri_explicita", True) is not False:
        raise ErroOAuth("invalid_request", "Falta redirect_uri: o pedido de autorização trouxe uma (RFC 6749 4.1.3).")
    if enviada is not None and enviada != pedido["redirect_uri"]:
        raise ErroOAuth("invalid_grant", "redirect_uri diferente da do pedido de autorização (RFC 6749 4.1.3).")
    if not hmac.compare_digest(desafio_s256(verificador), str(pedido["code_challenge"])):
        raise ErroOAuth("invalid_grant", "code_verifier não confere com o code_challenge (RFC 7636 4.6).")

    gasto = (
        db.table("oauth_codigo_mcp")
        .update({"usado_em": _instante(agora)})
        .eq("hash_codigo", hash_codigo)
        .is_("usado_em", "null")
        .execute()
        .data
        or []
    )
    if not gasto:
        raise ErroOAuth("invalid_grant", _CODIGO_INVALIDO)

    coordenador_id = str(linha["usuario_coordenacao_id"])
    if not _conta_pode_conectar(db, coordenador_id, config):
        raise ErroOAuth("invalid_grant", "A conta que aprovou não pode mais conectar uma IA ao SAS.")

    fim_da_conexao = agora + timedelta(days=config.validade_do_refresh_oauth_dias)
    expira_acesso = min(agora + timedelta(minutes=config.validade_do_acesso_oauth_minutos), fim_da_conexao)
    acesso, hash_acesso, prefixo = tokens.gerar()
    nome = _nome_da_conexao(cliente, pedido["redirect_uri"])
    conexao = (
        db.table("token_mcp")
        .insert(
            {
                "usuario_coordenacao_id": coordenador_id,
                "nome": nome,
                "origem": "oauth",
                "oauth_cliente_id": cliente.client_id,
                "hash_acesso": hash_acesso,
                "prefixo": prefixo,
                "criado_em": _instante(agora),
                "expira_em": _instante(expira_acesso),
            }
        )
        .execute()
        .data[0]
    )
    refresh = None
    if "refresh_token" in cliente.concessoes:
        refresh, hash_refresh = _novo_refresh()
        db.table("oauth_refresh_mcp").insert(
            {
                "hash_refresh": hash_refresh,
                "client_id": cliente.client_id,
                "usuario_coordenacao_id": coordenador_id,
                "token_mcp_id": str(conexao["id"]),
                "pedido_id": pedido["id"],
                "scope": ESCOPO,
                "resource": recurso or pedido.get("resource"),
                "criado_em": _instante(agora),
                "expira_em": _instante(fim_da_conexao),
            }
        ).execute()
    db.table("oauth_codigo_mcp").update({"token_mcp_id": str(conexao["id"])}).eq("hash_codigo", hash_codigo).execute()
    auditar(
        db, ACAO_CONEXAO_EMITIDA, canal=CANAL,
        ator_tipo="coordenador", ator_id=coordenador_id,
        recurso=recurso_do_token(str(conexao["id"])), ip=ip,
        # Como na emissão pela tela: o nome, nunca o token, o hash ou o prefixo.
        detalhe={"nome": nome, "origem": "oauth"},
    )
    return _resposta_de_token(acesso, expira_acesso, agora, refresh)


def _girar_refresh(
    db: Any, cliente: ClienteOAuth, campos: dict[str, str], ip: str | None, config: ConfiguracaoMcp
) -> dict[str, Any]:
    """refresh_token → access + refresh NOVOS; os antigos morrem (RFC 6749 §6,
    RFC 9700 §4.14.2).

    O access novo é a MESMA linha de token_mcp com outro hash — o antigo deixa
    de existir na hora, e a tela continua vendo uma conexão só. O refresh novo
    herda o prazo do velho. Refresh já girado que volta é sinal de que vazou
    (o legítimo e o ladrão, um deles tem o velho): a conexão inteira cai.
    """
    refresh = campos.get("refresh_token")
    if refresh is None:
        raise ErroOAuth("invalid_request", "Falta refresh_token.")
    escopo = campos.get("scope")
    if escopo is not None and set(escopo.split()) - {ESCOPO}:
        # §6: o refresh não pede escopo que a concessão não tem.
        raise ErroOAuth("invalid_scope", "O único escopo é sas.leitura.")
    if not _FORMATO_DO_REFRESH.fullmatch(refresh):
        raise ErroOAuth("invalid_grant", _REFRESH_INVALIDO)

    linhas = (
        db.table("oauth_refresh_mcp")
        .select("id, client_id, usuario_coordenacao_id, token_mcp_id, pedido_id, scope, resource, expira_em, "
                "revogado_em, substituido_por")
        .eq("hash_refresh", _sha256(refresh))
        .limit(1)
        .execute()
        .data
        or []
    )
    if not linhas:
        raise ErroOAuth("invalid_grant", _REFRESH_INVALIDO)
    linha = linhas[0]
    conexao_id = str(linha["token_mcp_id"])

    def derrubar(motivo: str) -> None:
        _derrubar_conexao(db, conexao_id, motivo=motivo, ator_tipo="sistema", ator_id=None, ip=ip)

    if linha["client_id"] != cliente.client_id:
        # O refresh de um app na mão de outro: vazou (§10.4).
        derrubar("refresh_de_outro_cliente")
        raise ErroOAuth("invalid_grant", _REFRESH_INVALIDO)
    if linha.get("revogado_em") is not None:
        if linha.get("substituido_por"):
            derrubar("refresh_reapresentado")
        raise ErroOAuth("invalid_grant", _REFRESH_INVALIDO)
    agora = _agora()
    fim_da_conexao = _ler_instante(linha.get("expira_em"))
    if fim_da_conexao is None or fim_da_conexao <= agora:
        raise ErroOAuth("invalid_grant", _REFRESH_INVALIDO)
    if not _conta_pode_conectar(db, str(linha["usuario_coordenacao_id"]), config):
        derrubar("conta_sem_permissao")
        raise ErroOAuth("invalid_grant", "A conta desta conexão não pode mais conectar uma IA ao SAS.")

    girado = (
        db.table("oauth_refresh_mcp")
        .update({"revogado_em": _instante(agora)})
        .eq("id", str(linha["id"]))
        .is_("revogado_em", "null")
        .execute()
        .data
        or []
    )
    if not girado:
        # Outra troca com o MESMO refresh ganhou agora há pouco: um dos dois
        # pedidos não é do app legítimo.
        derrubar("refresh_reapresentado")
        raise ErroOAuth("invalid_grant", _REFRESH_INVALIDO)

    acesso, hash_acesso, prefixo = tokens.gerar()
    expira_acesso = min(agora + timedelta(minutes=config.validade_do_acesso_oauth_minutos), fim_da_conexao)
    trocada = (
        db.table("token_mcp")
        .update({"hash_acesso": hash_acesso, "prefixo": prefixo, "expira_em": _instante(expira_acesso)})
        .eq("id", conexao_id)
        .is_("revogado_em", "null")
        .execute()
        .data
        or []
    )
    if not trocada:
        # A conexão foi revogada (na tela, pelo /revoke): o refresh morre com ela.
        derrubar("conexao_revogada")
        raise ErroOAuth("invalid_grant", "Esta conexão foi revogada no SAS.")

    novo, hash_novo = _novo_refresh()
    inserido = (
        db.table("oauth_refresh_mcp")
        .insert(
            {
                "hash_refresh": hash_novo,
                "client_id": cliente.client_id,
                "usuario_coordenacao_id": str(linha["usuario_coordenacao_id"]),
                "token_mcp_id": conexao_id,
                "pedido_id": linha.get("pedido_id"),
                "scope": linha.get("scope") or ESCOPO,
                "resource": linha.get("resource"),
                "criado_em": _instante(agora),
                "expira_em": _instante(fim_da_conexao),
            }
        )
        .execute()
        .data[0]
    )
    db.table("oauth_refresh_mcp").update({"substituido_por": str(inserido["id"])}).eq("id", str(linha["id"])).execute()
    return _resposta_de_token(acesso, expira_acesso, agora, novo)


def _token(
    campos: dict[str, str], recursos: list[str], cred: Credenciais, ip: str | None, config: ConfiguracaoMcp
) -> dict[str, Any]:
    tipo = campos.get("grant_type")
    if tipo is None:
        raise ErroOAuth("invalid_request", "Falta grant_type.")
    if tipo not in CONCESSOES:
        raise ErroOAuth("unsupported_grant_type", "Só authorization_code e refresh_token.")
    db = get_supabase()
    cliente = _cliente_autenticado(db, cred)
    if tipo not in cliente.concessoes:
        raise ErroOAuth("unauthorized_client", f"O app não cadastrou o grant {tipo}.")
    recurso = _conferir_recursos(recursos, config)
    if tipo == "authorization_code":
        return _trocar_codigo(db, cliente, campos, recurso, ip, config)
    return _girar_refresh(db, cliente, campos, ip, config)


@router.post("/oauth/token")
async def emitir_token(request: Request) -> Response:
    """A troca: código por access + refresh, e refresh por um par novo."""
    config = _config_ligada()
    try:
        _limitar(TETO_DO_TOKEN, request, config.oauth_tentativas_por_minuto)
        campos, recursos = await _formulario(request)
        cred = _credenciais(request, campos)
        corpo = await asyncio.to_thread(_token, campos, recursos, cred, _ip(request), config)
    except ErroOAuth as erro:
        return erro.resposta()
    return JSONResponse(corpo, headers=_SEM_CACHE)


# ─── /oauth/revoke (RFC 7009) ────────────────────────────────────────────


def _revogar_pelo_cliente(campos: dict[str, str], cred: Credenciais, ip: str | None) -> None:
    """Revoga o access OU o refresh — e, com ele, a conexão inteira.

    Revogar só o access deixaria o app pegar outro com o refresh no minuto
    seguinte; o RFC 7009 §2.1 deixa o servidor revogar a concessão toda, e é
    o que o app quer quando se desconecta. Token desconhecido, ou de OUTRO
    app, devolve 200 sem fazer nada (§2.2): dizer "existe, mas não é seu"
    contaria a quem tenta que acertou um token.
    """
    token = campos.get("token")
    if token is None:
        raise ErroOAuth("invalid_request", "Falta token (RFC 7009 2.1).")
    db = get_supabase()
    cliente = _cliente_autenticado(db, cred)
    alvo = None
    if tokens.formato_valido(token):
        linhas = (
            db.table("token_mcp")
            .select("id")
            .eq("hash_acesso", tokens.hash_do_token(token))
            .eq("origem", "oauth")
            .eq("oauth_cliente_id", cliente.client_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        alvo = linhas[0]["id"] if linhas else None
    elif _FORMATO_DO_REFRESH.fullmatch(token):
        linhas = (
            db.table("oauth_refresh_mcp").select("token_mcp_id, client_id").eq("hash_refresh", _sha256(token))
            .limit(1).execute().data
            or []
        )
        if linhas and linhas[0]["client_id"] == cliente.client_id:
            alvo = linhas[0]["token_mcp_id"]
    _derrubar_conexao(db, alvo, motivo="revogada_pelo_app", ator_tipo="oauth_cliente", ator_id=cliente.client_id, ip=ip)


@router.post("/oauth/revoke")
async def revogar_token(request: Request) -> Response:
    config = _config_ligada()
    try:
        _limitar(TETO_DO_TOKEN, request, config.oauth_tentativas_por_minuto)
        campos, _ = await _formulario(request)
        cred = _credenciais(request, campos)
        await asyncio.to_thread(_revogar_pelo_cliente, campos, cred, _ip(request))
    except ErroOAuth as erro:
        return erro.resposta()
    return Response(status_code=200, headers=_SEM_CACHE)
