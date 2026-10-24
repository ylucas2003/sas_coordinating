"""Horário de estudos (`app/horario_estudos.py`, docs/42).

O que este arquivo trava, em ordem de gravidade:

  1. **Um aluno não alcança o bloco de outro.** É dado pessoal de menor, e a
     rota edita e apaga por uuid. Filtro esquecido em PATCH ou DELETE não dá erro
     nenhum: um aluno apagaria o horário de outro. Bloco alheio tem de se
     comportar EXATAMENTE como bloco inexistente.
  2. **Criar vários dias é tudo ou nada.** O backend não tem transação; a
     proteção é validar a semana inteira ANTES do insert e escrever num INSERT
     só. Com um insert por dia, "seg a sex" falharia na quarta deixando segunda
     e terça criadas.
  3. **Sobreposição é recusada, e encostar não é sobrepor.** O banco não tem
     trava (um EXCLUDE pede `btree_gist`); é aqui que o erro "duas coisas às
     19h" é pego.
  4. **Nenhuma rota sai sem `get_current_aluno`.** Não existe visão da
     coordenação (docs/42 §0, decisão 4), e o jeito de ela aparecer por acidente
     é uma rota nova copiada sem o guard.
  5. **O horário volta como `"19:00"`**, nunca como o `"19:00:00"` do PostgREST.

Rodar:  cd api && ./.venv/bin/python -m pytest tests/test_horario_estudos.py -q
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app import horario_estudos as regras
from app.auth import get_current_aluno
from app.horario_estudos import (
    BlocoInexistente,
    BlocoInvalido,
    ConflitoDeHorario,
    hora_de,
    minutos_de,
    sobrepoe,
)

from .fake_postgrest import FakeCliente

ANA = "aluno-ana"
BIA = "aluno-bia"
TABELA = "bloco_horario_estudo"


def _banco(*blocos: dict) -> dict:
    return {TABELA: {b["id"]: dict(b) for b in blocos}}


def _bloco(id_: str, aluno: str, dia: int, hora: str, duracao: int, rotulo: str) -> dict:
    return {
        "id": id_,
        "aluno_id": aluno,
        "dia_semana": dia,
        "hora_inicio": hora,
        "duracao_minutos": duracao,
        "rotulo": rotulo,
    }


def _linhas(db: dict, aluno: str | None = None) -> list[dict]:
    todas = list(db.setdefault(TABELA, {}).values())
    return [b for b in todas if aluno is None or b["aluno_id"] == aluno]


# ─── Regras puras ────────────────────────────────────────────────────────


def test_minutos_aceita_as_duas_formas_da_hora():
    # "19:00:00" é o que o PostgREST devolve para uma coluna `time`.
    assert minutos_de("19:00") == 1140
    assert minutos_de("19:00:00") == 1140
    assert minutos_de("9:05") == 545
    assert minutos_de("00:00") == 0
    assert minutos_de("23:59") == 1439


@pytest.mark.parametrize("ruim", ["", "19h", "25:00", "19:60", "19:00:30", "abc", "19:0"])
def test_hora_malformada_e_recusada(ruim):
    with pytest.raises(BlocoInvalido):
        minutos_de(ruim)


def test_hora_de_volta_sempre_em_hh_mm():
    assert hora_de(1140) == "19:00"
    assert hora_de(545) == "09:05"
    assert hora_de(0) == "00:00"


def test_encostar_nao_e_sobrepor():
    """18:00–19:00 e 19:00–20:30 convivem: é como se monta uma tarde em sequência."""
    assert not sobrepoe(1080, 60, 1140, 90)
    assert not sobrepoe(1140, 90, 1080, 60)


def test_cruzar_e_sobrepor_nos_dois_sentidos_e_no_contido():
    assert sobrepoe(1140, 90, 1170, 60)      # começa dentro
    assert sobrepoe(1170, 60, 1140, 90)      # o inverso
    assert sobrepoe(1140, 120, 1170, 30)     # um contém o outro
    assert sobrepoe(1170, 30, 1140, 120)
    assert sobrepoe(1140, 90, 1140, 90)      # iguais


# ─── Criar ───────────────────────────────────────────────────────────────


def test_criar_cria_um_bloco_por_dia_e_devolve_so_os_criados():
    db = _banco()
    criados = regras.criar(FakeCliente(db), ANA, [1, 2, 3, 4, 5], "19:00", 90, "Termodinâmica")

    assert [b.diaSemana for b in criados] == [1, 2, 3, 4, 5]
    assert {b.horaInicio for b in criados} == {"19:00"}
    assert {b.rotulo for b in criados} == {"Termodinâmica"}
    assert len(_linhas(db, ANA)) == 5
    # O dono sai do argumento (que vem do token), nunca do corpo.
    assert {b["aluno_id"] for b in _linhas(db)} == {ANA}


def test_criar_varios_dias_e_um_insert_so(monkeypatch):
    """⚠️ É a atomicidade: o PostgREST executa um INSERT de várias linhas como um
    comando só. Se este número virar 5, "seg a sex" volta a poder falhar na
    quarta com segunda e terça já gravadas."""
    from tests import fake_postgrest

    chamadas = []
    original = fake_postgrest.Tabela.insert

    def contando(self, json, **kw):
        chamadas.append(json)
        return original(self, json, **kw)

    monkeypatch.setattr(fake_postgrest.Tabela, "insert", contando)

    regras.criar(FakeCliente(_banco()), ANA, [1, 2, 3, 4, 5], "19:00", 90, "Estudo")

    assert len(chamadas) == 1
    assert len(chamadas[0]) == 5


def test_criar_e_tudo_ou_nada_quando_um_dia_cruza():
    """A quarta já tem bloco às 19h. Nem segunda nem terça podem ter sido criadas."""
    db = _banco(_bloco("b1", ANA, 3, "19:00", 90, "Análise combinatória"))

    with pytest.raises(ConflitoDeHorario):
        regras.criar(FakeCliente(db), ANA, [1, 2, 3, 4, 5], "19:30", 60, "Revisão")

    assert [b["id"] for b in _linhas(db)] == ["b1"]


def test_conflito_diz_qual_dia_e_qual_bloco():
    db = _banco(_bloco("b1", ANA, 2, "19:00", 90, "Estequiometria"))

    with pytest.raises(ConflitoDeHorario) as erro:
        regras.criar(FakeCliente(db), ANA, [2], "20:00", 60, "Outra coisa")

    frase = str(erro.value)
    assert "Terça-feira" in frase
    assert "Estequiometria" in frase
    assert "19:00" in frase and "20:30" in frase


def test_blocos_que_se_encostam_podem_coexistir():
    db = _banco(_bloco("b1", ANA, 4, "18:00", 60, "Redação"))

    criados = regras.criar(FakeCliente(db), ANA, [4], "19:00", 90, "Revisar meus erros")

    assert len(criados) == 1
    assert len(_linhas(db, ANA)) == 2


def test_o_horario_de_outro_aluno_nao_conflita():
    """A sobreposição é dentro da semana de UM aluno. Se a Bia ocupasse a terça
    às 19h para a Ana, a ferramenta seria uma fila compartilhada."""
    db = _banco(_bloco("b1", BIA, 2, "19:00", 90, "Da Bia"))

    criados = regras.criar(FakeCliente(db), ANA, [2], "19:00", 90, "Da Ana")

    assert len(criados) == 1


def test_dias_repetidos_viram_um_bloco_so():
    db = _banco()
    criados = regras.criar(FakeCliente(db), ANA, [3, 3, 1, 3], "19:00", 60, "Estudo")

    assert [b.diaSemana for b in criados] == [1, 3]


def test_sem_nenhum_dia_e_recusado():
    with pytest.raises(BlocoInvalido):
        regras.criar(FakeCliente(_banco()), ANA, [], "19:00", 60, "Estudo")


@pytest.mark.parametrize(
    ("dias", "hora", "duracao", "rotulo"),
    [
        ([0], "19:00", 60, "Estudo"),                # dia fora de 1–7
        ([8], "19:00", 60, "Estudo"),
        ([True], "19:00", 60, "Estudo"),             # bool é int em Python
        ([1], "19:00", 14, "Estudo"),                # abaixo do mínimo
        ([1], "19:00", 481, "Estudo"),               # acima do máximo
        ([1], "23:30", 60, "Estudo"),                # atravessa a meia-noite
        ([1], "19:00", 60, ""),                      # sem rótulo
        ([1], "19:00", 60, "   "),                   # só espaço
        ([1], "19:00", 60, "x" * 81),                # rótulo longo demais
        ([1], "7pm", 60, "Estudo"),                  # hora fora do formato
    ],
)
def test_valores_que_nao_fazem_sentido_sao_recusados(dias, hora, duracao, rotulo):
    db = _banco()
    with pytest.raises(BlocoInvalido):
        regras.criar(FakeCliente(db), ANA, dias, hora, duracao, rotulo)
    assert _linhas(db) == []


def test_o_limite_da_meia_noite_e_inclusivo():
    """23:00 + 60 min termina exatamente à meia-noite: cabe. 23:01 não."""
    db = _banco()
    regras.criar(FakeCliente(db), ANA, [1], "23:00", 60, "Última hora do dia")
    with pytest.raises(BlocoInvalido):
        regras.criar(FakeCliente(db), ANA, [2], "23:01", 60, "Passa")


def test_rotulo_e_aparado():
    db = _banco()
    criados = regras.criar(FakeCliente(db), ANA, [1], "19:00", 60, "  Eletrostática  ")
    assert criados[0].rotulo == "Eletrostática"
    assert _linhas(db)[0]["rotulo"] == "Eletrostática"


def test_o_teto_de_blocos_e_respeitado():
    existentes = [
        _bloco(f"b{i}", ANA, 1 + i // 12, hora_de(14 * 60 + (i % 12) * 30), 15, f"B{i}")
        for i in range(59)
    ]
    db = _banco(*existentes)

    with pytest.raises(ConflitoDeHorario) as erro:
        regras.criar(FakeCliente(db), ANA, [6, 7], "09:00", 60, "Passa do teto")
    assert "60" in str(erro.value)

    # Um só ainda cabe: 59 + 1 = 60.
    assert len(regras.criar(FakeCliente(db), ANA, [6], "09:00", 60, "Cabe")) == 1


# ─── Listar ──────────────────────────────────────────────────────────────


def test_listar_devolve_so_os_blocos_do_aluno_por_dia_e_hora():
    db = _banco(
        _bloco("b1", ANA, 4, "19:15", 90, "Revisar meus erros"),
        _bloco("b2", ANA, 1, "19:00:00", 90, "Termodinâmica"),   # o formato do banco
        _bloco("b3", BIA, 1, "08:00", 60, "Da Bia"),
        _bloco("b4", ANA, 4, "18:00", 60, "Redação"),
    )

    blocos = regras.listar(FakeCliente(db), ANA)

    assert [(b.diaSemana, b.horaInicio, b.rotulo) for b in blocos] == [
        (1, "19:00", "Termodinâmica"),     # "19:00:00" normalizado
        (4, "18:00", "Redação"),
        (4, "19:15", "Revisar meus erros"),
    ]


def test_quem_nao_tem_bloco_recebe_lista_vazia():
    """É o estado mais comum, e a tela o desenha primeiro."""
    assert regras.listar(FakeCliente(_banco()), ANA) == []


# ─── Atualizar ───────────────────────────────────────────────────────────


def test_mudar_so_o_rotulo_nao_conflita_com_o_proprio_bloco():
    db = _banco(_bloco("b1", ANA, 2, "19:00", 90, "Estequiometria"))

    novo = regras.atualizar(FakeCliente(db), ANA, "b1", rotulo="Química orgânica")

    assert novo.rotulo == "Química orgânica"
    # O que não veio não foi mexido.
    assert (novo.diaSemana, novo.horaInicio, novo.duracaoMinutos) == (2, "19:00", 90)


def test_editar_um_dia_nao_mexe_nos_outros():
    db = _banco(
        _bloco("seg", ANA, 1, "19:00", 90, "Estudo"),
        _bloco("qua", ANA, 3, "19:00", 90, "Estudo"),
    )

    regras.atualizar(FakeCliente(db), ANA, "qua", hora_inicio="20:00")

    por_id = {b["id"]: b for b in _linhas(db)}
    assert por_id["qua"]["hora_inicio"] == "20:00"
    assert por_id["seg"]["hora_inicio"] == "19:00"


def test_mover_para_cima_de_outro_bloco_e_recusado_e_nada_muda():
    db = _banco(
        _bloco("b1", ANA, 2, "19:00", 90, "Estequiometria"),
        _bloco("b2", ANA, 2, "21:00", 60, "Inglês"),
    )

    with pytest.raises(ConflitoDeHorario):
        regras.atualizar(FakeCliente(db), ANA, "b2", hora_inicio="20:00")

    assert {b["id"]: b["hora_inicio"] for b in _linhas(db)} == {"b1": "19:00", "b2": "21:00"}


def test_mover_de_dia_valida_no_dia_novo():
    db = _banco(
        _bloco("b1", ANA, 2, "19:00", 90, "Terça"),
        _bloco("b2", ANA, 3, "19:00", 90, "Quarta"),
    )

    with pytest.raises(ConflitoDeHorario):
        regras.atualizar(FakeCliente(db), ANA, "b1", dia_semana=3)


def test_editar_valida_o_bloco_como_ele_fica():
    """Só a duração veio, mas ela estoura a meia-noite SOBRE o início já gravado."""
    db = _banco(_bloco("b1", ANA, 2, "23:00", 60, "Tarde da noite"))

    with pytest.raises(BlocoInvalido):
        regras.atualizar(FakeCliente(db), ANA, "b1", duracao_minutos=90)


def test_editar_bloco_de_outro_aluno_e_como_bloco_inexistente():
    """⚠️ O teste da razão de ser do filtro por `aluno_id`."""
    db = _banco(_bloco("b1", BIA, 2, "19:00", 90, "Da Bia"))

    with pytest.raises(BlocoInexistente):
        regras.atualizar(FakeCliente(db), ANA, "b1", rotulo="Invadido")

    assert _linhas(db)[0]["rotulo"] == "Da Bia"


def test_editar_bloco_que_nao_existe():
    with pytest.raises(BlocoInexistente):
        regras.atualizar(FakeCliente(_banco()), ANA, "nao-existe", rotulo="x")


# ─── Apagar ──────────────────────────────────────────────────────────────


def test_apagar_tira_so_o_bloco_pedido():
    db = _banco(
        _bloco("b1", ANA, 2, "19:00", 90, "Estequiometria"),
        _bloco("b2", ANA, 3, "19:00", 90, "Outro"),
    )

    regras.apagar(FakeCliente(db), ANA, "b1")

    assert [b["id"] for b in _linhas(db)] == ["b2"]


def test_apagar_bloco_de_outro_aluno_nao_apaga_e_diz_inexistente():
    """⚠️ Só por `id`, a Ana apagaria o horário da Bia adivinhando um uuid."""
    db = _banco(_bloco("b1", BIA, 2, "19:00", 90, "Da Bia"))

    with pytest.raises(BlocoInexistente):
        regras.apagar(FakeCliente(db), ANA, "b1")

    assert [b["id"] for b in _linhas(db)] == ["b1"]


def test_apagar_duas_vezes_a_segunda_diz_inexistente():
    db = _banco(_bloco("b1", ANA, 2, "19:00", 90, "Estequiometria"))
    regras.apagar(FakeCliente(db), ANA, "b1")

    with pytest.raises(BlocoInexistente):
        regras.apagar(FakeCliente(db), ANA, "b1")


# ─── A fronteira HTTP ────────────────────────────────────────────────────


def _rotas(monkeypatch, db):
    from app.routes import horario_estudos as rotas

    monkeypatch.setattr(rotas, "get_supabase", lambda: FakeCliente(db))
    return rotas


USUARIO_ANA = {"aluno_id": ANA, "tipo": "aluno"}


def test_rota_criar_traduz_os_tres_tipos_de_recusa(monkeypatch):
    from app.schemas.horario_estudos import CriarBlocos

    db = _banco(_bloco("b1", ANA, 2, "19:00", 90, "Estequiometria"))
    rotas = _rotas(monkeypatch, db)

    def criar(**campos):
        corpo = CriarBlocos(
            **{"diasSemana": [2], "horaInicio": "19:30", "duracaoMinutos": 60, "rotulo": "x"}
            | campos
        )
        return asyncio.run(rotas.criar_blocos(corpo, USUARIO_ANA))

    with pytest.raises(HTTPException) as conflito:
        criar()
    assert conflito.value.status_code == 409           # válido, mas bate com o que já tem

    with pytest.raises(HTTPException) as invalido:
        criar(duracaoMinutos=5)
    assert invalido.value.status_code == 422           # não faz sentido

    # A frase vai para o aluno como está.
    assert "duração" in invalido.value.detail


def test_rota_editar_e_apagar_bloco_alheio_dao_404(monkeypatch):
    from uuid import uuid4

    from app.schemas.horario_estudos import AtualizarBloco

    bloco_id = uuid4()
    db = _banco(_bloco(str(bloco_id), BIA, 2, "19:00", 90, "Da Bia"))
    rotas = _rotas(monkeypatch, db)

    with pytest.raises(HTTPException) as editar:
        asyncio.run(
            rotas.atualizar_bloco(bloco_id, AtualizarBloco(rotulo="Invadido"), USUARIO_ANA)
        )
    assert editar.value.status_code == 404

    with pytest.raises(HTTPException) as apagar:
        asyncio.run(rotas.apagar_bloco(bloco_id, USUARIO_ANA))
    assert apagar.value.status_code == 404

    assert _linhas(db)[0]["rotulo"] == "Da Bia"


def test_rota_apagar_responde_204_sem_corpo(monkeypatch):
    from uuid import uuid4

    bloco_id = uuid4()
    db = _banco(_bloco(str(bloco_id), ANA, 2, "19:00", 90, "Estequiometria"))
    rotas = _rotas(monkeypatch, db)

    resposta = asyncio.run(rotas.apagar_bloco(bloco_id, USUARIO_ANA))

    assert resposta.status_code == 204
    assert _linhas(db) == []


def test_rota_obter_devolve_a_semana_so_do_aluno_da_sessao(monkeypatch):
    db = _banco(
        _bloco("b1", ANA, 2, "19:00", 90, "Da Ana"),
        _bloco("b2", BIA, 2, "19:00", 90, "Da Bia"),
    )
    rotas = _rotas(monkeypatch, db)

    horario = asyncio.run(rotas.obter_horario(USUARIO_ANA))

    assert [b.rotulo for b in horario.blocos] == ["Da Ana"]


def test_toda_rota_do_horario_exige_aluno():
    """⚠️ Não existe visão da coordenação (docs/42 §0). O jeito de ela aparecer por
    acidente é uma rota nova copiada sem o guard — este teste a pega."""
    from app.routes import horario_estudos as rotas

    assert rotas.router.routes, "o router ficou vazio"
    for rota in rotas.router.routes:
        chamadas = [d.call for d in rota.dependant.dependencies]
        assert get_current_aluno in chamadas, f"{rota.methods} {rota.path} sem get_current_aluno"


def test_sessao_de_coordenacao_e_recusada():
    with pytest.raises(HTTPException) as erro:
        asyncio.run(get_current_aluno({"tipo": "coordenador", "papel": "administrador"}))
    assert erro.value.status_code == 403


def test_as_quatro_rotas_estao_no_app(monkeypatch):
    # `app.main` monta o app ao ser importado, e o guard de configuração recusa
    # subir sem `APP_ENV=dev` (CLAUDE.md, armadilha 3). O `cache_clear` nas duas
    # pontas é o mesmo de `test_cantina_retirada.py`: `get_settings` é cacheado.
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "dev")
    try:
        from app.main import app
    finally:
        get_settings.cache_clear()

    caminhos = {(m, r.path) for r in app.routes for m in getattr(r, "methods", set())}
    base = "/me/horario-estudos"
    assert ("GET", base) in caminhos
    assert ("POST", base) in caminhos
    assert ("PATCH", f"{base}/{{bloco_id}}") in caminhos
    assert ("DELETE", f"{base}/{{bloco_id}}") in caminhos
