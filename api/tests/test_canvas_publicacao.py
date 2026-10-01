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
    """O que `_publicar_uma` e `_rependurar` chamam. Sem `paginas`, o curso não
    tem página da aula e o caminho é o de criar."""

    def __init__(
        self,
        *,
        modulos: list[dict],
        itens: dict[str, list[dict]],
        quebra_modulos=False,
        paginas: list[dict] | None = None,
        corpos: dict[str, str] | None = None,
    ):
        self.modulos, self.itens, self.quebra_modulos = list(modulos), dict(itens), quebra_modulos
        self.paginas, self.corpos = paginas or [], corpos or {}
        self.pendurados: list[dict] = []
        self.modulos_criados: list[dict] = []
        self.paginas_atualizadas: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False

    async def listar_paginas(self, *_a: Any, **_k: Any) -> list[dict]:
        return self.paginas

    async def obter_pagina(self, _curso: str, slug: str) -> dict:
        titulo = next((p["title"] for p in self.paginas if p["url"] == slug), "?")
        return {"url": slug, "title": titulo, "body": self.corpos.get(slug, "")}

    async def atualizar_pagina(self, _curso: str, slug: str, *, corpo: str) -> dict:
        self.paginas_atualizadas.append(slug)
        return {"url": slug}

    async def criar_pagina(self, _curso: str, *, titulo: str, corpo: str) -> dict:
        return {"url": "slug-novo", "html_url": "https://canvas/x", "title": titulo}

    async def listar_modulos(self, _curso: str) -> list[dict]:
        if self.quebra_modulos:
            raise RuntimeError("Canvas fora do ar")
        return self.modulos

    async def listar_itens_modulo(self, _curso: str, modulo_id: str) -> list[dict]:
        return self.itens.get(str(modulo_id), [])

    async def criar_modulo(self, _curso: str, *, nome: str, publicado: bool) -> dict:
        criado = {"id": 9001, "name": nome, "published": publicado}
        self.modulos_criados.append(criado)
        self.modulos.append(criado)
        return criado

    async def criar_item_modulo(self, _curso, modulo_id, *, titulo, page_url, posicao=None):
        self.pendurados.append(
            {"modulo": str(modulo_id), "titulo": titulo, "posicao": posicao, "page_url": page_url}
        )
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


def _criar(
    canvas: Any,
    *,
    modulo_padrao_id: str | None,
    modulo_generico_id: str | None = None,
    simular: bool = False,
    titulo: str | None = None,
) -> dict:
    import asyncio

    aula = _db(ligado=True)["aula_gravacao"]["a1"]
    if titulo is not None:
        aula["titulo"] = titulo
    return asyncio.run(
        canvas_publicacao._publicar_uma(
            canvas, aula, simular=simular,
            modulo_padrao_id=modulo_padrao_id, modulo_generico_id=modulo_generico_id,
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


#  ─── Módulo genérico: último recurso ───────────────────────────────────────
#
# Antes, quando nada decidia, a página ficava fora de módulo — e 'publicado' é
# terminal, então ficava assim para sempre. Desde 30/09/2026 vai para
# "Outras aulas gravadas", publicado, um por curso.


def test_sem_modulo_possivel_cria_o_generico_publicado_e_pendura() -> None:
    c = _CanvasFalso(modulos=_MODULOS, itens=_ITENS)
    r = _criar(c, modulo_padrao_id=None)
    assert r["canvas_estado"] == "publicado"
    assert r["canvas_modulo_nome"] == "Outras aulas gravadas"
    assert len(c.modulos_criados) == 1
    # Despublicado, a aula sumiria para o aluno do mesmo jeito.
    assert c.modulos_criados[0]["published"] is True
    assert c.pendurados[0]["modulo"] == "9001"
    # O curso precisa guardar o id, senão a próxima aula cria outro.
    assert r["_modulo_generico_id"] == "9001"
    # O motivo vira a dica do selo para quem vai arrastar.
    assert "Outras aulas gravadas" in r["canvas_erro"]


def test_generico_existente_pelo_nome_e_adotado_sem_criar_outro() -> None:
    """Cobre o POST que estourou o timeout depois de criar, e o módulo que
    alguém da coordenação criou à mão."""
    modulos = [*_MODULOS, {"id": 777, "name": "OUTRAS AULAS GRAVADAS"}]
    c = _CanvasFalso(modulos=modulos, itens=_ITENS)
    r = _criar(c, modulo_padrao_id=None)
    assert c.modulos_criados == []
    assert c.pendurados[0]["modulo"] == "777"
    assert r["_modulo_generico_id"] == "777"


def test_generico_renomeado_continua_valendo_pelo_id() -> None:
    modulos = [*_MODULOS, {"id": 777, "name": "Aulas avulsas"}]
    c = _CanvasFalso(modulos=modulos, itens=_ITENS)
    r = _criar(c, modulo_padrao_id=None, modulo_generico_id="777")
    assert c.modulos_criados == []
    assert r["canvas_modulo_nome"] == "Aulas avulsas"
    # Já está guardado; nada a regravar.
    assert "_modulo_generico_id" not in r


def test_padrao_vem_antes_do_generico() -> None:
    """Física e Química não têm assunto na conferência: TODA aula delas cai no
    padrão. Trocar o padrão pelo genérico foi recusado em 30/09/2026."""
    modulos = [*_MODULOS, {"id": 777, "name": "Outras aulas gravadas"}]
    c = _CanvasFalso(modulos=modulos, itens=_ITENS)
    r = _criar(c, modulo_padrao_id="2738", modulo_generico_id="777")
    assert r["canvas_modulo_nome"] == "Aulas - Física 2"
    assert r["canvas_erro"] is None


def test_padrao_apagado_cai_no_generico() -> None:
    c = _CanvasFalso(modulos=_MODULOS, itens=_ITENS)
    r = _criar(c, modulo_padrao_id="9999")
    assert r["canvas_modulo_nome"] == "Outras aulas gravadas"
    assert "9999" in r["canvas_erro"]


_TRILHAS = [
    {"id": 1, "name": "Aulas - Trigonometria"},
    {"id": 2, "name": "Aulas - Números Complexos"},
]


def test_assunto_em_dois_modulos_cai_no_generico() -> None:
    itens = {
        "1": [{"title": "Aula 01 - 03/08/2026 - Complexos: Revisão", "position": 1}],
        "2": [{"title": "Aula 02 - 05/08/2026 - Complexos: Forma Algébrica", "position": 1}],
    }
    c = _CanvasFalso(modulos=_TRILHAS, itens=itens)
    r = _criar(c, modulo_padrao_id=None, titulo="Aula 09 - 27/08/2026 - Complexos: Raízes")
    assert r["canvas_modulo_nome"] == "Outras aulas gravadas"
    assert "mais de um módulo" in r["canvas_erro"]


def test_generico_nao_puxa_aula_quando_a_trilha_existe() -> None:
    """A primeira aula de Geometria caiu no genérico; depois a coordenação
    criou a trilha. A aula seguinte tem que ir para a trilha, e não empatar
    com o genérico (que faria cair nele de novo)."""
    modulos = [*_TRILHAS, {"id": 3, "name": "Aulas - Geometria"},
               {"id": 777, "name": "Outras aulas gravadas"}]
    itens = {
        "3": [{"title": "Aula 10 - 01/09/2026 - Geometria: Ângulos", "position": 1}],
        "777": [{"title": "Aula 09 - 27/08/2026 - Geometria: Retas", "position": 1}],
    }
    c = _CanvasFalso(modulos=modulos, itens=itens)
    r = _criar(c, modulo_padrao_id=None, titulo="Aula 11 - 27/08/2026 - Geometria: Triângulos")
    assert r["canvas_modulo_nome"] == "Aulas - Geometria"


# ─── Página do professor: registrar onde ela já está ────────────────────────
#
# Antes, embutir numa página existente não registrava módulo nenhum, e a tela
# mostrava como "fora de módulo" toda aula cuja página o professor já tinha
# pendurado.

_PAGINA_PROF = {
    "url": "aula-07-27-08-2026", "title": "AULA 7 - 27/08/2026 - Ondas",
    "html_url": "https://canvas/p7", "created_at": "2026-08-20T00:00:00Z",
}


def test_embutir_em_pagina_ja_pendurada_so_registra_o_modulo() -> None:
    itens = {"2738": [*_ITENS["2738"],
                      {"title": _PAGINA_PROF["title"], "position": 8,
                       "page_url": _PAGINA_PROF["url"]}]}
    c = _CanvasFalso(modulos=_MODULOS, itens=itens, paginas=[_PAGINA_PROF])
    r = _criar(c, modulo_padrao_id="2738")
    assert c.paginas_atualizadas == [_PAGINA_PROF["url"]]
    assert r["canvas_modulo_nome"] == "Aulas - Física 2"
    assert c.pendurados == [], "pendurar de novo duplicaria o item"


def test_embutir_em_pagina_solta_pendura_ela() -> None:
    c = _CanvasFalso(modulos=_MODULOS, itens=_ITENS, paginas=[_PAGINA_PROF])
    r = _criar(c, modulo_padrao_id="2738")
    assert r["canvas_modulo_nome"] == "Aulas - Física 2"
    assert c.pendurados[0]["page_url"] == _PAGINA_PROF["url"]
    # O título do item é o da página do professor, não um inventado.
    assert c.pendurados[0]["titulo"] == _PAGINA_PROF["title"]


def test_ensaio_nao_pendura_pagina_que_ja_tem_o_video() -> None:
    corpos = {_PAGINA_PROF["url"]: '<iframe src="https://www.youtube.com/embed/abc123">'}
    c = _CanvasFalso(modulos=_MODULOS, itens=_ITENS, paginas=[_PAGINA_PROF], corpos=corpos)
    _criar(c, modulo_padrao_id="2738", simular=True)
    assert c.pendurados == []
    assert c.modulos_criados == []


# ─── Segunda fase: o que já está publicado e fora de módulo ─────────────────


def _db_orfa(*, slug: str | None = "slug-velho", modulo: str | None = None) -> dict:
    db = _db(ligado=True, canvas_estado="publicado")
    db["aula_gravacao"]["a1"].update(
        {"canvas_pagina_slug": slug, "canvas_modulo_nome": modulo, "canvas_erro": "página fora de módulo: x"}
    )
    return db


def _usar_canvas(monkeypatch: pytest.MonkeyPatch, canvas: _CanvasFalso) -> None:
    monkeypatch.setattr(canvas_publicacao, "ClienteCanvas", lambda **_k: canvas)


def test_orfa_publicada_ganha_modulo_e_curso_guarda_o_generico(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _db_orfa()
    pagina = {"url": "slug-velho", "title": "Aula 07 - 27/08/2026"}
    c = _CanvasFalso(modulos=_MODULOS, itens=_ITENS, paginas=[pagina])
    _usar_canvas(monkeypatch, c)
    r = canvas_publicacao.varrer(FakeCliente(db))
    linha = db["aula_gravacao"]["a1"]
    # Curso sem padrão nos dados de teste: vai para o genérico.
    assert linha["canvas_modulo_nome"] == "Outras aulas gravadas"
    assert linha["canvas_estado"] == "publicado"
    assert db["curso_monitorado_gravacao"]["692"]["canvas_modulo_generico_id"] == "9001"
    assert len(r["rependuradas"]) == 1


def test_orfa_que_ja_estava_em_modulo_so_e_anotada(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _db_orfa()
    pagina = {"url": "slug-velho", "title": "Aula 07 - 27/08/2026"}
    itens = {"2738": [{"title": pagina["title"], "position": 3, "page_url": "slug-velho"}]}
    c = _CanvasFalso(modulos=_MODULOS, itens=itens, paginas=[pagina])
    _usar_canvas(monkeypatch, c)
    canvas_publicacao.varrer(FakeCliente(db))
    linha = db["aula_gravacao"]["a1"]
    assert linha["canvas_modulo_nome"] == "Aulas - Física 2"
    assert linha["canvas_erro"] is None
    assert c.pendurados == [] and c.modulos_criados == []


def test_aula_com_modulo_ou_sem_slug_nao_e_rependurada(sem_canvas: None) -> None:
    for db in (_db_orfa(modulo="Aulas - Física 2"), _db_orfa(slug=None)):
        assert canvas_publicacao.varrer(FakeCliente(db))["rependuradas"] == []


def test_ensaio_nao_rependura(sem_canvas: None) -> None:
    db = _db_orfa()
    r = canvas_publicacao.varrer(FakeCliente(db), simular=True)
    assert r["rependuradas"] == []
    assert db["aula_gravacao"]["a1"]["canvas_modulo_nome"] is None
