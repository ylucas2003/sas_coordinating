"""As tools da coordenação do docs/43 §4.3, e os consertos do mapa de LGPD de 24/10.

Tudo passa pelo REGISTRO de verdade (`REGISTRO.despachar`, sessão da
coordenação): é o caminho do chat e do MCP, com a coerção de argumento, o enum
e o erro genérico no meio. Uma tool chamada direto passaria por cima justamente
do lugar onde metade dos defeitos morava — o enum de `listar_alertas` recusava
os valores que o banco grava, e só pelo registro isso aparece.

O banco é o `FakeRico` daqui: o fake de sempre (tests/fake_postgrest.py) com o
que estas tools usam e ele não tinha —

  * PROJEÇÃO de coluna e embed de pai pela FK: o PostgREST só devolve o que se
    pede, e é isso que prova que e-mail, senha e link de vídeo não saem;
  * `neq`, `not_.in_`, `or_` e LIKE com `%` de verdade: o prefixo da trilha de
    auditoria (`nota/%/<simulado>`) só se prova com o curinga no meio;
  * comparação de número e de timestamptz pelo VALOR, não pelo texto;
  * ESCRITA PROIBIDA: tool da coordenação só lê, e aqui escrever é exceção;
  * o SCHEMA DAS MIGRATIONS (tests/esquema_das_migrations.py): coluna que não
    existe é 42703 e id torto em coluna uuid é 22P02, como no PostgREST. Sem
    isso o fake devolvia `None` para a coluna inventada, e `materias_problematicas`
    — que pedia `simulado.fase`, removida na 0003 — passou na suíte enquanto
    falhava sempre no banco de verdade (revisão paralela de 25/10).

Dados 100% sintéticos.

Rodar:  cd api && APP_ENV=dev ./.venv/bin/python -m pytest tests/test_chat_tools_coordenacao.py -q
"""

from __future__ import annotations

import ast
import json
import os
import re
import statistics as st
import subprocess
import sys
import types
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, NoReturn, get_args

import pytest
from postgrest.exceptions import APIError

from app.banco import consultas, estatisticas, importancia
from app.canvas_sync import estado as estado_do_sync
from app.chat.ferramentas import REGISTRO, Sessao
from app.chat.tools import banco_questoes, contexto, rotinas, trilha
from app.gravacoes_aula import consulta as gravacoes
from app.lembretes import motor
from app.lembretes.aplicacoes import aluno_simulado
from app.schemas.domain import Severidade
from app.stats import classificacao_ciclo, criterios, criterios_repo
from tests.esquema_das_migrations import esquema
from tests.fake_postgrest import FakeCliente, Query, Resp, _ordenavel

COORDENACAO = Sessao(tipo="coordenador", usuario="coord:teste", papel="coordenador")


# ─── O fake ──────────────────────────────────────────────────────────────


def _partes(selecao: str) -> list[str]:
    """O select dividido no nível de cima, respeitando os parênteses do embed."""
    partes, atual, profundidade = [], [], 0
    for c in selecao:
        profundidade += (c == "(") - (c == ")")
        if c == "," and profundidade == 0:
            partes.append("".join(atual).strip())
            atual = []
        else:
            atual.append(c)
    if "".join(atual).strip():
        partes.append("".join(atual).strip())
    return partes


def _por_id(db: dict, tabela: str, valor: Any) -> dict | None:
    linhas = db.get(tabela, {})
    if valor in linhas:
        return linhas[valor]
    return next((l for l in linhas.values() if l.get("id") == valor), None)


def _projetar(db: dict, linha: dict | None, selecao: str) -> dict | None:
    """Só as colunas pedidas. Embed: o que a linha já carrega (filho semeado
    junto, como `predicado_criterio`), ou o pai pela FK (`aluno:aluno_id(nome)`,
    `simulado(...)`), recursivo."""
    if linha is None:
        return None
    selecao = selecao.strip()
    if selecao in ("", "*"):
        return dict(linha)
    saida: dict[str, Any] = {}
    for item in _partes(selecao):
        if "(" not in item:
            saida[item] = linha.get(item)
            continue
        cabeca, resto = item.split("(", 1)
        interno = resto[: resto.rfind(")")]
        alias, _, fk = (p.strip() for p in cabeca.partition(":"))
        relacao = fk or alias
        junto = next(
            (linha[k] for k in (alias, relacao) if isinstance(linha.get(k), (list, dict))), None
        )
        if junto is not None:
            saida[alias] = (
                [_projetar(db, f, interno) for f in junto]
                if isinstance(junto, list)
                else _projetar(db, junto, interno)
            )
            continue
        coluna = relacao if relacao.endswith("_id") else f"{relacao}_id"
        valor = linha.get(coluna)
        saida[alias] = _projetar(db, _por_id(db, coluna[:-3], valor), interno) if valor else None
    return saida


_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T")


def _comparavel(v: Any) -> tuple:
    if isinstance(v, bool):
        return (3, str(v))
    if isinstance(v, (int, float)):
        return (0, float(v))
    if isinstance(v, str):
        if _ISO.match(v):
            momento = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if momento.tzinfo is None:
                momento = momento.replace(tzinfo=UTC)
            return (1, momento.timestamp())
        try:
            return (0, float(v))
        except ValueError:
            return (2, v)
    return (3, str(v))


def _casa_like(atual: Any, padrao: Any, sem_caixa: bool) -> bool:
    """LIKE/ILIKE como o banco o lê: o PostgREST troca `*` por `%`, e o
    Postgres lê `%` e `_` como curingas e a barra invertida como o ESCAPE
    padrão — `\\%` é o caractere `%` (lookup.literal_no_like conta com isso)."""
    if atual is None:
        return False
    texto, partes, i = str(padrao).replace("*", "%"), [], 0
    while i < len(texto):
        c = texto[i]
        if c == "\\" and i + 1 < len(texto):
            partes.append(re.escape(texto[i + 1]))
            i += 2
            continue
        partes.append(".*" if c == "%" else "." if c == "_" else re.escape(c))
        i += 1
    regex = "".join(partes)
    flags = re.DOTALL | (re.IGNORECASE if sem_caixa else 0)
    return re.fullmatch(regex, str(atual), flags) is not None


#: Um ramo do `or=(…)`: `coluna.op.valor`, com o valor entre aspas quando
#: tem vírgula ou ponto — o formato que `auditoria._recurso_comeca_com` monta.
_RAMO = re.compile(r'(\w+)\.(like|ilike|eq)\.(?:"((?:[^"\\]|\\.)*)"|([^,]*))')


def _algum_ramo_bate(linha: dict, filtro: str) -> bool:
    for m in _RAMO.finditer(filtro):
        coluna, operador, citado, cru = m.groups()
        valor = re.sub(r"\\(.)", r"\1", citado) if citado is not None else cru
        if operador == "eq" and str(linha.get(coluna)) == valor:
            return True
        if operador != "eq" and _casa_like(linha.get(coluna), valor, operador == "ilike"):
            return True
    return False


# ─── O que o PostgREST recusaria ─────────────────────────────────────────

#: Filtros que comparam o VALOR com a coluna: numa coluna uuid, o Postgres
#: converte o valor e recusa o que não é uuid (22P02).
_COMPARACOES = frozenset({"eq", "neq", "in", "nao_in", "lt", "lte", "gt", "gte"})


def _recusar(codigo: str, mensagem: str) -> NoReturn:
    """A mesma exceção que o postgrest-py levanta com a resposta de erro."""
    raise APIError({"code": codigo, "message": mensagem, "details": None, "hint": None})


def _tabela_do_embed(tabela: str, cabeca: str) -> str:
    """A tabela de `simulado(...)`, `aluno:aluno_id(...)` ou `simulado!inner(...)`."""
    alias, _, alvo = (p.strip() for p in cabeca.partition(":"))
    nome = (alvo or alias).split("!")[0].strip()
    if esquema().existe(nome):
        return nome
    if nome.endswith("_id") and nome in (esquema().colunas(tabela) or {}) and esquema().existe(nome[:-3]):
        return nome[:-3]
    _recusar("PGRST200", f"Could not find a relationship between '{tabela}' and '{nome}' in the schema cache")


def _conferir_selecao(tabela: str, selecao: str) -> None:
    colunas = esquema().colunas(tabela)
    if colunas is None:
        return  # view: o leitor não sabe as colunas, e o fake não as inventa
    for item in _partes(selecao or "*"):
        if item in ("", "*"):
            continue
        if "(" in item:
            cabeca, resto = item.split("(", 1)
            _conferir_selecao(_tabela_do_embed(tabela, cabeca), resto[: resto.rfind(")")])
            continue
        # `alias:coluna`, `coluna::tipo` e `coluna->chave` pedem a mesma coluna.
        coluna = item.split("::")[0].split(":")[-1].split("->")[0].strip()
        if coluna not in colunas:
            _recusar("42703", f"column {tabela}.{coluna} does not exist")


def _conferir_no_esquema(consulta: ConsultaRica) -> None:
    """Tabela, colunas pedidas, filtradas e ordenadas, e uuid bem formado."""
    if not esquema().existe(consulta.tabela):
        _recusar("PGRST205", f"Could not find the table 'public.{consulta.tabela}' in the schema cache")
    _conferir_selecao(consulta.tabela, consulta.colunas)
    colunas = esquema().colunas(consulta.tabela)
    if colunas is None:
        return
    for tipo, coluna, valor in consulta.filtros:
        nomes = [m.group(1) for m in _RAMO.finditer(valor)] if tipo == "or" else [coluna]
        for nome in nomes:
            if nome not in colunas:
                _recusar("42703", f"column {consulta.tabela}.{nome} does not exist")
        if tipo in _COMPARACOES and colunas.get(coluna) == "uuid":
            for item in valor if isinstance(valor, list) else [valor]:
                try:
                    uuid.UUID(str(item))
                except ValueError:
                    _recusar("22P02", f'invalid input syntax for type uuid: "{item}"')
    for coluna, _ in consulta._order:
        if coluna not in colunas:
            _recusar("42703", f"column {consulta.tabela}.{coluna} does not exist")


class _Negacao:
    def __init__(self, consulta: ConsultaRica):
        self.consulta = consulta

    def is_(self, coluna, valor):
        self.consulta.filtros.append(("nao_is", coluna, valor))
        return self.consulta

    def in_(self, coluna, valores):
        self.consulta.filtros.append(("nao_in", coluna, list(valores)))
        return self.consulta


class ConsultaRica(Query):
    falhar = False

    def neq(self, c, v):
        self.filtros.append(("neq", c, v))
        return self

    def or_(self, filtro):
        self.filtros.append(("or", None, filtro))
        return self

    @property
    def not_(self):
        return _Negacao(self)

    def _bate(self, linha) -> bool:
        for tipo, coluna, valor in self.filtros:
            atual = linha.get(coluna) if coluna else None
            if tipo == "eq" and atual != valor:
                return False
            if tipo == "neq" and atual == valor:
                return False
            if tipo == "in" and atual not in valor:
                return False
            if tipo == "nao_in" and atual in valor:
                return False
            if tipo == "is" and valor == "null" and atual is not None:
                return False
            if tipo == "nao_is" and valor == "null" and atual is None:
                return False
            if tipo in ("lt", "lte", "gt", "gte"):
                if atual is None:
                    return False
                a, b = _comparavel(atual), _comparavel(valor)
                ok = {"lt": a < b, "lte": a <= b, "gt": a > b, "gte": a >= b}[tipo]
                if not ok:
                    return False
            if tipo in ("like", "ilike") and not _casa_like(atual, valor, tipo == "ilike"):
                return False
            if tipo == "or" and not _algum_ramo_bate(linha, valor):
                return False
            if tipo == "contains" and not all(item in (atual or []) for item in valor):
                return False
        return True

    def execute(self):
        if self.falhar:
            raise RuntimeError("banco fora do ar (simulado no teste)")
        if self.op != "select":
            raise AssertionError(f"tool da coordenação tentou {self.op} em {self.tabela}")
        _conferir_no_esquema(self)
        linhas = [l for l in self.db.get(self.tabela, {}).values() if self._bate(l)]
        for coluna, desc in reversed(self._order):
            linhas.sort(key=lambda l, c=coluna: _ordenavel(l.get(c)), reverse=desc)
        n = len(linhas)
        if self._range:
            inicio, fim = self._range
            linhas = linhas[inicio : fim + 1]
        elif self._limit is not None:
            linhas = linhas[: self._limit]
        return Resp([_projetar(self.db, l, self.colunas) for l in linhas], count=n if self.contagem else None)


class TabelaRica:
    def __init__(self, cliente: FakeRico, nome: str):
        self.cliente, self.nome = cliente, nome

    def select(self, *colunas, count=None):
        consulta = ConsultaRica(self.cliente.db, self.nome, "select")
        consulta.colunas = ",".join(colunas)
        consulta.contagem = count
        consulta.falhar = self.nome in self.cliente.falhar_em
        self.cliente.consultas.append(consulta)
        return consulta

    def _escrita(self, *_a, **_k):
        self.cliente.escritas.append(self.nome)
        raise AssertionError(f"tool da coordenação escreveu em {self.nome}")

    insert = upsert = update = delete = _escrita


class FakeRico(FakeCliente):
    """O fake de sempre com projeção, embed, os filtros que faltavam e escrita
    proibida. `consultas` guarda cada leitura, para conferir limite e formato."""

    def __init__(self, db, *, falhar_em=()):
        super().__init__(db)
        self.falhar_em = frozenset(falhar_em)
        self.consultas: list[ConsultaRica] = []
        self.escritas: list[str] = []

    def table(self, nome):
        return TabelaRica(self, nome)

    def rpc(self, funcao, *_a, **_k):
        self.escritas.append(f"rpc:{funcao}")
        raise AssertionError(f"tool da coordenação chamou rpc {funcao}")

    def em(self, tabela: str) -> list[ConsultaRica]:
        return [c for c in self.consultas if c.tabela == tabela]


# ─── A escola sintética ──────────────────────────────────────────────────


def _id(classe: int, n: int) -> str:
    return str(uuid.UUID(int=(classe << 64) | n))


A, B, C, D, E, F = (_id(1, n) for n in range(1, 7))
#: (nome, matrícula, ativo, zona, tendência, perfil, média recente)
ALUNOS_SINTETICOS: dict[str, tuple] = {
    A: ("ALUNA SINTETICA UM", "9000001", True, "cinzenta", "caindo", "misterio", 5.0),
    B: ("ALUNO SINTETICO DOIS", "9000002", True, "top", "subindo", "regular", 7.5),
    C: ("ALUNA SINTETICA TRES", "9000003", True, "top", "estavel", "ancora", 7.1),
    D: ("ALUNO SINTETICO QUATRO", "9000004", True, "risco", "estavel", "regular", 3.0),
    E: ("ALUNA SINTETICA CINCO", "9000005", False, "risco", "caindo", "regular", 2.0),
    F: ("ALUNO SINTETICO SEIS", "9000006", True, "cinzenta", "estavel", "regular", 5.0),
}
NOME = {aid: v[0] for aid, v in ALUNOS_SINTETICOS.items()}
MATRICULA = {aid: v[1] for aid, v in ALUNOS_SINTETICOS.items()}

C1, C2, C3, C4 = (_id(3, n) for n in range(1, 5))
K1, K2 = _id(7, 1), _id(7, 2)
NOME_DA_COORDENACAO = {K1: "COORDENADORA SINTETICA", K2: "COORDENADOR OUTRO"}
SEDE_AD, SEDE_ON = _id(5, 1), _id(5, 2)
T1, T2 = _id(4, 1), _id(4, 2)
ANO = _id(8, 1)
MATERIAS = (
    ("matematica", "Matemática"), ("fisica", "Física"), ("quimica", "Química"),
    ("portugues", "Português"), ("ingles", "Inglês"), ("redacao", "Redação"),
)
MATERIA = {codigo: _id(6, i) for i, (codigo, _) in enumerate(MATERIAS, start=1)}

#: chave → (ciclo, matéria, tipo, dias atrás; negativo = no futuro)
_SIMULADOS = {
    "MAT_F1": (C2, "matematica", "fase_1", 30),
    "FIS_F1": (C2, "fisica", "fase_1", 29),
    "MAT_F2": (C2, "matematica", "fase_2", 22),
    "FIS_F2": (C2, "fisica", "fase_2", 21),
    "QUI_F2": (C2, "quimica", "fase_2", 20),
    "POR_F2": (C2, "portugues", "fase_2", 19),
    "MAT_F1_C1": (C1, "matematica", "fase_1", 120),
    "FIS_F2_C1": (C1, "fisica", "fase_2", 110),
}
#: Simulados nascidos no SAS, no futuro: (canvas_estado, tentativas)
_SIMULADOS_DO_SAS = {
    "SAS_PENDENTE": ("pendente", 0),
    "SAS_FALHOU": ("falhou", 2),
    "SAS_DESISTIU": ("falhou", 5),
    "SAS_DIVERGENTE": ("divergente", 0),
    "SAS_PROX": ("sincronizado", 0),
}
S = {chave: _id(2, i) for i, chave in enumerate([*_SIMULADOS, *_SIMULADOS_DO_SAS], start=1)}

_NOTAS = {
    A: {"MAT_F1": 9, "FIS_F1": 9, "MAT_F2": 3, "FIS_F2": 3, "QUI_F2": 6, "POR_F2": 2,
        "MAT_F1_C1": 8, "FIS_F2_C1": 8},
    B: {**{k: 8 for k in ("MAT_F1", "FIS_F1", "MAT_F2", "FIS_F2", "QUI_F2", "POR_F2")},
        "MAT_F1_C1": 3, "FIS_F2_C1": 3},
    C: {k: 6 for k in _SIMULADOS},
    D: {"MAT_F1": 3, "FIS_F1": 3, "MAT_F2": 3, "FIS_F2": 3, "QUI_F2": 2, "POR_F2": None,
        "MAT_F1_C1": 4, "FIS_F2_C1": 4},
    E: {k: (1 if k.endswith("_C1") else 2) for k in _SIMULADOS},
    F: {"POR_F2": 5},
}

REGUA_CRIADA = "meta-7-exatas"
EV1, EV2, EV3 = (_id(9, n) for n in range(1, 4))


@dataclass
class Escola:
    db: dict[str, dict[Any, dict]]
    agora: datetime
    hoje_brt: date

    def cliente(self, **kw) -> FakeRico:
        return FakeRico(self.db, **kw)


def nova_escola() -> Escola:
    agora = datetime.now(UTC)
    hoje = date.today()
    hoje_brt = agora.astimezone(motor.FUSO_BRASIL).date()
    amanha = hoje_brt + timedelta(days=1)
    db: dict[str, dict[Any, dict]] = {}

    def por(tabela: str, **linha) -> dict:
        tab = db.setdefault(tabela, {})
        tab[linha.get("id", f"{tabela}-{len(tab)}")] = linha
        return linha

    def ts(**delta) -> str:
        return (agora - timedelta(**delta)).isoformat()

    # Dimensões
    por("sede", id=SEDE_AD, codigo="AD", nome="Aldeota", modalidade="presencial")
    por("sede", id=SEDE_ON, codigo="ON", nome="Online", modalidade="online")
    por("ano_letivo", id=ANO, ano=hoje.year, canvas_course_id="900")
    por("turma", id=T1, sede_id=SEDE_AD, ano_letivo_id=ANO, serie=3, trilha="ITA", section_original="3o ITA AD")
    por("turma", id=T2, sede_id=SEDE_ON, ano_letivo_id=ANO, serie=3, trilha="ITA", section_original="3o ITA ON")
    for codigo, nome in MATERIAS:
        por("materia", id=MATERIA[codigo], codigo=codigo, nome=nome)
    erro_com_url = (
        "ConnectError: https://ari.instructure.com/api/v1/courses/900/assignment_groups"
        "?access_token=1234~abcdefghijklmnopqrstuvwxyz"
    )
    for cid, ordem, estado_canvas, erro in (
        (C1, 1, None, None), (C2, 2, None, None), (C3, 3, "falhou", erro_com_url), (C4, 4, "divergente", None),
    ):
        por("ciclo", id=cid, ano_letivo_id=ANO, ordem=ordem, nome=f"Ciclo {ordem} · ITA", vestibular_alvo="ITA",
            periodo_inicio=None, periodo_fim=None, canvas_estado=estado_canvas, canvas_erro=erro)

    # Simulados aplicados (vieram do Canvas) e os do SAS, no futuro
    for chave, (ciclo, materia, tipo, atras) in _SIMULADOS.items():
        por("simulado", id=S[chave], external_id=str(4000 + len(db.get("simulado", {}))), ciclo_id=ciclo,
            materia_id=MATERIA[materia], nome=f"{chave} - {materia.capitalize()}", rotulo_curto=chave,
            tipo=tipo, data_aplicacao=(hoje - timedelta(days=atras)).isoformat(), nota_maxima=10,
            e_agregado=False, anulado=False, nota_confiavel=True, quiz_id="777" if chave == "FIS_F2" else None,
            origem="canvas", canvas_estado=None, canvas_tentativas=0, canvas_erro=None, evento_agenda_id=None)
    for chave, (estado_canvas, tentativas) in _SIMULADOS_DO_SAS.items():
        por("simulado", id=S[chave], external_id=None, ciclo_id=C3, materia_id=MATERIA["fisica"],
            nome=f"{chave} - Física", rotulo_curto=chave, tipo="fase_2",
            data_aplicacao=(amanha if chave == "SAS_PROX" else hoje + timedelta(days=40)).isoformat(),
            nota_maxima=10, e_agregado=False, anulado=False, nota_confiavel=True, quiz_id=None, origem="sas",
            canvas_estado=estado_canvas, canvas_tentativas=tentativas,
            canvas_erro=erro_com_url if estado_canvas == "falhou" else None,
            evento_agenda_id=EV1 if chave == "SAS_PROX" else None)

    # Alunos — com as colunas de PII que NENHUMA tool seleciona
    for aid, (nome, matricula, ativo, zona, tendencia, perfil, media) in ALUNOS_SINTETICOS.items():
        por("aluno", id=aid, nome=nome, matricula=matricula, ativo=ativo, email=f"{matricula}@alunos.invalid",
            senha_hash="$2b$12$naoeparasair", foto_perfil_storage=None, canvas_user_id="123")
        por("matricula_turma", aluno_id=aid, turma_id=T1 if aid in (A, B) else T2,
            ativo_desde=(hoje - timedelta(days=300)).isoformat(), ativo_ate=None)
        por("vestibular_alvo_aluno", aluno_id=aid, vestibular="ITA")
        por("classificacao_aluno", aluno_id=aid, perfil=perfil, tendencia=tendencia, zona=zona,
            media_recente=media, desvio_recente=1.0, coef_tendencia=-0.5 if tendencia == "caindo" else 0.4,
            p_valor_tendencia=0.04, janela_simulados=5)
    for aid, notas in _NOTAS.items():
        for chave, valor in notas.items():
            por("nota", aluno_id=aid, simulado_id=S[chave], pontuacao=valor, presente=valor is not None,
                computavel=valor is not None, pontuacao_sas=None, pontuacao_canvas=valor)

    # Métrica geral de cada simulado aplicado
    for chave in _SIMULADOS:
        valores = sorted(float(n[chave]) for n in _NOTAS.values() if n.get(chave) is not None)
        ausentes = sum(1 for n in _NOTAS.values() if chave in n and n[chave] is None)
        por("metrica_simulado", simulado_id=S[chave], recorte_tipo="geral", recorte_id=None,
            media=st.mean(valores), mediana=st.median(valores), desvio_padrao=st.pstdev(valores),
            minimo=valores[0], maximo=valores[-1], quartil_1=valores[0], quartil_3=valores[-1],
            n_presentes=len(valores), n_ausentes=ausentes, pct_aprovados=50.0, pct_zona_critica=20.0,
            pct_excelencia=10.0, histograma={"largura_bin": 0.5, "maximo": 10, "contagens": [1] * 20})

    # O que o sistema já sinalizou
    for n, (severidade, categoria, atras, titulo, resolvido) in enumerate((
        ("vermelho", "QUEDA_RENDIMENTO", {"hours": 3}, "ALUNA SINTETICA UM caiu 2,1 pontos", False),
        ("vermelho", "DIFERENCA_ENTRE_SEDES", {"hours": 1}, "Física: Aldeota abaixo de Online", False),
        ("ambar", "MATERIA_EM_RISCO", {"minutes": 30}, "Química abaixo do histórico", False),
        ("verde", "SUBIDA_ATIPICA", {"minutes": 10}, "ALUNO SINTETICO DOIS subiu 5 pontos", False),
        ("cinza", "PANORAMA_CICLO", {"minutes": 5}, "Ciclo 2 concluído", False),
        ("vermelho", "QUEDA_RENDIMENTO", {"minutes": 1}, "já resolvido", True),
    ), start=1):
        por("alerta", id=_id(20, n), categoria=categoria, severidade=severidade, entidade_tipo="aluno",
            entidade_id=A, titulo=titulo, subtitulo="", disparado_em=ts(**atras), resolvido=resolvido)
    por("insight_ciclo", ciclo_id=C2, fase="todas", materia_codigo=None, tipo_insight="pratico",
        bullets=["42% da turma ficou abaixo do corte em Física."], gerado_em=ts(days=1))
    for i in (1, 2, 3):
        qid = _id(14, i)
        por("questao", id=qid, simulado_id=S["FIS_F2"], posicao=i, assunto="Cinemática",
            texto=f"<p>Uma bola é lançada para cima, questão {i}</p>")
        for j, aid in enumerate((A, B, C, D)):
            por("questao_resposta_aluno", aluno_id=aid, questao_id=qid, correta=(i + j) % 2 == 0)

    # Banco de questões — prova passada, sem pessoa
    for materia, codigo, nome, bloco_codigo, bloco_nome, ordem, assuntos in (
        ("Física", "1.1", "Fundamentos", "1", "Fundamentos da Física", 1, ["Grandezas", "Vetores"]),
        ("Física", "7.2", "Ondas e Acústica", "7", "Oscilações e Ondas Mecânicas", 2, ["Ondas sonoras"]),
        ("Física", "8.1", "Óptica Geométrica", "8", "Óptica", 3, ["Espelhos", "Lentes"]),
        ("Química", "1.1", "Estrutura Atômica", "1", "Química Geral", 1, ["Modelos atômicos"]),
        ("Química", "3.1", "Estequiometria", "3", "Cálculos Químicos", 2, ["Mol"]),
        ("Matemática", "1.1", "Conjuntos e Lógica", "1", "Fundamentos", 1, []),
    ):
        por("topico_taxonomia", materia=materia, codigo=codigo, nome=nome, bloco_codigo=bloco_codigo,
            bloco_nome=bloco_nome, ordem=ordem,
            topico_taxonomia_assunto=[{"ordem": i, "texto": t} for i, t in enumerate(assuntos)])
    alternativas = [{"letra": letra, "texto": f"opção {letra}"} for letra in "EDCBA"]
    for qid, materia, topicos, extra in (
        ("ita_2019_fase1_q01", "Física", ["7.2"], {"gabarito": "C", "gabarito_origem": "banca"}),
        ("ita_2021_fase1_q02", "Física", ["7.2"], {"gabarito": "B", "gabarito_origem": "sugerido"}),
        ("ita_2023_fase1_q07", "Física", ["8.1"], {
            "gabarito": "A", "gabarito_origem": "banca", "imagem_url": "https://bucket.invalid/q7.png",
            "usa_imagem_no_render": True, "resolucao_url": "https://youtu.be/RESOLUCAODOARI"}),
        ("ita_2023_fase2_q03", "Física", ["8.1", "7.2"], {
            "dissertativa": True, "resolucao_md": "Resolução escrita.", "resolucao_origem": "ia"}),
        ("ime_2022_fase1_q05", "Física", ["1.1"], {"extraido_por": "pagina"}),
        ("ita_2024_fase1_q09", "Física", [], {}),
        ("ita_2022_fase1_q11", "Química", ["1.1"], {}),
        ("ime_2023_fase2_q02", "Química", ["3.1"], {"dissertativa": True}),
    ):
        partes = re.fullmatch(r"(ita|ime)_(\d{4})_fase(\d)_q(\d+)", qid)
        vestibular, ano, fase, numero = (
            partes.group(1).upper(), int(partes.group(2)), int(partes.group(3)), int(partes.group(4))
        )
        dissertativa = extra.get("dissertativa", False)
        por("questao_vestibular", id=qid, vestibular=vestibular, ano=ano, fase=fase, materia=materia,
            numero=numero, dissertativa=dissertativa,
            enunciado_md=f"Uma bola é lançada  na questão {numero}.\n$$x^2$$",
            gabarito=extra.get("gabarito"), gabarito_origem=extra.get("gabarito_origem"),
            gabarito_confianca="alta", imagem_url=extra.get("imagem_url"),
            usa_imagem_no_render=extra.get("usa_imagem_no_render", False),
            resolucao_url=extra.get("resolucao_url"), resolucao_md=extra.get("resolucao_md"),
            resolucao_origem=extra.get("resolucao_origem"), extraido_por=extra.get("extraido_por", "pipeline"),
            revisado=True, arquivo_origem="lote.json",
            questao_vestibular_alternativa=[] if dissertativa else [dict(a) for a in alternativas])
        for codigo in topicos:
            por("questao_vestibular_topico", questao_id=qid, materia=materia, topico_codigo=codigo,
                confianca="alta", observacao=None)

    # Réguas criadas e quem as criou
    for k, nome in NOME_DA_COORDENACAO.items():
        por("usuario_coordenacao", id=k, nome=nome, email=f"{k[-4:]}@escola.invalid",
            senha_hash="$2b$12$naoeparasair", foto_perfil_storage=None, papel="coordenador")
    for versao, ativo, autor, descricao in (
        (1, False, K1, "Versão antiga"),
        (2, True, K2, "Meta interna; ver https://intranet.invalid/regua?token=abcdefghijklmnop"),
    ):
        por("criterio_classificacao", id=_id(13, versao), slug=REGUA_CRIADA, versao=versao,
            nome="Meta 7 em exatas", descricao=descricao, combinador="algum", fase=None, desempate=["media"],
            embutido=False, ativo=ativo, criado_em=ts(days=10 - versao), criado_por=autor,
            predicado_criterio=[
                {"posicao": i, "materia": m, "operador": ">=", "valor_nota": 7, "valor_acertos": None,
                 "valor_de": None, "eliminatorio": False, "entra_na_media": True, "peso": 1,
                 "fonte": "ata de 10/10 em https://drive.invalid/ata"}
                for i, m in enumerate(("matematica", "fisica", "quimica"), start=1)
            ])

    # Rodadas do sync: a de sucesso há 4 min, erros nas últimas 24 h e uma fora
    for n, (status, atras, resumo, erro) in enumerate((
        ("sucesso", {"minutes": 5}, {
            "alunos_processados": 900, "notas_gravadas": 12, "emails_preenchidos": 0,
            "avisos": ["section X ignorada",
                       "falhou em https://ari.instructure.com/api/v1/x?access_token=1234~abcdefghijklmnopqrstuvwxyz",
                       "a3", "a4"]}, None),
        ("erro", {"hours": 2}, None,
         "ConnectError: falhou em 'http://postgrest:3000/nota?select=*' Bearer abcdefghijklmnopqrstuvwxyz123456"),
        ("erro", {"hours": 20}, None, "timeout"),
        ("erro", {"hours": 30}, None, "antigo"),
        *(("sucesso", {"days": d}, {"notas_gravadas": 1}, None) for d in range(1, 13)),
    ), start=1):
        por("canvas_sync_execucao", id=_id(15, n), tipo="incremental", status=status, resumo=resumo,
            erro_mensagem=erro, iniciado_em=ts(**atras),
            finalizado_em=(agora - timedelta(**atras) + timedelta(minutes=1)).isoformat())

    # Gravações: (status, tentativas, vídeo, canvas, módulo, curso, atualizada há)
    por("curso_monitorado_gravacao", curso_id="581", nome="Física 3º ITA", ativo=True,
        publicar_no_canvas=True, canvas_modulo_id="m1")
    por("curso_monitorado_gravacao", curso_id="600", nome="Química 3º ITA", ativo=True,
        publicar_no_canvas=False, canvas_modulo_id=None)
    for n, (status, tentativas, video, canvas, modulo, curso, atras) in enumerate((
        ("publicado", 1, "VIDEOSECRETO1", "publicado", "Semana 1", "581", {"days": 1}),
        ("erro", 3, None, "pendente", None, "581", {"hours": 1}),
        ("erro", 1, None, "pendente", None, "581", {"hours": 1}),
        ("publicado_sem_confirmacao", 1, "VIDEOSECRETO4", "pendente", None, "581", {"hours": 2}),
        ("compondo", 1, None, "pendente", None, "581", {"hours": 5}),
        ("compondo", 1, None, "pendente", None, "581", {"minutes": 10}),
        ("publicado", 1, "VIDEOSECRETO7", "ambiguo", None, "581", {"days": 2}),
        ("publicado", 1, "VIDEOSECRETO8", "publicado", None, "581", {"days": 3}),
        ("aguardando_gravacao", 0, None, "pendente", None, "600", {"hours": 1}),
        ("publicando", 1, None, "pendente", None, "581", {"hours": 4}),
    ), start=1):
        por("aula_gravacao", id=_id(12, n), curso_id=curso, conferencia_id=f"conf-{n}",
            titulo=f"Aula {n} — Prof. Sintético", iniciada_em=ts(days=n), duracao_minutos=90, status=status,
            tentativas=tentativas, youtube_video_id=video, youtube_titulo=f"Aula {n} | Prof. Sintético",
            erro_detalhe=(
                "ReadTimeout: https://www.googleapis.com/upload/youtube?token=ya29.abcdefghijk"
                if status == "erro"
                # A escrita do id que não gravou (gravacoes_aula/rotas.py): o
                # Postgres cita a linha, com o vídeo e o lugar dele no S3.
                else (
                    "publicado mas o id não persistiu: APIError: {'code': '23514', 'details': "
                    f"'Failing row contains ({video}, Aula {n} (revisão), bucket-com-menores, aulas/{n}.mp4).', "
                    "'message': 'violates check constraint'}"
                )
                if status == "publicado_sem_confirmacao" else None
            ),
            canvas_estado=canvas,
            canvas_pagina_url=f"https://ari.instructure.com/courses/{curso}/pages/aula-{n}" if video else None,
            canvas_modulo_nome=modulo, canvas_erro=None, criado_em=ts(days=n), atualizado_em=ts(**atras),
            s3_bucket="bucket-com-menores", s3_chave_composto=f"aulas/{n}.mp4")

    # Lembretes: amanhã com aviso a coordenador e alunos; um em 10 dias; um cancelado
    for eid, dia, cancelado in ((EV1, amanha, None), (EV2, hoje_brt + timedelta(days=10), None),
                                (EV3, amanha + timedelta(days=1), ts(days=1))):
        por("evento_agenda", id=eid, tipo="simulado", titulo=f"Prova {eid[-1]}", data_evento=dia.isoformat(),
            hora_evento="07:00:00", criado_por="k1@escola.invalid", cancelado_em=cancelado)
    for n, (eid, tipo, dias_antes) in enumerate(((EV1, "coordenador", 1), (EV1, "aluno", 1), (EV3, "aluno", 1)),
                                                 start=1):
        por("regra_lembrete", id=_id(10, n), evento_agenda_id=eid, destinatario_tipo=tipo, canal="email",
            dias_antes=dias_antes, cancelada_em=None)
    chave = aluno_simulado.chave_idempotencia
    for n, (estado, enviar_em, enviado_em, tentativas, atualizado, chave_dia) in enumerate((
        ("agendado", agora + timedelta(hours=2), None, 0, agora, None),
        ("agendado", agora + timedelta(hours=3), None, 0, agora, chave(amanha, A)),
        ("enviado", agora - timedelta(hours=1), agora - timedelta(hours=1), 1, agora, chave(amanha, B)),
        ("cancelado", agora + timedelta(hours=3), None, 0, agora, chave(amanha, C)),
        ("falhou", agora - timedelta(hours=2), None, 5, agora - timedelta(hours=1), None),
        ("falhou", agora - timedelta(hours=3), None, 2, agora - timedelta(hours=2), None),
        ("falhou", agora - timedelta(hours=40), None, 5, agora - timedelta(hours=30), None),
        ("enviando", agora - timedelta(hours=2), None, 0, agora - timedelta(hours=2), None),
        ("enviando", agora - timedelta(minutes=5), None, 0, agora - timedelta(minutes=5), None),
        ("agendado", agora + timedelta(days=20), None, 0, agora, None),
        ("enviado", agora - timedelta(hours=31), agora - timedelta(hours=30), 1, agora, None),
    ), start=1):
        por("disparo", id=_id(11, n), regra_lembrete_id=_id(10, 1), destinatario=f"pessoa{n}@escola.invalid",
            canal="email", enviar_em=enviar_em.isoformat(), estado=estado, tentativas=tentativas,
            erro="SES: https://email.us-east-1.amazonaws.com rejeitou" if estado == "falhou" else None,
            assunto="Lembrete", corpo=f"Olá {NOME[A]}, amanhã tem prova.",
            enviado_em=enviado_em.isoformat() if enviado_em else None, atualizado_em=atualizado.isoformat(),
            contexto={"dia": amanha.isoformat(), "aluno_id": A, "nome": NOME[A]}, chave_idempotencia=chave_dia)

    # Trilha de auditoria: os canais que a tool lê, e os que nunca lê
    for n, (acao, canal, ator_tipo, ator, recurso, detalhe, atras) in enumerate((
        ("login_ok", "acesso", "coordenador", K1, None, {"nome": NOME_DA_COORDENACAO[K1]}, {"days": 12}),
        ("login_falhou", "acesso", None, "k1@escola.invalid", None, None, {"days": 11}),
        ("coordenador_criado", "acesso", "coordenador", K1, f"usuario_coordenacao/{K2}",
         {"email": "novo@escola.invalid", "nome": "FULANO NOVO"}, {"days": 10}),
        ("nota_editada", "nota", "coordenador", K1, f"nota/{A}/{S['FIS_F2']}", {
            "aluno": NOME[A], "valor_antes": 4.0, "valor_depois": 5.5, "valor_canvas": 4.0, "presente": True,
            "sincronizar_canvas": True, "canvas_ok": False,
            "canvas_erro": "401 em https://ari.instructure.com/api/v1/courses/1?access_token=999~abcdefghijklmnopqrstuvwxyz",
            "segredo_extra": "NAO-PODE-SAIR"}, {"days": 9}),
        ("nota_editada", "nota", "coordenador", K2, f"nota/{B}/{S['MAT_F2']}", {
            "aluno": NOME[B], "valor_antes": 6.0, "valor_depois": 7.0}, {"days": 8}),
        ("simulado_editado", "simulado", "coordenador", K1, f"simulado/{S['FIS_F2']}", {
            "campos": {"nome": "novo nome"}, "origem": "canvas", "sincronizar_canvas": False,
            "canvas_estado": "divergente"}, {"minutes": 10}),
        ("enviado_ao_canvas", "canvas", "coordenador", K2, f"nota/{A}/{S['FIS_F2']}", {
            "lote": C2, "ok": False, "erro": "500 em https://ari.instructure.com/api"}, {"minutes": 9}),
        ("criterio_criado", "criterio", "coordenador", K2, f"criterio/{REGUA_CRIADA}", {
            "nome": "Meta 7 em exatas", "versao": 1, "requisitos": 3}, {"minutes": 8}),
        ("pedido_criado", "cantina", "aluno", A, "pedido/1", {"nome": NOME[A]}, {"minutes": 7}),
        ("busca", "captacao", "coordenador", K1, "captacao/1", {"termo": "FULANO DE FORA"}, {"minutes": 6}),
        ("ciclo_criado", "ciclo", None, None, f"ciclo/{C2}", {
            "nome": "Ciclo 2 · ITA", "canvas_estado": "sincronizado", "canvas_erro": None}, {"minutes": 5}),
        ("chamada", "mcp", "coordenador", K1, "mcp/token-1", {"ferramenta": "listar_alunos"}, {"minutes": 4}),
    ), start=1):
        por("evento_auditoria", id=n, ocorrido_em=ts(**atras), acao=acao, canal=canal, ator_tipo=ator_tipo,
            ator_id=ator, recurso=recurso, ip="10.0.0.1", detalhe=detalhe, request_id=f"req-{n}")

    return Escola(db=db, agora=agora, hoje_brt=hoje_brt)


def chamar(cliente: FakeRico, ferramenta: str, /, **args) -> dict:
    # Só-posicional: `nome` também é argumento de tool (buscar_aluno_por_nome).
    return REGISTRO.despachar(COORDENACAO, ferramenta, cliente, args)


def _texto(resultado: Any) -> str:
    return json.dumps(resultado, ensure_ascii=False, default=str)


@pytest.fixture
def escola() -> Escola:
    return nova_escola()


# ─── listar_alertas: o enum e a ordem do banco ───────────────────────────


class TestListarAlertas:
    def test_o_enum_e_o_que_o_banco_grava(self):
        """CHECK da 0001, Literal do schema e o que o motor emite: a mesma lista."""
        sql = (Path(__file__).resolve().parents[1] / "migrations" / "0001_schema_inicial.sql").read_text()
        check = re.search(r"CHECK \(severidade IN \(([^)]*)\)\)", sql)
        assert tuple(re.findall(r"'(\w+)'", check.group(1))) == contexto.SEVERIDADES
        assert get_args(Severidade) == contexto.SEVERIDADES
        motor_de_alertas = (Path(__file__).resolve().parents[1] / "app" / "stats" / "alertas.py").read_text()
        assert set(re.findall(r'"severidade": "(\w+)"', motor_de_alertas)) <= set(contexto.SEVERIDADES)

    def test_a_ordem_dos_pesos_e_a_da_rota(self):
        from app.routes import alertas as rota

        assert list(contexto.SEVERIDADES) == sorted(rota._PESO_SEVERIDADE, key=rota._PESO_SEVERIDADE.get)

    def test_sem_filtro_vem_do_mais_severo_e_na_mesma_severidade_do_mais_recente(self, escola):
        r = chamar(escola.cliente(), "listar_alertas")
        assert [a["severidade"] for a in r["alertas"]] == ["vermelho", "vermelho", "ambar", "verde", "cinza"]
        vermelhos = [a["categoria"] for a in r["alertas"][:2]]
        assert vermelhos == ["DIFERENCA_ENTRE_SEDES", "QUEDA_RENDIMENTO"]   # o de 1 h antes do de 3 h
        assert r["total"] == 5                                              # o resolvido não entra

    @pytest.mark.parametrize(("pedido", "gravado", "quantos"), [
        ("vermelho", "vermelho", 2), ("critico", "vermelho", 2),
        ("ambar", "ambar", 1), ("atencao", "ambar", 1),
        ("cinza", "cinza", 1), ("informativo", "cinza", 1), ("verde", "verde", 1),
    ])
    def test_filtrar_pelo_valor_real_ou_pelo_nome_antigo(self, escola, pedido, gravado, quantos):
        r = chamar(escola.cliente(), "listar_alertas", severidade=pedido)
        assert "erro" not in r
        assert r["total"] == quantos
        assert {a["severidade"] for a in r["alertas"]} == {gravado}

    def test_severidade_inventada_e_categoria_inventada_sao_recusadas_pelo_registro(self, escola):
        assert "erro" in chamar(escola.cliente(), "listar_alertas", severidade="laranja")
        assert "erro" in chamar(escola.cliente(), "listar_alertas", categoria="queda")
        r = chamar(escola.cliente(), "listar_alertas", categoria="SUBIDA_ATIPICA")
        assert [a["severidade"] for a in r["alertas"]] == ["verde"]


# ─── Os consertos de identidade ──────────────────────────────────────────


class TestRelatorioCiclo:
    def test_aluno_em_risco_e_destaque_vem_com_id_e_matricula(self, escola):
        r = chamar(escola.cliente(), "relatorio_ciclo", ciclo_id=C2)
        assert "erro" not in r, r
        listados = [*r["alunosRisco"], *r["alunosDestaque"]]
        assert {a["alunoId"] for a in r["alunosRisco"]} == {A, D, F}      # E é inativa
        assert {a["alunoId"] for a in r["alunosDestaque"]} == {B, C}
        for a in listados:
            assert a["nome"] == NOME[a["alunoId"]]
            assert a["matricula"] == MATRICULA[a["alunoId"]]

    def test_o_select_do_aluno_nao_traz_email(self, escola):
        r = chamar(escola.cliente(), "relatorio_ciclo", ciclo_id=C2)
        assert "@alunos.invalid" not in _texto(r) and "senha" not in _texto(r)


class TestCompararAlunos:
    def test_maior_e_menor_vem_com_o_id_do_aluno_certo(self, escola):
        r = chamar(escola.cliente(), "comparar_alunos", aluno_ids=[A, B, C])
        assert r["maioresDiferencas"]
        por_id = {a["alunoId"]: a for a in r["alunos"]}
        for d in r["maioresDiferencas"]:
            for lado in ("maior", "menor"):
                aluno = por_id[d[lado]["alunoId"]]
                assert d[lado]["nome"] == aluno["nome"]
                assert d[lado]["media"] == aluno["porMateria"][d["materia"]]
            assert d["maior"]["media"] == max(a["porMateria"].get(d["materia"], -1) for a in r["alunos"])
            assert d["menor"]["media"] == min(
                a["porMateria"][d["materia"]] for a in r["alunos"] if d["materia"] in a["porMateria"]
            )


# ─── materias_problematicas: a fase é `simulado.tipo` ────────────────────


class TestMateriasProblematicas:
    def test_responde_com_dado_e_nao_com_falha(self, escola):
        """Pedia `simulado.fase`, removida na 0003: no PostgREST, 42703 em toda
        chamada, e o modelo ouvia "falhou do nosso lado" — numa tool exposta ao
        MCP e citada no prompt e nos roteiros (revisão paralela de 25/10). O
        fake confere o schema e reproduz a recusa."""
        cliente = escola.cliente()
        r = chamar(cliente, "materias_problematicas", ciclo_id=C2)
        assert "erro" not in r, r
        assert [m["materia"]["codigo"] for m in r["materias"]] == ["matematica", "fisica", "quimica", "portugues"]
        assert "tipo" in _partes(cliente.em("simulado")[0].colunas)

    def test_so_a_fase_2_entra_e_quem_diz_e_o_tipo(self, escola):
        mat = chamar(escola.cliente(), "materias_problematicas", ciclo_id=C2)["materias"][0]
        # Com o MAT_F1 junto, a média de A seria (9 + 3) / 2, e a da turma, 5,0.
        assert (mat["nAlunos"], mat["abaixoCorte"], mat["pctAbaixoCorte"], mat["media"]) == (5, 3, 60.0, 4.4)
        regua = criterios.por_slug(criterios.CRITERIO_DA_CASA)
        assert mat["corte"] == criterios.corte_da_materia(regua, "matematica")

    @pytest.mark.parametrize("ciclo_id", ["ciclo 2", "2º ciclo", ""])
    def test_ciclo_id_torto_e_erro_de_argumento_sem_ler(self, escola, ciclo_id):
        """O 22P02 virava "falhou do nosso lado, não repita", como nas tools
        das rotinas e da régua (revisão paralela de 25/10)."""
        cliente = escola.cliente()
        r = chamar(cliente, "materias_problematicas", ciclo_id=ciclo_id)
        assert r == {"erro": "ciclo_id deve ser um UUID; descubra-o com listar_ciclos"}
        assert not cliente.consultas

    def test_ciclo_id_em_caixa_alta_vale(self, escola):
        r = chamar(escola.cliente(), "materias_problematicas", ciclo_id=f" {C2.upper()} ")
        assert "erro" not in r and r["cicloId"] == C2


class TestTendenciaAluno:
    @pytest.mark.parametrize("aluno_id", ["Ana", "9000001", ""])
    def test_aluno_id_torto_e_erro_de_argumento_sem_ler(self, escola, aluno_id):
        cliente = escola.cliente()
        r = chamar(cliente, "tendencia_aluno", aluno_id=aluno_id)
        assert r == {"erro": "aluno_id deve ser um UUID; descubra-o com a tool de busca de aluno"}
        assert not cliente.consultas


class TestDicaDoIdTorto:
    @pytest.mark.parametrize(("nome", "argumento"), [("tendencia_aluno", "aluno_id"), ("materias_problematicas", "ciclo_id")])
    def test_so_cita_tool_que_o_mcp_tambem_tem(self, escola, nome, argumento):
        """As duas vão ao MCP: a dica de onde achar o id não pode mandar o
        modelo de lá para uma tool que ele não tem (`buscar_aluno_por_nome`
        não vai)."""
        erro = chamar(escola.cliente(), nome, **{argumento: "torto"})["erro"]
        citadas = {f.nome for f in REGISTRO.catalogo("coordenacao") if f.nome in erro}
        assert all(REGISTRO.obter(COORDENACAO, n).expor_no_mcp for n in {nome, *citadas})


# ─── Tetos de minimização (LGPD art. 6º, III) ────────────────────────────


def _com_alunos_extras(escola: Escola, n: int, *, zona: str = "risco", simulado: str = "MAT_F2") -> None:
    for i in range(n):
        aid = _id(30, i)
        escola.db["aluno"][aid] = {"id": aid, "nome": f"ALUNO EXTRA {i}", "matricula": f"8{i:06d}", "ativo": True}
        escola.db["classificacao_aluno"][f"extra-{i}"] = {
            "aluno_id": aid, "perfil": "regular", "tendencia": "estavel", "zona": zona,
            "media_recente": 1.0 + i / 1000, "coef_tendencia": 0.0,
        }
        escola.db["nota"][f"extra-{i}"] = {
            "aluno_id": aid, "simulado_id": S[simulado], "pontuacao": 5, "presente": True, "computavel": True,
            "pontuacao_sas": None, "pontuacao_canvas": 5,
        }


class TestBuscaPorNomeComCuringa:
    """`buscar_aluno_por_nome` lê o trecho como LETRAS (lookup.literal_no_like):
    `nome='__'` ou `'%%'` passava no mínimo de 2 caracteres e listava a escola
    (revisão de 26/10). O MCP serve a MESMA função — o teste do catálogo abaixo
    prova —, então o conserto vale nos dois."""

    @pytest.fixture
    def com_curingas(self, escola) -> Escola:
        for i, nome in enumerate(["CAIO 100% SINTETICO", "CAIO 1000 SINTETICO", "BIA_LIMA", "BIA-LIMA", "DAVI\\LIMA"]):
            aid = _id(31, i)
            escola.db["aluno"][aid] = {"id": aid, "nome": nome, "matricula": f"7{i:06d}", "ativo": True}
        return escola

    @staticmethod
    def _nomes(escola: Escola, termo: str) -> list[str]:
        return [a["nome"] for a in chamar(escola.cliente(), "buscar_aluno_por_nome", nome=termo)["alunos"]]

    def test_porcento_e_sublinhado_casam_so_o_caractere(self, com_curingas):
        assert self._nomes(com_curingas, "00% sint") == ["CAIO 100% SINTETICO"]
        assert self._nomes(com_curingas, "a_l") == ["BIA_LIMA"]
        assert self._nomes(com_curingas, "i\\l") == ["DAVI\\LIMA"]

    @pytest.mark.parametrize("termo", ["__", "%%", "_%", "\\\\"])
    def test_so_curinga_nao_lista_a_escola(self, com_curingas, termo):
        assert self._nomes(com_curingas, termo) == []

    @pytest.mark.parametrize("termo", ["**", "*a*", " * "])
    def test_asterisco_que_o_postgrest_le_como_porcento_nao_conta(self, com_curingas, termo):
        assert "erro" in chamar(com_curingas.cliente(), "buscar_aluno_por_nome", nome=termo)

    def test_o_mcp_serve_a_mesma_busca(self, com_curingas):
        from app.chat.tools import lookup
        from app.mcp.catalogo import Catalogo

        ferramenta = Catalogo(REGISTRO, teto_de_linhas=50).obter("buscar_aluno_por_nome")
        assert ferramenta is not None and ferramenta.handler is lookup.buscar_aluno_por_nome
        assert ferramenta.handler(com_curingas.cliente(), nome="__") == {"total": 0, "alunos": []}


class TestTetos:
    @pytest.mark.parametrize(("pedido", "esperado"), [(1000, 20), (-5, 1), (0, 1), (3, 3)])
    def test_buscar_aluno_por_nome(self, escola, pedido, esperado):
        cliente = escola.cliente()
        chamar(cliente, "buscar_aluno_por_nome", nome="sint", limite=pedido)
        assert cliente.em("aluno")[-1]._limit == esperado

    def test_notas_simulado(self, escola):
        _com_alunos_extras(escola, 120)
        r = chamar(escola.cliente(), "notas_simulado", simulado_id=S["MAT_F2"], limite=1000)
        assert len(r["notas"]) == 100 and r["total"] == 125 and r["truncado"] is True
        assert len(chamar(escola.cliente(), "notas_simulado", simulado_id=S["MAT_F2"], limite=-1)["notas"]) == 1

    @pytest.mark.parametrize("tool", ["alunos_em_risco", "alunos_destaque"])
    def test_alunos_por_zona(self, escola, tool):
        _com_alunos_extras(escola, 60, zona="risco" if tool == "alunos_em_risco" else "top")
        r = chamar(escola.cliente(), tool, limite=1000)
        assert len(r["alunos"]) == 50 and r["total"] > 50 and r["truncado"] is True
        assert len(chamar(escola.cliente(), tool, limite=0)["alunos"]) == 1

    def test_listar_alunos_limita_a_saida_e_nao_a_leitura(self, escola):
        """O `.limit(500)` do select cortava a leitura: `total` dizia 500 e a
        ordem pela média era só entre os primeiros 500."""
        _com_alunos_extras(escola, 600)
        cliente = escola.cliente()
        r = chamar(cliente, "listar_alunos", limite=1000)
        assert r["total"] == 606 and len(r["alunos"]) == 100
        assert r["alunos"][0]["alunoId"] == B                      # a maior média, que estava no fim
        assert all(c._limit is None for c in cliente.em("classificacao_aluno"))

    def test_alunos_similares(self, escola):
        _com_alunos_extras(escola, 30)
        r = chamar(escola.cliente(), "alunos_similares", aluno_id=A, k=1000)
        assert r["k"] == 20 and len(r["similares"]) == 20

    def test_trajetoria_aluno_tem_piso(self, escola):
        r = chamar(escola.cliente(), "trajetoria_aluno", aluno_id=A, limite=0)
        assert r["total"] == 1                                     # não a lista inteira


class TestBuscarAlunoPorMatricula:
    def test_acha_pela_matricula_e_nao_traz_mais_que_o_cadastro(self, escola):
        r = chamar(escola.cliente(), "buscar_aluno_por_matricula", matricula=" 9000002 ")
        assert r == {"aluno": {"id": B, "nome": NOME[B], "matricula": "9000002", "ativo": True}}

    def test_matricula_numerica_e_convertida_pelo_registro(self, escola):
        assert chamar(escola.cliente(), "buscar_aluno_por_matricula", matricula=9000004)["aluno"]["id"] == D

    @pytest.mark.parametrize("matricula", ["0000000", "  ", "90000"])
    def test_sem_aluno_e_erro(self, escola, matricula):
        assert "erro" in chamar(escola.cliente(), "buscar_aluno_por_matricula", matricula=matricula)


# ─── Banco de questões ───────────────────────────────────────────────────


class TestTopicosDoEdital:
    def test_a_busca_ignora_acento_e_olha_os_assuntos(self, escola):
        optica = chamar(escola.cliente(), "topicos_do_edital", busca="optica")
        assert [(t["materia"], t["codigo"]) for t in optica["topicos"]] == [("Física", "8.1")]
        lentes = chamar(escola.cliente(), "topicos_do_edital", busca="LENTES")
        assert [t["codigo"] for t in lentes["topicos"]] == ["8.1"]

    def test_o_resumo_da_materia_sai_pronto_do_dominio(self, escola):
        r = chamar(escola.cliente(), "topicos_do_edital", materia="Física")
        assert r["materias"] == [{
            "materia": "Física", "totalQuestoes": 6, "semClassificacao": 1, "anos": [2019, 2024],
            "fases": [1, 2], "vestibulares": ["IME", "ITA"],
        }]
        por_codigo = {t["codigo"]: t["totalQuestoes"] for t in r["topicos"]}
        assert por_codigo == {"1.1": 1, "7.2": 3, "8.1": 2}       # a mista conta nos dois
        assert "assuntos" not in r["topicos"][0]

    def test_limite_e_assuntos(self, escola):
        r = chamar(escola.cliente(), "topicos_do_edital", limite=1, incluir_assuntos=True)
        assert r["total"] == 6 and len(r["topicos"]) == 1 and r["truncado"] is True
        assert r["topicos"][0]["assuntos"] == ["Grandezas", "Vetores"]

    def test_materia_sem_acento_e_recusada_pelo_registro(self, escola):
        assert "erro" in chamar(escola.cliente(), "topicos_do_edital", materia="fisica")


class TestBuscarQuestoesDoBanco:
    def test_topico_com_materia(self, escola):
        r = chamar(escola.cliente(), "buscar_questoes_do_banco", materia="Física", topico="7.2")
        assert r["total"] == 3
        assert [q["id"] for q in r["questoes"]] == ["ita_2023_fase2_q03", "ita_2021_fase1_q02", "ita_2019_fase1_q01"]

    def test_topico_sem_materia_e_a_guarda_do_dominio(self, escola):
        r = chamar(escola.cliente(), "buscar_questoes_do_banco", topico="1.1")
        filtro = consultas.FiltrosQuestoes(topico="1.1")
        with pytest.raises(consultas.FiltroInvalido) as exc:
            consultas.validar_filtros(filtro)
        assert r == {"erro": str(exc.value)}

    def test_sem_assunto(self, escola):
        r = chamar(escola.cliente(), "buscar_questoes_do_banco", materia="Física", topico="sem-assunto")
        assert [q["id"] for q in r["questoes"]] == ["ita_2024_fase1_q09"]

    def test_anos_fase_e_busca(self, escola):
        anos = chamar(escola.cliente(), "buscar_questoes_do_banco", materia="Física", anos=[2023, "2023", 2023.0])
        assert {q["id"] for q in anos["questoes"]} == {"ita_2023_fase1_q07", "ita_2023_fase2_q03"}
        fase = chamar(escola.cliente(), "buscar_questoes_do_banco", materia="Física", fase="fase_2")
        assert [q["id"] for q in fase["questoes"]] == ["ita_2023_fase2_q03"]
        busca = chamar(escola.cliente(), "buscar_questoes_do_banco", materia="Química", busca="lançada")
        assert busca["total"] == 2

    @pytest.mark.parametrize("anos", [[3000], ["dois mil"], [True], [2020.5]])
    def test_ano_que_nao_e_ano_e_erro(self, escola, anos):
        assert "erro" in chamar(escola.cliente(), "buscar_questoes_do_banco", materia="Física", anos=anos)

    def test_fase_e_texto_do_vocabulario_da_coordenacao(self, escola):
        assert "erro" in chamar(escola.cliente(), "buscar_questoes_do_banco", fase="2")

    def test_a_pagina_tem_teto(self, escola):
        cliente = escola.cliente()
        chamar(cliente, "buscar_questoes_do_banco", limite=1000)
        assert cliente.em("questao_vestibular")[0]._range == (0, banco_questoes.TETO_DE_QUESTOES - 1)

    def test_nunca_sai_endereco(self, escola):
        lista = chamar(escola.cliente(), "buscar_questoes_do_banco", materia="Física", limite=20)
        aberta = chamar(escola.cliente(), "buscar_questoes_do_banco", questao_id="ita_2023_fase1_q07")
        for r in (lista, aberta):
            texto = _texto(r)
            assert "imagemUrl" not in texto and "resolucaoUrl" not in texto and "http" not in texto

    def test_questao_aberta_vem_inteira(self, escola):
        q = chamar(escola.cliente(), "buscar_questoes_do_banco", questao_id=" ita_2023_fase1_q07 ")["questao"]
        assert q["alternativas"] == {letra: f"opção {letra}" for letra in "ABCDE"}
        assert q["enunciado"].endswith("$$x^2$$") and "enunciadoResumo" not in q
        assert (q["dependeDeImagem"], q["resolucao"], q["colecao"]) == (True, "professor", "recentes")

    def test_resumo_colecao_e_resolucao(self, escola):
        r = chamar(escola.cliente(), "buscar_questoes_do_banco", materia="Física", limite=20)
        por_id = {q["id"]: q for q in r["questoes"]}
        assert por_id["ime_2022_fase1_q05"]["colecao"] == "arquivo"
        assert por_id["ita_2023_fase2_q03"]["resolucao"] == "ia"
        assert por_id["ita_2019_fase1_q01"]["resolucao"] is None
        assert por_id["ita_2019_fase1_q01"]["enunciadoResumo"] == "Uma bola é lançada na questão 1. $$x^2$$"
        assert por_id["ita_2023_fase2_q03"]["topicos"] == [
            {"codigo": "7.2", "nome": "Ondas e Acústica"}, {"codigo": "8.1", "nome": "Óptica Geométrica"},
        ]

    def test_questao_que_nao_existe(self, escola):
        assert "erro" in chamar(escola.cliente(), "buscar_questoes_do_banco", questao_id="ita_1900_fase1_q01")


class TestRecorrenciaNoBanco:
    def test_ordena_por_importancia_e_corta_so_a_saida(self, escola):
        oraculo = estatisticas.recorrencia(escola.cliente(), "Física").model_dump()
        r = chamar(escola.cliente(), "recorrencia_no_banco", materia="Física", limite=2)
        esperado = sorted(oraculo["topicos"], key=lambda t: -t["importancia"])[:2]
        assert [t["codigo"] for t in r["topicos"]] == [t["codigo"] for t in esperado]
        assert [t["importancia"] for t in r["topicos"]] == [round(t["importancia"], 1) for t in esperado]
        assert all(isinstance(t["importanciaRanking"], int) for t in r["topicos"])
        assert (r["nTopicos"], r["totalQuestoes"], r["semClassificacao"]) == (3, 6, 1)
        assert r["anos"] == [2019, 2024] and r["versaoParametro"] is None

    def test_ordenar_por_total(self, escola):
        r = chamar(escola.cliente(), "recorrencia_no_banco", materia="Física", ordenar_por="total")
        assert [t["codigo"] for t in r["topicos"]] == ["7.2", "8.1", "1.1"]

    def test_a_serie_do_topico_cobre_todos_os_anos_com_a_fatia_do_dominio(self, escola):
        oraculo = estatisticas.recorrencia(escola.cliente(), "Física").model_dump()
        r = chamar(escola.cliente(), "recorrencia_no_banco", materia="Física", topico="7.2")
        assert [p["ano"] for p in r["serie"]] == oraculo["anos"] == [2019, 2021, 2022, 2023, 2024]
        assert [p["ocorrencias"] for p in r["serie"]] == [1, 1, 0, 1, 0]
        for p in r["serie"]:
            assert p["pctDaProva"] == round(importancia.fatia_do_ano(p["ocorrencias"], p["questoes"]), 1)
        assert r["topico"]["total"] == 3

    def test_recorte_por_vestibular(self, escola):
        r = chamar(escola.cliente(), "recorrencia_no_banco", materia="Física", vestibular="IME")
        assert r["totalQuestoes"] == 1

    def test_erros(self, escola):
        assert "erro" in chamar(escola.cliente(), "recorrencia_no_banco", materia="Física", topico="9.9")
        assert "falta materia" in chamar(escola.cliente(), "recorrencia_no_banco")["erro"]


# ─── Réguas ──────────────────────────────────────────────────────────────


class TestReguasDeCorte:
    def test_lista_as_embutidas_e_as_criadas(self, escola):
        r = chamar(escola.cliente(), "reguas_de_corte")
        assert r["criadasIndisponiveis"] is False and "aviso" not in r
        slugs = [regua["slug"] for regua in r["reguas"]]
        assert slugs == [*criterios.CRITERIOS, REGUA_CRIADA]
        por_slug = {regua["slug"]: regua for regua in r["reguas"]}
        assert por_slug["tio-leo"]["daCasa"] is True and por_slug["tio-leo"]["embutida"] is True
        assert por_slug[REGUA_CRIADA]["embutida"] is False
        assert por_slug[REGUA_CRIADA]["cortes"] == {"matematica": 7.0, "fisica": 7.0, "quimica": 7.0}
        assert "http" not in _texto(r) and "token=" not in _texto(r)

    def test_detalhe_da_embutida_e_o_descrever_do_dominio(self, escola):
        r = chamar(escola.cliente(), "reguas_de_corte", slug="ita-f1")
        dominio = criterios.descrever_criterio(criterios.CRITERIOS["ita-f1"])
        assert r["cortes"] == dominio["cortes"] and r["eliminatorias"] == dominio["eliminatorias"]
        assert [p["fonte"] for p in r["predicados"]] == [p["fonte"] or None for p in dominio["predicados"]]
        assert r["embutida"] is True and "versoes" not in r

    def test_detalhe_da_criada_tem_as_versoes_com_o_nome_de_quem_fez(self, escola):
        r = chamar(escola.cliente(), "reguas_de_corte", slug=REGUA_CRIADA)
        assert [(v["versao"], v["ativa"], v["criadaPor"]) for v in r["versoes"]] == [
            (2, True, "COORDENADOR OUTRO"), (1, False, "COORDENADORA SINTETICA"),
        ]
        texto = _texto(r)
        assert K1 not in texto and K2 not in texto and "@escola.invalid" not in texto
        assert "http" not in texto and all("[endereço]" in p["fonte"] for p in r["predicados"])

    def test_slug_que_nao_existe(self, escola):
        r = chamar(escola.cliente(), "reguas_de_corte", slug="nao-existe")
        assert "não existe" in r["erro"] and REGUA_CRIADA in r["erro"]

    def test_banco_fora_nao_vira_so_existem_as_cinco(self, escola):
        cliente = escola.cliente(falhar_em={"criterio_classificacao"})
        lista = chamar(cliente, "reguas_de_corte")
        assert lista["criadasIndisponiveis"] is True and lista["total"] == 5 and "aviso" in lista
        criada = chamar(escola.cliente(falhar_em={"criterio_classificacao"}), "reguas_de_corte", slug=REGUA_CRIADA)
        assert "não consegui ler" in criada["erro"]


class TestCortadosPelaRegua:
    def test_os_numeros_saem_do_avaliador_sob_a_regua_escolhida(self, escola):
        r = chamar(escola.cliente(), "cortados_pela_regua", ciclo_id=C2, criterio=REGUA_CRIADA)
        assert "erro" not in r, r
        assert r["criterio"] == {"slug": REGUA_CRIADA, "nome": "Meta 7 em exatas"}
        assert (r["total"], r["cortados"], r["naoCortados"], r["naoAvaliados"]) == (6, 4, 1, 1)
        # Português tem nota baixa, mas a régua não o corta: fica fora da conta.
        assert r["abaixoDoCortePorMateria"] == {"matematica": 4, "fisica": 4, "quimica": 4}
        oraculo = classificacao_ciclo.classificar(
            escola.cliente(), ciclo_id=C2, criterio=criterios_repo.resolver(escola.cliente(), REGUA_CRIADA)
        )
        assert [a["alunoId"] for a in r["alunos"]] == [l["alunoId"] for l in oraculo if not l["aprovado"]]
        assert {a["alunoId"] for a in r["alunos"]} == {A, C, D, E}
        assert all(a["situacao"] == "cortado" and a["motivo"] for a in r["alunos"])

    def test_todos_com_a_situacao_de_cada_um(self, escola):
        r = chamar(escola.cliente(), "cortados_pela_regua", ciclo_id=C2, criterio=REGUA_CRIADA, so_cortados=False)
        situacao = {a["alunoId"]: a["situacao"] for a in r["alunos"]}
        assert (situacao[B], situacao[F], situacao[A]) == ("passa", "nao_avaliado", "cortado")

    def test_o_semaforo_so_conta_e_nao_sai(self, escola):
        texto = _texto(chamar(escola.cliente(), "cortados_pela_regua", ciclo_id=C2, so_cortados=False))
        assert not re.search(r"\b(tom|vermelho|ambar|verde)\b", texto)

    def test_regua_da_casa_por_padrao_e_limite(self, escola):
        r = chamar(escola.cliente(), "cortados_pela_regua", ciclo_id=C2, so_cortados=False, limite=1)
        assert r["criterio"]["slug"] == criterios.CRITERIO_DA_CASA
        assert len(r["alunos"]) == 1 and r["truncado"] is True and r["mostrados"] == 1

    def test_fase_no_vocabulario_da_coordenacao(self, escola, monkeypatch):
        pedidas = []
        original = classificacao_ciclo.classificar
        monkeypatch.setattr(
            classificacao_ciclo, "classificar",
            lambda cliente, **kw: pedidas.append(kw["fase"]) or original(cliente, **kw),
        )
        r = chamar(escola.cliente(), "cortados_pela_regua", ciclo_id=C2, fase="fase_2")
        assert pedidas == [2] and r["fase"] == 2

    def test_erros_legiveis(self, escola):
        inventada = chamar(escola.cliente(), "cortados_pela_regua", ciclo_id=C2, criterio="inventada")
        assert inventada["erro"].startswith("a régua 'inventada' não existe")
        assert REGUA_CRIADA in inventada["erro"]
        assert "não encontrado" in chamar(escola.cliente(), "cortados_pela_regua", ciclo_id=_id(3, 99))["erro"]

    def test_banco_fora_nao_vira_regua_que_nao_existe(self, escola):
        """`resolver` falha aberto: com `criterio_classificacao` fora, a régua
        criada dava o mesmo "não existe" de uma inventada, e o modelo afirmaria
        que ela não existe — enquanto `reguas_de_corte`, no mesmo estado, dizia
        "não consegui ler" (revisão paralela de 25/10). As duas dizem o mesmo."""
        cliente = escola.cliente(falhar_em={"criterio_classificacao"})
        r = chamar(cliente, "cortados_pela_regua", ciclo_id=C2, criterio=REGUA_CRIADA)
        assert "não consegui ler as réguas criadas" in r["erro"] and "não existe" not in r["erro"]
        assert not cliente.em("nota")                      # não classificou com régua nenhuma
        detalhe = chamar(escola.cliente(falhar_em={"criterio_classificacao"}), "reguas_de_corte", slug=REGUA_CRIADA)
        assert r == detalhe

    def test_a_regua_da_casa_nao_depende_das_criadas(self, escola):
        r = chamar(escola.cliente(falhar_em={"criterio_classificacao"}), "cortados_pela_regua", ciclo_id=C2)
        assert "erro" not in r and r["criterio"]["slug"] == criterios.CRITERIO_DA_CASA

    @pytest.mark.parametrize("ciclo_id", ["ciclo 2", "C2", "%"])
    def test_ciclo_id_torto_e_erro_de_argumento_sem_ler(self, escola, ciclo_id):
        """Id torto numa coluna uuid é 22P02 no PostgREST, e o despacho dizia
        "falhou do nosso lado, não repita" — o modelo concluía "indisponível"
        quando quem errou foi o id (revisão paralela de 25/10)."""
        cliente = escola.cliente()
        r = chamar(cliente, "cortados_pela_regua", ciclo_id=ciclo_id)
        assert r == {"erro": "ciclo_id deve ser um UUID; descubra-o com listar_ciclos"}
        assert not cliente.consultas

    def test_ciclo_id_em_caixa_alta_vale(self, escola):
        assert "erro" not in chamar(escola.cliente(), "cortados_pela_regua", ciclo_id=f" {C2.upper()} ")

    def test_tem_prazo_proprio(self):
        assert REGISTRO.obter(COORDENACAO, "cortados_pela_regua").prazo_s == 150.0


# ─── Rotinas ─────────────────────────────────────────────────────────────


class TestEstadoDoSyncCanvas:
    def test_o_atraso_e_a_regra_do_health_ready(self, escola):
        r = chamar(escola.cliente(), "estado_do_sync_canvas")
        assert r["atrasado"] is False and r["haMinutos"] <= 5
        assert r["limiteMinutos"] == estado_do_sync.limite_em_minutos()
        assert r["errosNasUltimas24h"] == 2

    def test_sem_sucesso_recente_esta_atrasado(self, escola):
        for linha in escola.db["canvas_sync_execucao"].values():
            if linha["status"] == "sucesso" and linha["resumo"] and "avisos" in linha["resumo"]:
                linha["status"] = "erro"
        assert chamar(escola.cliente(), "estado_do_sync_canvas")["atrasado"] is True

    def test_as_rodadas_mais_recentes_com_order_e_limit(self, escola):
        cliente = escola.cliente()
        r = chamar(cliente, "estado_do_sync_canvas", limite=1000)
        assert len(r["execucoes"]) == rotinas.TETO_DE_EXECUCOES
        assert r["execucoes"][0]["status"] == "sucesso"
        assert all(c._limit is not None for c in cliente.em("canvas_sync_execucao"))
        assert len(chamar(escola.cliente(), "estado_do_sync_canvas")["execucoes"]) == 5

    def test_erro_e_aviso_saem_limpos(self, escola):
        r = chamar(escola.cliente(), "estado_do_sync_canvas")
        texto = _texto(r)
        assert "http" not in texto and "access_token" not in texto and "abcdefghijklmnop" not in texto
        primeira = r["execucoes"][0]
        assert primeira["nAvisos"] == 4 and len(primeira["avisos"]) == 3
        assert primeira["numeros"] == {"alunos_processados": 900, "notas_gravadas": 12}
        assert r["execucoes"][1]["erro"].startswith("ConnectError")

    def test_escrita_pendente_separada_como_o_retry_a_ve(self, escola):
        escrita = chamar(escola.cliente(), "estado_do_sync_canvas")["escritaNoCanvas"]
        sims = escrita["simulados"]
        assert (sims["tentandoDeNovo"], sims["desistiu"], sims["divergente"]) == (2, 1, 1)
        assert sims["exemplos"][0]["situacao"] == "desistiu"
        assert sims["exemplos"][0]["nome"] == "SAS_DESISTIU"
        assert (escrita["ciclos"]["falhou"], escrita["ciclos"]["divergente"]) == (1, 1)


class TestPendenciasCanvasDoCiclo:
    def test_ciclo_que_nao_existe(self, escola):
        assert "não encontrado" in chamar(escola.cliente(), "pendencias_canvas_do_ciclo", ciclo_id=_id(3, 99))["erro"]

    @pytest.mark.parametrize("ciclo_id", ["ciclo 2", "nao-e-uuid", ""])
    def test_ciclo_id_torto_e_erro_de_argumento_sem_ler(self, escola, ciclo_id):
        """O 22P02 virava "falhou do nosso lado, não repita" (revisão paralela de 25/10)."""
        cliente = escola.cliente()
        r = chamar(cliente, "pendencias_canvas_do_ciclo", ciclo_id=ciclo_id)
        assert r == {"erro": "ciclo_id deve ser um UUID; descubra-o com listar_ciclos"}
        assert not cliente.consultas

    def test_grupo_e_simulados_com_erro_limpo(self, escola):
        r = chamar(escola.cliente(), "pendencias_canvas_do_ciclo", ciclo_id=C3)
        assert r["grupo"]["pendente"] is True and r["grupo"]["estado"] == "falhou"
        assert "http" not in _texto(r) and "access_token" not in _texto(r)
        assert {s["nome"] for s in r["simulados"]} == {"SAS_FALHOU", "SAS_DESISTIU", "SAS_DIVERGENTE"}
        assert r["totalNotas"] == 0 and r["nadaPendente"] is False

    def test_notas_divergentes_com_o_aluno_identificado(self, escola):
        # B tem 8 no FIS_F2 dos dois lados: editada, mas igual ao Canvas.
        no_sas = {(A, S["FIS_F2"]): 7, (B, S["FIS_F2"]): 8, (A, S["MAT_F2"]): 9, (B, S["MAT_F2"]): 9}
        for linha in escola.db["nota"].values():
            chave = (linha["aluno_id"], linha["simulado_id"])
            if chave in no_sas:
                linha["pontuacao_sas"] = no_sas[chave]
        r = chamar(escola.cliente(), "pendencias_canvas_do_ciclo", ciclo_id=C2, limite=2)
        assert r["totalNotas"] == 3 and len(r["notas"]) == 2
        for n in r["notas"]:
            assert n["alunoNome"] == NOME[n["alunoId"]] and n["noSas"] != n["noCanvas"]
        assert r["grupo"]["pendente"] is False

    def test_alem_do_teto_do_lote(self, escola):
        _com_alunos_extras(escola, 85)
        extras = {_id(30, i) for i in range(85)}
        for linha in escola.db["nota"].values():
            if linha["aluno_id"] in extras:
                linha["pontuacao_sas"] = 9
        r = chamar(escola.cliente(), "pendencias_canvas_do_ciclo", ciclo_id=C2, limite=1000)
        assert r["totalNotas"] == 85 and len(r["notas"]) == rotinas.TETO_DE_NOTAS_PENDENTES


class TestEstadoDasGravacoes:
    def test_so_os_problemas_e_por_que(self, escola):
        r = chamar(escola.cliente(), "estado_das_gravacoes")
        motivos = {a["id"]: a["motivos"] for a in r["aulas"]}
        assert motivos == {
            _id(12, 2): ["desistiu"], _id(12, 3): ["erro"], _id(12, 4): ["sem_confirmacao"],
            _id(12, 5): ["parada"], _id(12, 7): ["canvas_ambiguo"], _id(12, 8): ["fora_de_modulo"],
            _id(12, 10): ["parada"],
        }
        assert r["comProblema"] == 7 and r["totalAulas"] == 10

    def test_nunca_sai_link_de_video_de_menores(self, escola):
        texto = _texto(chamar(escola.cliente(), "estado_das_gravacoes", so_problemas=False, limite=30))
        for proibido in ("VIDEOSECRETO", "youtu", "instructure.com/courses", "youtubeTitulo", "canvasUrl",
                         "googleapis", "ya29", "bucket-com-menores", "aulas/"):
            assert proibido not in texto

    def test_o_video_nao_sai_nem_dentro_do_erro(self, escola):
        """O `Failing row contains (…)` do Postgres despeja a linha da aula, com
        o id do vídeo (que sozinho abre o não listado) e o lugar dele no S3; o
        `texto_seguro` só tira URL e credencial (revisão paralela de 25/10)."""
        aula = next(a for a in chamar(escola.cliente(), "estado_das_gravacoes")["aulas"]
                    if a["status"] == "publicado_sem_confirmacao")
        assert aula["erro"] == (
            "publicado mas o id não persistiu: APIError: {'code': '23514', 'details': "
            "'Failing row contains (…)"
        )

    @pytest.mark.parametrize("titulo", ["Aula 3 :)", "Aula (parte (1))", "Aula 3 (revisão"])
    def test_a_linha_despejada_sai_inteira_com_qualquer_parentese(self, escola, titulo):
        """O Postgres escreve os valores sem aspas: um título com parêntese
        solto ou aninhado enganava o pareamento de um nível, e o resto da linha
        saía — o S3 sempre, e o vídeo quando o id não ficou gravado, que é
        quando o `replace` do id não ajuda (correção da revisão paralela, 26/10)."""
        linha = escola.db["aula_gravacao"][_id(12, 4)]
        linha["youtube_video_id"] = None
        linha["erro_detalhe"] = (
            "publicado mas o id não persistiu: APIError: {'code': '23514', 'details': "
            f"'Failing row contains ({_id(12, 4)}, 581, conf-4, {titulo}, VIDEOSECRETO4, "
            "bucket-com-menores, aulas/4.mp4).', 'hint': None, 'message': 'violates check constraint'}"
        )
        aula = next(a for a in chamar(escola.cliente(), "estado_das_gravacoes")["aulas"] if a["id"] == _id(12, 4))
        assert aula["erro"].endswith("'details': 'Failing row contains (…)")
        for proibido in ("VIDEOSECRETO", "bucket-com-menores", "aulas/", "conf-4"):
            assert proibido not in aula["erro"]

    def test_o_id_do_video_sai_mesmo_fora_da_linha_despejada(self, escola):
        linha = escola.db["aula_gravacao"][_id(12, 4)]
        linha["erro_detalhe"] = "conferir no canal: VIDEOSECRETO4 subiu às 14h"
        aula = next(a for a in chamar(escola.cliente(), "estado_das_gravacoes")["aulas"] if a["id"] == _id(12, 4))
        assert aula["erro"] == "conferir no canal: [vídeo] subiu às 14h"

    def test_o_erro_e_limpo_antes_de_cortado(self, escola):
        """A tela recebe o erro cortado em 300; limpar DEPOIS desse corte deixava
        meia credencial, curta demais para o padrão, sair (revisão paralela de
        25/10). A tool lê o erro inteiro e o `texto_seguro` limpa, depois corta."""
        bruto = "Erro: https://" + "a" * 270 + " Bearer " + "Z" * 30
        assert len(bruto.split("Bearer ")[0]) < 300 < len(bruto)   # a credencial atravessa a posição 300
        escola.db["aula_gravacao"][_id(12, 2)]["erro_detalhe"] = bruto
        aula = next(a for a in chamar(escola.cliente(), "estado_das_gravacoes")["aulas"] if a["id"] == _id(12, 2))
        assert aula["erro"] == "Erro: [endereço] [credencial]"
        # A tela continua recebendo os 300 primeiros, sem limpeza: é dela.
        tela = next(a for a in gravacoes.painel(escola.cliente())["aulas"] if a["id"] == _id(12, 2))
        assert tela["erroDetalhe"] == bruto[:300]

    def test_contagens_na_ordem_da_tela(self, escola):
        r = chamar(escola.cliente(), "estado_das_gravacoes")
        assert list(r["porSituacao"]) == list(gravacoes.SITUACOES)
        assert r["porSituacao"] == {"aguardando": 1, "na_fila": 0, "processando": 3, "publicado": 4, "erro": 2}

    def test_curso_e_limite(self, escola):
        quimica = chamar(escola.cliente(), "estado_das_gravacoes", curso_id="600", so_problemas=False)
        assert [a["curso"] for a in quimica["aulas"]] == ["Química 3º ITA"]
        assert "erro" in chamar(escola.cliente(), "estado_das_gravacoes", curso_id="999")
        tres = chamar(escola.cliente(), "estado_das_gravacoes", so_problemas=False, limite=3)
        assert len(tres["aulas"]) == 3 and tres["truncado"] is True


class TestLembretesAgendados:
    @pytest.fixture
    def ligado(self, monkeypatch):
        monkeypatch.setattr(rotinas, "get_settings", lambda: types.SimpleNamespace(
            lembrete_aluno_ativo=True, lembrete_aluno_hora="18:00", email_teto_diario=150,
        ))
        monkeypatch.setattr(rotinas.email_ses, "email_configurado", lambda: True)

    def test_a_janela_e_os_horarios_do_motor(self, escola, ligado):
        r = chamar(escola.cliente(), "lembretes_agendados", dias=7)
        assert [e["eventoId"] for e in r["eventos"]] == [EV1, EV3]
        ev1, ev3 = r["eventos"]
        amanha = escola.hoje_brt + timedelta(days=1)
        assert ev1["simuladoId"] == S["SAS_PROX"] and ev3["cancelado"] is True
        assert ev1["lembretes"] == [
            {"para": "coordenador", "diasAntes": 1, "enviarEm": motor.calcular_enviar_em(
                amanha, time(7), 1).isoformat(), "cancelado": False},
            {"para": "alunos", "enviarEm": aluno_simulado.momento_envio(amanha, time(18)).isoformat(),
             "cancelado": False},
        ]

    def test_so_contagem_dos_disparos(self, escola, ligado):
        cliente = escola.cliente()
        r = chamar(cliente, "lembretes_agendados")
        assert r["alunosPorDia"] == [{
            "dia": (escola.hoje_brt + timedelta(days=1)).isoformat(),
            "enviarEm": aluno_simulado.momento_envio(escola.hoje_brt + timedelta(days=1), time(18)).isoformat(),
            "disparosMontados": 2, "enviados": 1,
        }]
        assert r["fila"] == {
            "agendadosNaJanela": 2, "falhasNasUltimas24h": {"vaoTentarDeNovo": 1, "desistiram": 1},
            "enviandoParados": 1,
        }
        assert r["configuracao"] == {
            "emailConfigurado": True, "lembretesDeAlunoLigados": True, "horaLembreteAluno": "18:00",
            "tetoDiario": 150, "enviadosNasUltimas24h": 1,
        }
        for consulta in cliente.em("disparo"):
            assert consulta.colunas.strip() == "id" and consulta.contagem == "exact" and consulta._limit == 1
        texto = _texto(r)
        assert "@" not in texto and NOME[A] not in texto and "amazonaws" not in texto

    def test_um_simulado_so(self, escola, ligado):
        r = chamar(escola.cliente(), "lembretes_agendados", simulado_id=S["SAS_PROX"])
        assert [e["eventoId"] for e in r["eventos"]] == [EV1]
        sem = chamar(escola.cliente(), "lembretes_agendados", simulado_id=S["MAT_F2"])
        assert sem["eventos"] == [] and "aviso" in sem
        assert "não encontrado" in chamar(escola.cliente(), "lembretes_agendados", simulado_id=_id(2, 99))["erro"]

    @pytest.mark.parametrize("simulado_id", ["P22", "nao-e-uuid"])
    def test_simulado_id_torto_e_erro_de_argumento_sem_ler(self, escola, ligado, simulado_id):
        """O 22P02 virava "falhou do nosso lado, não repita" (revisão paralela de 25/10)."""
        cliente = escola.cliente()
        r = chamar(cliente, "lembretes_agendados", simulado_id=simulado_id)
        assert r == {"erro": (
            "simulado_id deve ser um UUID; chame lembretes_agendados sem ele e use o simuladoId da resposta"
        )}
        assert not cliente.consultas

    def test_dias_tem_teto_e_piso(self, escola, ligado):
        assert chamar(escola.cliente(), "lembretes_agendados", dias=1000)["janelaDias"] == rotinas.TETO_DE_DIAS
        assert chamar(escola.cliente(), "lembretes_agendados", dias=-3)["janelaDias"] == 0


# ─── Trilha de auditoria ─────────────────────────────────────────────────


class TestHistoricoDeAlteracoes:
    def test_so_os_canais_da_trilha(self, escola):
        r = chamar(escola.cliente(), "historico_de_alteracoes")
        assert [e["acao"] for e in r["eventos"]] == [
            "ciclo_criado", "criterio_criado", "enviado_ao_canvas", "simulado_editado",
            "nota_editada", "nota_editada",
        ]
        assert {e["canal"] for e in r["eventos"]} <= set(trilha.CANAIS_DA_TRILHA)

    def test_nada_de_ip_request_id_ator_cru_nem_chave_fora_da_lista(self, escola):
        texto = _texto(chamar(escola.cliente(), "historico_de_alteracoes"))
        for proibido in ("10.0.0.1", "req-", "k1@escola.invalid", "novo@escola.invalid", "FULANO",
                         "NAO-PODE-SAIR", "segredo_extra", "access_token", "http", K1, K2, "lote"):
            assert proibido not in texto

    def test_quem_detalhe_e_recurso(self, escola):
        eventos = chamar(escola.cliente(), "historico_de_alteracoes", canal="nota")["eventos"]
        nota = eventos[-1]
        assert nota["quem"] == "COORDENADORA SINTETICA"
        assert nota["recurso"] == {"tipo": "nota", "id": f"{A}/{S['FIS_F2']}"}
        assert nota["detalhe"]["alunoId"] == A and nota["detalhe"]["alunoNome"] == NOME[A]
        assert (nota["detalhe"]["valor_antes"], nota["detalhe"]["valor_depois"]) == (4.0, 5.5)
        assert "[endereço]" in nota["detalhe"]["canvas_erro"]
        sistema = chamar(escola.cliente(), "historico_de_alteracoes", canal="ciclo")["eventos"][0]
        assert sistema["quem"] == "sistema"

    @pytest.mark.parametrize(("filtro", "esperadas"), [
        ({"aluno_id": A}, [7, 4]),
        ({"simulado_id": S["FIS_F2"]}, [7, 6, 4]),
        ({"aluno_id": A, "simulado_id": S["FIS_F2"]}, [7, 4]),
        ({"ciclo_id": C2}, [11]),
        ({"regua_slug": REGUA_CRIADA}, [8]),
        ({"ator_nome": "coordenadora"}, [6, 4]),
        ({"acao": "nota_editada"}, [5, 4]),
    ])
    def test_filtros_montados_de_id_validado(self, escola, filtro, esperadas):
        cliente = escola.cliente()
        r = chamar(cliente, "historico_de_alteracoes", **filtro)
        ids = [linha["id"] for c in cliente.em("evento_auditoria") for linha in c.execute().data]
        assert ids == esperadas, r

    def test_periodo_no_calendario_da_escola_e_em_z(self, escola):
        cliente = escola.cliente()
        desde = (escola.hoje_brt - timedelta(days=1)).isoformat()
        recentes = chamar(cliente, "historico_de_alteracoes", desde=desde)
        assert {e["acao"] for e in recentes["eventos"]} == {
            "ciclo_criado", "criterio_criado", "enviado_ao_canvas", "simulado_editado",
        }
        ate = (escola.hoje_brt - timedelta(days=5)).isoformat()
        antigos = chamar(escola.cliente(), "historico_de_alteracoes", ate=ate)
        assert [e["acao"] for e in antigos["eventos"]] == ["nota_editada", "nota_editada"]
        for consulta in cliente.em("evento_auditoria"):
            for tipo, _, valor in consulta.filtros:
                if tipo in ("gte", "lte"):
                    assert valor.endswith("Z") and "+" not in valor

    @pytest.mark.parametrize("args", [
        {"aluno_id": "abc"}, {"simulado_id": "%"}, {"regua_slug": "meta%"}, {"desde": "ontem"},
        {"aluno_id": A, "ciclo_id": C2}, {"ator_nome": "%%"},
    ])
    def test_entrada_torta_e_erro_sem_ler(self, escola, args):
        cliente = escola.cliente()
        assert "erro" in chamar(cliente, "historico_de_alteracoes", **args)
        assert not cliente.em("evento_auditoria")

    def test_canal_de_acesso_nem_e_opcao(self, escola):
        assert "erro" in chamar(escola.cliente(), "historico_de_alteracoes", canal="acesso")

    def test_ninguem_com_esse_nome(self, escola):
        r = chamar(escola.cliente(), "historico_de_alteracoes", ator_nome="ninguém")
        assert r["eventos"] == [] and "aviso" in r

    def test_limite(self, escola):
        cliente = escola.cliente()
        chamar(cliente, "historico_de_alteracoes", limite=1000)
        assert cliente.em("evento_auditoria")[0]._limit == trilha.TETO_DE_EVENTOS


# ─── O que vale para todas as tools novas ────────────────────────────────

NOVAS = {
    "buscar_aluno_por_matricula": {"matricula": "9000001"},
    "topicos_do_edital": {},
    "buscar_questoes_do_banco": {"materia": "Física"},
    "recorrencia_no_banco": {"materia": "Física"},
    "reguas_de_corte": {"slug": REGUA_CRIADA},
    "cortados_pela_regua": {"ciclo_id": C2},
    "estado_do_sync_canvas": {},
    "pendencias_canvas_do_ciclo": {"ciclo_id": C3},
    "estado_das_gravacoes": {"so_problemas": False},
    "lembretes_agendados": {},
    "historico_de_alteracoes": {"desde": "2026-01-01"},
}


class TestTodasAsNovas:
    def test_a_lista_e_a_do_docs_42(self):
        coordenacao = {f.nome for f in REGISTRO.catalogo("coordenacao")}
        assert set(NOVAS) <= coordenacao

    @pytest.mark.parametrize("nome", sorted(NOVAS))
    def test_so_leem_e_respondem(self, escola, nome):
        cliente = escola.cliente()
        r = chamar(cliente, nome, **NOVAS[nome])
        assert "erro" not in r, r
        assert cliente.escritas == []

    @pytest.mark.parametrize("nome", sorted(NOVAS))
    def test_timestamptz_em_filtro_vai_em_z(self, escola, nome):
        cliente = escola.cliente()
        chamar(cliente, nome, **NOVAS[nome])
        for consulta in cliente.consultas:
            for tipo, _, valor in consulta.filtros:
                if tipo in ("lt", "lte", "gt", "gte") and isinstance(valor, str) and _ISO.match(valor):
                    assert valor.endswith("Z") and "+" not in valor, (consulta.tabela, valor)

    @pytest.mark.parametrize("nome", sorted(NOVAS))
    def test_descricao_nos_quatro_blocos(self, nome):
        descricao = REGISTRO.obter(COORDENACAO, nome).descricao
        posicoes = [descricao.find(b) for b in ("Quando usar:", "Antes de chamar, confirme:", "Definições:", "Exemplo:")]
        assert -1 not in posicoes and posicoes == sorted(posicoes), nome


# ─── O fake confere o schema das migrations ──────────────────────────────


class TestOFakeConfereOEsquema:
    def test_o_leitor_sabe_que_fase_virou_tipo(self):
        simulado = esquema().colunas("simulado")
        assert "fase" not in simulado and simulado["tipo"] == "text"                  # 0003
        assert simulado["nota_confiavel"] == "boolean"                                  # 0043
        assert simulado["id"] == "uuid" and esquema().colunas("evento_auditoria")["canal"] == "text"
        # View existe, mas as colunas dela não são lidas — e o fake não inventa.
        assert "v_nota_dimensoes" in esquema().views and esquema().colunas("v_nota_dimensoes") is None

    @pytest.mark.parametrize(("monta", "codigo"), [
        (lambda c: c.table("simulado").select("id, fase"), "42703"),
        (lambda c: c.table("nota").select("simulado:simulado_id(fase)"), "42703"),
        (lambda c: c.table("simulado").select("id").eq("fase", "1a"), "42703"),
        (lambda c: c.table("simulado").select("id").order("fase"), "42703"),
        (lambda c: c.table("evento_auditoria").select("id").or_('fase.like."x%"'), "42703"),
        (lambda c: c.table("simulado").select("id").eq("ciclo_id", "ciclo 2"), "22P02"),
        (lambda c: c.table("simulado").select("id").in_("id", [S["MAT_F2"], "P22"]), "22P02"),
        (lambda c: c.table("tabela_que_nao_existe").select("id"), "PGRST205"),
        (lambda c: c.table("nota").select("prova(nome)"), "PGRST200"),
    ])
    def test_recusa_o_que_o_postgrest_recusaria(self, escola, monta, codigo):
        with pytest.raises(APIError) as exc:
            monta(escola.cliente()).execute()
        assert exc.value.code == codigo

    def test_aceita_o_que_existe_inclusive_no_embed(self, escola):
        linhas = (
            escola.cliente().table("nota")
            .select("pontuacao, simulado:simulado_id(tipo, materia:materia_id(nome))")
            .eq("simulado_id", S["MAT_F2"]).eq("aluno_id", A).execute().data
        )
        assert linhas == [{"pontuacao": 3, "simulado": {"tipo": "fase_2", "materia": {"nome": "Matemática"}}}]

    def test_a_escola_sintetica_so_tem_coluna_do_esquema(self, escola):
        """Coluna inventada na semente engana do mesmo jeito que a pedida pela
        tool: o `fase=None` dos simulados daqui era isso."""
        for tabela, linhas in escola.db.items():
            colunas = esquema().colunas(tabela)
            assert colunas is not None, tabela
            for linha in linhas.values():
                # Filho semeado junto da linha (`predicado_criterio`) é embed, não coluna.
                fora = {c for c in linha if c not in colunas and not esquema().existe(c)}
                assert not fora, (tabela, fora)


#: Uma chamada que devolve dado, para CADA tool da coordenação. Com o fake
#: conferindo o schema, é aqui que reprova a tool que pede coluna que não
#: existe — inclusive as que nenhum outro teste chama. Tool nova entra aqui: o
#: teste do catálogo reprova se faltar.
EXEMPLOS: dict[str, dict[str, Any]] = {
    **NOVAS,
    "buscar_aluno_por_nome": {"nome": "sint"},
    "obter_aluno": {"aluno_id": A},
    "listar_ciclos": {},
    "listar_simulados": {},
    "obter_simulado": {"simulado_id": S["MAT_F2"]},
    "listar_materias": {},
    "estatisticas_ciclo": {"ciclo_id": C2},
    "trajetoria_aluno": {"aluno_id": A},
    "histograma_simulado": {"simulado_id": S["MAT_F2"]},
    "notas_simulado": {"simulado_id": S["MAT_F2"]},
    "comparar_ciclos": {"ciclo_id_a": C2, "ciclo_id_b": C1},
    "comparar_alunos": {"aluno_ids": [A, B, C]},
    "comparar_simulados": {"simulado_ids": [S["MAT_F2"], S["FIS_F2"]]},
    "alunos_similares": {"aluno_id": A},
    "alunos_em_risco": {},
    "alunos_destaque": {},
    "tendencia_aluno": {"aluno_id": A},
    "materias_problematicas": {"ciclo_id": C2},
    "relatorio_aluno": {"aluno_id": A},
    "historico_aluno": {"aluno_id": A},
    "relatorio_ciclo": {"ciclo_id": C2},
    "gerar_grafico": {"tipo": "linha_temporal", "fonte": "aluno", "fonte_id": A},
    "exportar_csv": {"fonte": "notas_simulado", "fonte_id": S["MAT_F2"]},
    "listar_alertas": {},
    "insights_do_ciclo": {"ciclo_id": C2},
    "listar_alunos": {},
    "listar_sedes": {},
    "listar_turmas": {},
    "questoes_do_simulado": {"simulado_id": S["FIS_F2"]},
    "navegar_para": {"tipo": "aluno", "id": A},
    "roteiro_da_coordenacao": {"nome": "diagnostico_do_ciclo"},
    # A cantina (decisão de 30/10): aqui sem cardápio nenhum, o caminho do vazio.
    # O caminho cheio está em test_chat_tools_cantina.py.
    "cantinas_e_regras": {},
    "calendario_da_cantina": {},
    "cardapio_da_cantina": {},
    "pedidos_da_refeicao": {"refeicao": "almoco"},
    "custos_da_cantina": {},
    "direitos_a_refeicao": {},
    "restricoes_alimentares": {},
}


class TestTodoOCatalogo:
    def test_toda_tool_da_coordenacao_tem_exemplo(self):
        assert set(EXEMPLOS) == {f.nome for f in REGISTRO.catalogo("coordenacao")}

    @pytest.mark.parametrize("nome", sorted(EXEMPLOS))
    def test_pede_ao_banco_so_o_que_existe(self, escola, nome):
        r = chamar(escola.cliente(), nome, **EXEMPLOS[nome])
        assert "erro" not in r, r


# ─── As tools leem o domínio, não a rota ─────────────────────────────────

_API = Path(__file__).resolve().parents[1]
_MODULOS_DAS_TOOLS = sorted((_API / "app" / "chat" / "tools").glob("*.py"))
#: O router do agendador e o que ele puxa: vídeo de aula com menores.
_PIPELINE_DE_VIDEO = frozenset(
    f"app.gravacoes_aula.{m}"
    for m in ("rotas", "armazenamento_s3", "canvas_publicacao", "compositor", "downloader", "publicador_youtube")
)


class TestAcoplamento:
    """Até 25/10, `rotinas.py` lia as regras da rodada de gravações como nomes
    privados de `gravacoes_aula/rotas.py` — o router do agendador, que puxa S3,
    YouTube, ffmpeg e o downloader —, e `trilha.py` lia `despachante._filtro_ts`
    e `criterios_repo._RE_SLUG` (revisão paralela de 25/10). O que a tool usa
    de outro módulo é público e mora no domínio."""

    def test_as_tools_nao_puxam_rota_nem_o_pipeline_de_video(self):
        # Processo novo: nesta suíte, outro teste já pode ter importado as rotas.
        codigo = "import sys, app.chat.tools; print(sorted(m for m in sys.modules if m.startswith('app.')))"
        saida = subprocess.run(  # noqa: S603 — argv fixo: o próprio interpretador e código constante
            [sys.executable, "-c", codigo], cwd=_API, env={**os.environ, "APP_ENV": "dev"},
            capture_output=True, text=True, check=True, timeout=120,
        )
        importados = ast.literal_eval(saida.stdout.strip().splitlines()[-1])
        assert "app.gravacoes_aula.regras_da_rodada" in importados        # a prova de que leu o processo certo
        proibidos = [m for m in importados if m.startswith(("app.routes", "app.main")) or m in _PIPELINE_DE_VIDEO]
        assert not proibidos, proibidos

    @pytest.mark.parametrize("arquivo", _MODULOS_DAS_TOOLS, ids=lambda p: p.name)
    def test_nenhum_nome_privado_de_outro_modulo(self, arquivo):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        importados: set[str] = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.ImportFrom):
                importados |= {n.asname or n.name for n in no.names}
            elif isinstance(no, ast.Import):
                importados |= {(n.asname or n.name).split(".")[0] for n in no.names}
        privados = sorted({
            f"{no.value.id}.{no.attr}"
            for no in ast.walk(arvore)
            if isinstance(no, ast.Attribute) and isinstance(no.value, ast.Name)
            and no.value.id in importados and no.attr.startswith("_") and not no.attr.startswith("__")
        })
        assert not privados, privados
