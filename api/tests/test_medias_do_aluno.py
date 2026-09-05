"""As três médias do aluno e os direitos de refeição (docs/39 · fase 4).

Estas duas regras erram CALADAS, que é o motivo de o arquivo existir.

**As médias.** Uma nota contada no grupo errado não levanta exceção: ela
desloca uma coluna em 900 linhas, e o coordenador ordena por um número que
descreve outro ciclo. O que os testes trancam é o par que a tela não pode
tomar sozinha — QUAIS ciclos são "o primeiro" e "o último" (a mesma escolha
para todo mundo, e só entre os que já aconteceram) e o que entra em cada
grupo.

**O aluno sem nota nenhuma.** É a chegada de TODO aluno novo, e o formato tem
de sobreviver a ela sem inventar: `None` em toda célula, rótulo de coluna
presente. Um `0.0` ali manda a coordenação procurar um aluno em risco que não
existe — é a diferença entre "não sei" e "zero" que o produto inteiro persegue.

**A LGPD.** `test_a_lista_nao_carrega_restricao_alimentar` guarda a decisão do
docs/38 §2.6: dado de saúde de menor não viaja numa lista de 900. Se alguém
"completar" o aluno com a restrição um dia, é aqui que aparece.

Os handlers são chamados direto, com um `FakeCliente` no lugar do PostgREST —
o padrão de `test_alertas.py` e `test_papeis.py`.

Rodar:  cd api && ./.venv/bin/python -m pytest tests/test_medias_do_aluno.py -q
"""

import asyncio
from datetime import date

import pytest

from app.routes import alunos
from app.routes.alunos import (
    MATERIAS_DO_DETALHAMENTO,
    ReferenciaDeMedias,
    medias_por_aluno,
    medias_vazias,
)
from tests.fake_postgrest import FakeCliente

# ─── Peças do cenário ─────────────────────────────────────────────────────

REFERENCIA = ReferenciaDeMedias(
    ciclos_do_ano=frozenset({"c1", "c2", "c3"}),
    ciclo_primeiro="c1",
    ciclo_ultimo="c3",
    rotulo_ano="2026",
    rotulo_primeiro="1º Ciclo · ITA",
    rotulo_ultimo="3º Ciclo · IME",
)


def nota(aluno: str, ciclo: str, valor: float, materia: str | None = "matematica") -> dict:
    """Uma nota já normalizada em 0–10 — a forma que `medias_por_aluno` recebe."""
    return {"aluno_id": aluno, "nota": valor, "ciclo_id": ciclo, "materia": materia}


# ─── A função pura: o que entra em cada grupo ─────────────────────────────


def test_media_do_ano_soma_todos_os_ciclos_do_ano():
    saida = medias_por_aluno(
        [nota("A1", "c1", 4.0), nota("A1", "c2", 6.0), nota("A1", "c3", 8.0)],
        referencia=REFERENCIA,
    )
    assert saida["A1"].ano.geral == 6.0


def test_ciclo_de_outro_ano_fica_de_fora_da_media_do_ano():
    """"Média do ano" é do ano vigente — o ciclo de 2025 não entra em 2026."""
    saida = medias_por_aluno(
        [nota("A1", "c1", 4.0), nota("A1", "c-do-ano-passado", 10.0)],
        referencia=REFERENCIA,
    )
    assert saida["A1"].ano.geral == 4.0


def test_primeiro_e_ultimo_ciclo_recortam_so_o_proprio_ciclo():
    saida = medias_por_aluno(
        [nota("A1", "c1", 3.0), nota("A1", "c2", 9.0), nota("A1", "c3", 7.0)],
        referencia=REFERENCIA,
    )
    assert saida["A1"].primeiroCiclo.geral == 3.0
    assert saida["A1"].ultimoCiclo.geral == 7.0


def test_o_ciclo_de_referencia_e_o_mesmo_para_todo_mundo():
    """A R6 no eixo da coluna: ordenar por "último ciclo" tem de comparar o
    MESMO ciclo entre linhas vizinhas.

    A2 tem nota no c3 e A1 não. Se o "último ciclo" fosse o último *de cada
    aluno*, A1 mostraria o c2 nessa coluna e as duas linhas estariam sendo
    comparadas em provas diferentes — sem nada na tela dizendo isso.
    """
    saida = medias_por_aluno(
        [nota("A1", "c1", 5.0), nota("A1", "c2", 9.0), nota("A2", "c3", 4.0)],
        referencia=REFERENCIA,
    )
    assert saida["A1"].ultimoCiclo.geral is None
    assert saida["A2"].ultimoCiclo.geral == 4.0


def test_ciclo_unico_e_ao_mesmo_tempo_o_primeiro_e_o_ultimo():
    """Só um ciclo aconteceu: as duas colunas coincidem, e isso é verdade."""
    referencia = ReferenciaDeMedias(
        ciclos_do_ano=frozenset({"c1"}),
        ciclo_primeiro="c1",
        ciclo_ultimo="c1",
        rotulo_ano="2026",
        rotulo_primeiro="1º Ciclo · ITA",
        rotulo_ultimo="1º Ciclo · ITA",
    )
    saida = medias_por_aluno([nota("A1", "c1", 6.0)], referencia=referencia)
    assert saida["A1"].primeiroCiclo.geral == 6.0
    assert saida["A1"].ultimoCiclo.geral == 6.0
    assert saida["A1"].ano.geral == 6.0


# ─── A função pura: o detalhamento por matéria ────────────────────────────


def test_detalhamento_abre_so_as_materias_com_taxonomia_de_edital():
    """Português entra na média GERAL, mas não ganha coluna (docs/19 §4.1)."""
    assert MATERIAS_DO_DETALHAMENTO == ("matematica", "fisica", "quimica")

    saida = medias_por_aluno(
        [
            nota("A1", "c1", 8.0, "matematica"),
            nota("A1", "c1", 6.0, "fisica"),
            nota("A1", "c1", 4.0, "quimica"),
            nota("A1", "c1", 2.0, "portugues"),
        ],
        referencia=REFERENCIA,
    )
    grupo = saida["A1"].primeiroCiclo
    assert (grupo.matematica, grupo.fisica, grupo.quimica) == (8.0, 6.0, 4.0)
    assert grupo.geral == 5.0   # os quatro, Português incluído


def test_prova_sem_materia_entra_no_geral_e_em_nenhuma_coluna():
    """A prova agregada da Fase 1 não tem `materia_id` — e não some da média."""
    saida = medias_por_aluno(
        [nota("A1", "c1", 7.0, None), nota("A1", "c1", 3.0, "fisica")],
        referencia=REFERENCIA,
    )
    grupo = saida["A1"].primeiroCiclo
    assert grupo.geral == 5.0
    assert grupo.fisica == 3.0
    assert grupo.matematica is None


# ─── A função pura: o aluno que ainda não tem nota ────────────────────────


def test_materia_sem_nota_e_none_e_nunca_zero():
    saida = medias_por_aluno([nota("A1", "c1", 8.0, "matematica")], referencia=REFERENCIA)
    grupo = saida["A1"].primeiroCiclo
    assert grupo.fisica is None
    assert grupo.quimica is None


def test_aluno_sem_nota_nenhuma_nao_aparece_no_agregado():
    assert medias_por_aluno([], referencia=REFERENCIA) == {}


def test_medias_vazias_mantem_o_rotulo_e_zera_nada():
    """A coluna existe; o aluno é que ainda não tem nota nela."""
    vazio = medias_vazias(REFERENCIA)
    assert vazio.ano.referencia == "2026"
    assert vazio.primeiroCiclo.referencia == "1º Ciclo · ITA"
    assert vazio.ultimoCiclo.referencia == "3º Ciclo · IME"
    assert vazio.ano.geral is None
    assert vazio.ultimoCiclo.matematica is None


def test_o_rotulo_viaja_junto_do_numero():
    """Rótulo e número na mesma resposta: separá-los deixaria a tela nomear um
    ciclo que o número não é, no primeiro ciclo novo."""
    saida = medias_por_aluno([nota("A1", "c3", 5.0)], referencia=REFERENCIA)
    assert saida["A1"].ultimoCiclo.referencia == "3º Ciclo · IME"


# ─── A referência: que ano e que dois ciclos ──────────────────────────────


def _simulados(*linhas: dict) -> dict[str, dict]:
    return {linha["id"]: linha for linha in linhas}


def simulado(
    id_: str,
    ciclo: str,
    data: str,
    *,
    materia: str | None = "m-mat",
    anulado: bool = False,
    agregado: bool = False,
    nota_maxima: float = 10,
) -> dict:
    return {
        "id": id_,
        "ciclo_id": ciclo,
        "materia_id": materia,
        "data_aplicacao": data,
        "nota_maxima": nota_maxima,
        "anulado": anulado,
        "e_agregado": agregado,
        "nota_confiavel": True,
    }


CICLOS = {
    "c1": {"id": "c1", "ordem": 1, "nome": "1º Ciclo", "vestibular_alvo": "ITA", "ano_letivo_id": "a2026"},
    "c2": {"id": "c2", "ordem": 2, "nome": "2º Ciclo", "vestibular_alvo": "IME", "ano_letivo_id": "a2026"},
    "c3": {"id": "c3", "ordem": 3, "nome": "3º Ciclo", "vestibular_alvo": "ITA", "ano_letivo_id": "a2026"},
    "cv": {"id": "cv", "ordem": 9, "nome": "9º Ciclo", "vestibular_alvo": "ITA", "ano_letivo_id": "a2025"},
}
ANOS = {"a2026": {"id": "a2026", "ano": 2026}, "a2025": {"id": "a2025", "ano": 2025}}


def _cliente_de_ciclos() -> FakeCliente:
    return FakeCliente({"ciclo": dict(CICLOS), "ano_letivo": dict(ANOS)})


def test_ciclo_agendado_para_o_futuro_nao_vira_o_ultimo_ciclo():
    """Sem isto, o ciclo de novembro seria "o último" em setembro — e a coluna
    inteira nasceria vazia, sem nada dizendo por quê."""
    simulados = _simulados(
        simulado("s1", "c1", "2026-03-10"),
        simulado("s2", "c2", "2026-05-10"),
        simulado("s3", "c3", "2026-11-10"),
    )
    ref = alunos._referencia_de_medias(
        _cliente_de_ciclos(), simulados, hoje=date(2026, 9, 5)
    )
    assert ref.ciclo_primeiro == "c1"
    assert ref.ciclo_ultimo == "c2"
    # O c3 continua no ANO: a média do ano soma o que já houver dele.
    assert ref.ciclos_do_ano == frozenset({"c1", "c2", "c3"})


def test_ano_vigente_e_o_maior_com_ciclo_ja_aplicado():
    simulados = _simulados(
        simulado("s0", "cv", "2025-04-10"),
        simulado("s1", "c1", "2026-03-10"),
    )
    ref = alunos._referencia_de_medias(
        _cliente_de_ciclos(), simulados, hoje=date(2026, 9, 5)
    )
    assert ref.rotulo_ano == "2026"
    assert "cv" not in ref.ciclos_do_ano


def test_sem_ciclo_aplicado_a_referencia_fica_vazia():
    """Banco novo, ou o ano ainda não começou. Nada de rótulo inventado."""
    ref = alunos._referencia_de_medias(
        _cliente_de_ciclos(), _simulados(simulado("s3", "c3", "2026-11-10")),
        hoje=date(2026, 1, 5),
    )
    assert ref == alunos.REFERENCIA_VAZIA
    assert ref.rotulo_ano is None


def test_prova_anulada_nao_faz_o_ciclo_existir():
    """O ciclo cujo único simulado foi anulado não aconteceu, para efeito de média."""
    simulados = _simulados(
        simulado("s1", "c1", "2026-03-10"),
        simulado("s3", "c3", "2026-08-10", anulado=True),
    )
    ref = alunos._referencia_de_medias(
        _cliente_de_ciclos(), simulados, hoje=date(2026, 9, 5)
    )
    assert ref.ciclo_ultimo == "c1"


def test_rotulo_carrega_o_edital_do_ciclo():
    """Dois ciclos com o mesmo número e editais diferentes são colunas diferentes."""
    ref = alunos._referencia_de_medias(
        _cliente_de_ciclos(),
        _simulados(simulado("s1", "c1", "2026-03-10"), simulado("s2", "c2", "2026-05-10")),
        hoje=date(2026, 9, 5),
    )
    assert ref.rotulo_primeiro == "1º Ciclo · ITA"
    assert ref.rotulo_ultimo == "2º Ciclo · IME"


# ─── O endpoint inteiro, com o banco falso ────────────────────────────────


def _banco() -> dict:
    """Dois alunos: um com histórico, outro recém-chegado e sem nota nenhuma."""
    return {
        "aluno": {
            "A1": {
                "id": "A1",
                "nome": "Ana Beatriz",
                "ativo": True,
                "foto_perfil_storage": None,
                # Está no banco (coluna de `aluno`, migration 0049) — e não pode
                # sair por esta rota.
                "restricao_alimentar": "alergia a amendoim",
            },
            "A2": {
                "id": "A2",
                "nome": "Zeca Novato",
                "ativo": True,
                "foto_perfil_storage": None,
                "restricao_alimentar": None,
            },
        },
        "matricula_turma": {
            "m1": {"aluno_id": "A1", "turma_id": "T1", "ativo_desde": "2026-02-01", "ativo_ate": None},
            "m2": {"aluno_id": "A2", "turma_id": "T1", "ativo_desde": "2026-08-01", "ativo_ate": None},
        },
        "turma": {"T1": {"id": "T1", "sede_id": "S1"}},
        "vestibular_alvo_aluno": {"v1": {"aluno_id": "A1", "vestibular": "ITA"}},
        "classificacao_aluno": {},
        "ciclo": dict(CICLOS),
        "ano_letivo": dict(ANOS),
        "materia": {
            "m-mat": {"id": "m-mat", "codigo": "matematica"},
            "m-fis": {"id": "m-fis", "codigo": "fisica"},
            "m-por": {"id": "m-por", "codigo": "portugues"},
        },
        "simulado": {
            "s1": simulado("s1", "c1", "2026-03-10", materia="m-mat", nota_maxima=20),
            "s2": simulado("s2", "c2", "2026-05-10", materia="m-fis"),
            "s3": simulado("s3", "c2", "2026-05-11", materia="m-por"),
            "sx": simulado("sx", "c2", "2026-05-12", materia="m-mat", anulado=True),
        },
        "nota": {
            # 16 de 20 acertos → 8,0. A normalização tem de acontecer.
            "n1": {"aluno_id": "A1", "simulado_id": "s1", "pontuacao": 16, "presente": True, "computavel": True},
            "n2": {"aluno_id": "A1", "simulado_id": "s2", "pontuacao": 4, "presente": True, "computavel": True},
            "n3": {"aluno_id": "A1", "simulado_id": "s3", "pontuacao": 6, "presente": True, "computavel": True},
            # Prova anulada: nota existe, média não conta.
            "n4": {"aluno_id": "A1", "simulado_id": "sx", "pontuacao": 10, "presente": True, "computavel": True},
            # Ausência e zero-sem-resposta: nenhum dos dois é desempenho.
            "n5": {"aluno_id": "A2", "simulado_id": "s1", "pontuacao": None, "presente": False, "computavel": True},
            "n6": {"aluno_id": "A2", "simulado_id": "s2", "pontuacao": 0, "presente": True, "computavel": False},
        },
        "direito_refeicao_aluno": {
            "d1": {"aluno_id": "A1", "refeicao": "janta"},
            "d2": {"aluno_id": "A1", "refeicao": "almoco"},
        },
    }


@pytest.fixture
def banco(monkeypatch) -> dict:
    db = _banco()
    monkeypatch.setattr(alunos, "get_supabase", lambda: FakeCliente(db))
    # O relógio congelado: sem ele o teste passaria a depender do dia em que roda.
    monkeypatch.setattr(alunos, "hoje_na_escola", lambda: date(2026, 9, 5))
    return db


def _listar() -> list:
    """Os três filtros explícitos, e isso NÃO é verbosidade.

    Chamado sem argumentos, o handler recebe os objetos `Query(None)` do
    FastAPI como valor — e `if turma_id and ...` passa a ser verdadeiro para
    um objeto que não é turma nenhuma, peneirando a lista inteira. A lista
    voltava vazia e todo assert falhava por um motivo que não é o do teste.
    """
    return asyncio.run(alunos.listar_alunos(recorte=None, sede_id=None, turma_id=None))


def _por_id(lista: list) -> dict:
    return {a.id: a for a in lista}


def test_listar_alunos_traz_as_tres_medias_ja_normalizadas(banco):
    a1 = _por_id(_listar())["A1"]
    # c1: 16/20 → 8,0.  c2: Física 4,0 e Português 6,0 → 5,0.  Ano: os três → 6,0.
    assert a1.medias.primeiroCiclo.geral == 8.0
    assert a1.medias.ultimoCiclo.geral == 5.0
    assert a1.medias.ano.geral == 6.0


def test_listar_alunos_abre_o_grupo_nas_materias_do_edital(banco):
    a1 = _por_id(_listar())["A1"]
    assert a1.medias.primeiroCiclo.matematica == 8.0
    assert a1.medias.ultimoCiclo.fisica == 4.0
    # Português entrou no geral do ciclo 2 e em coluna nenhuma.
    assert a1.medias.ultimoCiclo.matematica is None
    assert a1.medias.ultimoCiclo.quimica is None


def test_prova_anulada_nao_entra_na_media(banco):
    """A nota da `sx` (10,0) puxaria a média do ciclo 2 de 5,0 para 6,67."""
    a1 = _por_id(_listar())["A1"]
    assert a1.medias.ultimoCiclo.geral == 5.0


def test_aluno_novo_sem_nota_nenhuma_nao_quebra_e_nao_mente(banco):
    """A chegada de todo aluno: ausência e zero-sem-resposta, nada mais.

    É o caso que hoje quebrava ou mentia — `None` em toda célula, e o rótulo da
    coluna ainda presente, porque a coluna existe.
    """
    a2 = _por_id(_listar())["A2"]
    assert a2.medias.ano.geral is None
    assert a2.medias.primeiroCiclo.geral is None
    assert a2.medias.ultimoCiclo.geral is None
    assert a2.medias.ano.referencia == "2026"
    assert a2.medias.primeiroCiclo.referencia == "1º Ciclo · ITA"


def test_direitos_de_refeicao_vem_junto_do_aluno_e_ordenados(banco):
    lista = _por_id(_listar())
    assert lista["A1"].direitos == ["almoco", "janta"]
    assert lista["A2"].direitos == []


def test_a_lista_nao_carrega_restricao_alimentar(banco):
    """LGPD (docs/38 §2.6): dado de saúde de menor não viaja em lista de 900.

    Ele existe no banco e está preenchido para a A1 — se algum dia alguém
    "completar" o aluno com ele, este teste é que grita.
    """
    despejo = _por_id(_listar())["A1"].model_dump()
    assert "restricao_alimentar" not in despejo
    assert "restricaoAlimentar" not in despejo
    assert not any("restricao" in campo for campo in alunos.AlunoDaCoordenacao.model_fields)


def test_obter_aluno_traz_o_mesmo_formato_da_lista(banco):
    """A ficha não pode discordar da linha — é o mesmo aluno."""
    ficha = asyncio.run(alunos.obter_aluno("A1"))
    linha = _por_id(_listar())["A1"]
    assert ficha.medias.model_dump() == linha.medias.model_dump()
    assert ficha.direitos == linha.direitos
