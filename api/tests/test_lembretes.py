"""Motor de lembretes (P2) — funções puras.

O cálculo do `enviar_em` e a composição do e-mail são o que o despachante
executa às cegas; se saírem errados, o lembrete chega no dia errado ou com
texto errado sem ninguém perceber. Ver docs/12-plano-p2-motor-lembretes.md.

Rodar:  cd api && ./.venv/bin/python -m pytest tests/ -q
"""

from datetime import date, datetime, time, timedelta

import pytest

from app.lembretes.motor import FUSO_BRASIL, calcular_enviar_em, compor_email


def test_enviar_em_dias_antes():
    quando = calcular_enviar_em(date(2026, 9, 20), time(7, 0), 3)
    assert quando == datetime(2026, 9, 17, 7, 0, tzinfo=FUSO_BRASIL)


def test_enviar_em_zero_dias_e_no_dia_na_hora():
    quando = calcular_enviar_em(date(2026, 9, 20), time(7, 0), 0)
    assert quando == datetime(2026, 9, 20, 7, 0, tzinfo=FUSO_BRASIL)


def test_enviar_em_vira_o_mes():
    quando = calcular_enviar_em(date(2026, 3, 2), time(7, 0), 5)
    assert quando.date() == date(2026, 2, 25)


def test_enviar_em_sem_janela_de_silencio():
    # Decisão A8 (docs/12 §1): madrugada é madrugada — 2h fica 2h.
    quando = calcular_enviar_em(date(2026, 9, 20), time(2, 0), 1)
    assert quando.hour == 2


def test_enviar_em_carrega_fuso_brasil():
    quando = calcular_enviar_em(date(2026, 9, 20), time(7, 0), 3)
    assert quando.utcoffset() == timedelta(hours=-3)


def test_compor_email_traz_titulo_data_e_hora():
    assunto, corpo = compor_email(
        titulo="3_P2 - Matemática - 20/09/2026",
        data_evento=date(2026, 9, 20),
        hora_evento=time(7, 0),
        hoje=date(2026, 9, 17),
    )
    assert "3_P2 - Matemática" in assunto
    assert "20/09/2026" in corpo
    assert "07:00" in corpo


@pytest.mark.parametrize(
    "hoje, trecho",
    [
        (date(2026, 9, 17), "em 3 dias"),
        (date(2026, 9, 19), "amanhã"),
        (date(2026, 9, 20), "hoje"),
        (date(2026, 9, 22), "era em 20/09/2026"),  # disparo atrasado que só saiu depois
    ],
)
def test_compor_email_distancia_ate_o_evento(hoje, trecho):
    _, corpo = compor_email(
        titulo="X", data_evento=date(2026, 9, 20), hora_evento=time(7, 0), hoje=hoje
    )
    assert trecho in corpo


# ─────────────────────────────────────────────────────────────────────────
# P3 · lembrete de aluno (docs/13 §4.9)
#
# Tudo aqui é função pura. O que exige banco — claim concorrente, varredura,
# re-ancoragem — fica na verificação manual da §6 do plano.
# ─────────────────────────────────────────────────────────────────────────

from app.lembretes.aplicacoes.aluno_simulado import (  # noqa: E402
    aluno_id_da_chave,
    chave_idempotencia,
    compor_digest,
    escolher_ancora,
    filtrar_audiencia,
    momento_envio,
)
from app.lembretes.supressao import interpretar_evento_ses  # noqa: E402

# ─── enviar_em do aluno ──────────────────────────────────────────────────


def test_momento_envio_e_na_vespera_em_hora_fixa():
    # Janela de silêncio (A8 reaberta): a hora do evento NÃO manda — prova às
    # 7h não vira e-mail às 7h da manhã.
    quando = momento_envio(date(2026, 9, 21), time(18, 0))
    assert quando == datetime(2026, 9, 20, 18, 0, tzinfo=FUSO_BRASIL)


def test_momento_envio_vira_o_mes_e_carrega_fuso():
    quando = momento_envio(date(2026, 3, 1), time(18, 0))
    assert quando.date() == date(2026, 2, 28)
    assert quando.utcoffset() == timedelta(hours=-3)


# ─── chave de idempotência ───────────────────────────────────────────────


def test_chave_e_estavel_por_dia_e_aluno():
    a = chave_idempotencia(date(2026, 9, 21), "aluno-1")
    assert a == "aluno-dia:2026-09-21:aluno-1"
    # Mesmo aluno, mesmo dia → mesma chave: o índice único impede o segundo
    # disparo mesmo que o e-mail dele tenha mudado no meio.
    assert a == chave_idempotencia(date(2026, 9, 21), "aluno-1")
    assert a != chave_idempotencia(date(2026, 9, 22), "aluno-1")


def test_aluno_id_da_chave_ida_e_volta():
    assert aluno_id_da_chave(chave_idempotencia(date(2026, 9, 21), "x-9")) == "x-9"
    assert aluno_id_da_chave("outra-coisa:2026-09-21:x") is None
    assert aluno_id_da_chave("") is None


# ─── âncora do dia ───────────────────────────────────────────────────────


def _evento(id_, hora):
    return {"regra_id": f"r-{id_}", "evento": {"id": id_, "hora_evento": hora}}


def test_ancora_e_o_evento_mais_cedo():
    eventos = [_evento("b", "09:30"), _evento("a", "07:00")]
    assert escolher_ancora(eventos)["regra_id"] == "r-a"


def test_ancora_com_empate_e_estavel():
    # Empate resolvido pelo id — sem isso, dois ticks poderiam re-ancorar em
    # pingue-pongue.
    eventos = [_evento("z", "07:00"), _evento("a", "07:00")]
    assert escolher_ancora(eventos)["regra_id"] == "r-a"
    assert escolher_ancora(list(reversed(eventos)))["regra_id"] == "r-a"


# ─── audiência ───────────────────────────────────────────────────────────


def _aluno(id_, email="a@x.com", ativo=True, nome="Fulano de Tal"):
    return {"id": id_, "nome": nome, "email": email, "ativo": ativo}


def test_audiencia_so_com_matricula_ativa_na_turma_do_ano():
    alunos = [_aluno("1"), _aluno("2", "b@x.com"), _aluno("3", "c@x.com")]
    matriculas = [
        {"aluno_id": "1", "turma_id": "t1", "ativo_ate": None},
        {"aluno_id": "2", "turma_id": "t9", "ativo_ate": None},   # outra turma
        {"aluno_id": "3", "turma_id": "t1", "ativo_ate": "2026-01-01"},  # saiu
    ]
    audiencia = filtrar_audiencia(
        alunos=alunos, matriculas=matriculas, turma_ids={"t1"}, invalidos=set()
    )
    assert [a["aluno_id"] for a in audiencia] == ["1"]


def test_audiencia_exclui_inativo_sem_email_e_queimado():
    alunos = [
        _aluno("1", "ok@x.com"),
        _aluno("2", "inativo@x.com", ativo=False),
        _aluno("3", ""),                       # sem e-mail: silêncio conhecido
        _aluno("4", "Queimado@X.com"),         # bounce — e o caixa alta importa
    ]
    matriculas = [
        {"aluno_id": str(i), "turma_id": "t1", "ativo_ate": None} for i in range(1, 5)
    ]
    audiencia = filtrar_audiencia(
        alunos=alunos,
        matriculas=matriculas,
        turma_ids={"t1"},
        invalidos={"queimado@x.com"},
    )
    assert [a["aluno_id"] for a in audiencia] == ["1"]


def test_audiencia_nao_duplica_aluno_com_duas_matriculas():
    matriculas = [
        {"aluno_id": "1", "turma_id": "t1", "ativo_ate": None},
        {"aluno_id": "1", "turma_id": "t2", "ativo_ate": None},
    ]
    audiencia = filtrar_audiencia(
        alunos=[_aluno("1")], matriculas=matriculas, turma_ids={"t1", "t2"},
        invalidos=set(),
    )
    assert len(audiencia) == 1


# ─── digest ──────────────────────────────────────────────────────────────


def _prova(titulo, hora):
    return {"titulo": titulo, "hora_evento": hora}


def test_digest_de_uma_prova():
    msg = compor_digest(
        nome="Maria Silva",
        dia=date(2026, 9, 21),
        eventos=[_prova("3_P2 - Matemática - 21/09/2026", "07:00:00")],
        link_descadastro="https://sas/x",
    )
    assert "21/09" in msg.assunto
    assert "1 prova" in msg.assunto
    assert "Olá, Maria." in msg.corpo
    assert "07:00 · 3_P2 - Matemática - 21/09/2026" in msg.corpo
    assert "https://sas/x" in msg.corpo


def test_digest_lista_todas_as_provas_do_dia():
    msg = compor_digest(
        nome="Maria",
        dia=date(2026, 9, 21),
        eventos=[_prova("Matemática", "07:00:00"), _prova("Física", "09:30:00")],
        link_descadastro="https://sas/x",
    )
    assert "2 provas" in msg.assunto
    assert msg.corpo.index("07:00") < msg.corpo.index("09:30")


def test_digest_sem_nome_nao_quebra_a_saudacao():
    msg = compor_digest(
        nome="", dia=date(2026, 9, 21), eventos=[_prova("X", "07:00:00")],
        link_descadastro="l",
    )
    assert msg.corpo.startswith("Olá.")


def test_digest_nao_traz_nota_nem_desempenho():
    # Conteúdo mínimo é decisão (docs/13 §1): e-mail de menor de idade em massa.
    msg = compor_digest(
        nome="Maria", dia=date(2026, 9, 21), eventos=[_prova("X", "07:00:00")],
        link_descadastro="l",
    )
    for proibido in ("nota", "média", "desempenho", "ranking"):
        assert proibido not in msg.corpo.lower()


# ─── eventos do SES (bounce/complaint) ───────────────────────────────────


def _sns(corpo: dict) -> dict:
    import json
    return {"Type": "Notification", "Message": json.dumps(corpo)}


def test_bounce_permanente_queima_o_endereco():
    eventos = interpretar_evento_ses(_sns({
        "notificationType": "Bounce",
        "bounce": {
            "bounceType": "Permanent",
            "bounceSubType": "General",
            "bouncedRecipients": [{"emailAddress": "nao-existe@x.com"}],
        },
    }))
    assert eventos == [("nao-existe@x.com", "bounce", "General")]


def test_bounce_transiente_e_ignorado():
    # Caixa cheia não é endereço errado — quem re-tenta é o disparo.
    eventos = interpretar_evento_ses(_sns({
        "notificationType": "Bounce",
        "bounce": {
            "bounceType": "Transient",
            "bounceSubType": "MailboxFull",
            "bouncedRecipients": [{"emailAddress": "cheia@x.com"}],
        },
    }))
    assert eventos == []


def test_complaint_queima_o_endereco():
    eventos = interpretar_evento_ses(_sns({
        "notificationType": "Complaint",
        "complaint": {
            "complaintFeedbackType": "abuse",
            "complainedRecipients": [{"emailAddress": "spam@x.com"}],
        },
    }))
    assert eventos == [("spam@x.com", "complaint", "abuse")]


@pytest.mark.parametrize("payload", [
    {},
    {"Type": "Notification", "Message": "isto não é json"},
    {"notificationType": "Delivery"},
    {"Type": "Notification", "Message": '{"notificationType":"Bounce"}'},
])
def test_payload_estranho_nao_explode(payload):
    # O endpoint é público: payload inesperado é o caso normal, não a exceção.
    assert interpretar_evento_ses(payload) == []


# ─── rede de dev e descadastro ───────────────────────────────────────────


def test_destinatario_de_teste_redireciona_e_diz_de_quem_era(monkeypatch):
    from app.config import get_settings
    from app.lembretes.email import aplicar_destinatario_teste

    monkeypatch.setenv("EMAIL_DESTINATARIO_TESTE", "dev@teste.com")
    get_settings.cache_clear()
    try:
        alvo, assunto = aplicar_destinatario_teste("aluno@x.com", "Simulados de amanhã")
        assert alvo == "dev@teste.com"
        # Sem o prefixo, 873 e-mails viram 873 mensagens idênticas na mesma caixa.
        assert assunto == "[para: aluno@x.com] Simulados de amanhã"
    finally:
        get_settings.cache_clear()


def test_sem_destinatario_de_teste_nada_muda(monkeypatch):
    from app.config import get_settings
    from app.lembretes.email import aplicar_destinatario_teste

    monkeypatch.setenv("EMAIL_DESTINATARIO_TESTE", "")
    get_settings.cache_clear()
    try:
        assert aplicar_destinatario_teste("a@x.com", "X") == ("a@x.com", "X")
    finally:
        get_settings.cache_clear()


def test_token_de_descadastro_ida_e_volta_e_adulteracao():
    from app.lembretes.descadastro import gerar_token, montar_link, token_valido

    assert token_valido("aluno@x.com", gerar_token("aluno@x.com"))
    # Caixa alta não cria um segundo endereço.
    assert token_valido("Aluno@X.com", gerar_token("aluno@x.com"))
    assert not token_valido("aluno@x.com", "deadbeefdeadbeef")
    assert not token_valido("outro@x.com", gerar_token("aluno@x.com"))
    assert "descadastrar?e=aluno%40x.com&t=" in montar_link("aluno@x.com")


def test_webhook_do_ses_recusa_token_errado(monkeypatch):
    """Endpoint público: token no path é a barreira, e ele falha ANTES de
    tocar no banco (por isso este teste roda sem cliente nenhum)."""
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app

    monkeypatch.setenv("SES_WEBHOOK_TOKEN", "segredo")
    get_settings.cache_clear()
    try:
        cliente = TestClient(create_app())
        assert cliente.post("/email/eventos-ses/errado", json={}).status_code == 404
        assert cliente.get(
            "/lembretes/descadastrar", params={"e": "a@x.com", "t": "invalido"}
        ).status_code == 400
    finally:
        get_settings.cache_clear()
