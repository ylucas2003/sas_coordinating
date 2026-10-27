"""O catálogo do MCP: as tools do registro que a política expôs (docs/43 §5.1).

Não há tool escrita para o MCP. São as do registro único
(`app/chat/ferramentas.py`) de escopo `coordenacao` com `expor_no_mcp=True` —
quem decide o que sai do SAS é a política de lá, tool por tool. Este módulo só
TRADUZ: a `Ferramenta` vira a `Tool` do SDK, e os argumentos ganham o teto de
linhas antes do despacho.

Três coisas que o MCP muda em relação ao chat do app:

  * o SCHEMA é normalizado para cliente estrito — sem `$schema`, sem
    `format`, sem `default` (vai para a descrição, onde o modelo o lê) e sem
    tupla. É o checklist de compatibilidade que o MCP da Solomon levantou para
    claude.ai e ChatGPT (docs/43 §2);
  * toda tool vai anotada `readOnlyHint=True`. Tool que o registro não marca
    `somente_leitura` NÃO entra, mesmo com `expor_no_mcp` — o MCP só lê, e a
    anotação não pode mentir;
  * o parâmetro de limite (`limite`, `k`) ganha TETO: minimização (LGPD
    art. 6º, III). Sem ele, `buscar_aluno_por_nome(nome="al", limite=1000)`
    trouxe todos os alunos no levantamento de LGPD, e `limite=-1` numa tool
    que corta com `linhas[:limite]` devolve a lista inteira menos o último.
"""

from __future__ import annotations

import copy
import inspect
import json
import logging
import re
from collections.abc import Iterable
from typing import Any

import mcp.types as types

from ..chat.ferramentas import Ferramenta, Registro

log = logging.getLogger("sas.mcp.catalogo")

ESCOPO = "coordenacao"

#: Os nomes de parâmetro que são TETO de linhas nas tools do registro (todos
#: inteiros: `limite` em dez tools, `k` em `alunos_similares`). Tool nova com
#: outro nome de limite entra aqui — `test_mcp_catalogo` quebra se um inteiro
#: de tool exposta não estiver aqui nem em `INTEIROS_QUE_NAO_SAO_LIMITE`.
NOMES_DE_LIMITE = frozenset({"limite", "k"})

#: Inteiros de tool exposta que NÃO limitam linhas (um ano, um número de
#: ciclo). Vazia hoje; declarar aqui é dizer, por escrito, que não é teto.
INTEIROS_QUE_NAO_SAO_LIMITE: frozenset[str] = frozenset()

#: As tools expostas que só servem com o NOME do aluno saindo do SAS. Entraram
#: em 26/10, quando o dono decidiu que o MCP mostra o nome
#: (`ConfiguracaoMcp.mostrar_nome_do_aluno`, o padrão); com o pseudônimo
#: ligado de novo, ficam FORA do catálogo, porque com ele nenhuma das duas
#: funciona: `buscar_aluno_por_nome` recebe o nome digitado e devolveria ao
#: provedor o par nome ↔ matrícula que o pseudônimo existe para não entregar,
#: e `listar_alertas` traz o nome interpolado no título, gravado uma vez — o
#: portão do pseudônimo (passada 3) recusaria toda chamada.
SO_COM_NOME_DO_ALUNO: frozenset[str] = frozenset({"buscar_aluno_por_nome", "listar_alertas"})

_INTEIRO = re.compile(r"[+-]?\d+")

# Palavras do JSON Schema que carregam SUBschema, e de que jeito. É por elas
# que a normalização desce — e NUNCA por `properties` adentro como se fosse
# schema: lá as chaves são NOMES de parâmetro, e um parâmetro chamado
# `format` ou `default` não pode sumir.
_SUBSCHEMA = frozenset(
    {"items", "not", "additionalProperties", "contains", "if", "then", "else", "propertyNames"}
)
_LISTA_DE_SUBSCHEMAS = frozenset({"anyOf", "oneOf", "allOf"})
_MAPA_DE_SUBSCHEMAS = frozenset({"properties", "patternProperties", "$defs", "definitions"})
#: Saem sem deixar rastro: o cliente estrito recusa ou ignora.
_RETIRADAS = frozenset({"$schema", "format", "additionalItems"})


# ─── O schema ────────────────────────────────────────────────────────────


def normalizar_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
    """O schema dos argumentos como cliente estrito aceita. Nunca altera a entrada."""
    raiz = _normalizar(copy.deepcopy(schema) if isinstance(schema, dict) else {})
    # O topo é sempre um objeto com `properties`, mesmo vazio: há cliente que
    # recusa tool sem os dois.
    raiz["type"] = "object"
    propriedades = raiz.get("properties")
    if not isinstance(propriedades, dict):
        propriedades = raiz["properties"] = {}
    obrigatorios = raiz.get("required")
    if isinstance(obrigatorios, list):
        raiz["required"] = [n for n in obrigatorios if isinstance(n, str) and n in propriedades]
        if not raiz["required"]:
            del raiz["required"]
    return raiz


def _normalizar(no: dict[str, Any]) -> dict[str, Any]:
    for palavra in _RETIRADAS & no.keys():
        del no[palavra]

    if "default" in no:
        padrao = no.pop("default")
        texto = f"Padrão: {json.dumps(padrao, ensure_ascii=False)}."
        no["description"] = f"{no['description'].rstrip()} {texto}" if no.get("description") else texto

    # Tupla (`items` em lista, ou `prefixItems`): o cliente estrito recusa.
    # Vira lista homogênea quando os itens têm o mesmo tipo; senão, lista
    # sem tipo de item — quem confere o argumento de verdade é o registro.
    # Com `prefixItems` E `items` (o resto da lista, em 2020-12), o `items`
    # já diz o tipo e fica.
    tupla = no.pop("prefixItems", None)
    if isinstance(no.get("items"), list):
        tupla = no.pop("items")
    if isinstance(tupla, list) and "items" not in no:
        tipos = {item.get("type") for item in tupla if isinstance(item, dict)}
        if len(tipos) == 1 and None not in tipos:
            no["items"] = {"type": tipos.pop()}

    for palavra, valor in list(no.items()):
        if palavra in _SUBSCHEMA and isinstance(valor, dict):
            no[palavra] = _normalizar(valor)
        elif palavra in _LISTA_DE_SUBSCHEMAS and isinstance(valor, list):
            no[palavra] = [_normalizar(v) if isinstance(v, dict) else v for v in valor]
        elif palavra in _MAPA_DE_SUBSCHEMAS and isinstance(valor, dict):
            no[palavra] = {k: _normalizar(v) if isinstance(v, dict) else v for k, v in valor.items()}
    return no


# ─── O teto de linhas ────────────────────────────────────────────────────


def parametros_de_limite(f: Ferramenta) -> list[str]:
    return [
        nome
        for nome, esquema in f.propriedades.items()
        if nome in NOMES_DE_LIMITE and (esquema or {}).get("type") == "integer"
    ]


def _como_inteiro(valor: Any) -> int | None:
    """O inteiro inequívoco que o modelo quis mandar, ou None.

    A mesma leitura que o registro faz depois (`ferramentas._coagir`): o teto
    tem de valer também para `"1000"` e `1000.0`, senão o texto contornaria o
    teto e só depois seria convertido em número. `True` não é limite.
    """
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    if isinstance(valor, str) and _INTEIRO.fullmatch(valor.strip()):
        return int(valor.strip())
    return None


def _padrao_do_handler(f: Ferramenta, nome: str) -> Any:
    try:
        parametro = inspect.signature(f.handler).parameters.get(nome)
    except (TypeError, ValueError):
        return None
    if parametro is None or parametro.default is inspect.Parameter.empty:
        return inspect.Parameter.empty
    return parametro.default


def aplicar_teto(f: Ferramenta, argumentos: dict[str, Any] | None, teto: int) -> dict[str, Any]:
    """Os argumentos com todo parâmetro de limite dentro de [1, teto].

    Abaixo de 1 também é corrigido: `linhas[:limite]` com `limite=-1` devolve
    a lista inteira menos o último. Ausente, vale o default do HANDLER — é ele
    que o registro aplica —, a não ser que o default passe do teto ou não
    tenha teto nenhum (None): aí entra o teto. Valor que não é inteiro fica
    como veio, para o registro recusar com a mensagem certa.
    """
    args = dict(argumentos) if isinstance(argumentos, dict) else {}
    for nome in parametros_de_limite(f):
        if args.get(nome) is not None:
            valor = _como_inteiro(args[nome])
            if valor is not None:
                args[nome] = min(max(valor, 1), teto)
            continue
        padrao = _padrao_do_handler(f, nome)
        if padrao is inspect.Parameter.empty:
            continue
        if padrao is None or (isinstance(padrao, int) and not isinstance(padrao, bool) and padrao > teto):
            args[nome] = teto
    return args


# ─── O catálogo ──────────────────────────────────────────────────────────


def ferramentas_expostas(registro: Registro, *, com_nome_do_aluno: bool = True) -> list[Ferramenta]:
    expostas: list[Ferramenta] = []
    for f in registro.catalogo(ESCOPO):
        if not f.expor_no_mcp:
            continue
        if not com_nome_do_aluno and f.nome in SO_COM_NOME_DO_ALUNO:
            continue
        if not f.somente_leitura:
            log.warning(
                "ferramenta marcada para o MCP sem ser somente leitura: fica de fora",
                extra={"ferramenta": f.nome},
            )
            continue
        expostas.append(f)
    return expostas


def _tool(f: Ferramenta, teto: int) -> types.Tool:
    schema = normalizar_schema(f.parametros)
    for nome in parametros_de_limite(f):
        esquema = schema["properties"][nome]
        # O teto também é dito ao modelo: pedir 200 e receber 50 calado faria
        # ele concluir que a turma tem 50 alunos.
        esquema["minimum"] = 1
        esquema["maximum"] = teto
        aviso = f"No máximo {teto}."
        esquema["description"] = f"{esquema['description'].rstrip()} {aviso}" if esquema.get("description") else aviso
    return types.Tool(
        name=f.nome,
        description=f.descricao,
        inputSchema=schema,
        annotations=types.ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            # O mundo da tool é o banco do SAS, não a internet.
            openWorldHint=False,
        ),
    )


class Catalogo:
    """O que `tools/list` mostra e o que `tools/call` aceita — a MESMA lista.

    Montado uma vez por processo: o registro não muda em execução, e o
    `_tool_cache` do SDK é um só para todos os usuários (lowlevel/server.py),
    então um catálogo que variasse por pessoa não estaria protegido por ele
    de qualquer jeito.
    """

    def __init__(self, registro: Registro, *, teto_de_linhas: int, com_nome_do_aluno: bool = True) -> None:
        self.teto_de_linhas = teto_de_linhas
        self._por_nome = {
            f.nome: f for f in ferramentas_expostas(registro, com_nome_do_aluno=com_nome_do_aluno)
        }
        self._tools = [_tool(f, teto_de_linhas) for f in self._por_nome.values()]

    def listar(self) -> list[types.Tool]:
        return list(self._tools)

    def nomes(self) -> Iterable[str]:
        return self._por_nome.keys()

    def obter(self, nome: str) -> Ferramenta | None:
        """A ferramenta, se ela está NO CATÁLOGO DO MCP.

        É a guarda que o SDK não faz: uma tool fora do `tools/list` chega ao
        handler do `call_tool` mesmo assim, só com um aviso no log
        (lowlevel/server.py). Sem esta conferência, uma tool do registro que a
        política NÃO expôs (`gerar_grafico`, `navegar_para`) — ou uma de
        `SO_COM_NOME_DO_ALUNO` com o pseudônimo ligado — seria chamável pelo
        nome.
        """
        return self._por_nome.get(nome) if isinstance(nome, str) else None

    def preparar_argumentos(self, f: Ferramenta, argumentos: dict[str, Any] | None) -> dict[str, Any]:
        return aplicar_teto(f, argumentos, self.teto_de_linhas)
