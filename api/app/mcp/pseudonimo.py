"""Nome de aluno → matrícula no que o MCP devolve (LGPD, docs/43 §5.4 e §6).

O MCP manda o retorno das tools a um provedor de IA de FORA da escola, sob a
conta de quem conectou. Com o pseudônimo ligado (MCP_MOSTRAR_NOME_DO_ALUNO=false)
ele não manda NOME de aluno: troca por "Aluno <matrícula>". Desde 26/10 isto é
OPÇÃO, e não o padrão: o dono decidiu que o MCP mostra o nome real
(`configuracao.ConfiguracaoMcp.mostrar_nome_do_aluno`), e o módulo fica para
quem quiser voltar à matrícula. A regra foi levantada tool por tool no mapa de
LGPD de 24/10 — as 30 tools da coordenação rodadas contra dados sintéticos — e
mora aqui, no MCP, NUNCA no registro: o chat do app continua com nome, por
decisão registrada (`agente.py`).

⚠️ Pseudônimo não é anonimização. A matrícula é o SIS User ID e circula em
lista de chamada: quem é da escola reidentifica "Aluno 9000001". Para a LGPD
continua sendo dado pessoal (art. 5º, I; art. 13, §4º) de adolescente
(art. 14). O que isto evita é o NOME no histórico de conversa do provedor.

A função é pura — sem I/O, testável sem banco. Recebe o retorno da tool e dois
insumos explícitos (o mapa id → matrícula e os nomes de aluno), devolve uma
CÓPIA com o nome trocado, ou levanta `PseudonimoRecusado` quando sobra nome
que a regra não sabe trocar. Recusa é a chamada inteira como erro; nunca sai
resultado parcial.

Antes das passadas, o resultado vira a FORMA EM QUE VAI SAIR: o JSON de
`serializar_para_modelo` (ferramentas.py, `default=str`). Tupla vira lista; set,
bytes, data e objeto viram o `str()` deles. As passadas conferem essa forma, e é
ela que sai — senão um nome dentro de uma tupla (`sorted(zip(nomes, medias))`,
um `model_dump()` com campo tupla) ou no `str()` de um objeto passaria pelo
portão sem ser visto e sairia assim mesmo (revisão de 24/10).

As três passadas:

  1. ESTRUTURAL. Dict com `alunoId` ou `matricula` é dict de ALUNO (nas tools
     da coordenação, só dict de aluno tem uma dessas chaves). Nele, `nome` e
     `alunoNome` viram o rótulo. Nada mais muda.
  2. POR VALOR, no mesmo resultado. Dict sem chave de entidade cujo `nome` é
     exatamente um nome trocado na passada 1 — o `maior`/`menor` de
     `comparar_alunos.maioresDiferencas`, que só têm {nome, media}. Com
     homônimos no mesmo resultado, recusa: não há como saber qual é qual.
  3. PORTÃO, fail-closed. (a) Dict não trocado com `nome` e coluna de
     classificação de aluno (zona, perfil, tendencia, mediaRecente) é nome de
     aluno sem identidade: recusa. (b) Texto — valor OU chave — que contém o
     nome completo de um aluno: recusa. O (b) é cinto de segurança, não o
     mecanismo: ele só conhece o nome ATUAL de cada aluno.
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
import threading
import time
import unicodedata
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from .dados import CriarCliente, cliente_novo

#: Chaves que carregam o NOME do aluno dentro de um dict de aluno.
CHAVES_DE_NOME = ("nome", "alunoNome")
#: Só dict de aluno tem estas chaves nas tools da coordenação (mapa de LGPD).
MARCAS_DE_ALUNO = ("alunoId", "matricula")
#: Colunas de `classificacao_aluno`: dict com `nome` e uma delas é de aluno.
CHAVES_SO_DE_ALUNO = frozenset({"zona", "perfil", "tendencia", "mediaRecente"})
#: Dict com alguma destas é outra entidade identificada (ciclo, simulado,
#: sede, turma, matéria) — a passada 2 nunca o toca.
CHAVES_DE_ENTIDADE = frozenset({"id", "simuladoId", "cicloId", "sedeId", "turmaId", "codigo"})

#: Quanto o cadastro (id, matrícula, nome) fica em memória. Curto porque o
#: sync do Canvas cria aluno: um aluno novo fica, por até isto, sem matrícula
#: no mapa (cai no rótulo por hash, ainda sem nome) e fora do portão (b).
VALIDADE_DO_CADASTRO_S = 60.0


class PseudonimoRecusado(Exception):
    """Sobrou nome de aluno que a regra não sabe trocar. Nada sai."""


# ─── A regra ─────────────────────────────────────────────────────────────


def _norm(s: str) -> str:
    """Sem acento, sem caixa, espaços colapsados: "JOÃO  Silva" == "joao silva"."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.casefold().split())


def _texto(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _chave(v: Any) -> str | None:
    """Um id ou matrícula como texto. Matrícula inteira (12345) também vale:
    o SIS User ID é texto no banco, mas uma tool que o converter não pode
    fazer o dict deixar de ser de aluno."""
    if isinstance(v, str):
        return v.strip() or None
    if isinstance(v, int) and not isinstance(v, bool):
        return str(v)
    return None


def rotulo(aluno_id: str | None, matricula: str | None) -> str:
    """'Aluno <matrícula>'; sem matrícula, 'Aluno #<10 hex do sha256 do id>'.

    O hash só aparece quando o id falta no mapa: `aluno.matricula` é NOT NULL
    UNIQUE (0001). É estável — o mesmo id dá o mesmo rótulo em toda tool.
    """
    if matricula:
        return f"Aluno {matricula}"
    if aluno_id:
        return "Aluno #" + hashlib.sha256(aluno_id.encode()).hexdigest()[:10]
    raise PseudonimoRecusado("dict de aluno sem matrícula nem id")


def _id_do_aluno(d: dict) -> str | None:
    if (aid := _chave(d.get("alunoId"))) is not None:
        return aid
    # `id` só é id de ALUNO quando o mesmo dict traz a matrícula: {id, nome}
    # sozinho é ciclo, simulado, sede ou turma.
    if _chave(d.get("matricula")) is not None:
        return _chave(d.get("id"))
    return None


def _como_json(resultado: Any) -> Any:
    """O resultado como o modelo vai lê-lo: só dict, list, str, número, bool e None.

    O MESMO `json.dumps(..., default=str)` de `serializar_para_modelo`, ida e
    volta — e por isso também uma cópia: a entrada não é tocada. Chave que o
    json não escreve (uma tupla) levanta TypeError, e quem chama transforma em
    falha: o que não se consegue serializar não se consegue conferir.
    """
    return json.loads(json.dumps(resultado, ensure_ascii=False, default=str))


#: Chave que entra no caminho da recusa como é: nome de CAMPO (`porAluno`,
#: `alunosRisco`). Qualquer outra — nome com espaço, matrícula, uuid, sigla —
#: vira `<chave>`. O caminho vai para o log, e chave também é dado: com a
#: chave crua, `{"porAluno": {"<nome>": ...}}` punha o nome no motivo
#: (revisão de 24/10).
_CHAVE_DE_CAMPO = re.compile(r"[a-z_][A-Za-z0-9_]{0,63}")


def _segmento(chave: Any) -> str:
    return f".{chave}" if isinstance(chave, str) and _CHAVE_DE_CAMPO.fullmatch(chave) else ".<chave>"


def _caminhar(no: Any, caminho: str = "$") -> Iterator[tuple[str, dict]]:
    if isinstance(no, dict):
        yield caminho, no
        for k, v in no.items():
            yield from _caminhar(v, caminho + _segmento(k))
    elif isinstance(no, list):
        for i, v in enumerate(no):
            yield from _caminhar(v, f"{caminho}[{i}]")


def _textos(no: Any, caminho: str = "$") -> Iterator[tuple[str, str]]:
    """Todo texto do resultado — os valores E as chaves dos dicts.

    A chave entra porque `{"porAluno": {"ANA SOUZA": 7.5}}` também é nome de
    aluno saindo, e uma regra que só olhasse valor deixaria passar."""
    if isinstance(no, str):
        yield caminho, no
    elif isinstance(no, dict):
        for k, v in no.items():
            if isinstance(k, str):
                yield f"{caminho}.<chave>", k
            yield from _textos(v, caminho + _segmento(k))
    elif isinstance(no, list):
        for i, v in enumerate(no):
            yield from _textos(v, f"{caminho}[{i}]")


@functools.lru_cache(maxsize=4)
def _padrao_de_nomes(nomes: frozenset[str]) -> re.Pattern[str] | None:
    """Uma regex com todos os nomes, compilada uma vez por cadastro (~10 ms
    para 900 nomes). Só nome com 2+ palavras: um de uma palavra casaria com
    texto comum. Os mais longos primeiro, para a alternância preferir o
    nome inteiro."""
    alvos = sorted(
        {n for n in (_norm(x) for x in nomes if _texto(x)) if len(n.split()) >= 2},
        key=len,
        reverse=True,
    )
    if not alvos:
        return None
    return re.compile(r"(?<!\w)(?:" + "|".join(re.escape(a) for a in alvos) + r")(?!\w)")


def pseudonimizar(
    resultado: Any,
    *,
    matricula_por_id: Mapping[str, str],
    nomes_de_alunos: Iterable[str] = (),
) -> Any:
    """Uma cópia de `resultado` sem nome de aluno, ou `PseudonimoRecusado`.

    A cópia já está na forma JSON (`_como_json`): é ela que se serializa
    depois, e não o original. Idempotente — p(p(x)) == p(x) — e não toca a
    entrada.
    """
    copia = _como_json(resultado)
    rotulados: set[int] = set()
    trocados: dict[str, set[str]] = {}

    # Passada 1 — estrutural.
    for _, d in _caminhar(copia):
        if not any(_chave(d.get(k)) is not None for k in MARCAS_DE_ALUNO):
            continue
        aid = _id_do_aluno(d)
        mat = _chave(d.get("matricula")) or _chave(matricula_por_id.get(aid or ""))
        rot = rotulo(aid, mat)
        for k in CHAVES_DE_NOME:
            if _texto(d.get(k)):
                trocados.setdefault(_norm(d[k]), set()).add(rot)
                d[k] = rot
                rotulados.add(id(d))

    # Passada 2 — por valor, no MESMO resultado.
    for caminho, d in _caminhar(copia):
        if id(d) in rotulados or CHAVES_DE_ENTIDADE & d.keys():
            continue
        valor = d.get("nome")
        if _texto(valor) and _norm(valor) in trocados:
            rotulos = trocados[_norm(valor)]
            if len(rotulos) != 1:
                raise PseudonimoRecusado(f"{caminho}: nome ambíguo entre {len(rotulos)} alunos")
            d["nome"] = next(iter(rotulos))
            rotulados.add(id(d))

    # Passada 3 — portão.
    for caminho, d in _caminhar(copia):
        if id(d) in rotulados:
            continue
        if _texto(d.get("nome")) and CHAVES_SO_DE_ALUNO & d.keys():
            raise PseudonimoRecusado(f"{caminho}: dict de aluno sem alunoId nem matrícula")
    nomes = nomes_de_alunos if isinstance(nomes_de_alunos, frozenset) else frozenset(nomes_de_alunos)
    padrao = _padrao_de_nomes(nomes)
    if padrao is not None:
        for caminho, s in _textos(copia):
            if padrao.search(_norm(s)):
                # O caminho vai para o log; o TEXTO não — é ele que tem o nome.
                raise PseudonimoRecusado(f"{caminho}: texto com nome de aluno")
    return copia


# ─── O cadastro: (id, matrícula, nome) de todo aluno ────────────────────


@dataclass(frozen=True)
class Cadastro:
    matricula_por_id: Mapping[str, str]
    nomes: frozenset[str]

    @classmethod
    def das_linhas(cls, linhas: Iterable[Mapping[str, Any]]) -> Cadastro:
        matricula_por_id: dict[str, str] = {}
        nomes: set[str] = set()
        for linha in linhas:
            aid, mat = _chave(linha.get("id")), _chave(linha.get("matricula"))
            if aid and mat:
                matricula_por_id[aid] = mat
            if _texto(linha.get("nome")):
                nomes.add(linha["nome"])
        return cls(matricula_por_id=matricula_por_id, nomes=frozenset(nomes))


class CadastroDeAlunos:
    """O cadastro em memória, relido a cada `VALIDADE_DO_CADASTRO_S`.

    Todo aluno, ativo ou não: uma tool pode devolver aluno inativo, e o
    portão (b) precisa do nome dele também. São ~900 linhas de três colunas —
    o GRANT da 0071 em `aluno` cobre exatamente (id, matricula, nome, ativo).

    Chamado de dentro de threads (`asyncio.to_thread`), por isso a trava: sem
    ela, a primeira rajada de chamadas releria o cadastro uma vez por thread.

    Falha ao reler SOBE, sem cair no cadastro velho: quem chama transforma em
    recusa. Sem o cadastro não há como saber o que é nome de aluno.
    """

    def __init__(
        self,
        *,
        validade_s: float = VALIDADE_DO_CADASTRO_S,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self._validade_s = validade_s
        self._relogio = relogio
        self._trava = threading.Lock()
        self._atual: Cadastro | None = None
        self._lido_em = 0.0

    def obter(self, criar_cliente: CriarCliente) -> Cadastro:
        with self._trava:
            if self._atual is not None and self._relogio() - self._lido_em < self._validade_s:
                return self._atual
            with cliente_novo(criar_cliente) as cliente:
                linhas = (
                    cliente.table("aluno").select("id, matricula, nome").execute().data or []
                )
            self._atual = Cadastro.das_linhas(linhas)
            self._lido_em = self._relogio()
            return self._atual
