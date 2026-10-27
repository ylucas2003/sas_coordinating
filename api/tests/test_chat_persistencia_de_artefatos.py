"""A gravação dos artefatos do chat — e a conversa que não quebra quando ela falha.

O defeito que estes testes existem para não deixar voltar (docs/43 §4.1,
defeito 6): `_talvez_salvar_artefato` roda DENTRO do gerador SSE, depois de o
`end` já ter ido para o browser. Um INSERT recusado em `chat_artefato` — o
CHECK da 0038 não conhecia os tipos do aluno — levantava ali e deixava sem
gravar as mensagens `tool` seguintes, a resposta final e o update da thread. A
pessoa lia a resposta; ao recarregar, ela não existia, e a thread ficava com
`tool_calls` sem resposta.

Nada aqui toca OpenAI: o agente é um gerador de mentira que emite o `end` de
uma volta, e o banco é o FakeCliente (tests/fake_postgrest.py) — com o CHECK
da 0038 imitado onde o teste precisa dele. O CHECK de verdade é conferido
lendo as migrations, no fim do arquivo.

Rodar:  cd api && APP_ENV=dev ./.venv/bin/python -m pytest tests/test_chat_persistencia_de_artefatos.py -q
"""

import asyncio
import datetime
import json
import logging
import pathlib
import re

import pytest

from app.chat import agente, rotas
from app.chat.ferramentas import TIPOS_DE_ARTEFATO, Sessao
from app.chat.perfis import perfil_aluno, perfil_coordenador

from .fake_postgrest import FakeCliente, Tabela

ALUNO = Sessao(tipo="aluno", usuario="aluno:a1", aluno_id="a1", nome="Ana")
COORDENACAO = Sessao(tipo="coordenador", usuario="coord:c1", papel="coordenador")
THREAD = "t1"
RESPOSTA = "Você está na zona cinzenta pela régua do colégio."

#: O CHECK de `chat_artefato.tipo` como a 0038 o deixou.
CHECK_DA_0038 = frozenset({"histograma", "linha_temporal", "tabela", "csv", "navegacao"})

BARRAS = {
    "tipo": "barras_corte",
    "titulo": "Régua Tio Leo",
    "payload": {"materias": [{"materia": "Química", "nota": 3.8, "corte": 4.0}]},
}


# ─── O banco ──────────────────────────────────────────────────────────────


class _Recusado:
    """O `execute` de um INSERT que o Postgres recusa, como o postgrest-py o
    entrega: exceção na hora de executar."""

    def __init__(self, mensagem):
        self.mensagem = mensagem

    def execute(self):
        raise RuntimeError(self.mensagem)


class _ArtefatoComCheck(Tabela):
    def __init__(self, db, nome, aceitos):
        super().__init__(db, nome)
        self.aceitos = aceitos

    def insert(self, json, **kw):
        if json.get("tipo") not in self.aceitos:
            return _Recusado(
                'new row for relation "chat_artefato" violates check constraint '
                '"chat_artefato_tipo_check"'
            )
        return super().insert(json, **kw)


class ClienteComCheckDa0038(FakeCliente):
    """O banco de antes da 0070: recusa os cartões do aluno."""

    def table(self, nome):
        if nome == "chat_artefato":
            return _ArtefatoComCheck(self.db, nome, CHECK_DA_0038)
        return super().table(nome)


class _QueSerializa(Tabela):
    def insert(self, json_, **kw):
        # O postgrest-py manda o corpo por `json=` do httpx, que serializa SEM
        # `default`: uma `date` no payload levantava aqui, na gravação.
        json.dumps(json_)
        return super().insert(json_, **kw)


class ClienteQueSerializa(FakeCliente):
    def table(self, nome):
        return _QueSerializa(self.db, nome)


class _MensagemQueFalha(Tabela):
    def __init__(self, db, nome, falha):
        super().__init__(db, nome)
        self.falha = falha

    def insert(self, json_, **kw):
        if self.falha(json_):
            return _Recusado("connection reset")
        return super().insert(json_, **kw)


class ClienteQuePerdeMensagem(FakeCliente):
    """O banco que deixa de gravar UMA mensagem do turno — a que `falha` escolhe."""

    def __init__(self, db, falha):
        super().__init__(db)
        self.falha = falha

    def table(self, nome):
        if nome == "chat_mensagem":
            return _MensagemQueFalha(self.db, nome, self.falha)
        return super().table(nome)


def _banco(usuario="aluno:a1"):
    return {
        "chat_thread": {THREAD: {"id": THREAD, "usuario_id": usuario, "titulo": "Nova conversa"}},
        "chat_mensagem": {},
        "chat_artefato": {},
    }


# ─── O turno ──────────────────────────────────────────────────────────────


def _chamada(id_, nome, resultado):
    return {"id": id_, "nome": nome, "args": {}, "resultado": resultado}


@pytest.fixture
def rodar(monkeypatch):
    """Roda `_stream_mensagem` de verdade, com um agente que só emite o `end`."""

    def _rodar(cliente, sessao, tool_calls, texto_final=RESPOSTA):
        async def gerar_resposta(cliente_db, **_):
            yield agente.Evento("start", {"thread_id": THREAD})
            yield agente.Evento("token", {"texto": texto_final})
            yield agente.Evento("end", {
                "texto_final": texto_final,
                "tool_calls": tool_calls,
                "tokens_in": 10,
                "tokens_out": 5,
                "modelo": "modelo-de-teste",
            })

        monkeypatch.setattr(agente, "gerar_resposta", gerar_resposta)
        monkeypatch.setattr(agente, "gerar_titulo", lambda pergunta, resposta: None)
        perfil = perfil_aluno(sessao) if sessao.escopo == "aluno" else perfil_coordenador(sessao)

        async def consumir():
            return [
                pedaco
                async for pedaco in rotas._stream_mensagem(
                    cliente, THREAD, sessao.usuario, "como estou?", perfil
                )
            ]

        return b"".join(asyncio.run(consumir())).decode()

    return _rodar


def _mensagens(db):
    return sorted(db["chat_mensagem"].values(), key=lambda m: m["ordem"])


def _eventos(sse):
    """Os eventos do stream, já decodificados: [(nome, dados)]."""
    saida = []
    for bloco in sse.strip().split("\n\n"):
        nome = re.search(r"^event: (.+)$", bloco, re.M).group(1)
        dados = json.loads(re.search(r"^data: (.+)$", bloco, re.M).group(1))
        saida.append((nome, dados))
    return saida


# ─── A conversa não quebra ────────────────────────────────────────────────


class TestInsertRecusadoNaoQuebraAConversa:
    def test_a_resposta_final_e_gravada_mesmo_com_o_cartao_recusado(self, rodar, caplog):
        db = _banco()
        caplog.set_level(logging.ERROR, logger="sas.chat.rotas")
        sse = rodar(
            ClienteComCheckDa0038(db),
            ALUNO,
            [
                _chamada("c1", "minha_zona", {"zona": "cinzenta", "artefato": BARRAS}),
                _chamada("c2", "minhas_notas", {"total": 0, "simulados": []}),
            ],
        )

        papeis = [(m["papel"], m.get("nome_tool")) for m in _mensagens(db)]
        assert papeis == [
            ("user", None),
            ("assistant", None),            # o turno com os tool_calls
            ("tool", "minha_zona"),
            ("tool", "minhas_notas"),        # a mensagem tool SEGUINTE também
            ("assistant", None),            # e a resposta final
        ]
        assert _mensagens(db)[-1]["conteudo"] == RESPOSTA
        assert db["chat_thread"][THREAD].get("ultima_msg_em"), "o update da thread também"
        assert db["chat_artefato"] == {}
        assert "event: mensagem_salva" in sse
        falhas = [r for r in caplog.records if "artefato não gravado" in r.getMessage()]
        assert falhas and falhas[0].exc_info, "o stack do INSERT recusado vai para o log"

    def test_um_cartao_recusado_nao_impede_o_seguinte(self, rodar):
        db = _banco()
        histograma = {"tipo": "histograma", "titulo": "Sua prova", "payload": {"contagens": [1]}}
        rodar(
            ClienteComCheckDa0038(db),
            ALUNO,
            [
                _chamada("c1", "minha_zona", {"artefato": BARRAS}),
                _chamada("c2", "distribuicao_do_simulado", {"artefato": histograma}),
            ],
        )
        [gravado] = db["chat_artefato"].values()
        tool_c2 = next(m for m in _mensagens(db) if m.get("tool_call_id") == "c2")
        assert (gravado["tipo"], gravado["mensagem_id"]) == ("histograma", tool_c2["id"])

    def test_mensagem_tool_que_nao_grava_nao_leva_o_turno_junto(self, rodar, caplog):
        db = _banco()
        caplog.set_level(logging.ERROR, logger="sas.chat.rotas")
        rodar(
            ClienteQuePerdeMensagem(db, lambda linha: linha.get("nome_tool") == "quebra"),
            ALUNO,
            [
                _chamada("c1", "quebra", {"artefato": BARRAS}),
                _chamada("c2", "minhas_notas", {"total": 0}),
            ],
        )
        papeis = [(m["papel"], m.get("nome_tool")) for m in _mensagens(db)]
        assert papeis == [("user", None), ("assistant", None), ("tool", "minhas_notas"), ("assistant", None)]
        # Sem a mensagem tool, o cartão não tem onde pendurar.
        assert db["chat_artefato"] == {}
        assert any("mensagem de tool não gravada" in r.getMessage() for r in caplog.records)

    def test_turno_de_tool_calls_que_nao_grava_nao_leva_a_resposta_junto(self, rodar, caplog):
        db = _banco()
        caplog.set_level(logging.ERROR, logger="sas.chat.rotas")
        rodar(
            ClienteQuePerdeMensagem(db, lambda linha: bool(linha.get("tool_calls"))),
            ALUNO,
            [_chamada("c1", "minha_zona", {"artefato": BARRAS})],
        )
        papeis = [(m["papel"], m.get("nome_tool")) for m in _mensagens(db)]
        assert papeis == [("user", None), ("tool", "minha_zona"), ("assistant", None)]
        assert _mensagens(db)[-1]["conteudo"] == RESPOSTA
        # O cartão continua pendurado na mensagem tool: a releitura o devolve.
        assert [a["tipo"] for a in db["chat_artefato"].values()] == ["barras_corte"]
        assert any("turno com tool_calls não gravado" in r.getMessage() for r in caplog.records)


# ─── O que se grava ───────────────────────────────────────────────────────


class TestOQueSeGrava:
    def test_os_cartoes_do_aluno_vao_pendurados_na_mensagem_tool(self, rodar):
        db = _banco()
        prova = {"tipo": "prova", "payload": {"simuladoId": "s1"}}
        lista = {"tipo": "lista_questoes", "titulo": "Missão de hoje", "payload": {"itens": []}}
        rodar(
            FakeCliente(db),
            ALUNO,
            [
                _chamada("c1", "minha_zona", {"artefato": BARRAS}),
                _chamada("c2", "meu_desempenho_em_simulado", {"tipo": "fase_1", "artefato": prova}),
                _chamada("c3", "missao_de_hoje", {"artefato": lista}),
            ],
        )
        tool_por_chamada = {m["tool_call_id"]: m["id"] for m in _mensagens(db) if m["papel"] == "tool"}
        gravados = {
            a["mensagem_id"]: (a["tipo"], a["titulo"], a["payload"])
            for a in db["chat_artefato"].values()
        }
        assert gravados == {
            tool_por_chamada["c1"]: ("barras_corte", BARRAS["titulo"], BARRAS["payload"]),
            tool_por_chamada["c2"]: ("prova", None, {"simuladoId": "s1"}),
            tool_por_chamada["c3"]: ("lista_questoes", "Missão de hoje", {"itens": []}),
        }

    def test_tipo_no_topo_nao_vira_cartao(self, rodar):
        """`meu_desempenho_em_simulado` devolve `tipo` = o tipo do simulado."""
        db = _banco()
        rodar(
            FakeCliente(db),
            ALUNO,
            [_chamada("c1", "meu_desempenho_em_simulado", {"tipo": "histograma", "payload": {}})],
        )
        assert db["chat_artefato"] == {}

    def test_o_escopo_da_sessao_decide_o_catalogo(self, rodar):
        """Na coordenação: as formas antigas gravam como sempre; cartão do
        aluno pelo campo genérico, não."""
        db = _banco(usuario="coord:c1")
        rodar(
            FakeCliente(db),
            COORDENACAO,
            [
                _chamada("c1", "gerar_grafico", {"tipo": "linha_temporal", "titulo": "Ciclo", "payload": {"pontos": []}}),
                _chamada("c2", "navegar_para", {"tipo": "navegacao", "titulo": "Ana", "payload": {"rota": "/alunos/A1"}}),
                _chamada("c3", "exportar_csv", {"tipo": "csv", "titulo": "x", "nLinhas": 1, "conteudo": "a\n1\n"}),
                _chamada("c4", "obter_aluno", {"artefato": BARRAS}),
            ],
        )
        assert sorted(a["tipo"] for a in db["chat_artefato"].values()) == ["csv", "linha_temporal", "navegacao"]
        csv = next(a for a in db["chat_artefato"].values() if a["tipo"] == "csv")
        assert csv["payload"] == {"conteudo": "a\n1\n", "nLinhas": 1}

    def test_o_aluno_nao_grava_link_pelo_campo_generico(self, rodar):
        db = _banco()
        link = {"tipo": "navegacao", "payload": {"rota": "/alunos/OUTRO"}}
        rodar(FakeCliente(db), ALUNO, [_chamada("c1", "minha_zona", {"artefato": link})])
        assert db["chat_artefato"] == {}

    def test_resultado_com_erro_nao_grava_cartao(self, rodar):
        db = _banco()
        rodar(FakeCliente(db), ALUNO, [_chamada("c1", "minha_zona", {"erro": "sem nota", "artefato": BARRAS})])
        assert db["chat_artefato"] == {}

    def test_data_no_payload_e_gravada_como_texto(self, rodar):
        db = _banco()
        prova = {"tipo": "prova", "payload": {"simuladoId": "s1", "data": datetime.date(2026, 10, 30)}}
        rodar(ClienteQueSerializa(db), ALUNO, [_chamada("c1", "meu_desempenho_em_simulado", {"artefato": prova})])
        [gravado] = db["chat_artefato"].values()
        assert gravado["payload"] == {"simuladoId": "s1", "data": "2026-10-30"}

    def test_o_historico_guarda_o_aviso_e_nao_o_payload(self, rodar):
        """O que volta ao modelo nas mensagens seguintes é o que ele leu."""
        db = _banco()
        rodar(FakeCliente(db), ALUNO, [_chamada("c1", "minha_zona", {"zona": "cinzenta", "artefato": BARRAS})])
        tool = next(m for m in _mensagens(db) if m["papel"] == "tool")
        assert json.loads(tool["conteudo"]) == {
            "zona": "cinzenta",
            "artefato": {"tipo": "barras_corte", "anexado": True},
        }


# ─── O stream ─────────────────────────────────────────────────────────────


class TestOStream:
    def test_data_no_resultado_nao_derruba_o_end(self, rodar):
        """O `end` leva o resultado CHEIO ao front — e é dele que a persistência
        depende. Uma `date` esquecida levantava no `json.dumps` do evento."""
        db = _banco()
        prova = {"tipo": "prova", "payload": {"data": datetime.date(2026, 10, 30)}}
        sse = rodar(
            FakeCliente(db),
            ALUNO,
            [_chamada("c1", "meu_desempenho_em_simulado", {"quando": datetime.date(2026, 10, 24), "artefato": prova})],
        )
        eventos = dict(_eventos(sse))
        resultado = eventos["end"]["tool_calls"][0]["resultado"]
        assert resultado["quando"] == "2026-10-24"
        # O front recebe o artefato inteiro, com o payload: é ele que desenha.
        assert resultado["artefato"]["payload"] == {"data": "2026-10-30"}
        assert "mensagem_salva" in eventos

    def test_os_eventos_saem_no_formato_de_sempre(self, rodar):
        sse = rodar(FakeCliente(_banco()), ALUNO, [])
        nomes = [nome for nome, _ in _eventos(sse)]
        assert nomes == ["user_salvo", "start", "token", "end", "mensagem_salva"]
        assert sse.startswith("event: user_salvo\ndata: {")


# ─── O CHECK do banco ─────────────────────────────────────────────────────

MIGRATIONS = pathlib.Path(__file__).resolve().parent.parent / "migrations"
_CHECK_DO_TIPO = re.compile(r"chat_artefato_tipo_check\s+CHECK\s*\(\s*tipo\s+IN\s*\(([^)]*)\)", re.S)


def _tipos(trecho):
    return set(re.findall(r"'([a-z_]+)'", trecho))


class TestCheckDoBanco:
    """O FakeCliente não tem CHECK — foi assim que a recusa passou despercebida.
    Estes testes leem as migrations (o mesmo padrão de test_canvas_sob_controle)."""

    def test_o_check_vigente_aceita_todo_tipo_do_catalogo(self):
        ultimo = None
        for arquivo in sorted(MIGRATIONS.glob("0*.sql")):
            if arquivo.name.endswith(".down.sql"):
                continue
            for achado in _CHECK_DO_TIPO.finditer(arquivo.read_text(encoding="utf-8")):
                ultimo = _tipos(achado.group(1))
        assert ultimo is not None, "nenhum CHECK de chat_artefato.tipo nas migrations"
        catalogo = set().union(*TIPOS_DE_ARTEFATO.values())
        assert catalogo <= ultimo, f"o banco recusaria: {sorted(catalogo - ultimo)}"

    def test_o_down_da_0070_apaga_o_que_o_check_antigo_recusaria(self):
        """Sem o DELETE antes, o CHECK antigo não se aplica e o rollback falha."""
        up = (MIGRATIONS / "0070_chat_artefato_tipos_do_aluno.sql").read_text(encoding="utf-8")
        down = (MIGRATIONS / "0070_chat_artefato_tipos_do_aluno.down.sql").read_text(encoding="utf-8")
        depois = _tipos(_CHECK_DO_TIPO.search(up).group(1))
        de_volta = _tipos(_CHECK_DO_TIPO.search(down).group(1))
        apagados = _tipos(re.search(r"DELETE FROM chat_artefato\s+WHERE tipo IN \(([^)]*)\)", down).group(1))
        assert de_volta == CHECK_DA_0038
        assert apagados == depois - de_volta
