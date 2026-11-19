"""O aviso da missão do dia — o primeiro evento de push (docs/45 §16).

O que este arquivo trava:

  1. O aviso fala do MESMO assunto que a aba Hoje mostra: os ids que o corte
     "já mexeu hoje" confere saem do mesmo sorteio (`missao_e_questoes_do_dia`).
  2. O texto da tela bloqueada só tem o que é igual para todos, e vale até a
     missão virar (TTL até a meia-noite de Fortaleza).
  3. Quem recebe: aluno ativo com aparelho, menos quem já mexeu no assunto de
     hoje, hoje. Coordenação e aluno que saiu ficam de fora.
  4. O silêncio das 22h às 7h vale mesmo com o crontab errado.
  5. Uma vez por dia: o segundo disparo do dia não manda nada, e um erro ANTES
     da reserva não gasta a vaga.

Mesma convenção de test_push.py: handlers chamados direto, `FakeCliente` no lugar
do PostgREST, fabricante num `httpx.MockTransport`. A trava de verdade (o UNIQUE e
o `ON CONFLICT DO NOTHING` do PostgREST) foi conferida num Postgres real — o fake
só a imita.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from fastapi import BackgroundTasks

from app.auth import exigir_scheduler_secret
from app.banco import missao
from app.banco.missao import FUSO_DA_ESCOLA
from app.push import envio, missao_do_dia, registro
from app.routes import push_eventos as rotas

from .fake_postgrest import FakeCliente
from .test_missao_do_dia import montar_banco
from .test_push import CHAVE, Aparelho, decifrar

#: Quinta, 19/11/2026, 15h20 em Fortaleza — o horário do crontab.
AGORA = datetime(2026, 11, 19, 15, 20, tzinfo=FUSO_DA_ESCOLA)
HOJE = AGORA.date()


def _inscricao(id_: str, aparelho: Aparelho, *, aluno: str | None = None, coordenacao: str | None = None) -> dict:
    return {
        "id": id_,
        "aluno_id": aluno,
        "usuario_coordenacao_id": coordenacao,
        "endpoint": aparelho.endpoint,
        "chave_p256dh": aparelho.p256dh,
        "chave_auth": aparelho.auth_b64,
        "plataforma": "android",
        "falhas_seguidas": 0,
        "ultimo_envio_ok_em": None,
        "criada_em": (AGORA - timedelta(days=3)).astimezone(UTC).isoformat(),
    }


def _mexeu(aluno: str, questao: str, quando: datetime) -> dict:
    return {
        "aluno_id": aluno,
        "questao_id": questao,
        "resolvida": False,
        "alternativa_escolhida": "A",
        "acertou": False,
        # Em UTC, como o PostgREST devolve um timestamptz.
        "atualizado_em": quando.astimezone(UTC).isoformat(),
    }


class Turma:
    """O banco de um dia: acervo do test_missao_do_dia, alunos, aparelhos e treino."""

    def __init__(self) -> None:
        self.db = montar_banco()
        sorteio = missao.missao_e_questoes_do_dia(FakeCliente(self.db), HOJE)
        assert sorteio is not None
        self.missao, self.questoes = sorteio
        # Uma questão de OUTRO assunto, para provar que o corte é pelo assunto de hoje.
        self.questao_de_outro_assunto = next(
            ligacao["questao_id"]
            for ligacao in self.db["questao_vestibular_topico"].values()
            if ligacao["questao_id"] not in self.questoes
        )
        self.aparelhos: dict[str, Aparelho] = {}
        self.db["aluno"] = {}
        self.db["inscricao_push"] = {}
        self.db["questao_estudo_aluno"] = {}
        self.db["envio_push"] = {}

    def aluno(self, id_: str, *, ativo: bool = True, aparelhos: int = 1) -> None:
        self.db["aluno"][id_] = {"id": id_, "nome": id_.upper(), "ativo": ativo}
        for n in range(aparelhos):
            self._aparelho(f"{id_}-{n}", aluno=id_)

    def coordenacao(self, id_: str) -> None:
        self._aparelho(f"{id_}-0", coordenacao=id_)

    def _aparelho(self, id_: str, **dono: str) -> None:
        aparelho = Aparelho(f"https://fcm.googleapis.com/fcm/send/{id_}")
        self.aparelhos[id_] = aparelho
        self.db["inscricao_push"][id_] = _inscricao(id_, aparelho, **dono)

    def treinou(self, aluno: str, questao: str, quando: datetime) -> None:
        self.db["questao_estudo_aluno"][f"{aluno}|{questao}"] = _mexeu(aluno, questao, quando)

    def uma_questao_de_hoje(self) -> str:
        return sorted(self.questoes)[0]

    @property
    def cliente(self) -> FakeCliente:
        return FakeCliente(self.db)


@pytest.fixture
def turma() -> Turma:
    return Turma()


# ─── 1. O mesmo sorteio ───────────────────────────────────────────────────


def test_missao_e_questoes_e_o_mesmo_sorteio_da_aba_hoje(turma):
    cliente = turma.cliente
    assert missao.missao_do_dia(cliente, HOJE) == turma.missao
    ligadas = {
        ligacao["questao_id"]
        for ligacao in turma.db["questao_vestibular_topico"].values()
        if (ligacao["materia"], ligacao["topico_codigo"]) == (turma.missao.materia, turma.missao.topicoCodigo)
    }
    # São as RESPONDÍVEIS do assunto: subconjunto das ligadas, e com lastro.
    assert turma.questoes <= ligadas
    assert len(turma.questoes) >= missao.QUESTOES_DA_MISSAO


def test_acervo_vazio_nao_tem_missao_nem_questoes():
    assert missao.missao_e_questoes_do_dia(FakeCliente({}), HOJE) is None


# ─── 2. O texto e a validade ──────────────────────────────────────────────


def test_o_aviso_diz_o_assunto_e_nada_pessoal(turma):
    n = missao_do_dia.notificacao(turma.missao, AGORA)
    assert n.titulo == f"Missão de hoje: {turma.missao.nome}"
    assert n.corpo == f"10 questões de {turma.missao.materia}. O desafio é o mesmo para toda a turma."
    assert (n.url, n.tag, n.topico, n.urgencia) == ("/", "missao-do-dia", "missao-do-dia", "normal")


def test_nome_comprido_vai_para_o_corpo(turma):
    comprido = turma.missao.model_copy(update={"nome": "Assunto " * 12})
    n = missao_do_dia.notificacao(comprido, AGORA)
    assert n.titulo == "Missão de hoje"
    assert n.corpo.startswith(comprido.nome.strip()[:20])
    assert len(n.corpo) <= 200


@pytest.mark.parametrize(
    ("agora", "segundos"),
    [
        (AGORA, 8 * 3600 + 40 * 60),
        # O mesmo instante dito em UTC: 18h20 de Greenwich são 15h20 em Fortaleza.
        (datetime(2026, 11, 19, 18, 20, tzinfo=UTC), 8 * 3600 + 40 * 60),
        (datetime(2026, 11, 19, 7, 0, tzinfo=FUSO_DA_ESCOLA), 17 * 3600),
        # Perto da virada, um piso: TTL zero é "entregue agora ou descarte".
        (datetime(2026, 11, 19, 23, 59, 50, tzinfo=FUSO_DA_ESCOLA), 60),
    ],
)
def test_vale_ate_a_missao_virar_a_meia_noite_de_fortaleza(agora, segundos):
    assert missao_do_dia.segundos_ate_virar(agora) == segundos


@pytest.mark.parametrize(
    ("hora", "minuto", "pode"),
    [(6, 59, False), (7, 0, True), (15, 20, True), (21, 59, True), (22, 0, False), (3, 0, False)],
)
def test_silencio_das_22h_as_7h(hora, minuto, pode):
    agora = datetime(2026, 11, 19, hora, minuto, tzinfo=FUSO_DA_ESCOLA)
    assert missao_do_dia.dentro_do_horario(agora) is pode


def test_o_horario_e_o_de_fortaleza_e_nao_o_do_servidor():
    # 00h30 UTC do dia 20 ainda é 21h30 do dia 19 em Fortaleza: pode mandar.
    assert missao_do_dia.dentro_do_horario(datetime(2026, 11, 20, 0, 30, tzinfo=UTC))
    # 10h UTC são 7h em Fortaleza; 9h59 UTC ainda é silêncio.
    assert not missao_do_dia.dentro_do_horario(datetime(2026, 11, 19, 9, 59, tzinfo=UTC))


# ─── 3. Quem recebe ───────────────────────────────────────────────────────


def test_quem_recebe_e_quem_fica_de_fora(turma):
    turma.aluno("a1")
    turma.aluno("a2", aparelhos=2)  # uma pessoa, dois aparelhos
    turma.aluno("saiu", ativo=False)
    turma.aluno("ja-fez")
    turma.treinou("ja-fez", turma.uma_questao_de_hoje(), AGORA - timedelta(hours=2))
    turma.aluno("fez-ontem")
    turma.treinou("fez-ontem", turma.uma_questao_de_hoje(), AGORA - timedelta(days=1))
    turma.aluno("outro-assunto")
    turma.treinou("outro-assunto", turma.questao_de_outro_assunto, AGORA - timedelta(hours=1))
    turma.coordenacao("coord")

    preparo = missao_do_dia.preparar(turma.cliente, AGORA)

    alvo = {i["id"] for i in preparo.inscricoes}
    assert alvo == {"a1-0", "a2-0", "a2-1", "fez-ontem-0", "outro-assunto-0"}
    assert (preparo.destinatarios, preparo.pulados) == (4, 1)
    assert preparo.resumo() == {"dia": "2026-11-19", "destinatarios": 4, "pulados": 1, "aparelhos": 5}
    assert preparo.motivo is None


def test_mexeu_logo_depois_da_meia_noite_conta_como_hoje(turma):
    turma.aluno("madrugador")
    # 00h05 de Fortaleza = 03h05 UTC. Num corte pela data UTC, isto seria hoje
    # também — o caso que separa os dois é o de 22h da véspera, abaixo.
    turma.treinou("madrugador", turma.uma_questao_de_hoje(), datetime(2026, 11, 19, 0, 5, tzinfo=FUSO_DA_ESCOLA))
    turma.aluno("da-vespera")
    # 22h da véspera em Fortaleza já é dia 19 em UTC (01h). Contar como hoje
    # pularia quem treinou ONTEM o assunto que por acaso voltou.
    turma.treinou("da-vespera", turma.uma_questao_de_hoje(), datetime(2026, 11, 18, 22, 0, tzinfo=FUSO_DA_ESCOLA))

    preparo = missao_do_dia.preparar(turma.cliente, AGORA)
    assert {i["aluno_id"] for i in preparo.inscricoes} == {"da-vespera"}


def test_todos_ja_mexeram(turma):
    turma.aluno("a1")
    turma.treinou("a1", turma.uma_questao_de_hoje(), AGORA - timedelta(minutes=5))
    preparo = missao_do_dia.preparar(turma.cliente, AGORA)
    assert preparo.inscricoes == [] and preparo.motivo == "todos_ja_mexeram"
    assert preparo.notificacao is not None  # havia missão; só não havia a quem dizer


def test_ninguem_com_aparelho(turma):
    turma.coordenacao("coord")
    preparo = missao_do_dia.preparar(turma.cliente, AGORA)
    assert preparo.motivo == "ninguem_com_aparelho" and preparo.inscricoes == []


# ─── 4. A rota do cron ────────────────────────────────────────────────────


@pytest.fixture
def ligado(monkeypatch, turma):
    monkeypatch.setattr(envio, "chave_do_servidor", lambda: CHAVE)
    monkeypatch.setattr(rotas, "chave_do_servidor", lambda: CHAVE)
    monkeypatch.setattr(rotas, "get_supabase", lambda: turma.cliente)
    monkeypatch.setattr(rotas, "_agora", lambda: AGORA)
    return turma


@pytest.fixture
def fabricante(monkeypatch) -> list[httpx.Request]:
    """Todo POST que sairia para o FCM, respondido com 201."""
    recebidos: list[httpx.Request] = []
    cliente_real = httpx.Client
    monkeypatch.setattr(
        envio.httpx, "Client",
        lambda **kw: cliente_real(
            transport=httpx.MockTransport(lambda r: (recebidos.append(r), httpx.Response(201))[1]), **kw
        ),
    )
    return recebidos


def _disparar() -> tuple[dict, BackgroundTasks]:
    tarefas = BackgroundTasks()
    resposta = rotas.enviar_missao_do_dia(tarefas)
    return resposta, tarefas


def _rodar(tarefas: BackgroundTasks) -> None:
    for tarefa in tarefas.tasks:
        tarefa.func(*tarefa.args, **tarefa.kwargs)


def test_a_rota_exige_o_segredo_do_agendador():
    rota = next(r for r in rotas.router.routes if r.path == "/push/eventos/missao-do-dia")
    assert exigir_scheduler_secret in {d.call for d in rota.dependant.dependencies}


def test_aceita_responde_na_hora_e_manda_depois(ligado, fabricante):
    ligado.aluno("a1")
    ligado.aluno("a2")

    resposta, tarefas = _disparar()
    assert resposta == {"status": "aceito", "dia": "2026-11-19", "destinatarios": 2, "pulados": 0, "aparelhos": 2}
    assert fabricante == [], "nada sai antes da resposta"

    _rodar(tarefas)
    assert {str(r.url) for r in fabricante} == {ligado.aparelhos["a1-0"].endpoint, ligado.aparelhos["a2-0"].endpoint}
    pedido = next(r for r in fabricante if str(r.url) == ligado.aparelhos["a1-0"].endpoint)
    texto = json.loads(decifrar(pedido.content, ligado.aparelhos["a1-0"].privada, ligado.aparelhos["a1-0"].auth))
    assert texto == {
        "titulo": f"Missão de hoje: {ligado.missao.nome}",
        "corpo": f"10 questões de {ligado.missao.materia}. O desafio é o mesmo para toda a turma.",
        "url": "/",
        "tag": "missao-do-dia",
    }
    assert pedido.headers["Topic"] == "missao-do-dia"
    assert pedido.headers["TTL"] == str(8 * 3600 + 40 * 60)

    [linha] = ligado.db["envio_push"].values()
    assert linha["tipo"] == "missao-do-dia" and linha["referencia"] == "2026-11-19"
    assert linha["concluido_em"] is not None
    assert (linha["destinatarios"], linha["pulados"], linha["entregues"], linha["falhas"]) == (2, 0, 2, 0)
    assert all(i["ultimo_envio_ok_em"] for i in ligado.db["inscricao_push"].values())


def test_uma_vez_por_dia(ligado, fabricante, monkeypatch):
    ligado.aluno("a1")
    _, tarefas = _disparar()
    _rodar(tarefas)
    assert len(fabricante) == 1

    resposta, tarefas = _disparar()
    assert resposta == {"status": "ja_enviado", "dia": "2026-11-19"}
    assert tarefas.tasks == []
    assert len(fabricante) == 1 and len(ligado.db["envio_push"]) == 1

    # No dia seguinte a vaga é outra.
    monkeypatch.setattr(rotas, "_agora", lambda: AGORA + timedelta(days=1))
    resposta, tarefas = _disparar()
    assert resposta["status"] == "aceito" and resposta["dia"] == "2026-11-20"
    _rodar(tarefas)
    assert len(fabricante) == 2


def test_erro_antes_da_reserva_nao_gasta_a_vaga(ligado, fabricante, monkeypatch):
    ligado.aluno("a1")
    original = missao_do_dia.preparar
    caidas = iter([True])

    def cai_na_primeira(*a, **k):
        if next(caidas, False):
            raise RuntimeError("PostgREST fora")
        return original(*a, **k)

    monkeypatch.setattr(missao_do_dia, "preparar", cai_na_primeira)
    with pytest.raises(RuntimeError):
        _disparar()
    assert ligado.db["envio_push"] == {}

    # O disparo seguinte do mesmo dia ainda manda.
    resposta, tarefas = _disparar()
    assert resposta["status"] == "aceito"
    _rodar(tarefas)
    assert len(fabricante) == 1


def test_envio_interrompido_fecha_a_linha_com_o_motivo(ligado, monkeypatch):
    ligado.aluno("a1")

    def caiu(*_a, **_k):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(registro, "enviar_para_inscricoes", caiu)
    resposta, tarefas = _disparar()
    assert resposta["status"] == "aceito"
    _rodar(tarefas)  # não propaga: ninguém leria a exceção de uma tarefa de fundo

    [linha] = ligado.db["envio_push"].values()
    assert linha["concluido_em"] is not None
    assert linha["observacao"] == "interrompido: ConnectError"
    # E a vaga continua usada: não se refaz no mesmo dia.
    assert _disparar()[0]["status"] == "ja_enviado"


def test_sem_missao_registra_e_nao_manda(ligado, fabricante, monkeypatch):
    ligado.aluno("a1")
    monkeypatch.setattr(missao_do_dia, "missao_e_questoes_do_dia", lambda *_a, **_k: None)
    resposta, tarefas = _disparar()
    assert resposta["status"] == "sem_missao" and tarefas.tasks == []
    [linha] = ligado.db["envio_push"].values()
    assert linha["observacao"] == "sem_missao" and linha["concluido_em"] is not None
    assert fabricante == []


def test_todos_ja_mexeram_registra_e_nao_manda(ligado, fabricante):
    ligado.aluno("a1")
    ligado.treinou("a1", ligado.uma_questao_de_hoje(), AGORA - timedelta(minutes=30))
    resposta, tarefas = _disparar()
    assert resposta == {"status": "todos_ja_mexeram", "dia": "2026-11-19", "destinatarios": 0, "pulados": 1, "aparelhos": 0}
    assert tarefas.tasks == [] and fabricante == []
    [linha] = ligado.db["envio_push"].values()
    assert (linha["pulados"], linha["observacao"]) == (1, "todos_ja_mexeram")


def test_fora_do_horario_nao_le_nem_reserva(ligado, fabricante, monkeypatch):
    ligado.aluno("a1")
    monkeypatch.setattr(rotas, "_agora", lambda: datetime(2026, 11, 19, 23, 0, tzinfo=FUSO_DA_ESCOLA))
    assert _disparar()[0] == {"status": "fora_do_horario", "hora": "23:00"}
    assert ligado.db["envio_push"] == {} and fabricante == []


def test_desligado_sem_chave(ligado, monkeypatch):
    monkeypatch.setattr(rotas, "chave_do_servidor", lambda: None)
    assert _disparar()[0] == {"status": "desligado"}
    assert ligado.db["envio_push"] == {}


# ─── 5. O registro, sozinho ───────────────────────────────────────────────


def test_reservar_e_atomico_por_tipo_e_referencia():
    db: dict = {}
    cliente = FakeCliente(db)
    primeiro = registro.reservar(cliente, "missao-do-dia", "2026-11-19")
    assert primeiro is not None
    assert registro.reservar(cliente, "missao-do-dia", "2026-11-19") is None
    # Outro tipo no mesmo dia é outra vaga.
    assert registro.reservar(cliente, "outro-evento", "2026-11-19") is not None
    assert registro.reservar(cliente, "missao-do-dia", date(2026, 11, 20).isoformat()) is not None
    assert len(db["envio_push"]) == 3
