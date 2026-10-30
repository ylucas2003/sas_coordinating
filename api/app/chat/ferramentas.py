"""O registro único das ferramentas do assistente (docs/43 §3).

Até 24/10/2026 eram dois despachantes — `tools.executar` para a coordenação e
`tools_aluno.executar_para_aluno` para o aluno — que só tinham em comum o
formato do erro. Toda guarda que se quisesse (prazo, chamada repetida, erro sem
texto cru) teria de ser escrita duas vezes, e o MCP da coordenação (docs/43 §5)
seria a terceira cópia. O desenho vem do `runToolCall` do MCP da Solomon: um
ponto de passagem só, e as superfícies — hoje o agente de `agente.py`, amanhã o
MCP — leem dele.

Três peças:

  `Sessao`      quem está do outro lado, SEMPRE montada do JWT;
  `Ferramenta`  uma tool e o que se sabe dela (escopo, leitura, prazo);
  `Registro`    o catálogo por escopo e o despacho, que aplica as invariantes
                do docs/43 §3.2 na ordem em que estão lá.

As tools continuam nos módulos de sempre (`tools/*.py`, `tools_aluno.py`,
`roteiros.py`), no formato `(schema, handler)`: este arquivo as recolhe, não as
reescreve. O que o par não diz — o prazo próprio de uma tool, se ela vai ao MCP
— o módulo declara num `METADADOS` opcional (`_ferramentas_do_modulo`).

E o que uma tool pode anexar à resposta, além do texto, também mora aqui: o
catálogo FECHADO de artefatos por escopo (`TIPOS_DE_ARTEFATO`) e a única leitura
de "que artefatos este resultado produziu" (`artefatos_do_resultado`), que
`rotas.py` usa para gravar e que o front espelha em `chatStream.ts`.
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import functools
import inspect
import json
import logging
import math
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from types import ModuleType
from typing import Any, Literal

from ..auth import papel_da_sessao
from . import roteiros as _roteiros
from . import tools as _tools_coordenacao
from . import tools_aluno as _tools_aluno

log = logging.getLogger("sas.chat.ferramentas")

Escopo = Literal["aluno", "coordenacao"]

#: Abaixo dos 300 s que o nginx reserva para a volta inteira de tool calling,
#: com folga para o modelo ainda responder depois. É estimativa: não havia
#: medida de duração por tool antes deste módulo, e o log que ele grava é o que
#: permite recalibrar (docs/43 §8).
PRAZO_PADRAO_S = 90.0

#: O mesmo teto que `agente.py` já aplicava ao conteúdo de `role=tool`.
LIMITE_DO_RESULTADO = 60_000

#: Campos que identificam a PESSOA no escopo do aluno. Vêm do token, nunca do
#: modelo: um `aluno_id` alucinado — ou plantado por injeção — não pode
#: escolher de quem é a nota que o mentor lê.
_IDENTIDADE_DO_ALUNO = frozenset({"aluno_id"})

#: O mesmo para a coordenação: o `sub` da conta conectada, que nenhum schema
#: declara e o modelo não escolhe. Ao contrário do `aluno_id`, só chega à tool
#: que o PEDE na assinatura (`_identidade_da_coordenacao`): quase toda tool da
#: coordenação lê a escola inteira e não tem dono. A que tem é a lista do
#: banco de questões — "o dono é sempre o da sessão, nunca vem da URL nem do
#: corpo" (docs/22 §5.2) —, desde 30/10 também no MCP (docs/43 §4.4).
_IDENTIDADE_DA_COORDENACAO = frozenset({"coordenador_id"})

_INTEIRO = re.compile(r"[+-]?\d+")


# ─── Sessão ──────────────────────────────────────────────────────────────


class SessaoRecusada(Exception):
    """O token não abre sessão de assistente. A mensagem vai para o 403."""


@dataclass(frozen=True)
class Sessao:
    tipo: Literal["aluno", "coordenador"]
    #: O dono das threads em `chat_thread.usuario_id`: `aluno:<id>` ou `coord:<sub>`.
    usuario: str
    aluno_id: str | None = None
    papel: str | None = None
    nome: str = ""

    @property
    def escopo(self) -> Escopo:
        return "aluno" if self.tipo == "aluno" else "coordenacao"

    @property
    def coordenador_id(self) -> str | None:
        """O `sub` da conta da coordenação: `usuario` sem o `coord:`.

        Derivado, e não um campo, porque `usuario` já é ele (`sessao_do_token`
        e o MCP montam `coord:<sub>`, o MCP com o `coordenador_id` do token —
        `usuario_coordenacao.id`, o mesmo `sub` do JWT): dois campos com a
        mesma identidade divergiriam no primeiro lugar que montasse um só.
        """
        if self.tipo != "coordenador":
            return None
        return self.usuario.removeprefix("coord:") or None


def sessao_do_token(user: dict) -> Sessao:
    """A sessão do assistente a partir do payload do JWT. Fail-closed.

    Decide duas coisas que não podem divergir — de quem é a thread e qual
    catálogo a pessoa enxerga —, e por isso mora num lugar só. Um `else`
    genérico aqui daria o escopo de COORDENAÇÃO, com as tools que leem
    qualquer um dos ~900 alunos, a todo token que não fosse de aluno: foi o
    caminho do token de download (test_auth_chat.py) e seria o da cantina
    (test_cantina.py).
    """
    tipo = user.get("tipo")
    nome = (user.get("nome") or "").strip()

    if tipo == "aluno":
        aluno_id = user.get("aluno_id")
        if not aluno_id:
            raise SessaoRecusada("Token de aluno sem identidade")
        return Sessao(
            tipo="aluno", usuario=f"aluno:{aluno_id}", aluno_id=str(aluno_id), nome=nome
        )

    if tipo == "coordenador":
        sub = user.get("sub")
        if not sub:
            raise SessaoRecusada("Token sem identidade de coordenação")
        return Sessao(
            tipo="coordenador", usuario=f"coord:{sub}", papel=papel_da_sessao(user), nome=nome
        )

    raise SessaoRecusada("Token não autoriza uso do chat")


# ─── Ferramenta ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Ferramenta:
    nome: str
    descricao: str
    #: JSON Schema dos argumentos — o que o MODELO vê. A validação que vale é
    #: a do despacho (invariante 3), não esta: o modelo manda o que quiser.
    parametros: dict[str, Any]
    escopo: Escopo
    #: O handler de sempre: `(cliente, **args)` na coordenação e
    #: `(cliente, *, aluno_id, **args)` no aluno.
    handler: Callable[..., Any]
    #: Não altera dado de NEGÓCIO. Cache derivado não conta: `meu_insight_do_ciclo`
    #: grava em `insight_aluno_ciclo`, e continua sendo leitura do ponto de vista
    #: de quem pergunta.
    somente_leitura: bool = True
    #: Entra no catálogo do MCP da coordenação (docs/43 §5.1). Desligado por
    #: padrão: quem liga é o `METADADOS` do módulo, tool por tool, porque cada
    #: uma é dado saindo do SAS para um provedor de fora (docs/43 §5.4). NUNCA
    #: no escopo do aluno — o registro recusa no import.
    expor_no_mcp: bool = False
    prazo_s: float = PRAZO_PADRAO_S

    @property
    def propriedades(self) -> dict[str, Any]:
        return (self.parametros or {}).get("properties") or {}

    def schema_openai(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.nome,
                "description": self.descricao,
                "parameters": self.parametros,
            },
        }


@functools.cache
def parametros_do_handler(handler: Callable[..., Any]) -> tuple[frozenset[str], frozenset[str]]:
    """(aceitos, obrigatórios) da assinatura, sem o `cliente` do começo.

    Lido da ASSINATURA, e não do `required` do schema, porque é ela que decide
    se a chamada quebra: um `required` esquecido no schema não impede o
    `TypeError`, e o teste de higiene usa esta mesma função para pegar a
    divergência entre os dois.
    """
    aceitos: list[str] = []
    obrigatorios: list[str] = []
    for i, (nome, p) in enumerate(inspect.signature(handler).parameters.items()):
        if i == 0 or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        aceitos.append(nome)
        if p.default is p.empty:
            obrigatorios.append(nome)
    return frozenset(aceitos), frozenset(obrigatorios)


# ─── A volta ─────────────────────────────────────────────────────────────


@dataclass
class Volta:
    """Uma resposta do agente: da mensagem do usuário até o texto final.

    Guarda o que já foi consultado com SUCESSO, para a invariante 4 — e
    sucesso ENTREGUE: o que o prazo abandonou não conta, mesmo que a thread
    termine bem depois (`despachar_async`). Não é cache de resultado, de
    propósito: devolver o resultado anterior faria o modelo tratá-lo como dado
    novo. O MCP da Solomon trocou cache por erro explícito pelo mesmo motivo
    (`observability/toolInstrumentation.ts` de lá).
    """

    _feitas: set[str] = field(default_factory=set)

    def ja_feita(self, chave: str) -> bool:
        return chave in self._feitas

    def registrar(self, chave: str) -> None:
        self._feitas.add(chave)


# ─── A resposta de prazo ─────────────────────────────────────────────────


class RespostaDePrazo(dict):
    """O que `despachar_async` devolve quando a tool passa do prazo.

    É o erro que o modelo lê — um dict como o de qualquer erro, e só isso vai
    para o JSON: o histórico, o SSE, `chat_mensagem` — mais `thread`, um Future
    que se resolve quando a thread abandonada termina DE FATO. É para quem
    emprestou recurso à chamada e só pode reavê-lo depois disso: o agente
    segura o cliente extra e a vaga de MAX_TOOLS_SIMULTANEAS até lá
    (agente.py). Copiado — `copy`, `deepcopy`, pickle — vira dict simples: o
    Future não viaja.
    """

    def __init__(self, erro: str, *, thread: asyncio.Future[None]) -> None:
        super().__init__(erro=erro)
        self.thread = thread

    def __reduce__(self) -> tuple[Any, ...]:
        return (dict, (dict(self),))


def _avisar_o_loop(loop: asyncio.AbstractEventLoop, fim: asyncio.Future[None]) -> None:
    """Resolve, de dentro da thread da tool, o Future do loop. Nunca lança: com o
    loop já fechado (o processo desligando) não sobra quem espere."""

    def resolver() -> None:
        if not fim.done():
            fim.set_result(None)

    with contextlib.suppress(RuntimeError):
        loop.call_soon_threadsafe(resolver)


# ─── O registro ──────────────────────────────────────────────────────────


class Registro:
    def __init__(self, ferramentas: Iterable[Ferramenta]) -> None:
        self._por_nome: dict[str, Ferramenta] = {}
        for f in ferramentas:
            # Nome único entre os DOIS escopos: o log, a auditoria e o MCP
            # identificam a tool só pelo nome.
            if f.nome in self._por_nome:
                raise ValueError(f"duas ferramentas com o nome {f.nome!r}")
            # O MCP é da coordenação (docs/43 §0): uma tool do aluno lá fora
            # seria o dado de um menor lido por uma IA de terceiro, e sem o
            # `aluno_id` do token para amarrá-la a alguém.
            if f.expor_no_mcp and f.escopo != "coordenacao":
                raise ValueError(f"{f.nome!r} é do escopo {f.escopo!r} e não pode ir ao MCP")
            self._por_nome[f.nome] = f

    def catalogo(self, escopo: Escopo) -> list[Ferramenta]:
        return [f for f in self._por_nome.values() if f.escopo == escopo]

    def schemas_openai(self, escopo: Escopo) -> list[dict[str, Any]]:
        return [f.schema_openai() for f in self.catalogo(escopo)]

    def obter(self, sessao: Sessao, nome: str) -> Ferramenta | None:
        """A ferramenta, se ela existe NO ESCOPO da sessão."""
        f = self._por_nome.get(nome)
        return f if f is not None and f.escopo == sessao.escopo else None

    def despachar(
        self,
        sessao: Sessao,
        nome: str,
        cliente: Any,
        args: dict | None,
        *,
        volta: Volta | None = None,
    ) -> dict[str, Any]:
        """Executa uma chamada de tool. Síncrono: as tools leem pelo cliente
        PostgREST, que é síncrono — quem está num event loop usa
        `despachar_async`."""
        resultado, consulta = self._despachar(sessao, nome, cliente, args, volta)
        if consulta is not None and volta is not None:
            volta.registrar(consulta)
        return resultado

    async def despachar_async(
        self,
        sessao: Sessao,
        nome: str,
        cliente: Any,
        args: dict | None,
        *,
        volta: Volta | None = None,
    ) -> dict[str, Any]:
        """`despachar` numa thread, com o prazo da ferramenta (invariante 5).

        ⚠️ O prazo abandona a thread, não a mata — Python não tem como. Ela
        termina sozinha e grava a própria linha de log com a duração real, que
        é justamente a medida de que o docs/43 §8 precisa para recalibrar. Duas
        coisas decorrem disso, e moram aqui:

          * a consulta só conta como feita (invariante 4) quando o resultado
            CHEGA a quem chamou: o registro na `Volta` acontece aqui, depois da
            espera, e não na thread. Feito lá, a abandonada que terminasse bem
            depois do prazo registraria uma consulta cujo resultado ninguém
            leu, e a chamada idêntica seguinte ouviria "o resultado está
            acima" — um resultado que o modelo nunca viu (revisão antecipada do
            motor, 25/10);
          * quem emprestou recurso à chamada — o agente, com o cliente extra e
            a vaga de MAX_TOOLS_SIMULTANEAS — só pode reavê-lo quando a thread
            terminar DE FATO: a resposta de prazo é uma `RespostaDePrazo`, que
            traz esse fim em `.thread`.
        """
        f = self.obter(sessao, nome)
        prazo = f.prazo_s if f is not None else PRAZO_PADRAO_S
        inicio = time.perf_counter()
        loop = asyncio.get_running_loop()
        fim_da_thread: asyncio.Future[None] = loop.create_future()

        def na_thread() -> tuple[dict[str, Any], str | None]:
            try:
                return self._despachar(sessao, nome, cliente, args, volta)
            finally:
                _avisar_o_loop(loop, fim_da_thread)

        try:
            resultado, consulta = await asyncio.wait_for(asyncio.to_thread(na_thread), timeout=prazo)
        except TimeoutError:
            _registrar_chamada(sessao, nome, "prazo", inicio)
            return RespostaDePrazo(
                f"A consulta '{nome}' passou de {prazo:.0f} s e foi abandonada. "
                "Responda com o que você já tem, ou proponha ao usuário uma "
                "pergunta mais estreita.",
                thread=fim_da_thread,
            )
        if consulta is not None and volta is not None:
            volta.registrar(consulta)
        return resultado

    def _despachar(
        self,
        sessao: Sessao,
        nome: str,
        cliente: Any,
        args: dict | None,
        volta: Volta | None,
    ) -> tuple[dict[str, Any], str | None]:
        """A chamada, com a linha de log: o resultado e, se ela deu certo, a
        chave da consulta — que quem ENTREGA o resultado registra na volta."""
        inicio = time.perf_counter()
        resultado, desfecho, chave = self._executar(sessao, nome, cliente, args, volta)
        _registrar_chamada(sessao, nome, desfecho, inicio)
        return resultado, (chave if desfecho == "ok" else None)

    def _executar(
        self,
        sessao: Sessao,
        nome: str,
        cliente: Any,
        args: dict | None,
        volta: Volta | None,
    ) -> tuple[dict[str, Any], str, str | None]:
        # 1 · Escopo. Fora dele, a resposta é a mesma de um nome inventado:
        # confirmar que a tool existe já seria dizer ao aluno o que a
        # coordenação consegue ver.
        f = self.obter(sessao, nome)
        if f is None:
            return {"erro": f"tool '{nome}' não existe"}, "inexistente", None

        # 2 e 3 · Identidade e argumentos.
        kwargs, erro = _preparar_argumentos(f, sessao, args)
        if erro is not None:
            return {"erro": erro}, "argumento", None

        # 4 · Repetição na mesma resposta. Aqui só se CONSULTA a volta; quem
        # registra é quem entrega o resultado (`despachar`, `despachar_async`).
        chave = _chave_da_chamada(nome, kwargs)
        if volta is not None and volta.ja_feita(chave):
            return {
                "erro": (
                    "Esta consulta já foi feita nesta mesma resposta, com os mesmos "
                    "argumentos, e o resultado está acima. Use-o em vez de repetir."
                )
            }, "repetida", None

        # 6 · Erro interno.
        try:
            if f.escopo == "aluno":
                bruto = f.handler(cliente, aluno_id=sessao.aluno_id, **kwargs)
            else:
                bruto = f.handler(cliente, **_identidade_da_coordenacao(f, sessao), **kwargs)
        except Exception:
            # O stack vai para o log; o texto da exceção NÃO vai ao modelo, que
            # o repetiria para o usuário — mensagem de exceção pode carregar a
            # URL do PostgREST (docs/14 §5, a mesma regra do handler de 500).
            log.exception(
                "ferramenta falhou",
                extra={"ferramenta": nome, "escopo": f.escopo, "usuario": sessao.usuario},
            )
            return {
                "erro": (
                    f"A consulta '{nome}' falhou do nosso lado. Não repita a chamada; "
                    "diga ao usuário que esse dado não está disponível agora."
                )
            }, "falha", None

        resultado = bruto if isinstance(bruto, dict) else {"resultado": bruto}
        if "erro" in resultado:
            # Erro de DOMÍNIO, escrito pela própria tool para o modelo ler
            # ("este simulado não tem detalhe por questão"). Não conta como
            # consulta feita: tentar de novo com outro argumento é legítimo.
            return resultado, "erro", None
        return resultado, "ok", chave


# ─── Argumentos ──────────────────────────────────────────────────────────


def _preparar_argumentos(
    f: Ferramenta, sessao: Sessao, args: dict | None
) -> tuple[dict[str, Any], str | None]:
    """Invariantes 2 e 3: os kwargs que o handler vai receber, ou o erro."""
    brutos = dict(args) if isinstance(args, dict) else {}

    identidade = _IDENTIDADE_DO_ALUNO if f.escopo == "aluno" else _IDENTIDADE_DA_COORDENACAO
    intrusos = sorted(identidade & brutos.keys())
    if intrusos:
        # Aviso, e não info: num escopo que não declara a identidade, ela só
        # chega por alucinação ou por alguém tentando ler o de outra pessoa.
        # (Fora do schema ela já seria descartada abaixo; tirar aqui é o que
        # deixa o rastro no log.)
        log.warning(
            "identidade no argumento descartada: %s",
            ", ".join(intrusos),
            extra={"ferramenta": f.nome, "escopo": f.escopo, "usuario": sessao.usuario},
        )
        for campo in intrusos:
            brutos.pop(campo)

    propriedades = f.propriedades
    kwargs: dict[str, Any] = {}
    for campo, valor in brutos.items():
        # Chave fora do schema é DESCARTADA, não recusada: o modelo inventa
        # parâmetro com frequência, e recusar custa uma volta inteira do loop.
        # `None` também sai, para o default do handler valer.
        if campo not in propriedades or valor is None:
            continue
        valor, erro = _coagir(campo, valor, propriedades[campo] or {})
        if erro is not None:
            return {}, f"argumentos inválidos para '{f.nome}': {erro}"
        kwargs[campo] = valor

    _, obrigatorios = parametros_do_handler(f.handler)
    faltando = sorted(obrigatorios - identidade - kwargs.keys())
    if faltando:
        return {}, f"argumentos inválidos para '{f.nome}': falta {', '.join(faltando)}"
    return kwargs, None


def _identidade_da_coordenacao(f: Ferramenta, sessao: Sessao) -> dict[str, Any]:
    """`coordenador_id` da SESSÃO para a tool da coordenação que o pede; {} para
    as outras — que nem o aceitariam (`TypeError`)."""
    aceitos, _ = parametros_do_handler(f.handler)
    if "coordenador_id" not in aceitos:
        return {}
    return {"coordenador_id": sessao.coordenador_id}


def _coagir(campo: str, valor: Any, esquema: dict[str, Any]) -> tuple[Any, str | None]:
    """Confere o tipo e o enum do JSON Schema, convertendo o que é inequívoco.

    O modelo manda `"limite": "10"` e `"ativo": "true"` com frequência. Converter
    o caso inequívoco poupa uma volta; o resto vira erro que diz o que se
    esperava, em vez de um `TypeError` lá dentro do handler.
    """
    tipo = esquema.get("type")

    if tipo == "integer":
        if isinstance(valor, float) and valor.is_integer():
            valor = int(valor)
        elif isinstance(valor, str) and _INTEIRO.fullmatch(valor.strip()):
            valor = int(valor.strip())
        # `bool` é subclasse de `int` em Python: `True` não é um limite.
        if isinstance(valor, bool) or not isinstance(valor, int):
            return valor, f"'{campo}' deveria ser um número inteiro"
    elif tipo == "number":
        if isinstance(valor, str):
            try:
                valor = float(valor.strip().replace(",", "."))
            except ValueError:
                return valor, f"'{campo}' deveria ser um número"
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return valor, f"'{campo}' deveria ser um número"
    elif tipo == "boolean":
        if isinstance(valor, str) and valor.strip().lower() in ("true", "false"):
            valor = valor.strip().lower() == "true"
        if not isinstance(valor, bool):
            return valor, f"'{campo}' deveria ser true ou false"
    elif tipo == "string":
        # Id numérico às vezes chega como número.
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            valor = str(valor)
        if not isinstance(valor, str):
            return valor, f"'{campo}' deveria ser um texto"
    elif tipo == "array" and not isinstance(valor, list):
        return valor, f"'{campo}' deveria ser uma lista"

    opcoes = esquema.get("enum")
    if opcoes is not None and valor not in opcoes:
        return valor, f"'{campo}' deve ser um de: {', '.join(map(str, opcoes))}"
    return valor, None


def _chave_da_chamada(nome: str, kwargs: dict[str, Any]) -> str:
    return f"{nome}:{json.dumps(kwargs, sort_keys=True, ensure_ascii=False, default=str)}"


def _registrar_chamada(sessao: Sessao, nome: str, desfecho: str, inicio: float) -> None:
    log.info(
        "ferramenta %s: %s",
        nome,
        desfecho,
        extra={
            "ferramenta": nome,
            "escopo": sessao.escopo,
            "desfecho": desfecho,
            "duracao_ms": int((time.perf_counter() - inicio) * 1000),
            "usuario": sessao.usuario,
        },
    )


# ─── Artefatos ───────────────────────────────────────────────────────────

#: O CATÁLOGO FECHADO do que uma resposta pode anexar além do texto, por
#: escopo (docs/27 §7; docs/43 §4.1, defeito 6). O modelo escolhe de uma lista e
#: nunca produz markup (docs/27 §9, regra 1): tipo fora daqui não é gravado, e o
#: CHECK de `chat_artefato.tipo` (migration 0070) aceita a união dos dois, mais
#: o `tabela` da 0008. O front espelha o do aluno em `web/src/dominio/chatStream.ts`
#: (`CATALOGO_DE_ARTEFATOS`) — mudou aqui, mude lá e numa migration nova; os
#: dois descompassos reprovam teste (test_chat_ferramentas.py e
#: test_chat_persistencia_de_artefatos.py).
#:
#: Ficam de fora de propósito: `extrato_xp`, porque o XP ainda é mock (docs/26
#: §3); `formula`, que é da família inline (docs/27 §3); e `tabela`, que o CHECK
#: aceita desde a 0008 sem que tool nenhuma a produza.
TIPOS_DE_ARTEFATO: dict[Escopo, frozenset[str]] = {
    "aluno": frozenset(
        {"barras_corte", "questao", "lista_questoes", "prova", "linha_temporal", "histograma"}
    ),
    "coordenacao": frozenset({"histograma", "linha_temporal", "csv", "navegacao"}),
}

#: Só nascem da tool própria, nunca do campo genérico `artefato`: o link de
#: `navegacao` tem a rota montada no servidor a partir de (tipo, id) e o rótulo
#: lido do banco (docs/31 §2.4), e o `csv` é o export de `exportar_csv`. Aceitos
#: pelo campo genérico, qualquer tool poderia fabricar um link. O front recusa os
#: dois pelo mesmo caminho (`artefatoAnexado`, chatStream.ts).
_SO_DA_TOOL_PROPRIA = frozenset({"csv", "navegacao"})

#: O que o campo genérico aceita em ALGUM escopo. É o que `serializar_para_modelo`
#: confere, porque ela não sabe de que escopo veio o resultado.
_TIPOS_DO_CAMPO_GENERICO = frozenset().union(*TIPOS_DE_ARTEFATO.values()) - _SO_DA_TOOL_PROPRIA

#: Teto do título do cartão. Título é uma linha acima do gráfico; passou disto,
#: é texto que veio parar no lugar errado — e ele é impresso na tela de um menor
#: e gravado em `chat_artefato.titulo`.
LIMITE_DO_TITULO = 200


def artefatos_do_resultado(nome_tool: str, resultado: Any, escopo: Escopo) -> list[dict[str, Any]]:
    """Os artefatos que uma chamada de tool produziu, no formato em que são
    gravados: `{tipo, titulo, payload}`. A ÚNICA leitura disso no backend.

    Duas origens, e só duas:

      (a) as formas ANTIGAS, reconhecidas pelo NOME da tool — `gerar_grafico`
          (histograma ou linha temporal), `navegar_para` (navegacao) e
          `exportar_csv` (csv) —, com o `tipo` no topo do resultado. É o
          comportamento de antes deste catálogo, mantido como estava;
      (b) o campo genérico ANINHADO `artefato: {tipo, titulo?, payload}`, de
          qualquer tool, só com tipo do catálogo do escopo e nunca `navegacao`
          nem `csv`.

    ⚠️ `tipo` no topo do resultado NUNCA vira artefato fora de (a):
    `meu_desempenho_em_simulado` devolve `tipo` = o tipo do SIMULADO
    (`fase_1`, `fase_2`), e ler o topo transformaria isso em cartão. É por isso
    que o campo genérico é aninhado (chatStream.test.ts trava o mesmo no front).

    Descarta, com uma linha de log, o que não cabe: tipo fora do catálogo do
    escopo, payload que não é objeto, título que não é texto ou passa de
    `LIMITE_DO_TITULO`. Nunca levanta — quem chama está dentro do gerador SSE,
    depois de a resposta já ter ido para a tela.
    """
    if not isinstance(resultado, dict) or "erro" in resultado:
        return []
    catalogo = TIPOS_DE_ARTEFATO.get(escopo, frozenset())

    candidatos: list[tuple[Any, Any, Any]] = []
    antiga = _forma_antiga(nome_tool, resultado)
    if antiga is not None:
        candidatos.append(antiga)

    anexado = resultado.get("artefato")
    if isinstance(anexado, dict):
        tipo_anexado = anexado.get("tipo")
        # `isinstance` antes do `in`: um tipo que viesse como lista nem é
        # hashable, e o `in` num frozenset levantaria aqui dentro.
        if isinstance(tipo_anexado, str) and tipo_anexado in _SO_DA_TOOL_PROPRIA:
            _descartar(nome_tool, escopo, tipo_anexado, "tipo que só a tool própria produz")
        else:
            candidatos.append((anexado.get("tipo"), anexado.get("titulo"), anexado.get("payload")))
    elif anexado is not None:
        _descartar(nome_tool, escopo, None, "o campo `artefato` não é um objeto")

    artefatos: list[dict[str, Any]] = []
    for tipo, titulo, payload in candidatos:
        motivo = _motivo_de_descarte(tipo, titulo, payload, catalogo)
        if motivo is not None:
            _descartar(nome_tool, escopo, tipo, motivo)
            continue
        artefatos.append({"tipo": tipo, "titulo": titulo, "payload": payload})
    return artefatos


def _forma_antiga(nome_tool: str, resultado: dict[str, Any]) -> tuple[Any, Any, Any] | None:
    """(a) de `artefatos_do_resultado`: o formato próprio de três tools."""
    tipo = resultado.get("tipo")
    if nome_tool == "gerar_grafico" and tipo in ("histograma", "linha_temporal"):
        return tipo, resultado.get("titulo"), resultado.get("payload")
    if nome_tool == "navegar_para" and tipo == "navegacao":
        # Gravado como os outros: reabrir a conversa amanhã tem de devolver os
        # mesmos links clicáveis, não um texto órfão.
        return tipo, resultado.get("titulo"), resultado.get("payload")
    if nome_tool == "exportar_csv" and tipo == "csv":
        # O conteúdo vai no payload (no MVP — para escala, subir pro Storage).
        return (
            tipo,
            resultado.get("titulo"),
            {"conteudo": resultado.get("conteudo"), "nLinhas": resultado.get("nLinhas")},
        )
    return None


def _motivo_de_descarte(
    tipo: Any, titulo: Any, payload: Any, permitidos: frozenset[str]
) -> str | None:
    if not isinstance(tipo, str) or tipo not in permitidos:
        return "tipo fora do catálogo do escopo"
    if not isinstance(payload, dict):
        return "payload não é um objeto"
    if titulo is not None and not isinstance(titulo, str):
        return "título não é texto"
    if isinstance(titulo, str) and len(titulo) > LIMITE_DO_TITULO:
        return f"título com mais de {LIMITE_DO_TITULO} caracteres"
    return None


def _descartar(nome_tool: str, escopo: Escopo, tipo: Any, motivo: str) -> None:
    # Aviso: é tool produzindo o que o catálogo não aceita — erro de quem a
    # escreveu, e a tela pode ter mostrado um cartão que some ao recarregar. Só
    # tipo e motivo: o payload pode carregar dado do aluno.
    log.warning(
        "artefato descartado (%s): %s",
        tipo if isinstance(tipo, str) else type(tipo).__name__,
        motivo,
        extra={"ferramenta": nome_tool, "escopo": escopo},
    )


def _artefato_como_aviso(resultado: Any) -> Any:
    """O campo genérico `artefato` como o MODELO o lê: só o tipo e se anexou.

    O payload é para a tela desenhar — repete o que já está no resultado, ou é
    só o id que o cartão usa para buscar o resto —, e iria ao modelo DUAS vezes:
    nesta volta e, gravado em `chat_mensagem`, em toda mensagem seguinte da
    thread. Do cartão o modelo precisa saber que ele existe, para não
    descrevê-lo de novo nem prometer um que não veio — e por isso `anexado` é
    falso quando o artefato não passaria no catálogo de nenhum escopo.

    As formas antigas (`tipo` no topo) ficam como estão: é o que o modelo lia
    antes, e nelas o payload É o resultado.
    """
    if not isinstance(resultado, dict) or resultado.get("artefato") is None:
        return resultado
    bruto = resultado["artefato"]
    if isinstance(bruto, dict):
        tipo = bruto.get("tipo")
        valido = (
            _motivo_de_descarte(tipo, bruto.get("titulo"), bruto.get("payload"), _TIPOS_DO_CAMPO_GENERICO)
            is None
        )
    else:
        tipo, valido = None, False
    # Cópia rasa: quem grava o artefato lê o resultado CHEIO depois daqui.
    return {
        **resultado,
        "artefato": {"tipo": tipo if isinstance(tipo, str) else None, "anexado": valido},
    }


# ─── O resultado, como o modelo o lê ─────────────────────────────────────

#: Abaixo disto uma lista não encolhe mais: com cabeça e cauda tão curtas, o
#: modelo já não teria o que ler.
_MINIMO_DE_ITENS = 6

_AVISO_DE_COMPACTACAO = (
    "Listas encurtadas para caber no limite: ficaram os primeiros e os últimos "
    "itens de cada uma. Não afirme nada sobre os itens omitidos; se precisar "
    "deles, faça uma consulta mais estreita."
)


def serializar_para_modelo(resultado: Any, limite: int = LIMITE_DO_RESULTADO) -> str:
    """O resultado como `content` de `role=tool`: JSON VÁLIDO de até `limite`.

    Antes era `json.dumps(resultado)[:60_000]` — um corte no meio do JSON, que
    o modelo lia como dado e que ia assim mesmo para `chat_mensagem`, de onde
    volta como histórico nas mensagens seguintes. Aqui as listas mais longas
    encolhem pela metade até caber, mantendo começo e fim: o topo de um ranking
    está no começo e a ponta recente de uma série, no fim (a mesma escolha do
    `compactToolResult.ts` da Solomon, que só fatia e nunca reescreve um
    número). E o resultado diz o que omitiu, para o modelo não concluir nada
    sobre o que não viu.

    Antes de tudo, o artefato aninhado vira `{"tipo": ..., "anexado": true}`
    (`_artefato_como_aviso`): o payload é da tela, não do modelo. O resultado
    recebido não é alterado.
    """
    resultado = _artefato_como_aviso(resultado)
    texto = _json(resultado)
    if len(texto) <= limite:
        return texto

    copia = copy.deepcopy(resultado if isinstance(resultado, dict) else {"resultado": resultado})
    omitidos: dict[str, int] = {}
    # Teto de rodadas só por segurança: cada uma corta metade da maior lista,
    # então o normal é parar em poucas.
    for _ in range(64):
        alvo = _maior_lista(copia)
        if alvo is None or len(alvo[1]) <= _MINIMO_DE_ITENS:
            break
        caminho, lista = alvo
        manter = max(_MINIMO_DE_ITENS, len(lista) // 2)
        cauda = max(1, manter // 4)
        omitidos[caminho] = omitidos.get(caminho, 0) + len(lista) - manter
        lista[:] = lista[: manter - cauda] + lista[len(lista) - cauda :]
        copia["_compactado"] = {"itens_omitidos": omitidos, "aviso": _AVISO_DE_COMPACTACAO}
        if len(_json(copia)) <= limite:
            break

    final = _json(copia)
    if len(final) > limite:
        # Nada mais encolhe — o volume está num texto, não numa lista. Ainda
        # assim sai JSON válido. Um terço do limite porque o escape de aspas e
        # barras pode quase dobrar o tamanho do trecho.
        final = _json(
            {
                "_compactado": {"aviso": "Resultado grande demais; mostrado só o começo."},
                "inicio": texto[: limite // 3],
            }
        )
    log.info("resultado compactado de %d para %d caracteres", len(texto), len(final))
    return final


def _json(valor: Any) -> str:
    # `default=str` porque a convenção "tools devolvem só JSON-serializável"
    # (tools/__init__.py) é convenção: uma data esquecida derrubava a volta.
    return json.dumps(valor, ensure_ascii=False, default=str)


def _maior_lista(raiz: Any) -> tuple[str, list] | None:
    """A lista com mais itens em qualquer profundidade, e o caminho até ela."""
    melhor: tuple[str, list] | None = None
    pilha: list[tuple[str, Any]] = [("", raiz)]
    while pilha:
        caminho, no = pilha.pop()
        if isinstance(no, list):
            if melhor is None or len(no) > len(melhor[1]):
                melhor = (caminho or "(raiz)", no)
            pilha.extend(
                (f"{caminho}[{i}]", item) for i, item in enumerate(no) if isinstance(item, (dict, list))
            )
        elif isinstance(no, dict):
            pilha.extend(
                (f"{caminho}.{k}" if caminho else str(k), v)
                for k, v in no.items()
                if k != "_compactado" and isinstance(v, (dict, list))
            )
    return melhor


# ─── O registro do SAS ───────────────────────────────────────────────────


def _da_tupla(schema: dict[str, Any], handler: Callable[..., Any], escopo: Escopo) -> Ferramenta:
    return Ferramenta(
        nome=schema["name"],
        descricao=schema.get("description") or "",
        parametros=schema.get("parameters") or {"type": "object", "properties": {}},
        escopo=escopo,
        handler=handler,
    )


#: O que um módulo pode dizer de uma tool no `METADADOS`. Chave fora daqui é
#: recusada no import: um `"expor_mcp": True` com erro de digitação ficaria
#: desligado em silêncio, e uma chave inventada amanhã seria lida como se valesse.
CHAVES_DE_METADADOS = frozenset({"prazo_s", "expor_no_mcp"})

#: O prazo de uma tool não passa disto: o nginx corta a volta INTEIRA em 300 s
#: (invariante 5), e um prazo maior nunca chegaria a disparar.
PRAZO_MAXIMO_S = 300.0


def _ferramentas_do_modulo(modulo: ModuleType, *listas: tuple[str, Escopo]) -> list[Ferramenta]:
    """As tools de um módulo, com o que o `METADADOS` dele diz de cada uma.

    `listas` diz de que atributo sai cada lista `(schema, handler)` e de que
    escopo ela é — `("TOOLS", "coordenacao")`; `roteiros.py` tem uma de cada.

    `METADADOS` é OPCIONAL, e cada chave dele também:

        METADADOS = {"estado_do_sync_canvas": {"prazo_s": 20.0, "expor_no_mcp": True}}

    Ele fica no módulo, ao lado do `TOOLS`, para quem escreve a tool decidir o
    prazo e a exposição no mesmo lugar em que escreve o handler — e não numa
    lista central que envelhece longe dele.

    Falha FECHADA no import, com ValueError: chave desconhecida, nome que não
    está nas listas do módulo, valor do tipo errado, e `expor_no_mcp` no
    escopo do aluno. Todos são erro de quem escreveu o módulo, e o pior momento
    para descobrir é com o MCP no ar: uma tool exposta por engano é dado de
    aluno saindo do SAS (docs/43 §5.4).
    """
    origem = getattr(modulo, "__name__", repr(modulo))
    ferramentas = [
        _da_tupla(schema, handler, escopo)
        for atributo, escopo in listas
        for schema, handler in getattr(modulo, atributo)
    ]

    metadados = getattr(modulo, "METADADOS", None)
    if metadados is None:
        return ferramentas
    if not isinstance(metadados, dict):
        raise ValueError(f"{origem}.METADADOS tem de ser um dict por nome de tool")

    escopo_por_nome = {f.nome: f.escopo for f in ferramentas}
    for nome, extra in metadados.items():
        if nome not in escopo_por_nome:
            raise ValueError(f"{origem}.METADADOS cita {nome!r}, que não está nas tools do módulo")
        if not isinstance(extra, dict):
            raise ValueError(f"{origem}.METADADOS[{nome!r}] tem de ser um dict")
        desconhecidas = sorted(set(extra) - CHAVES_DE_METADADOS)
        if desconhecidas:
            raise ValueError(
                f"{origem}.METADADOS[{nome!r}]: chave desconhecida {', '.join(desconhecidas)} "
                f"(as que existem: {', '.join(sorted(CHAVES_DE_METADADOS))})"
            )
        if "prazo_s" in extra:
            prazo = extra["prazo_s"]
            # `bool` é subclasse de `int` em Python: `True` não é um prazo.
            if (
                isinstance(prazo, bool)
                or not isinstance(prazo, (int, float))
                or not math.isfinite(prazo)
                or not 0 < prazo <= PRAZO_MAXIMO_S
            ):
                raise ValueError(
                    f"{origem}.METADADOS[{nome!r}]: prazo_s tem de ser um número de "
                    f"segundos entre 0 e {PRAZO_MAXIMO_S:.0f}"
                )
        if "expor_no_mcp" in extra:
            if not isinstance(extra["expor_no_mcp"], bool):
                raise ValueError(f"{origem}.METADADOS[{nome!r}]: expor_no_mcp tem de ser bool")
            if extra["expor_no_mcp"] and escopo_por_nome[nome] != "coordenacao":
                raise ValueError(
                    f"{origem}.METADADOS[{nome!r}]: tool do escopo "
                    f"{escopo_por_nome[nome]!r} não vai ao MCP — ele é da coordenação"
                )

    ajustadas: list[Ferramenta] = []
    for f in ferramentas:
        ajustes = dict(metadados.get(f.nome) or {})
        if "prazo_s" in ajustes:
            ajustes["prazo_s"] = float(ajustes["prazo_s"])
        ajustadas.append(replace(f, **ajustes) if ajustes else f)
    return ajustadas


def _montar_registro() -> Registro:
    """O registro do SAS: as tools de `tools/*.py`, de `tools_aluno.py` e as de
    `roteiros.py`, cada uma com os metadados do próprio módulo."""
    return Registro(
        [
            *(
                f
                for modulo in _tools_coordenacao._MODULOS
                for f in _ferramentas_do_modulo(modulo, ("TOOLS", "coordenacao"))
            ),
            *_ferramentas_do_modulo(_tools_aluno, ("TOOLS", "aluno")),
            *_ferramentas_do_modulo(
                _roteiros, ("TOOLS_ALUNO", "aluno"), ("TOOLS_COORDENACAO", "coordenacao")
            ),
        ]
    )


REGISTRO = _montar_registro()
