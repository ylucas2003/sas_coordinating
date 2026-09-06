"""Endpoints de alunos.

Cada aluno tem matrícula ativa em uma turma (matricula_turma.ativo_ate IS NULL).
Perfil/tendência/zona/media_recente vêm de `classificacao_aluno`, populada
pelo stats engine ao fim de cada upload. Sparkline vem das últimas N notas
em ordem cronológica.

Desde a fase 4 do docs/39 o aluno sai daqui com mais duas coisas que a lista de
varredura precisa e não tinha: as **três médias** (do ano, do primeiro ciclo e
do último) abertas nas matérias com taxonomia de edital, e os **direitos de
refeição**. As duas viajam junto do aluno de propósito — derivar as médias no
front custaria baixar as notas dos 900 a cada carregamento, e o front não pode
recalcular o que o servidor já sabe.

⚠️ **A restrição alimentar NÃO entra aqui**, e isso é decisão, não esquecimento
(docs/38 §2.6): é dado de saúde de menor, a categoria mais sensível da LGPD, e
mora na tela de direitos da cantina, sob clique. Uma coluna a mais na lista de
900 seria exatamente o vazamento que aquela decisão evitou.
"""

from __future__ import annotations

import base64
import math
import statistics as st
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .. import storage
from ..auditoria import registrar as auditar
from ..auth import get_current_coordenador
from ..banco.missao import hoje_na_escola
from ..schemas.domain import Aluno
from ..stats import classificacao as _classif
from ..stats.utils import (
    como_float,
    filtro_nota_valida,
    nota_real,
    simulado_entra_no_agregado,
)
from ..supabase_client import get_supabase

router = APIRouter(
    prefix="/alunos",
    tags=["alunos"],
    dependencies=[Depends(get_current_coordenador)],
)


# ─── Helpers de mapeamento ────────────────────────────────────────────────


def _mapa_turma_para_sede(cliente) -> dict[str, str]:
    resp = cliente.table("turma").select("id, sede_id").execute()
    return {linha["id"]: linha["sede_id"] for linha in (resp.data or [])}


def _mapa_aluno_para_turma_ativa(cliente) -> dict[str, str]:
    resp = (
        cliente.table("matricula_turma")
        .select("aluno_id, turma_id, ativo_desde, ativo_ate")
        .is_("ativo_ate", "null")
        .execute()
    )
    mapa: dict[str, tuple[str, str]] = {}
    for linha in resp.data or []:
        aluno_id = linha["aluno_id"]
        ativo_desde = linha.get("ativo_desde") or ""
        previo = mapa.get(aluno_id)
        if previo is None or ativo_desde > previo[1]:
            mapa[aluno_id] = (linha["turma_id"], ativo_desde)
    return {aluno_id: t[0] for aluno_id, t in mapa.items()}


def _vestibulares_por_aluno(cliente) -> dict[str, list[str]]:
    resp = cliente.table("vestibular_alvo_aluno").select("aluno_id, vestibular").execute()
    mapa: dict[str, list[str]] = defaultdict(list)
    for linha in resp.data or []:
        mapa[linha["aluno_id"]].append(linha["vestibular"])
    return mapa


def _passar_recorte(aluno: Aluno, recorte: str | None) -> bool:
    if not recorte:
        return True
    if recorte == "em-risco":
        return aluno.zona == "risco"
    if recorte == "em-ascensao":
        return aluno.tendencia == "subindo"
    if recorte == "perfil-irregular":
        return aluno.perfil == "misterio"
    if recorte == "zona-corte":
        return aluno.zona == "cinzenta"
    return True


# ─── As três médias e os direitos (docs/39 · fase 4) ─────────────────────

#: As três matérias que o detalhamento abre — e só elas (docs/19 §4.1). São as
#: que têm taxonomia de edital: uma coluna de Português diria um número sem
#: dizer onde estudar, que é a pergunta que justifica abrir o grupo. As outras
#: continuam dentro de `geral`; o que elas não ganham é coluna própria.
MATERIAS_DO_DETALHAMENTO = ("matematica", "fisica", "quimica")

#: As duas refeições. Mesmo conjunto do CHECK de `direito_refeicao_aluno`
#: (migration 0049) — fechado por Literal para um terceiro valor quebrar no
#: build do front, e não numa célula em branco na tela.
Refeicao = Literal["almoco", "janta"]

_TAMANHO_PAGINA = 1000


class MediaDoGrupo(BaseModel):
    """Uma média e as três matérias em que ela abre.

    **Todo campo é `None` quando não há nota — nunca 0,0.** Zero é uma nota que
    alguém tirou; a célula que imprime 0,0 para quem não fez prova nenhuma
    manda o coordenador procurar um aluno que não existe. É o caso de chegada
    de todo aluno novo, e o formato tem de sobreviver a ele.
    """

    #: Como a coluna se chama NESTA carga: "2026", "1º Ciclo · ITA". Viaja
    #: junto do número, e não numa rota à parte, porque quem escolheu o ciclo
    #: foi o servidor — rótulo e número em requisições separadas divergem no
    #: primeiro ciclo novo, e a tela afirmaria um ciclo que o número não é.
    referencia: str | None = None
    geral: float | None = None
    matematica: float | None = None
    fisica: float | None = None
    quimica: float | None = None


class MediasDoAluno(BaseModel):
    """Os três grupos da lista de varredura, na ordem em que ela os lê."""

    ano: MediaDoGrupo = Field(default_factory=MediaDoGrupo)
    primeiroCiclo: MediaDoGrupo = Field(default_factory=MediaDoGrupo)
    ultimoCiclo: MediaDoGrupo = Field(default_factory=MediaDoGrupo)


class AlunoDaCoordenacao(Aluno):
    """O aluno como a COORDENAÇÃO o lê: com as médias e os direitos.

    Subclasse, e não campo novo em `schemas/domain.py`, porque `Aluno` é o
    contrato compartilhado — o chat, os lembretes e a área do aluno o
    constroem sem ter estes dois dados, e um campo obrigatório lá quebraria
    todos eles por causa de uma coluna de tabela.
    """

    medias: MediasDoAluno = Field(default_factory=MediasDoAluno)
    #: Almoço e janta, nada além. A restrição alimentar fica na cantina — ver
    #: o aviso no topo do módulo.
    direitos: list[Refeicao] = Field(default_factory=list)


@dataclass(frozen=True)
class ReferenciaDeMedias:
    """A que ano e a que dois ciclos as três colunas respondem.

    Escolha do servidor, calculada uma vez por requisição e usada tanto para
    filtrar as notas quanto para escrever o rótulo — as duas coisas saindo da
    MESMA estrutura é o que impede a coluna de dizer "Ciclo 1" enquanto soma o
    Ciclo 2.
    """

    ciclos_do_ano: frozenset[str]
    ciclo_primeiro: str | None
    ciclo_ultimo: str | None
    rotulo_ano: str | None
    rotulo_primeiro: str | None
    rotulo_ultimo: str | None


REFERENCIA_VAZIA = ReferenciaDeMedias(frozenset(), None, None, None, None, None)


def _rotulo_de_ciclo(ciclo: dict) -> str:
    """"1º Ciclo · ITA" — o nome do ciclo e, quando existe, o edital dele.

    O vestibular entra porque a lista mistura ciclos de ITA e de IME: dois
    ciclos com o mesmo número e editais diferentes são colunas diferentes, e
    sem o sufixo o cabeçalho não distinguiria um do outro.
    """
    nome = (ciclo.get("nome") or "").strip() or f"Ciclo {ciclo.get('ordem')}"
    alvo = ciclo.get("vestibular_alvo")
    return f"{nome} · {alvo}" if alvo else nome


def _mapa_simulados(cliente) -> dict[str, dict]:
    """{simulado_id: linha}. São dezenas — cabe inteiro na memória.

    Carregado à parte em vez de embutido em cada nota: o embed repetiria a
    prova em cada uma das ~44 mil linhas de `nota`, e o que trafega é o mesmo
    objeto centenas de vezes.
    """
    resp = (
        cliente.table("simulado")
        .select(
            "id, ciclo_id, materia_id, nota_maxima, data_aplicacao, "
            "anulado, e_agregado, nota_confiavel"
        )
        .execute()
    )
    return {linha["id"]: linha for linha in (resp.data or [])}


def _codigo_por_materia(cliente) -> dict[str, str]:
    """{materia_id: codigo}. O código é o slug ASCII ('matematica'), não o nome."""
    resp = cliente.table("materia").select("id, codigo").execute()
    return {linha["id"]: linha.get("codigo") for linha in (resp.data or [])}


def _referencia_de_medias(
    cliente, simulados: dict[str, dict], *, hoje: date | None = None
) -> ReferenciaDeMedias:
    """Qual é o ano vigente, e quais são o primeiro e o último ciclo dele.

    Duas decisões que a tela não pode tomar:

      1. **Um ciclo só conta depois de acontecer** — tem pelo menos um simulado
         aplicado até hoje. Sem isso, um ciclo agendado para novembro seria o
         "último ciclo" em setembro, e a coluna inteira nasceria vazia.
      2. **O ciclo de referência é o MESMO para todo mundo.** Usar o último
         ciclo *de cada aluno* faria a ordenação comparar ciclos diferentes
         entre linhas vizinhas — a mentira gráfica que a R6 existe para
         impedir, agora na coluna em vez de no gráfico.
    """
    dia = (hoje or hoje_na_escola()).isoformat()
    ciclos = (
        cliente.table("ciclo")
        .select("id, ordem, nome, vestibular_alvo, ano_letivo_id")
        .execute()
        .data
        or []
    )
    anos = cliente.table("ano_letivo").select("id, ano").execute().data or []
    ano_por_id = {linha["id"]: linha.get("ano") for linha in anos}

    aplicados = {
        sim.get("ciclo_id")
        for sim in simulados.values()
        if simulado_entra_no_agregado(sim) and str(sim.get("data_aplicacao") or "") <= dia
    }
    candidatos = [
        c
        for c in ciclos
        if c["id"] in aplicados and ano_por_id.get(c.get("ano_letivo_id")) is not None
    ]
    if not candidatos:
        return REFERENCIA_VAZIA

    ano = max(ano_por_id[c["ano_letivo_id"]] for c in candidatos)
    do_ano = [c for c in ciclos if ano_por_id.get(c.get("ano_letivo_id")) == ano]
    aconteceram = sorted(
        (c for c in do_ano if c["id"] in aplicados),
        key=lambda c: c.get("ordem") if c.get("ordem") is not None else 0,
    )
    primeiro, ultimo = aconteceram[0], aconteceram[-1]
    return ReferenciaDeMedias(
        ciclos_do_ano=frozenset(c["id"] for c in do_ano),
        ciclo_primeiro=primeiro["id"],
        ciclo_ultimo=ultimo["id"],
        rotulo_ano=str(ano),
        rotulo_primeiro=_rotulo_de_ciclo(primeiro),
        rotulo_ultimo=_rotulo_de_ciclo(ultimo),
    )


def _carregar_notas_validas(cliente, *, aluno_ids: list[str] | None = None) -> list[dict]:
    """As notas que contam, PAGINANDO — só as três colunas de que a média precisa.

    Pagina pelo mesmo motivo de `stats/classificacao._carregar_notas_com_simulado`:
    sem `range`, a média dos 900 sairia de uma fatia arbitrária das ~44 mil
    linhas de `nota` e estaria errada **sem erro nenhum** (CLAUDE.md,
    armadilha 2).

    `filtro_nota_valida` é quem diz o que é "nota que conta" — presente e
    computável. A régua do AGREGADO (anulado, agregado, prova não confiável) é
    coluna de `simulado` e não passa por filtro do PostgREST; ela é aplicada no
    join em Python, por `simulado_entra_no_agregado`.
    """
    linhas: list[dict] = []
    offset = 0
    while True:
        query = filtro_nota_valida(
            cliente.table("nota").select("aluno_id, simulado_id, pontuacao")
        )
        if aluno_ids is not None:
            query = query.in_("aluno_id", aluno_ids)
        lote = query.range(offset, offset + _TAMANHO_PAGINA - 1).execute().data or []
        linhas.extend(lote)
        if len(lote) < _TAMANHO_PAGINA:
            return linhas
        offset += _TAMANHO_PAGINA


def _notas_para_medias(
    cliente,
    simulados: dict[str, dict],
    codigos: dict[str, str],
    *,
    aluno_ids: list[str] | None = None,
) -> Iterator[dict]:
    """{aluno_id, nota (0–10), ciclo_id, materia} — o join de `nota` com `simulado`.

    A normalização para 0–10 acontece aqui, uma vez: `nota.pontuacao` são
    ACERTOS, e o número de questões varia de prova para prova. Somar acertos de
    provas diferentes é somar coisas diferentes.
    """
    for linha in _carregar_notas_validas(cliente, aluno_ids=aluno_ids):
        sim = simulados.get(linha.get("simulado_id"))
        if sim is None or not simulado_entra_no_agregado(sim):
            continue
        nota = nota_real(
            como_float(linha.get("pontuacao")), como_float(sim.get("nota_maxima"))
        )
        if nota is None:
            continue
        yield {
            "aluno_id": linha["aluno_id"],
            "nota": nota,
            "ciclo_id": sim.get("ciclo_id"),
            "materia": codigos.get(sim.get("materia_id")),
        }


def _media(valores: list[float]) -> float | None:
    """A média, ou `None` quando não há nota. Nunca 0,0 — ver `MediaDoGrupo`."""
    return round(st.mean(valores), 2) if valores else None


def medias_por_aluno(
    notas: Iterable[dict], *, referencia: ReferenciaDeMedias
) -> dict[str, MediasDoAluno]:
    """{aluno_id: as três médias}, a partir de notas já normalizadas em 0–10.

    Função PURA — nenhuma I/O — porque é ela que erra calado: uma nota contada
    no grupo errado não levanta exceção, só desloca uma coluna em 900 linhas.
    O join com `simulado` e a leitura do banco ficam nos chamadores.

    Um ciclo pode ser ao mesmo tempo o primeiro e o último (só um aconteceu):
    aí a mesma nota entra nos dois grupos, e as duas colunas coincidem. É o
    estado verdadeiro do ano, não um bug de contagem.

    Aluno sem nota nenhuma simplesmente não aparece no resultado — quem
    preenche a lacuna com `medias_vazias` é o endpoint, para toda linha da
    tabela ter a mesma forma.
    """
    acumulado: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
        lambda: {grupo: defaultdict(list) for grupo in ("ano", "primeiro", "ultimo")}
    )

    for nota in notas:
        ciclo = nota.get("ciclo_id")
        if ciclo is None:
            continue
        grupos = []
        if ciclo in referencia.ciclos_do_ano:
            grupos.append("ano")
        if ciclo == referencia.ciclo_primeiro:
            grupos.append("primeiro")
        if ciclo == referencia.ciclo_ultimo:
            grupos.append("ultimo")
        if not grupos:
            continue

        valor = nota["nota"]
        materia = nota.get("materia")
        for grupo in grupos:
            balde = acumulado[nota["aluno_id"]][grupo]
            balde["geral"].append(valor)
            if materia in MATERIAS_DO_DETALHAMENTO:
                balde[materia].append(valor)

    def montar(balde: dict[str, list[float]], rotulo: str | None) -> MediaDoGrupo:
        return MediaDoGrupo(
            referencia=rotulo,
            geral=_media(balde.get("geral", [])),
            matematica=_media(balde.get("matematica", [])),
            fisica=_media(balde.get("fisica", [])),
            quimica=_media(balde.get("quimica", [])),
        )

    return {
        aluno_id: MediasDoAluno(
            ano=montar(baldes["ano"], referencia.rotulo_ano),
            primeiroCiclo=montar(baldes["primeiro"], referencia.rotulo_primeiro),
            ultimoCiclo=montar(baldes["ultimo"], referencia.rotulo_ultimo),
        )
        for aluno_id, baldes in acumulado.items()
    }


def medias_vazias(referencia: ReferenciaDeMedias) -> MediasDoAluno:
    """As três colunas com rótulo e sem número — a chegada de todo aluno novo.

    O rótulo continua vindo: a coluna existe, o aluno é que ainda não tem nota
    nela. Devolver a estrutura ausente faria a tela decidir entre "sem dado" e
    "coluna inexistente", que são coisas diferentes.
    """
    return MediasDoAluno(
        ano=MediaDoGrupo(referencia=referencia.rotulo_ano),
        primeiroCiclo=MediaDoGrupo(referencia=referencia.rotulo_primeiro),
        ultimoCiclo=MediaDoGrupo(referencia=referencia.rotulo_ultimo),
    )


def _direitos_por_aluno(cliente, *, aluno_ids: list[str] | None = None) -> dict[str, list[str]]:
    """{aluno_id: ['almoco', 'janta']}. A linha existir é o direito (0049).

    Ordenado para a coluna não trocar de ordem entre dois carregamentos — a
    tabela desenha os dois glifos na sequência em que chegam.
    """
    query = cliente.table("direito_refeicao_aluno").select("aluno_id, refeicao")
    if aluno_ids is not None:
        query = query.in_("aluno_id", aluno_ids)
    mapa: dict[str, list[str]] = defaultdict(list)
    for linha in query.execute().data or []:
        mapa[linha["aluno_id"]].append(linha["refeicao"])
    return {aluno_id: sorted(lista) for aluno_id, lista in mapa.items()}


# ─── Endpoints ───────────────────────────────────────────────────────────


@router.get("", response_model=list[AlunoDaCoordenacao])
async def listar_alunos(
    recorte: str | None = Query(None, description="em-risco | em-ascensao | perfil-irregular | zona-corte"),
    sede_id: str | None = Query(None, alias="sedeId"),
    turma_id: str | None = Query(None, alias="turmaId"),
) -> list[AlunoDaCoordenacao]:
    """A lista de varredura: um aluno por linha, com as médias e os direitos.

    As médias saem prontas daqui em vez de derivadas na tela porque derivá-las
    no front custaria baixar as notas dos 900 a cada carregamento — e porque a
    escolha de QUAIS ciclos são "o primeiro" e "o último" é do servidor
    (`_referencia_de_medias`).
    """
    cliente = get_supabase()

    aluno_para_turma = _mapa_aluno_para_turma_ativa(cliente)
    turma_para_sede = _mapa_turma_para_sede(cliente)
    classificacoes = _classif.mapa_classificacao(cliente)
    vestibulares = _vestibulares_por_aluno(cliente)
    sparklines = _classif.sparkline_por_aluno(cliente)

    simulados = _mapa_simulados(cliente)
    referencia = _referencia_de_medias(cliente, simulados)
    medias = medias_por_aluno(
        _notas_para_medias(cliente, simulados, _codigo_por_materia(cliente)),
        referencia=referencia,
    )
    direitos = _direitos_por_aluno(cliente)

    resp = (
        cliente.table("aluno")
        .select("id, nome, ativo, foto_perfil_storage")
        .order("nome")
        .execute()
    )

    alunos: list[AlunoDaCoordenacao] = []
    for linha in resp.data or []:
        id_aluno = linha["id"]
        id_turma = aluno_para_turma.get(id_aluno)
        if not id_turma:
            continue
        id_sede = turma_para_sede.get(id_turma, "")

        if turma_id and id_turma != turma_id:
            continue
        if sede_id and id_sede != sede_id:
            continue

        classif = classificacoes.get(id_aluno) or {}
        aluno = AlunoDaCoordenacao(
            id=id_aluno,
            nome=linha["nome"],
            turmaId=id_turma,
            sedeId=id_sede,
            vestibularesAlvo=vestibulares.get(id_aluno, []),
            ativo=bool(linha.get("ativo", True)),
            perfil=classif.get("perfil", "regular"),
            tendencia=classif.get("tendencia", "estavel"),
            zona=classif.get("zona", "cinzenta"),
            media=como_float(classif.get("media_recente")),
            sparkline=sparklines.get(id_aluno, []),
            temFoto=linha.get("foto_perfil_storage") is not None,
            medias=medias.get(id_aluno) or medias_vazias(referencia),
            direitos=direitos.get(id_aluno, []),
        )
        if not _passar_recorte(aluno, recorte):
            continue
        alunos.append(aluno)

    return alunos


@router.get("/{aluno_id}", response_model=AlunoDaCoordenacao)
async def obter_aluno(aluno_id: str) -> AlunoDaCoordenacao:
    cliente = get_supabase()
    resp = (
        cliente.table("aluno")
        .select("id, nome, ativo, email, foto_perfil_storage")
        .eq("id", aluno_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail=f"aluno {aluno_id} não encontrado")

    aluno_para_turma = _mapa_aluno_para_turma_ativa(cliente)
    turma_para_sede = _mapa_turma_para_sede(cliente)
    classificacoes = _classif.mapa_classificacao(cliente)
    vestibulares = _vestibulares_por_aluno(cliente)
    sparklines = _classif.sparkline_por_aluno(cliente)

    id_turma = aluno_para_turma.get(aluno_id, "")
    id_sede = turma_para_sede.get(id_turma, "") if id_turma else ""
    classif = classificacoes.get(aluno_id) or {}

    # Aqui a varredura de notas é restrita a UM aluno: a ficha não paga o preço
    # da lista. `GET /me` também cai neste caminho (routes/me.py), e o aluno
    # recebe as próprias médias e os próprios direitos — nunca os de outro.
    simulados = _mapa_simulados(cliente)
    referencia = _referencia_de_medias(cliente, simulados)
    medias = medias_por_aluno(
        _notas_para_medias(
            cliente, simulados, _codigo_por_materia(cliente), aluno_ids=[aluno_id]
        ),
        referencia=referencia,
    )
    direitos = _direitos_por_aluno(cliente, aluno_ids=[aluno_id])

    linha = resp.data[0]
    return AlunoDaCoordenacao(
        id=linha["id"],
        nome=linha["nome"],
        turmaId=id_turma,
        sedeId=id_sede,
        vestibularesAlvo=vestibulares.get(aluno_id, []),
        ativo=bool(linha.get("ativo", True)),
        email=linha.get("email"),
        perfil=classif.get("perfil", "regular"),
        tendencia=classif.get("tendencia", "estavel"),
        zona=classif.get("zona", "cinzenta"),
        media=como_float(classif.get("media_recente")),
        sparkline=sparklines.get(aluno_id, []),
        temFoto=linha.get("foto_perfil_storage") is not None,
        medias=medias.get(aluno_id) or medias_vazias(referencia),
        direitos=direitos.get(aluno_id, []),
    )


@router.get("/{aluno_id}/trajetoria")
async def trajetoria_aluno(aluno_id: str) -> list[dict]:
    """Lista cronológica das notas do aluno (já em escala 0–10).

    Retorna `pontuacao` normalizada (`acertos / total * 10`). O cliente recebe
    direto o número que faz sentido pra interpretar — nunca acertos brutos.
    """
    cliente = get_supabase()
    resp = (
        cliente.table("nota")
        .select(
            "pontuacao, presente, simulado("
            "id, nome, data_aplicacao, anulado, e_agregado, nota_confiavel, "
            "materia_id, nota_maxima, tipo"
            ")"
        )
        .eq("aluno_id", aluno_id)
        # A prova não confiável continua na linha; o zero sem resposta, não —
        # ele não é desempenho, e afundaria a série de quem não fez a prova.
        .eq("computavel", True)
        .execute()
    )
    linhas: list[dict] = []
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        if not linha.get("presente"):
            continue
        nota = nota_real(
            como_float(linha.get("pontuacao")),
            como_float(sim.get("nota_maxima")),
        )
        if nota is None:
            continue
        linhas.append(
            {
                "simuladoId": sim.get("id"),
                "simulado": sim.get("nome"),
                "dataAplicacao": sim.get("data_aplicacao"),
                "materiaId": sim.get("materia_id"),
                "tipo": sim.get("tipo"),
                "pontuacao": round(nota, 2),
            }
        )
    linhas.sort(key=lambda r: r["dataAplicacao"] or "")
    return linhas


@router.get("/{aluno_id}/heatmap")
async def heatmap_aluno(aluno_id: str) -> dict:
    """Matriz matérias × simulados pra heatmap.

    Saída:
        {
          "materias": ["Matemática", "Física", ...],
          "simulados": [{
              "id", "nome", "rotulo", "dataAplicacao",
              "cicloId", "cicloOrdem", "cicloNome", "vestibularAlvo",
              "fase"  // "fase_1" | "fase_2" | None
          }, ...],
          "celulas": [{"materia", "simuladoId", "pontuacao"}, ...]
        }
    """
    cliente = get_supabase()
    resp = (
        cliente.table("nota")
        .select(
            "pontuacao, presente, simulado("
            "id, nome, rotulo_curto, data_aplicacao, materia_id, tipo, "
            "anulado, e_agregado, nota_confiavel, motivo_nota_nao_confiavel, nota_maxima, "
            "ciclo:ciclo_id(id, ordem, nome, vestibular_alvo)"
            ")"
        )
        .eq("aluno_id", aluno_id)
        # Sem filtro de `computavel`: é a ficha do aluno. Uma nota que saiu da
        # média continua aparecendo, marcada — quem some daqui é a ausência.
        .eq("presente", True)
        .execute()
    )

    materias_resp = cliente.table("materia").select("id, nome").execute()
    nome_materia = {m["id"]: m["nome"] for m in (materias_resp.data or [])}

    simulados_vistos: dict[str, dict] = {}
    celulas: list[dict] = []
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        materia = nome_materia.get(sim.get("materia_id"))
        if not materia:
            continue
        nota = nota_real(
            como_float(linha.get("pontuacao")),
            como_float(sim.get("nota_maxima")),
        )
        if nota is None:
            continue
        sid = sim["id"]
        if sid not in simulados_vistos:
            ciclo = sim.get("ciclo") or {}
            simulados_vistos[sid] = {
                "id": sid,
                "nome": sim.get("nome"),
                "rotulo": sim.get("rotulo_curto") or sim.get("nome"),
                "dataAplicacao": sim.get("data_aplicacao"),
                "cicloId": ciclo.get("id"),
                "cicloOrdem": ciclo.get("ordem"),
                "cicloNome": ciclo.get("nome"),
                "vestibularAlvo": ciclo.get("vestibular_alvo"),
                "fase": sim.get("tipo"),
            }
        celulas.append(
            {
                "materia": materia,
                "simuladoId": sid,
                "pontuacao": round(nota, 2),
            }
        )

    # Ordena primeiro por (ciclo_ordem, fase, data) — coloca tudo do ciclo 1
    # junto, depois ciclo 2, etc. Simulados sem ciclo ordem ficam por último.
    simulados_ordenados = sorted(
        simulados_vistos.values(),
        key=lambda s: (
            s.get("cicloOrdem") if s.get("cicloOrdem") is not None else 999,
            0 if s.get("fase") == "fase_1" else (1 if s.get("fase") == "fase_2" else 2),
            s.get("dataAplicacao") or "",
        ),
    )
    materias_distintas = sorted({c["materia"] for c in celulas})
    return {
        "materias": materias_distintas,
        "simulados": simulados_ordenados,
        "celulas": celulas,
    }


@router.get("/{aluno_id}/similares")
async def alunos_similares(aluno_id: str, k: int = 5) -> list[dict]:
    """kNN por vetor de features (média por matéria + desvio + slope).

    Distância euclidiana. Retorna os `k` alunos mais próximos (excluindo o
    próprio). Vetor com NaN em uma feature pula essa coordenada na soma.
    """
    cliente = get_supabase()
    vetores = _vetores_de_features(cliente)
    if aluno_id not in vetores:
        return []

    alvo = vetores[aluno_id]
    distancias: list[tuple[str, float]] = []
    for outro_id, vec in vetores.items():
        if outro_id == aluno_id:
            continue
        dist = _distancia(alvo, vec)
        if dist is None:
            continue
        distancias.append((outro_id, dist))

    distancias.sort(key=lambda x: x[1])
    top = distancias[:k]

    # Anexa nome e classificação.
    nomes_resp = cliente.table("aluno").select("id, nome").execute()
    nomes = {a["id"]: a["nome"] for a in (nomes_resp.data or [])}
    classif = _classif.mapa_classificacao(cliente)

    saida: list[dict] = []
    for outro_id, dist in top:
        c = classif.get(outro_id) or {}
        saida.append(
            {
                "alunoId": outro_id,
                "nome": nomes.get(outro_id, outro_id),
                "distancia": round(dist, 3),
                "perfil": c.get("perfil"),
                "tendencia": c.get("tendencia"),
                "zona": c.get("zona"),
                "media": como_float(c.get("media_recente")),
            }
        )
    return saida


# ─── Vetor de features por aluno ─────────────────────────────────────────


def _vetores_de_features(cliente) -> dict[str, list[float | None]]:
    """{aluno_id: [media_mat1, media_mat2, ..., desvio, slope]}.

    Materias ordenadas alfabeticamente por nome → ordem estável. None onde
    o aluno não tem nota da matéria.
    """
    materias_resp = cliente.table("materia").select("id, nome").execute()
    materias = sorted(materias_resp.data or [], key=lambda m: m["nome"])
    materia_ids = [m["id"] for m in materias]

    # Notas com materia_id e pontuação — normalizadas em 0–10 antes de
    # virar feature. Sem isso, vetores de alunos comparam apples to oranges.
    resp = (
        cliente.table("nota")
        .select(
            "aluno_id, pontuacao, simulado("
            "materia_id, data_aplicacao, anulado, e_agregado, nota_confiavel, nota_maxima"
            ")"
        )
        .eq("presente", True)
        .eq("computavel", True)
        .execute()
    )

    notas_por_aluno: dict[str, list[dict]] = defaultdict(list)
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        mid = sim.get("materia_id")
        nota = nota_real(
            como_float(linha.get("pontuacao")),
            como_float(sim.get("nota_maxima")),
        )
        if nota is None or not mid:
            continue
        notas_por_aluno[linha["aluno_id"]].append(
            {"materia_id": mid, "pontuacao": nota, "data": sim.get("data_aplicacao") or ""}
        )

    classif = _classif.mapa_classificacao(cliente)

    vetores: dict[str, list[float | None]] = {}
    for aluno_id, notas in notas_por_aluno.items():
        por_materia: dict[str, list[float]] = defaultdict(list)
        for n in notas:
            por_materia[n["materia_id"]].append(n["pontuacao"])
        # 6 médias por matéria
        v: list[float | None] = []
        for mid in materia_ids:
            valores = por_materia.get(mid, [])
            v.append(st.mean(valores) if valores else None)
        # Desvio geral
        todas = [n["pontuacao"] for n in notas]
        v.append(st.stdev(todas) if len(todas) > 1 else None)
        # Slope (vem da classificação)
        c = classif.get(aluno_id) or {}
        v.append(como_float(c.get("coef_tendencia")))
        vetores[aluno_id] = v
    return vetores


def _distancia(a: list[float | None], b: list[float | None]) -> float | None:
    if len(a) != len(b):
        return None
    soma = 0.0
    dimensoes_validas = 0
    for x, y in zip(a, b, strict=True):
        if x is None or y is None:
            continue
        soma += (x - y) ** 2
        dimensoes_validas += 1
    if dimensoes_validas == 0:
        return None
    # Normaliza pela dimensão pra não penalizar alunos com matérias faltando.
    return math.sqrt(soma / dimensoes_validas)


# ─── Acesso do aluno (área do aluno) ─────────────────────────────────────
# A rota POST /alunos/{id}/resetar-acesso SAIU em 04/09 (docs/35 §11.5).
#
# Ela zerava `aluno.senha_hash` para liberar um novo "primeiro acesso", e era o
# fallback da coordenação para quem perdia a senha ou estava sem e-mail no
# Canvas. Com o aluno entrando SÓ pelo Canvas, não há senha para zerar nem
# primeiro acesso para liberar: aluno sem acesso é aluno sem `canvas_user_id`,
# e isso se resolve no Canvas, não aqui.
#
# A coluna `aluno.senha_hash` fica com o que já tinha — apagar perde dado e não
# devolve nada.


# ─── Foto de perfil (visão da coordenação) ───────────────────────────────
# Upload é sempre autosserviço (routes/foto_perfil.py, POST /me/foto) — a
# coordenação só VÊ e REMOVE. Decisão em aberto (docs/sprints.html · SPRINT
# FOTO): quem consente pela foto de um menor. Enquanto isso não está fechado,
# a coordenação não tem como mandar foto por outra pessoa — só tirar uma foto
# imprópria do ar (P5).


@router.get("/{aluno_id}/foto")
async def foto_do_aluno(aluno_id: str) -> dict:
    cliente = get_supabase()
    resp = (
        cliente.table("aluno")
        .select("foto_perfil_storage")
        .eq("id", aluno_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail=f"aluno {aluno_id} não encontrado")
    caminho = resp.data[0].get("foto_perfil_storage")
    if not caminho:
        return {"fotoDataUrl": None}

    lido = storage.ler_foto_perfil(caminho)
    if lido is None:
        return {"fotoDataUrl": None}
    conteudo, content_type = lido
    return {"fotoDataUrl": f"data:{content_type};base64,{base64.b64encode(conteudo).decode()}"}


@router.delete("/{aluno_id}/foto")
async def remover_foto_do_aluno(
    aluno_id: str, request: Request, coordenador: dict = Depends(get_current_coordenador)
) -> dict:
    """Tira uma foto imprópria do ar (docs/sprints.html · SPRINT FOTO · P5).
    O titular também pode remover a própria foto — via DELETE /me/foto."""
    cliente = get_supabase()
    resp = (
        cliente.table("aluno")
        .select("foto_perfil_storage")
        .eq("id", aluno_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail=f"aluno {aluno_id} não encontrado")
    caminho = resp.data[0].get("foto_perfil_storage")
    if not caminho:
        return {"ok": True}

    cliente.table("aluno").update(
        {"foto_perfil_storage": None, "foto_perfil_atualizada_em": None}
    ).eq("id", aluno_id).execute()
    storage.remover_foto_perfil(caminho)

    auditar(
        cliente, "foto_perfil_removida", canal="acesso",
        ator_tipo="coordenador", ator_id=coordenador.get("sub"),
        recurso=f"aluno/{aluno_id}",
        ip=request.client.host if request.client else None,
        detalhe={"por_titular": False},
    )
    return {"ok": True}
