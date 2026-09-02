"""As duas coleções do acervo (`consultas.MODOS_DA_COLECAO`).

"Recentes" e "Arquivo" são vocabulário de produto; a coluna que de fato separa
as duas é `extraido_por` (0031/0033). O que este arquivo trava:

  1. **A partição é total.** Todo valor que o CHECK da migration aceita cai em
     exatamente uma coleção. Uma questão órfã de coleção não daria erro nenhum:
     ela simplesmente não apareceria em lado nenhum da navegação, e ninguém
     descobre o que não está na tela. O teste lê a lista de valores DA PRÓPRIA
     MIGRATION, então um quarto modo de extração no futuro quebra aqui em vez
     de sumir com um lote inteiro em silêncio.
  2. **O filtro alcança o `total`, e não só as linhas da página.** É dele que
     sai o "1.760 questões" da tela; um total do acervo inteiro sob uma lista
     filtrada é número errado sem erro.
  3. **A coleção compõe com os outros filtros** em vez de substituí-los.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.banco import consultas

from .fake_postgrest import FakeCliente

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def modos_aceitos_pelo_banco() -> set[str]:
    """Os valores que o CHECK de `extraido_por` aceita, lidos da migration mais
    recente que o define — a 0033 hoje, outra amanhã."""
    padrao = re.compile(r"extraido_por\s+IN\s*\(([^)]*)\)", re.IGNORECASE)
    achados: list[tuple[str, str]] = []
    for arquivo in sorted(MIGRATIONS.glob("*.sql")):
        if arquivo.name.endswith(".down.sql"):
            continue
        for lista in padrao.findall(arquivo.read_text(encoding="utf-8")):
            achados.append((arquivo.name, lista))
    assert achados, "nenhuma migration define o CHECK de extraido_por"
    _, ultima = achados[-1]
    return set(re.findall(r"'([^']+)'", ultima))


def questao(id_: str, *, extraido_por: str, ano: int = 2019, vestibular: str = "ITA") -> dict:
    return {
        "id": id_,
        "vestibular": vestibular,
        "ano": ano,
        "fase": 1,
        "materia": "Matemática",
        "numero": int(id_.rsplit("q", 1)[-1]),
        "dissertativa": False,
        "enunciado_md": "…",
        "gabarito": None,
        "gabarito_origem": None,
        "gabarito_confianca": None,
        "imagem_url": None,
        "usa_imagem_no_render": False,
        "resolucao_url": None,
        "resolucao_md": None,
        "resolucao_origem": None,
        "extraido_por": extraido_por,
        "revisado": False,
    }


ACERVO = [
    questao("recente_q01", extraido_por="pipeline", ano=2019),
    questao("recente_q02", extraido_por="pipeline", ano=2021),
    questao("recente_q03", extraido_por="pipeline", ano=2022, vestibular="IME"),
    questao("arquivo_q04", extraido_por="pagina", ano=2011),
    questao("arquivo_q05", extraido_por="pagina", ano=2009, vestibular="IME"),
    # O piloto de 1973: página escaneada lida por visão. Fica no Arquivo por
    # decisão de 02/09 — ver o comentário de `MODOS_DA_COLECAO`.
    questao("piloto_q06", extraido_por="visao", ano=1973),
]


@pytest.fixture
def cliente() -> FakeCliente:
    return FakeCliente(
        {
            "questao_vestibular": {q["id"]: dict(q) for q in ACERVO},
            "questao_vestibular_topico": {},
            "topico_taxonomia": {},
        }
    )


def ids(pagina) -> set[str]:
    return {q.id for q in pagina.questoes}


# ─── 1 · A partição é total e disjunta ───────────────────────────────────


def test_toda_questao_do_acervo_cabe_em_exatamente_uma_colecao():
    """A trava que impede um lote de sumir da navegação sem aviso."""
    cobertos = [m for modos in consultas.MODOS_DA_COLECAO.values() for m in modos]

    assert set(cobertos) == modos_aceitos_pelo_banco()
    assert len(cobertos) == len(set(cobertos)), "um modo em duas coleções"


def test_o_piloto_de_1973_esta_no_arquivo():
    """'visao' é página inteira e acervo antigo, como 'pagina'. Deixá-lo fora
    das duas coleções o tornaria inalcançável pela tela."""
    assert "visao" in consultas.MODOS_DA_COLECAO["arquivo"]


# ─── 2 · O filtro alcança o total ────────────────────────────────────────


def test_recentes_traz_so_o_recorte_da_questao(cliente):
    pagina = consultas.listar_questoes(cliente, consultas.FiltrosQuestoes(colecao="recentes"))

    assert ids(pagina) == {"recente_q01", "recente_q02", "recente_q03"}
    assert pagina.total == 3


def test_arquivo_traz_pagina_inteira_e_o_piloto(cliente):
    pagina = consultas.listar_questoes(cliente, consultas.FiltrosQuestoes(colecao="arquivo"))

    assert ids(pagina) == {"arquivo_q04", "arquivo_q05", "piloto_q06"}
    assert pagina.total == 3


def test_sem_colecao_traz_o_acervo_inteiro(cliente):
    pagina = consultas.listar_questoes(cliente, consultas.FiltrosQuestoes())

    assert len(pagina.questoes) == 6
    assert pagina.total == 6


def test_o_total_segue_a_colecao_e_nao_o_acervo(cliente):
    """O "N questões" da tela sai daqui. Se `total` ignorasse a coleção, a
    lista mostraria 3 cartões sob a legenda "6 questões"."""
    recentes = consultas.listar_questoes(
        cliente, consultas.FiltrosQuestoes(colecao="recentes", por_pagina=2)
    )

    assert len(recentes.questoes) == 2
    assert recentes.total == 3


# ─── 3 · Compõe com os outros filtros ────────────────────────────────────


def test_colecao_e_vestibular_se_combinam(cliente):
    pagina = consultas.listar_questoes(
        cliente, consultas.FiltrosQuestoes(colecao="arquivo", vestibular="IME")
    )

    assert ids(pagina) == {"arquivo_q05"}
    assert pagina.total == 1


def test_paginar_dentro_da_colecao_nao_repete_nem_perde(cliente):
    """A ordem é total (`ano desc, numero, id`), então a virada de página não
    embaralha os empates — é o que o `.order("id")` de `listar_questoes` compra."""
    primeira = consultas.listar_questoes(
        cliente, consultas.FiltrosQuestoes(colecao="recentes", pagina=1, por_pagina=2)
    )
    segunda = consultas.listar_questoes(
        cliente, consultas.FiltrosQuestoes(colecao="recentes", pagina=2, por_pagina=2)
    )

    assert ids(primeira) & ids(segunda) == set()
    assert ids(primeira) | ids(segunda) == {"recente_q01", "recente_q02", "recente_q03"}
    # Ano decrescente: 2022, 2021 na primeira página; 2019 sobra para a segunda.
    assert [q.ano for q in primeira.questoes] == [2022, 2021]
