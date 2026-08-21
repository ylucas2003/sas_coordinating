"""Varredura da véspera (P3) — o fluxo, contra um fake do PostgREST.

O que estes testes cobrem e os de `test_lembretes.py` não: a SEQUÊNCIA. A
varredura é reconciliação — materializa, re-ancora, cancela — e quase todo bug
dela só aparece na segunda rodada, depois de o mundo ter mudado no meio.

Ver docs/13-plano-p3-lembrete-aluno.md §4.3 e §6 (etapas 9-12).
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.lembretes import despachante
from app.lembretes.aplicacoes import aluno_simulado
from app.lembretes.motor import FUSO_BRASIL, cancelar_disparos_do_evento

from .fake_postgrest import FakeCliente

AMANHA_OFFSET = timedelta(days=1)


def _amanha() -> date:
    return datetime.now(timezone.utc).astimezone(FUSO_BRASIL).date() + AMANHA_OFFSET


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    """Varredura ligada e SES configurado — sem tocar no .env do dev."""
    from app.config import get_settings

    get_settings.cache_clear()
    for chave, valor in {
        "LEMBRETE_ALUNO_ATIVO": "true",
        "LEMBRETE_ALUNO_HORA": "18:00",
        "EMAIL_ENVIOS_POR_SEGUNDO": "1000",   # sem sleep real na suíte
        "AWS_SES_ACCESS_KEY_ID": "x",
        "AWS_SES_SECRET_ACCESS_KEY": "y",
        "EMAIL_REMETENTE": "sas@teste.com",
        "EMAIL_DESTINATARIO_TESTE": "",
    }.items():
        monkeypatch.setenv(chave, valor)
    yield
    get_settings.cache_clear()


@pytest.fixture
def banco():
    db = {
        "turma": {"t1": {"id": "t1", "ano_letivo_id": "ano1"},
                  "t9": {"id": "t9", "ano_letivo_id": "outro-ano"}},
        "ciclo": {"c1": {"id": "c1", "ano_letivo_id": "ano1"}},
        "aluno": {}, "matricula_turma": {}, "simulado": {},
        "evento_agenda": {}, "regra_lembrete": {}, "disparo": {}, "email_invalido": {},
    }
    for i in range(1, 4):
        db["aluno"][f"a{i}"] = {"id": f"a{i}", "nome": f"Aluno {i}",
                                "email": f"a{i}@x.com", "ativo": True}
        db["matricula_turma"][f"m{i}"] = {"id": f"m{i}", "aluno_id": f"a{i}",
                                          "turma_id": "t1", "ativo_ate": None}
    # De outra turma: não é audiência de simulado deste ano letivo.
    db["aluno"]["z"] = {"id": "z", "nome": "Zeca", "email": "z@x.com", "ativo": True}
    db["matricula_turma"]["mz"] = {"id": "mz", "aluno_id": "z", "turma_id": "t9",
                                   "ativo_ate": None}
    return db


def _agendar(db, eid, titulo, hora, dia=None):
    """Equivale ao POST /simulados/agendar com avisarAlunos=true."""
    db["evento_agenda"][eid] = {
        "id": eid, "tipo": "simulado", "titulo": titulo,
        "data_evento": (dia or _amanha()).isoformat(),
        "hora_evento": hora, "cancelado_em": None,
    }
    db["regra_lembrete"][f"r-{eid}"] = {
        "id": f"r-{eid}", "evento_agenda_id": eid, "destinatario_tipo": "aluno",
        "canal": "email", "dias_antes": 1, "cancelada_em": None,
    }
    db["simulado"][f"s-{eid}"] = {"id": f"s-{eid}", "ciclo_id": "c1",
                                  "evento_agenda_id": eid}


def _vivos(db):
    return [d for d in db["disparo"].values()
            if d["estado"] in ("agendado", "falhou", "enviando")]


# ─── materialização ──────────────────────────────────────────────────────


def test_varredura_materializa_um_por_aluno_da_audiencia(banco):
    cliente = FakeCliente(banco)
    _agendar(banco, "e1", "P3 - Matemática", "07:00:00")

    resultado = aluno_simulado.materializar(cliente)

    assert resultado["criados"] == 3
    # Zeca, de turma de outro ano letivo, não entra.
    assert {d["destinatario"] for d in _vivos(banco)} == {"a1@x.com", "a2@x.com", "a3@x.com"}
    esperado = aluno_simulado.momento_envio(_amanha(), time(18, 0))
    assert all(d["enviar_em"] == esperado.isoformat() for d in _vivos(banco))


def test_varredura_rodando_de_novo_nao_duplica(banco):
    cliente = FakeCliente(banco)
    _agendar(banco, "e1", "P3 - Matemática", "07:00:00")
    aluno_simulado.materializar(cliente)

    assert aluno_simulado.materializar(cliente)["criados"] == 0
    assert len(_vivos(banco)) == 3


def test_duas_provas_no_mesmo_dia_continuam_um_email_so(banco):
    cliente = FakeCliente(banco)
    _agendar(banco, "e1", "P3 - Matemática", "07:00:00")
    aluno_simulado.materializar(cliente)
    _agendar(banco, "e2", "P4 - Física", "09:30:00")

    assert aluno_simulado.materializar(cliente)["criados"] == 0
    assert len(_vivos(banco)) == 3

    mensagem = aluno_simulado.preparar(
        cliente, regra=banco["regra_lembrete"]["r-e1"], disparo=_vivos(banco)[0]
    )
    assert "2 provas" in mensagem.assunto
    assert mensagem.corpo.index("07:00") < mensagem.corpo.index("09:30")


def test_aluno_que_saiu_da_audiencia_e_cancelado(banco):
    cliente = FakeCliente(banco)
    _agendar(banco, "e1", "P3 - Matemática", "07:00:00")
    aluno_simulado.materializar(cliente)

    banco["matricula_turma"]["m1"]["ativo_ate"] = "2026-08-01"   # saiu da turma
    resultado = aluno_simulado.materializar(cliente)

    assert resultado["cancelados"] == 1
    assert {d["destinatario"] for d in _vivos(banco)} == {"a2@x.com", "a3@x.com"}


def test_endereco_queimado_sai_da_audiencia(banco):
    banco["email_invalido"]["a1@x.com"] = {"endereco": "a1@x.com", "motivo": "bounce"}
    cliente = FakeCliente(banco)
    _agendar(banco, "e1", "P3 - Matemática", "07:00:00")

    assert aluno_simulado.materializar(cliente)["criados"] == 2


def test_varredura_desligada_nao_materializa_nada(banco, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("LEMBRETE_ALUNO_ATIVO", "false")
    get_settings.cache_clear()
    cliente = FakeCliente(banco)
    _agendar(banco, "e1", "P3 - Matemática", "07:00:00")

    assert aluno_simulado.materializar(cliente) == {"status": "desligado"}
    assert not banco["disparo"]


# ─── cancelamento e remarque ─────────────────────────────────────────────


def test_cancelar_uma_prova_do_dia_nao_cala_o_email(banco):
    cliente = FakeCliente(banco)
    _agendar(banco, "e1", "P3 - Matemática", "07:00:00")
    _agendar(banco, "e2", "P4 - Física", "09:30:00")
    aluno_simulado.materializar(cliente)

    banco["evento_agenda"]["e1"]["cancelado_em"] = "2026-08-20T10:00:00Z"
    cancelar_disparos_do_evento(cliente, "e1")

    # A regra morreu; os disparos, não — o dia ainda tem prova.
    assert len(_vivos(banco)) == 3
    assert aluno_simulado.materializar(cliente)["reancorados"] == 3
    assert {d["regra_lembrete_id"] for d in _vivos(banco)} == {"r-e2"}

    mensagem = aluno_simulado.preparar(
        cliente, regra=banco["regra_lembrete"]["r-e2"], disparo=_vivos(banco)[0]
    )
    assert "1 prova" in mensagem.assunto
    assert "Matemática" not in mensagem.corpo


def test_dia_esvaziado_nao_envia_nada(banco):
    cliente = FakeCliente(banco)
    _agendar(banco, "e1", "P3 - Matemática", "07:00:00")
    aluno_simulado.materializar(cliente)
    disparo = _vivos(banco)[0]

    banco["evento_agenda"]["e1"]["cancelado_em"] = "2026-08-20T10:00:00Z"
    cancelar_disparos_do_evento(cliente, "e1")

    # A guarda no envio devolve None...
    assert aluno_simulado.preparar(
        cliente, regra=banco["regra_lembrete"]["r-e1"], disparo=disparo
    ) is None
    # ...e a varredura limpa a fila.
    assert aluno_simulado.materializar(cliente)["cancelados"] == 3
    assert not _vivos(banco)


def test_remarque_cancela_o_dia_antigo_e_rematerializa_no_novo(banco):
    cliente = FakeCliente(banco)
    _agendar(banco, "e1", "P3 - Matemática", "07:00:00")
    aluno_simulado.materializar(cliente)

    banco["evento_agenda"]["e1"]["data_evento"] = (_amanha() + timedelta(days=3)).isoformat()
    assert aluno_simulado.materializar(cliente)["cancelados"] == 3
    assert not _vivos(banco)

    banco["evento_agenda"]["e1"]["data_evento"] = _amanha().isoformat()
    # Chave livre de novo porque o índice único ignora 'cancelado'.
    assert aluno_simulado.materializar(cliente)["criados"] == 3


# ─── despachante ─────────────────────────────────────────────────────────


def _vencer(db):
    passado = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    for disparo in db["disparo"].values():
        if disparo["estado"] == "agendado":
            disparo["enviar_em"] = passado


def test_tick_envia_grava_o_que_saiu_e_nao_reenvia(banco, monkeypatch):
    enviados = []
    monkeypatch.setattr(
        despachante.email_ses, "enviar_email",
        lambda **kw: enviados.append(kw),
    )
    cliente = FakeCliente(banco)
    _agendar(banco, "e1", "P3 - Matemática", "07:00:00")
    aluno_simulado.materializar(cliente)
    _vencer(banco)

    resultado = asyncio.run(despachante.processar_disparos_vencidos(cliente))

    assert resultado["enviados"] == 3
    assert len(enviados) == 3
    entregues = [d for d in banco["disparo"].values() if d["estado"] == "enviado"]
    assert all(d["assunto"] and d["corpo"] and d["enviado_em"] for d in entregues)

    # Regressão: o tick seguinte roda a varredura de novo. 'enviado' é
    # terminal mas OCUPA a chave — recriar aqui quebraria a rodada.
    segunda = asyncio.run(despachante.processar_disparos_vencidos(cliente))
    assert segunda["enviados"] == 0
    assert segunda["materializacao"]["aluno"]["criados"] == 0
    assert len(enviados) == 3


def test_falha_de_envio_vira_estado_e_re_tenta(banco, monkeypatch):
    def explodir(**kw):
        raise RuntimeError("SES fora do ar")

    monkeypatch.setattr(despachante.email_ses, "enviar_email", explodir)
    cliente = FakeCliente(banco)
    _agendar(banco, "e1", "P3 - Matemática", "07:00:00")
    aluno_simulado.materializar(cliente)
    _vencer(banco)

    resultado = asyncio.run(despachante.processar_disparos_vencidos(cliente))

    assert resultado["falharam"] == 3
    falhos = [d for d in banco["disparo"].values() if d["estado"] == "falhou"]
    assert all(d["tentativas"] == 1 and "SES fora do ar" in d["erro"] for d in falhos)

    # Consertou o mundo → o tick seguinte entrega, sem ninguém remarcar nada.
    monkeypatch.setattr(despachante.email_ses, "enviar_email", lambda **kw: None)
    assert asyncio.run(despachante.processar_disparos_vencidos(cliente))["enviados"] == 3


def test_teto_diario_para_a_rodada_sem_gastar_tentativa(banco, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("EMAIL_TETO_DIARIO", "2")
    get_settings.cache_clear()
    monkeypatch.setattr(despachante.email_ses, "enviar_email", lambda **kw: None)
    cliente = FakeCliente(banco)
    _agendar(banco, "e1", "P3 - Matemática", "07:00:00")
    aluno_simulado.materializar(cliente)
    _vencer(banco)

    resultado = asyncio.run(despachante.processar_disparos_vencidos(cliente))

    assert resultado["enviados"] == 2
    assert resultado["motivo_parada"] == "teto_diario"
    assert resultado["restantes"] == 1
    # O que sobrou continua na fila, intacto: teto não é erro.
    sobrou = [d for d in banco["disparo"].values() if d["estado"] == "agendado"]
    assert len(sobrou) == 1 and sobrou[0]["tentativas"] == 0


def test_endereco_queimado_depois_de_materializado_nao_recebe(banco, monkeypatch):
    """Bounce que chega DEPOIS da materialização, antes do envio.

    Quem barra é a varredura, que roda no início do mesmo tick — por isso o
    cancelamento aparece em `materializacao`, não no contador do despachante.
    """
    enviados = []
    monkeypatch.setattr(
        despachante.email_ses, "enviar_email", lambda **kw: enviados.append(kw)
    )
    cliente = FakeCliente(banco)
    _agendar(banco, "e1", "P3 - Matemática", "07:00:00")
    aluno_simulado.materializar(cliente)
    _vencer(banco)
    banco["email_invalido"]["a1@x.com"] = {"endereco": "a1@x.com", "motivo": "bounce"}

    resultado = asyncio.run(despachante.processar_disparos_vencidos(cliente))

    assert resultado["enviados"] == 2
    assert resultado["materializacao"]["aluno"]["cancelados"] == 1
    assert "a1@x.com" not in {e["destinatario"] for e in enviados}


def test_despachante_barra_queimado_mesmo_sem_varredura(banco, monkeypatch):
    """A segunda rede: com a varredura desligada (ou num disparo de
    coordenador, que ela não toca), quem barra é o próprio despachante."""
    from app.config import get_settings

    enviados = []
    monkeypatch.setattr(
        despachante.email_ses, "enviar_email", lambda **kw: enviados.append(kw)
    )
    cliente = FakeCliente(banco)
    _agendar(banco, "e1", "P3 - Matemática", "07:00:00")
    aluno_simulado.materializar(cliente)
    _vencer(banco)
    banco["email_invalido"]["a1@x.com"] = {"endereco": "a1@x.com", "motivo": "bounce"}

    monkeypatch.setenv("LEMBRETE_ALUNO_ATIVO", "false")
    get_settings.cache_clear()
    resultado = asyncio.run(despachante.processar_disparos_vencidos(cliente))

    assert resultado["enviados"] == 2
    assert resultado["cancelados"] == 1
    assert "a1@x.com" not in {e["destinatario"] for e in enviados}


def test_varredura_quebrada_nao_segura_a_fila(banco, monkeypatch):
    """Materializar e enviar são independentes.

    Um erro na varredura não pode impedir o envio do que já está
    materializado — inclusive o lembrete do coordenador, que nem passa por
    ela. O erro fica visível no resultado do tick.
    """
    enviados = []
    monkeypatch.setattr(
        despachante.email_ses, "enviar_email", lambda **kw: enviados.append(kw)
    )
    cliente = FakeCliente(banco)
    _agendar(banco, "e1", "P3 - Matemática", "07:00:00")
    aluno_simulado.materializar(cliente)
    _vencer(banco)

    def explodir(_cliente):
        raise RuntimeError("varredura explodiu")

    monkeypatch.setattr(aluno_simulado, "materializar", explodir)
    resultado = asyncio.run(despachante.processar_disparos_vencidos(cliente))

    assert "varredura explodiu" in resultado["materializacao"]["erro"]
    assert resultado["enviados"] == 3
    assert len(enviados) == 3
