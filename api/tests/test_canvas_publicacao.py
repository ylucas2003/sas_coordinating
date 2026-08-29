"""A varredura que escreve no Canvas — o único módulo do projeto que faz PUT
num curso com ~900 alunos.

O que estes testes travam é a passagem do interruptor: `publicar_no_canvas`
nasce desligado em todo curso, e a migration 0035 manda ligar um por vez
DEPOIS de conferir o ensaio. Todo o valor dessa ordem depende de duas coisas
que já estiveram quebradas — a aula continuar elegível enquanto o curso está
desligado, e o ensaio ter o que mostrar.
"""

from typing import Any

import pytest

from app.gravacoes_aula import canvas_publicacao
from tests.fake_postgrest import FakeCliente


def _db(*, ligado: bool, canvas_estado: str = "pendente", tentativas: int = 0) -> dict:
    return {
        "curso_monitorado_gravacao": {
            "692": {"curso_id": "692", "nome": "Física", "publicar_no_canvas": ligado},
        },
        "aula_gravacao": {
            "a1": {
                "id": "a1",
                "curso_id": "692",
                "conferencia_id": 1,
                "titulo": "Física - Prof. Renan - AULA 7",
                "iniciada_em": "2026-08-27T20:23:00+00:00",
                "youtube_video_id": "abc123",
                "youtube_titulo": "SAS ITA/IME 2026 - Prof Renan - Aula 7 (27/08/2026)",
                "canvas_estado": canvas_estado,
                "canvas_tentativas": tentativas,
            },
        },
    }


@pytest.fixture
def sem_canvas(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum teste aqui pode encostar no Canvas de verdade."""

    def explode(*_a: Any, **_k: Any) -> None:
        raise AssertionError("a varredura não devia ter chamado o Canvas neste caso")

    monkeypatch.setattr(canvas_publicacao, "ClienteCanvas", explode)


def test_curso_desligado_nao_toca_no_canvas(sem_canvas: None) -> None:
    r = canvas_publicacao.varrer(FakeCliente(_db(ligado=False)))
    assert r["analisadas"] == 0


def test_curso_desligado_NAO_carimba_a_aula(sem_canvas: None) -> None:
    """O ponto de todo este arquivo.

    A varredura antes marcava `canvas_estado='ignorado'`, e 'ignorado' ficava
    fora dos retentáveis. Resultado: a primeira rodada horária tirava a aula do
    pool para sempre, e ligar o curso depois não publicava nada — em silêncio.
    """
    db = _db(ligado=False)
    canvas_publicacao.varrer(FakeCliente(db))
    assert db["aula_gravacao"]["a1"]["canvas_estado"] == "pendente"


def test_ligar_o_curso_depois_recupera_a_aula(monkeypatch: pytest.MonkeyPatch) -> None:
    """Passa a rodada com o curso desligado, liga, e a aula tem que voltar."""
    db = _db(ligado=False)
    canvas_publicacao.varrer(FakeCliente(db))  # rodada com o curso desligado

    db["curso_monitorado_gravacao"]["692"]["publicar_no_canvas"] = True
    vistas: list[str] = []
    monkeypatch.setattr(
        canvas_publicacao,
        "_publicar_uma",
        _fake_publicar(vistas),
    )
    r = canvas_publicacao.varrer(FakeCliente(db))
    assert vistas == ["a1"], "a aula tinha que voltar ao pool ao ligar o curso"
    assert r["analisadas"] == 1


def test_aula_ja_carimbada_ignorado_e_resgatada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resgate do que a versão anterior já carimbou em produção."""
    db = _db(ligado=True, canvas_estado="ignorado")
    vistas: list[str] = []
    monkeypatch.setattr(canvas_publicacao, "_publicar_uma", _fake_publicar(vistas))
    canvas_publicacao.varrer(FakeCliente(db))
    assert vistas == ["a1"]


def test_ensaio_enxerga_curso_desligado(monkeypatch: pytest.MonkeyPatch) -> None:
    """`?simular=true` é o que se roda ANTES de ligar — com o curso desligado
    ele precisa ter o que mostrar, senão o ritual da migration não existe."""
    db = _db(ligado=False)
    vistas: list[str] = []
    monkeypatch.setattr(canvas_publicacao, "_publicar_uma", _fake_publicar(vistas))
    r = canvas_publicacao.varrer(FakeCliente(db), simular=True)
    assert vistas == ["a1"]
    assert r["simulado"] is True


def test_ensaio_nao_escreve_no_banco(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _db(ligado=True)
    monkeypatch.setattr(canvas_publicacao, "_publicar_uma", _fake_publicar([]))
    canvas_publicacao.varrer(FakeCliente(db), simular=True)
    assert db["aula_gravacao"]["a1"]["canvas_estado"] == "pendente"
    assert db["aula_gravacao"]["a1"]["canvas_tentativas"] == 0


def test_ambiguo_e_conflito_nao_sao_retentados(sem_canvas: None) -> None:
    """São decisões de "não escrever" que pedem gente olhando."""
    for estado in ("ambiguo", "conflito"):
        db = _db(ligado=True, canvas_estado=estado)
        assert canvas_publicacao.varrer(FakeCliente(db))["analisadas"] == 0, estado


def test_teto_de_tentativas_tira_a_aula_do_pool(sem_canvas: None) -> None:
    db = _db(ligado=True, canvas_estado="falhou", tentativas=3)
    assert canvas_publicacao.varrer(FakeCliente(db))["analisadas"] == 0


def test_falha_incrementa_tentativas(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _db(ligado=True)

    async def falha(*_a: Any, **_k: Any) -> dict:
        raise RuntimeError("Canvas fora do ar")

    monkeypatch.setattr(canvas_publicacao, "_publicar_uma", falha)
    canvas_publicacao.varrer(FakeCliente(db))
    linha = db["aula_gravacao"]["a1"]
    assert linha["canvas_estado"] == "falhou"
    assert linha["canvas_tentativas"] == 1


def test_varredura_nao_escreve_atualizado_em(monkeypatch: pytest.MonkeyPatch) -> None:
    """`atualizado_em` é o relógio do corte por esfriamento do pipeline de
    vídeo; carimbá-lo aqui esquentaria aula que já esfriou."""
    db = _db(ligado=True)
    monkeypatch.setattr(canvas_publicacao, "_publicar_uma", _fake_publicar([]))
    canvas_publicacao.varrer(FakeCliente(db))
    assert "atualizado_em" not in db["aula_gravacao"]["a1"]


def _fake_publicar(vistas: list[str]):
    async def _publicar(_canvas: Any, aula: dict, **_kw: Any) -> dict:
        vistas.append(aula["id"])
        return {"canvas_estado": "publicado", "canvas_pagina_url": "https://canvas/x"}

    return _publicar


# ─── Pendurar no módulo ─────────────────────────────────────────────────────
#
# Criar a página e pendurá-la são chamadas separadas no Canvas. A automação
# fazia só a primeira, e as quatro páginas de 29/08/2026 nasceram publicadas e
# fora de módulo: existiam, e o aluno não achava.


class _CanvasFalso:
    """Só o que `_publicar_uma` chama no caminho de criar página."""

    def __init__(self, *, modulos: list[dict], itens: dict[str, list[dict]], quebra_modulos=False):
        self.modulos, self.itens, self.quebra_modulos = modulos, itens, quebra_modulos
        self.pendurados: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False

    async def listar_paginas(self, *_a: Any, **_k: Any) -> list[dict]:
        return []

    async def criar_pagina(self, _curso: str, *, titulo: str, corpo: str) -> dict:
        return {"url": "slug-novo", "html_url": "https://canvas/x", "title": titulo}

    async def listar_modulos(self, _curso: str) -> list[dict]:
        if self.quebra_modulos:
            raise RuntimeError("Canvas fora do ar")
        return self.modulos

    async def listar_itens_modulo(self, _curso: str, modulo_id: str) -> list[dict]:
        return self.itens.get(str(modulo_id), [])

    async def criar_item_modulo(self, _curso, modulo_id, *, titulo, page_url, posicao=None):
        self.pendurados.append({"modulo": str(modulo_id), "titulo": titulo, "posicao": posicao})
        return {"id": 1, "position": posicao or 99}


_MODULOS = [{"id": 2738, "name": "Aulas - Física 2"}]
_ITENS = {
    "2738": [
        {"title": "Aula 05 - 20/08/2026 - Movimento Circular", "position": 5},
        {"title": "Aula 06 - 21/08/2026 - MCUV e Aceleração angular", "position": 6},
        {"title": "Aula 07 - 15/04/2026 - 2ª Lei da Termodinâmica", "position": 7},
    ]
}


@pytest.fixture(autouse=True)
def _youtube_diz_unlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    """O guard de privacidade abre o YouTube antes de escrever. Nos testes ele
    responde 'unlisted' — o caminho 'private' tem teste próprio."""
    monkeypatch.setattr(
        canvas_publicacao.publicador_youtube, "privacidade", lambda _v: "unlisted"
    )


def _criar(canvas: Any, *, modulo_padrao_id: str | None) -> dict:
    import asyncio

    aula = _db(ligado=True)["aula_gravacao"]["a1"]
    return asyncio.run(
        canvas_publicacao._publicar_uma(
            canvas, aula, simular=False, modulo_padrao_id=modulo_padrao_id
        )
    )


def test_criar_pagina_tambem_pendura_no_modulo() -> None:
    c = _CanvasFalso(modulos=_MODULOS, itens=_ITENS)
    r = _criar(c, modulo_padrao_id="2738")
    assert r["canvas_estado"] == "publicado"
    assert r["canvas_modulo_nome"] == "Aulas - Física 2"
    assert len(c.pendurados) == 1
    # Depois da Aula 06 (21/08) — NÃO no fim, depois do bloco de abril.
    assert c.pendurados[0]["posicao"] == 7


def test_falha_ao_pendurar_nao_derruba_a_publicacao() -> None:
    """A página já existe e já tem o vídeo. Perder a publicação porque a
    listagem de módulos falhou trocaria um problema pequeno (arrastar a página)
    por um grande — a gravação some do Canvas em ~7 dias."""
    c = _CanvasFalso(modulos=[], itens={}, quebra_modulos=True)
    r = _criar(c, modulo_padrao_id="2738")
    assert r["canvas_estado"] == "publicado"
    assert r["canvas_pagina_url"]
    assert r["canvas_modulo_nome"] is None
    assert "fora de módulo" in r["canvas_erro"]


def test_sem_modulo_possivel_publica_e_avisa() -> None:
    c = _CanvasFalso(modulos=_MODULOS, itens=_ITENS)
    r = _criar(c, modulo_padrao_id=None)
    assert r["canvas_estado"] == "publicado"
    assert r["canvas_modulo_nome"] is None
    assert "fora de módulo" in r["canvas_erro"]
    assert c.pendurados == []
