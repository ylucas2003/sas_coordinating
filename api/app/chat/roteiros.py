"""Roteiros — o método de uma tarefa, carregado só quando a tarefa aparece (docs/43 §4.3).

"Revise meu simulado", "monte meu plano da semana", "faça o diagnóstico do
ciclo" pedem sempre a mesma sequência de consultas e os mesmos cuidados. Escrito
no system prompt, esse método iria em TODA chamada ao modelo, inclusive no "oi";
o system prompt de ~575 linhas do MCP da Solomon é o exemplo do que se quer
evitar (docs/43 §2). Aqui cada método é um markdown curto em
`roteiros/<escopo>/<nome>.md`, e uma tool o entrega quando o modelo pede — o
custo vai só para a conversa que precisa dele.

Os mesmos arquivos da coordenação viram `prompts` do MCP (docs/43 §5.1). O
contrato que o servidor MCP consome é este, e não muda depois de publicado:

    listar(escopo) -> list[Roteiro]        em ordem de nome
    obter(escopo, nome) -> Roteiro | None
    Roteiro(nome, titulo, descricao, escopo, texto)

O formato do arquivo é um cabeçalho fechado entre `---`, com exatamente três
campos, e o texto depois dele:

    ---
    nome: revisar_simulado
    titulo: Revisar um simulado
    descricao: Uma linha — é o que o modelo lê para decidir quando carregar.
    ---
    1. ...

Falha FECHADA no import, com ValueError: cabeçalho torto, campo faltando ou a
mais, nome diferente do arquivo, pasta de escopo vazia. Roteiro quebrado é erro
de quem o escreveu, e o pior momento de descobrir é no meio de uma conversa.

As tools daqui (`TOOLS_ALUNO`, `TOOLS_COORDENACAO`) seguem as convenções de
`tools/__init__.py` — só leem, devolvem dict, erro como `{"erro": ...}` — e
quem as recolhe é `ferramentas._montar_registro`. Não leem banco: os roteiros
são carregados uma vez, do disco, quando o módulo é importado.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Só para o verificador de tipos: `ferramentas` importa este módulo para
    # recolher as tools, e o import em tempo de execução seria circular.
    from .ferramentas import Escopo

#: Onde moram os arquivos. Vai para a imagem com o resto de `app/` (o
#: Dockerfile copia a árvore inteira, e o rsync do deploy só filtra o que o
#: .gitignore ignora).
PASTA_DOS_ROTEIROS = Path(__file__).with_name("roteiros")

#: Uma pasta por escopo, com os mesmos nomes do registro (docs/43 §3.1).
ESCOPOS: tuple[Escopo, ...] = ("aluno", "coordenacao")

#: Os campos do cabeçalho, todos obrigatórios.
_CAMPOS = ("nome", "titulo", "descricao")

#: O nome vira valor de `enum` no schema da tool e nome de prompt no MCP:
#: minúsculas, dígitos e sublinhado, como os nomes das tools.
_NOME = re.compile(r"[a-z][a-z0-9_]*")


@dataclass(frozen=True)
class Roteiro:
    nome: str
    titulo: str
    #: Uma linha. Entra na descrição da tool, que vai em toda chamada ao
    #: modelo: é o que ele lê para saber QUANDO carregar o roteiro.
    descricao: str
    escopo: Escopo
    #: O método em si, em markdown curto. Só vai ao modelo quando ele pede.
    texto: str


# ─── Leitura ─────────────────────────────────────────────────────────────


def ler_roteiro(caminho: Path, escopo: Escopo) -> Roteiro:
    """Um arquivo de roteiro. ValueError se ele não estiver no formato."""
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    if not linhas or linhas[0].strip() != "---":
        raise ValueError(f"{caminho}: o roteiro começa pelo cabeçalho entre '---'")
    fim = next((i for i in range(1, len(linhas)) if linhas[i].strip() == "---"), None)
    if fim is None:
        raise ValueError(f"{caminho}: o cabeçalho não tem o '---' de fechamento")

    campos: dict[str, str] = {}
    for linha in linhas[1:fim]:
        if not linha.strip():
            continue
        chave, separador, valor = linha.partition(":")
        chave = chave.strip()
        if not separador or chave not in _CAMPOS:
            raise ValueError(
                f"{caminho}: linha de cabeçalho inválida {linha!r} — os campos são "
                f"{', '.join(_CAMPOS)}"
            )
        if chave in campos:
            raise ValueError(f"{caminho}: o campo {chave!r} aparece duas vezes")
        campos[chave] = valor.strip()

    faltando = [c for c in _CAMPOS if not campos.get(c)]
    if faltando:
        raise ValueError(f"{caminho}: falta {', '.join(faltando)} no cabeçalho")
    # O nome é o do arquivo: dois nomes para a mesma coisa é como um roteiro
    # some — renomeia-se o arquivo e o enum continua oferecendo o nome velho.
    if campos["nome"] != caminho.stem:
        raise ValueError(f"{caminho}: o nome {campos['nome']!r} tem de ser o do arquivo")
    if not _NOME.fullmatch(campos["nome"]):
        raise ValueError(f"{caminho}: nome {campos['nome']!r} fora do padrão [a-z0-9_]")

    texto = "\n".join(linhas[fim + 1 :]).strip()
    if not texto:
        raise ValueError(f"{caminho}: roteiro sem texto")
    return Roteiro(
        nome=campos["nome"],
        titulo=campos["titulo"],
        descricao=campos["descricao"],
        escopo=escopo,
        texto=texto,
    )


def carregar(pasta: Path = PASTA_DOS_ROTEIROS) -> dict[str, dict[str, Roteiro]]:
    """Todos os roteiros, por escopo e por nome, em ordem de nome.

    Pasta de escopo vazia também é ValueError: o enum da tool não pode ser
    vazio, e uma imagem sem os arquivos é imagem quebrada — melhor a API
    recusar subir do que o mentor perder o método sem ninguém ver.
    """
    por_escopo: dict[str, dict[str, Roteiro]] = {}
    for escopo in ESCOPOS:
        arquivos = sorted((pasta / escopo).glob("*.md"))
        if not arquivos:
            raise ValueError(f"nenhum roteiro em {pasta / escopo}")
        por_escopo[escopo] = {r.nome: r for r in (ler_roteiro(a, escopo) for a in arquivos)}
    return por_escopo


_ROTEIROS = carregar()


def listar(escopo: str) -> list[Roteiro]:
    """Os roteiros de um escopo, em ordem de nome. Escopo desconhecido: nenhum."""
    return list(_ROTEIROS.get(escopo, {}).values())


def obter(escopo: str, nome: str) -> Roteiro | None:
    """Um roteiro do escopo, ou `None` — inclusive se o nome é do OUTRO escopo."""
    return _ROTEIROS.get(escopo, {}).get(nome)


# ─── As tools ────────────────────────────────────────────────────────────

#: Vai junto do texto: o roteiro é o método para montar a resposta, não a
#: resposta — colado na conversa, viraria uma lista de nomes de tool na tela.
_COMO_USAR = (
    "Siga estes passos para montar a resposta. Não copie o roteiro para quem "
    "perguntou: ele é o seu método, não o conteúdo da resposta."
)


def _entregar(escopo: str, nome: str) -> dict[str, Any]:
    roteiro = obter(escopo, nome)
    if roteiro is None:
        # O enum do schema já barra nome inventado no despacho (docs/43 §3.2,
        # invariante 3); isto é para quem chama o handler direto.
        existentes = ", ".join(r.nome for r in listar(escopo))
        return {"erro": f"Não existe o roteiro '{nome}'. Os que existem: {existentes}."}
    return {
        "nome": roteiro.nome,
        "titulo": roteiro.titulo,
        "roteiro": roteiro.texto,
        "comoUsar": _COMO_USAR,
    }


def roteiro_do_mentor(cliente: Any, *, aluno_id: str, nome: str) -> dict[str, Any]:
    """O roteiro de uma tarefa do Tio Léo.

    `aluno_id` chega porque o registro o injeta em toda tool do escopo do aluno
    (ferramentas.py, invariante 2); o roteiro é o mesmo para todo aluno.
    """
    return _entregar("aluno", nome)


def roteiro_da_coordenacao(cliente: Any, *, nome: str) -> dict[str, Any]:
    """O roteiro de uma análise do assistente da coordenação."""
    return _entregar("coordenacao", nome)


def _schema(nome_da_tool: str, escopo: str, abertura: str) -> dict[str, Any]:
    roteiros = listar(escopo)
    # A lista vai NA descrição, e não só no enum: o modelo escolhe a tool pela
    # descrição, e um enum de nomes soltos não diz quando cada roteiro serve.
    catalogo = "\n".join(f"- {r.nome}: {r.descricao}" for r in roteiros)
    return {
        "name": nome_da_tool,
        "description": f"{abertura}\n{catalogo}",
        "parameters": {
            "type": "object",
            "properties": {
                "nome": {
                    "type": "string",
                    "enum": [r.nome for r in roteiros],
                    "description": "Qual roteiro carregar.",
                },
            },
            "required": ["nome"],
        },
    }


TOOLS_ALUNO: list[tuple[dict, Callable]] = [
    (
        _schema(
            "roteiro_do_mentor",
            "aluno",
            "Carrega o roteiro — o passo a passo — de uma tarefa de mentoria. Chame "
            "ANTES de responder quando o pedido do aluno for uma destas tarefas, e "
            "siga os passos: eles dizem que tools chamar, em que ordem e com que "
            "cuidado.",
        ),
        roteiro_do_mentor,
    ),
]

TOOLS_COORDENACAO: list[tuple[dict, Callable]] = [
    (
        _schema(
            "roteiro_da_coordenacao",
            "coordenacao",
            "Carrega o roteiro — o passo a passo — de uma análise da coordenação. "
            "Chame ANTES de responder quando o pedido for uma destas análises, e siga "
            "os passos: eles dizem que tools chamar, em que ordem e com que cuidado.",
        ),
        roteiro_da_coordenacao,
    ),
]
