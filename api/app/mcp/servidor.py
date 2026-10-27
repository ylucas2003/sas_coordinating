"""O servidor MCP da coordenação: o `Server` de BAIXO nível do SDK (docs/43 §5).

Baixo nível, e não FastMCP, porque as tools já existem — são as do registro
único (`app/chat/ferramentas.py`) — e o FastMCP quer definir tool por
decorador, com validação e serialização próprias. Aqui o SDK só fala o
protocolo; o despacho, a validação de argumento, o prazo e o erro sem texto
cru continuam sendo os do registro, o mesmo caminho do chat do app.

O que o SDK 1.30.0 NÃO faz, e este módulo faz (cada um verificado no mapa do
SDK de 24/10):

  * tool fora do `tools/list` chega ao handler do `call_tool` mesmo assim —
    o catálogo recusa pelo nome (`Catalogo.obter`);
  * exceção dentro do handler vai CRUA ao cliente (`str(e)`, com a URL do
    PostgREST se ela estiver na mensagem) — aqui nada sobe;
  * `get_access_token()` fica velho no modo stateful — a identidade sai do
    `scope["user"]` DESTE request, posto pelo BearerAuthBackend;
  * com `validate_input=True` o `jsonschema` recusa `"10"` num inteiro que o
    registro converteria — a validação fica com o registro (invariante 3);
  * todo método responde a qualquer token aceito — aqui tools/list e
    prompts/* passam pela mesma regra de papel do tools/call
    (`_exigir_quem_pode_consultar`).

A ordem de uma chamada: identidade → limite por minuto → papel → catálogo →
teto de linhas → registro (cliente PostgREST novo) → pseudônimo (só com
MCP_MOSTRAR_NOME_DO_ALUNO=false; desde 26/10 o padrão é o nome real) →
serialização → auditoria. O limite vem antes do catálogo para que sondar nome
de tool também gaste a cota, e antes do papel para que a recusa de quem não
pode também tenha teto (cada recusa é uma linha de auditoria).
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

import mcp.types as types
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from mcp.server.lowlevel import Server
from mcp.shared.exceptions import McpError

from ..auth import PAPEIS_DE_COORDENACAO
from ..chat.ferramentas import REGISTRO, Ferramenta, Registro, Sessao, serializar_para_modelo
from ..observabilidade import request_id_aceito, request_id_atual
from ..supabase_client import criar_cliente_supabase
from . import auditoria_mcp, tokens
from .catalogo import ESCOPO, Catalogo
from .configuracao import ConfiguracaoMcp, get_configuracao_mcp
from .dados import CriarCliente, cliente_novo, fechar_cliente
from .pseudonimo import CadastroDeAlunos, PseudonimoRecusado, pseudonimizar
from .tokens import Identidade

log = logging.getLogger("sas.mcp")

NOME_DO_SERVIDOR = "sas-coordenacao"
VERSAO = "0.0.1"

#: O único escopo do MCP. É o que o `RequireAuthMiddleware` exige e o que o
#: token pessoal (e, na Fase 3, o do OAuth) carrega.
ESCOPO_DE_LEITURA = "sas.leitura"
#: O `client_id` do AccessToken do token pessoal. No OAuth (Fase 3) é o
#: client_id do cadastro dinâmico.
CLIENTE_DO_ACESSO = "sas-mcp"

_TAMANHO_MAXIMO_DO_NOME = 128  # o teto de nome de tool do protocolo

MENSAGEM_SEM_IDENTIDADE = (
    "Não consegui confirmar a sua conexão com o SAS (token revogado, vencido ou "
    "serviço fora do ar). Peça a quem administra o SAS uma conexão nova."
)
MENSAGEM_LGPD = (
    "O resultado desta consulta traria nome de aluno que o MCP não sabe trocar pela "
    "matrícula, e por isso foi bloqueado inteiro (LGPD, docs/43 §5.4). Não repita a "
    "chamada; use outra ferramenta."
)
MENSAGEM_SO_ADMINISTRADOR = (
    "Esta conexão está em nome de uma conta que não é de administrador, e este SAS está "
    "configurado para que só o administrador consulte por uma IA de fora (LGPD, docs/43 "
    "§5.4). Não repita a chamada; diga ao usuário que peça acesso a quem administra o SAS."
)


def _mensagem_de_falha(nome: str) -> str:
    # A mesma frase do registro (ferramentas.py), para o modelo reagir igual.
    return (
        f"A consulta '{nome}' falhou do nosso lado. Não repita a chamada; "
        "diga ao usuário que esse dado não está disponível agora."
    )


# ─── Identidade ──────────────────────────────────────────────────────────


def acesso_da_identidade(token: str, identidade: Identidade) -> AccessToken:
    """O `AccessToken` do SDK que carrega a identidade até o `call_tool`."""
    return AccessToken(
        token=token,
        client_id=CLIENTE_DO_ACESSO,
        scopes=[ESCOPO_DE_LEITURA],
        subject=identidade.coordenador_id,
        claims={"token_id": identidade.token_id, "nome": identidade.nome, "papel": identidade.papel},
    )


def identidade_do_acesso(acesso: AccessToken) -> Identidade | None:
    claims = acesso.claims or {}
    token_id = claims.get("token_id")
    if not acesso.subject or not token_id:
        return None
    papel = claims.get("papel")
    return Identidade(
        token_id=str(token_id),
        coordenador_id=str(acesso.subject),
        nome=str(claims.get("nome") or ""),
        papel=papel if papel in PAPEIS_DE_COORDENACAO else "coordenador",
    )


#: Recebe o request HTTP da chamada (ou None, no stdio e no cliente em
#: memória) e devolve quem chama — ou None, e aí nada roda.
Identificador = Callable[[Any], Awaitable[Identidade | None]]


async def identidade_do_pedido(pedido: Any) -> Identidade | None:
    """HTTP: a identidade que o BearerAuthBackend validou NESTE request.

    `scope.get("user")` e não `request.user`: a propriedade faz assert quando
    o AuthenticationMiddleware não está instalado — e sem ele aqui tem de dar
    None (recusa), não exceção.
    """
    escopo = getattr(pedido, "scope", None)
    usuario = escopo.get("user") if isinstance(escopo, dict) else None
    if not isinstance(usuario, AuthenticatedUser):
        return None
    return identidade_do_acesso(usuario.access_token)


async def conferir_em_thread(
    token: str, criar_cliente: CriarCliente = criar_cliente_supabase
) -> Identidade | None:
    """`tokens.conferir` fora do event loop: o PostgREST é síncrono, e o MCP
    atende todo mundo num loop só. Erro de banco SOBE."""
    if not tokens.formato_valido(token):
        return None

    def _conferir() -> Identidade | None:
        with cliente_novo(criar_cliente) as cliente:
            return tokens.conferir(cliente, token)

    return await asyncio.to_thread(_conferir)


class IdentidadePeloToken:
    """stdio: o token vem do ambiente e é RECONFERIDO a cada chamada.

    Conferir só na subida deixaria um token revogado valendo até alguém
    reiniciar o processo — e "a próxima consulta já é recusada" é a promessa
    da tela de revogar.
    """

    def __init__(self, token: str, criar_cliente: CriarCliente = criar_cliente_supabase) -> None:
        self._token = token
        self._criar_cliente = criar_cliente

    async def __call__(self, pedido: Any) -> Identidade | None:
        try:
            return await conferir_em_thread(self._token, self._criar_cliente)
        except Exception:
            log.warning("não consegui reconferir o token do stdio", exc_info=True)
            return None


# ─── Limite por minuto ───────────────────────────────────────────────────


class LimitePorMinuto:
    """Janela deslizante de 60 s por token, EM MEMÓRIA.

    Vale porque o MCP é um processo só (uvicorn com o app como objeto não
    sobe worker). Com dois, cada um teria a sua contagem e o limite dobraria
    calado — o mesmo motivo do limite de login em routes/auth.py.

    Sem trava: tudo aqui roda no event loop, sem `await` entre ler e gravar.
    """

    JANELA_S = 60.0

    def __init__(self, por_minuto: int, *, relogio: Callable[[], float] = time.monotonic) -> None:
        self.por_minuto = por_minuto
        self._relogio = relogio
        self._chamadas: dict[str, deque[float]] = {}
        self._ja_recusado: set[str] = set()

    def admitir(self, chave: str) -> tuple[bool, bool]:
        """(admitida, primeira recusa desde a última admitida).

        A segunda metade existe para a auditoria: registrar CADA recusa daria
        a quem passou do limite um jeito de encher `evento_auditoria` sem teto
        — fica a primeira, que é a que diz "bateu no limite às 14h32".
        """
        agora = self._relogio()
        fila = self._chamadas.setdefault(chave, deque())
        while fila and fila[0] <= agora - self.JANELA_S:
            fila.popleft()
        if len(fila) < self.por_minuto:
            fila.append(agora)
            self._ja_recusado.discard(chave)
            return True, False
        primeira = chave not in self._ja_recusado
        self._ja_recusado.add(chave)
        return False, primeira


# ─── Roteiros (os prompts do MCP) ────────────────────────────────────────


#: `app.chat.roteiros`, calculado do pacote para valer em qualquer raiz.
_MODULO_DE_ROTEIROS = __name__.rsplit(".", 2)[0] + ".chat.roteiros"


class FonteDeRoteiros(Protocol):
    """O contrato de `app.chat.roteiros` (docs/43 §4.3): os playbooks da
    coordenação, os mesmos arquivos que o assistente do app carrega."""

    def listar(self, escopo: str) -> list[Any]: ...

    def obter(self, escopo: str, nome: str) -> Any | None: ...


def roteiros_do_sas() -> FonteDeRoteiros | None:
    """O módulo de roteiros, se ele existir neste checkout.

    Import tardio e tolerante SÓ à ausência do próprio módulo: sem roteiros o
    MCP sobe com `prompts/list` vazio, mas um erro de import DENTRO dele sobe,
    para não esconder bug como se fosse "ainda não tem".
    """
    # `import_module` e não `from ..chat import roteiros`: este levanta um
    # ImportError genérico quando o submódulo falta, indistinguível de um
    # import quebrado lá dentro.
    try:
        return importlib.import_module(_MODULO_DE_ROTEIROS)  # type: ignore[return-value]
    except ModuleNotFoundError as erro:
        if erro.name != _MODULO_DE_ROTEIROS:
            raise
        return None


# ─── O servidor ──────────────────────────────────────────────────────────


def instrucoes(config: ConfiguracaoMcp) -> str:
    """As `instructions` do initialize: mínimas, de propósito. O método fica
    nas descrições das tools e nos roteiros (docs/43 §5.1).

    Com o nome real (o padrão desde 26/10), o texto não fala em matrícula: era
    a frase do pseudônimo, e dizê-la com o nome saindo faria o modelo trocar
    um pelo outro por conta própria. O que fica é o lembrete de que são
    adolescentes — a minimização (LGPD art. 6º, III) também vale no que o
    modelo repete."""
    aluno = (
        "Os alunos aparecem pelo nome, como no SAS. São adolescentes: use o que vier deles só "
        "para responder ao que foi perguntado."
        if config.mostrar_nome_do_aluno
        else (
            "O aluno aparece pela matrícula ('Aluno 2026001'), nunca pelo nome: não tente "
            "descobrir o nome nem o peça ao usuário — quem precisa dele consulta o próprio SAS."
        )
    )
    return (
        "SAS: o acompanhamento das turmas ITA/IME do Colégio Ari de Sá — simulados, ciclos de "
        "provas, notas e os alunos que pedem atenção. Este servidor só LÊ: nenhuma ferramenta "
        f"altera dado. {aluno} As listas vêm com no máximo {config.teto_de_linhas} itens; "
        "prefira perguntas estreitas (um ciclo, um simulado, um aluno)."
    )


def _resultado(resultado: dict[str, Any]) -> types.CallToolResult:
    # Texto já compactado pelo `serializar_para_modelo`, e não um dict: dict
    # o SDK devolveria também como structuredContent e como JSON com indent=2,
    # passando por cima da compactação (lowlevel/server.py).
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=serializar_para_modelo(resultado))],
        isError="erro" in resultado,
    )


def _erro(texto: str) -> types.CallToolResult:
    return _resultado({"erro": texto})


@dataclass(frozen=True)
class _Chamador:
    identidade: Identidade
    ip: str | None
    request_id: str | None


def montar_servidor(
    *,
    config: ConfiguracaoMcp | None = None,
    registro: Registro | None = None,
    identificar: Identificador = identidade_do_pedido,
    criar_cliente: CriarCliente = criar_cliente_supabase,
    roteiros: FonteDeRoteiros | None = None,
    cadastro: CadastroDeAlunos | None = None,
    limite: LimitePorMinuto | None = None,
) -> Server:
    """O Server do MCP. Tudo que fala com o mundo entra por parâmetro — é o
    que deixa os testes rodarem sem rede e sem banco."""
    config = config or get_configuracao_mcp()
    registro = registro or REGISTRO
    catalogo = Catalogo(
        registro, teto_de_linhas=config.teto_de_linhas, com_nome_do_aluno=config.mostrar_nome_do_aluno
    )
    cadastro = cadastro or CadastroDeAlunos()
    limite = limite or LimitePorMinuto(config.limite_por_minuto)

    servidor: Server = Server(NOME_DO_SERVIDOR, version=VERSAO, instructions=instrucoes(config))

    def _pedido_atual() -> Any:
        try:
            return servidor.request_context.request
        except LookupError:
            return None

    def _fonte_de_roteiros() -> FonteDeRoteiros | None:
        return roteiros if roteiros is not None else roteiros_do_sas()

    async def _auditar(
        chamador: _Chamador, ferramenta: str | None, desfecho: str, inicio: float, linhas: int
    ) -> None:
        duracao_ms = int((time.perf_counter() - inicio) * 1000)

        def _gravar() -> None:
            with cliente_novo(criar_cliente) as cliente:
                auditoria_mcp.registrar_chamada(
                    cliente,
                    identidade=chamador.identidade,
                    ferramenta=ferramenta,
                    desfecho=desfecho,
                    duracao_ms=duracao_ms,
                    linhas=linhas,
                    ip=chamador.ip,
                    request_id=chamador.request_id,
                )

        try:
            await asyncio.to_thread(_gravar)
        except Exception:
            # Melhor-esforço, como `auditoria.registrar` — mas ERROR, como o
            # INSERT que falha em `registrar_chamada`: a chamada ficou sem
            # linha na trilha (docs/43 §5.3).
            log.error(
                "[AÇÃO NECESSÁRIA] não consegui abrir cliente para auditar a chamada do MCP",
                exc_info=True,
                extra={"ferramenta": ferramenta, "desfecho": desfecho},
            )

    def _pseudonimizar(resultado: dict[str, Any]) -> Any:
        atual = cadastro.obter(criar_cliente)
        return pseudonimizar(
            resultado,
            matricula_por_id=atual.matricula_por_id,
            nomes_de_alunos=atual.nomes,
        )

    async def _despachar(
        f: Ferramenta, identidade: Identidade, argumentos: dict[str, Any] | None
    ) -> tuple[dict[str, Any], str]:
        sessao = Sessao(
            tipo="coordenador",
            usuario=f"coord:{identidade.coordenador_id}",
            papel=identidade.papel,
            nome=identidade.nome,
        )
        args = catalogo.preparar_argumentos(f, argumentos)
        # Criado numa thread: montar o cliente HTTP lê o pacote de CAs do
        # disco, e isso não pode parar o event loop de todo mundo.
        cliente = await asyncio.to_thread(criar_cliente)
        inicio = time.perf_counter()
        try:
            resultado = await registro.despachar_async(sessao, f.nome, cliente, args)
        finally:
            # Passou do prazo, a thread da tool continua rodando com este
            # cliente (o registro a abandona, não a mata): fechá-lo agora
            # derrubaria a requisição dela no meio. Fica para o coletor.
            if time.perf_counter() - inicio < f.prazo_s:
                await asyncio.to_thread(fechar_cliente, cliente)

        if not config.mostrar_nome_do_aluno:
            try:
                resultado = await asyncio.to_thread(_pseudonimizar, resultado)
            except PseudonimoRecusado as recusa:
                # O motivo traz só o CAMINHO do campo: o texto que tinha o nome
                # nunca entra nele, e chave que não é nome de campo vira
                # `<chave>` (pseudonimo._segmento) — senão o nome iria ao log.
                log.warning("resultado recusado pelo pseudônimo: %s", recusa, extra={"ferramenta": f.nome})
                return {"erro": MENSAGEM_LGPD}, "recusa_lgpd"
            except Exception:
                # Sem o cadastro, ou com um resultado que nem vira JSON, não há
                # como saber o que é nome de aluno: recusa.
                log.exception("não consegui pseudonimizar o resultado", extra={"ferramenta": f.nome})
                return {"erro": _mensagem_de_falha(f.nome)}, "falha"
        return resultado, ("erro" if "erro" in resultado else "ok")

    def _pode_consultar(identidade: Identidade) -> bool:
        """MCP_EMISSAO_SO_ADMINISTRADOR vale para USAR, não só para emitir.

        Só na emissão, a regra cairia sozinha: um administrador rebaixado
        seguiria com a IA de fora lendo a escola inteira até o token vencer
        (90 dias), e os tokens que coordenadores emitiram com a regra
        desligada voltariam a valer depois de ela ser religada. O papel vem
        da RPC, lido da tabela A CADA requisição — o mesmo princípio de
        `auth.conta_ainda_e_administradora`: rebaixamento que só vale depois
        não é rebaixamento.
        """
        return not config.emissao_so_administrador or identidade.papel == "administrador"

    async def _exigir_quem_pode_consultar() -> None:
        """A porta de `_pode_consultar` também no que DESCREVE o servidor:
        tools/list, prompts/list e prompts/get.

        Só no tools/call, o token de quem não é administrador — emitido com a
        regra desligada, de um administrador rebaixado, ou plantado — abria o
        catálogo inteiro, com os schemas, e o texto dos roteiros da
        coordenação (revisão final de 26/10). Erro JSON-RPC, e não lista
        vazia: "0 ferramentas" não diz a ninguém por quê, e o cliente mostra a
        mensagem. A mesma para qualquer nome de roteiro — não confirma qual
        existe. O `initialize` fica aberto: as `instructions` dizem o que o
        servidor é, não o que há nele, e recusá-lo seria uma falha de conexão
        sem explicação nenhuma.
        """
        try:
            identidade = await identificar(_pedido_atual())
        except Exception:
            # Exceção solta aqui iria crua ao cliente, como `str(e)`
            # (lowlevel/server.py) — vira o "não consegui confirmar".
            log.exception("não consegui identificar quem lista o servidor")
            identidade = None
        if identidade is None:
            mensagem = MENSAGEM_SEM_IDENTIDADE
        elif not _pode_consultar(identidade):
            mensagem = MENSAGEM_SO_ADMINISTRADOR
        else:
            return
        raise McpError(types.ErrorData(code=types.INVALID_REQUEST, message=mensagem))

    async def _chamar(nome: str, argumentos: dict[str, Any] | None, inicio: float) -> types.CallToolResult:
        pedido = _pedido_atual()
        identidade = await identificar(pedido)
        if identidade is None:
            # No HTTP não acontece: o RequireAuthMiddleware barra antes. Sem
            # identidade não roda nada — nem a auditoria, que não teria de quem.
            log.warning("chamada de tool sem identidade validada: recusada")
            return _erro(MENSAGEM_SEM_IDENTIDADE)

        cliente_http = getattr(pedido, "client", None)
        rid = request_id_atual()
        if rid == "-":
            # Sem o middleware da casa: o header do cliente, pela mesma régua
            # dele (um id torto derrubava o INSERT da trilha — auditoria_mcp).
            cabecalhos = getattr(pedido, "headers", None)
            rid = request_id_aceito(cabecalhos.get("x-request-id")) if cabecalhos is not None else None
        chamador = _Chamador(
            identidade=identidade,
            ip=getattr(cliente_http, "host", None),
            request_id=rid,
        )

        conhecida = catalogo.obter(nome)
        admitida, primeira_recusa = limite.admitir(identidade.token_id)
        if not admitida:
            if primeira_recusa:
                await _auditar(chamador, conhecida.nome if conhecida else None, "limite", inicio, 0)
            return _erro(
                f"Limite de {limite.por_minuto} consultas por minuto desta conexão atingido. "
                "Espere um minuto antes de consultar de novo."
            )

        if not _pode_consultar(identidade):
            # Antes do catálogo: a resposta é a mesma para qualquer nome, e
            # quem não pode consultar não descobre o que existe.
            await _auditar(chamador, conhecida.nome if conhecida else None, "sem_permissao", inicio, 0)
            return _erro(MENSAGEM_SO_ADMINISTRADOR)

        f = conhecida
        if f is None:
            await _auditar(chamador, None, "inexistente", inicio, 0)
            # A mesma resposta do registro para nome inventado: não confirma
            # que a tool existe fora do MCP (docs/43 §3.2, invariante 1).
            return _erro(f"tool '{str(nome)[:_TAMANHO_MAXIMO_DO_NOME]}' não existe")

        try:
            resultado, desfecho = await _despachar(f, identidade, argumentos)
        except Exception:
            # O registro já não deixa a tool subir exceção; o que chega aqui é
            # do caminho em volta dela (abrir o cliente, a thread). Vira a
            # mesma falha genérica — e, ao contrário da última barreira
            # abaixo, com identidade conhecida, então AUDITADA.
            log.exception("chamada do MCP falhou fora da tool", extra={"ferramenta": f.nome})
            resultado, desfecho = {"erro": _mensagem_de_falha(f.nome)}, "falha"
        linhas = auditoria_mcp.contar_linhas(resultado) if desfecho == "ok" else 0
        await _auditar(chamador, f.nome, desfecho, inicio, linhas)
        return _resultado(resultado)

    @servidor.list_tools()
    async def listar_ferramentas() -> list[types.Tool]:
        return catalogo.listar()

    # A porta do tools/list vai no handler do PROTOCOLO, e não na função de
    # cima: o SDK a chama também por dentro, com `None`, quando o tools/call
    # não acha o nome no cache dele (`_get_cached_tool_definition`,
    # lowlevel/server.py). Ali a recusa sairia pelo `except` do call_tool do
    # SDK, sem passar por `_chamar` — e sem a linha `sem_permissao` na trilha.
    _listar_do_sdk = servidor.request_handlers[types.ListToolsRequest]

    async def _listar_pelo_protocolo(pedido: types.ListToolsRequest | None) -> types.ServerResult:
        if pedido is not None:
            await _exigir_quem_pode_consultar()
        return await _listar_do_sdk(pedido)

    servidor.request_handlers[types.ListToolsRequest] = _listar_pelo_protocolo

    # validate_input=False: quem valida e converte é o registro (invariante 3).
    @servidor.call_tool(validate_input=False)
    async def chamar_ferramenta(nome: str, argumentos: dict[str, Any]) -> types.CallToolResult:
        inicio = time.perf_counter()
        try:
            return await _chamar(nome, argumentos, inicio)
        except Exception:
            # Última barreira: o SDK mandaria `str(e)` ao cliente. Nome fora
            # do catálogo não vai ao log como "ferramenta": é texto do cliente.
            conhecida = nome if catalogo.obter(nome) is not None else None
            log.exception("chamada de tool do MCP falhou", extra={"ferramenta": conhecida})
            return _erro(_mensagem_de_falha(str(nome)[:_TAMANHO_MAXIMO_DO_NOME]))

    @servidor.list_prompts()
    async def listar_roteiros() -> list[types.Prompt]:
        await _exigir_quem_pode_consultar()
        fonte = _fonte_de_roteiros()
        if fonte is None:
            return []
        try:
            itens = await asyncio.to_thread(fonte.listar, ESCOPO)
        except Exception:
            log.exception("não consegui listar os roteiros da coordenação")
            return []
        return [
            types.Prompt(name=r.nome, title=r.titulo, description=r.descricao)
            for r in itens
            if getattr(r, "escopo", ESCOPO) == ESCOPO
        ]

    @servidor.get_prompt()
    async def obter_roteiro(nome: str, argumentos: dict[str, str] | None) -> types.GetPromptResult:
        await _exigir_quem_pode_consultar()
        fonte = _fonte_de_roteiros()
        roteiro = None
        if fonte is not None:
            try:
                roteiro = await asyncio.to_thread(fonte.obter, ESCOPO, nome)
            except LookupError:
                roteiro = None
            except Exception:
                # McpError com texto nosso: exceção solta viraria erro JSON-RPC
                # com `str(e)` cru (lowlevel/server.py).
                log.exception("não consegui ler o roteiro", extra={"rota": nome})
                raise McpError(
                    types.ErrorData(code=types.INTERNAL_ERROR, message="Não consegui ler esse roteiro agora.")
                ) from None
        if roteiro is None or getattr(roteiro, "escopo", ESCOPO) != ESCOPO:
            raise McpError(
                types.ErrorData(
                    code=types.INVALID_PARAMS,
                    message=f"roteiro '{str(nome)[:_TAMANHO_MAXIMO_DO_NOME]}' não existe",
                )
            )
        return types.GetPromptResult(
            description=roteiro.descricao,
            messages=[
                types.PromptMessage(
                    role="user", content=types.TextContent(type="text", text=roteiro.texto)
                )
            ],
        )

    return servidor
