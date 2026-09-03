"""Envio em lote ao Canvas (docs/32 §4).

⚠️ **Todo teste aqui é com mock, e isso não é comodidade.** O
`CANVAS_API_TOKEN` do `.env` é de admin do colégio (risco 4 do docs/18 §7): um
lote descuidado altera dezenas de objetos reais de uma vez. É a diferença entre
esta parte e todas as outras do sprint. A verificação contra o Canvas de
verdade é passo manual, deliberado, num ciclo escolhido de propósito.

O que se prova é contrato, e são quatro coisas — as mesmas quatro que fazem um
lote ser melhor que N cliques em vez de pior:

  1. ORDEM: grupo → assignments → notas.
  2. PARAR quando o grupo falha, em vez de mandar 40 assignments para um lugar
     que não existe.
  3. RESULTADO POR ITEM. Um lote que diz "sucesso" tendo falhado em 3 de 12 é
     pior que não ter lote.
  4. NADA TRUNCADO EM SILÊNCIO.
"""

from __future__ import annotations

import asyncio

import pytest

from app.routes import ciclos as rota_ciclos
from tests.fake_postgrest import FakeCliente


@pytest.fixture
def db():
    return {
        "ciclo": {
            "c1": {"id": "c1", "nome": "Ciclo 4 · ITA · 2026",
                   "canvas_estado": "divergente", "canvas_erro": None},
        },
        "simulado": {
            "s1": {"id": "s1", "ciclo_id": "c1", "nome": "P1 - Matemática",
                   "rotulo_curto": "P1", "origem": "sas",
                   "canvas_estado": "divergente", "canvas_erro": None},
            "s2": {"id": "s2", "ciclo_id": "c1", "nome": "P2 - Física",
                   "rotulo_curto": "P2", "origem": "canvas",
                   "canvas_estado": "sincronizado", "canvas_erro": None},
        },
        "nota": {
            ("a1", "s1"): {"aluno_id": "a1", "simulado_id": "s1",
                           "pontuacao_sas": 8, "pontuacao_canvas": 5},
            ("a2", "s1"): {"aluno_id": "a2", "simulado_id": "s1",
                           "pontuacao_sas": 7, "pontuacao_canvas": 7},
            ("a3", "s1"): {"aluno_id": "a3", "simulado_id": "s1",
                           "pontuacao_sas": None, "pontuacao_canvas": 6},
        },
        "evento_auditoria": {},
    }


class _Request:
    client = None


COORD = {"sub": "coord-1"}


def _chamar_lote(cliente):
    return asyncio.run(
        rota_ciclos.enviar_ciclo_ao_canvas_em_lote("c1", _Request(), COORD)
    )


def _pendencias(cliente):
    return asyncio.run(rota_ciclos.pendencias_canvas("c1", COORD))


def _mockar(monkeypatch, cliente, *, chamadas, grupo_ok=True, simulado="sincronizado", nota_ok=True):
    monkeypatch.setattr(rota_ciclos, "get_supabase", lambda: cliente)

    async def criar_grupo(_c, ciclo_id):
        chamadas.append(("ciclo", ciclo_id))
        return ({"canvas_estado": "sincronizado"} if grupo_ok
                else {"canvas_estado": "falhou", "erro": "sem token"})

    async def enviar_simulado(_c, simulado_id):
        chamadas.append(("simulado", simulado_id))
        return simulado

    async def enviar_nota(_c, *, aluno_id, simulado_id):
        chamadas.append(("nota", f"{aluno_id}/{simulado_id}"))
        return {"ok": nota_ok} if nota_ok else {"ok": False, "erro": "aluno sem canvas_user_id"}

    monkeypatch.setattr(rota_ciclos.escrita, "criar_grupo_do_ciclo", criar_grupo)
    monkeypatch.setattr(rota_ciclos.escrita, "enviar_simulado", enviar_simulado)
    monkeypatch.setattr(rota_ciclos.escrita, "enviar_nota", enviar_nota)


# ─── A leitura, que é o que o coordenador vê antes de clicar ──────────────


def test_pendencias_nao_escrevem_nada(db, monkeypatch):
    cliente = FakeCliente(db)
    monkeypatch.setattr(rota_ciclos, "get_supabase", lambda: cliente)
    antes = {k: dict(v) for k, v in db["ciclo"].items()}
    _pendencias(cliente)
    assert db["ciclo"] == antes


def test_pendencias_listam_os_tres_tipos(db, monkeypatch):
    cliente = FakeCliente(db)
    monkeypatch.setattr(rota_ciclos, "get_supabase", lambda: cliente)
    p = _pendencias(cliente)
    assert p["grupo"]["pendente"] is True
    # Só o simulado nascido no SAS e fora de sincronia.
    assert [s["id"] for s in p["simulados"]] == ["s1"]
    # Só a nota cuja edição do SAS difere do Canvas — a igual e a não editada
    # não são pendência.
    assert [n["alunoId"] for n in p["notas"]] == ["a1"]
    assert p["total"] == 3


# ─── O lote ───────────────────────────────────────────────────────────────


def test_ordem_grupo_depois_simulados_depois_notas(db, monkeypatch):
    cliente = FakeCliente(db)
    chamadas: list[tuple[str, str]] = []
    _mockar(monkeypatch, cliente, chamadas=chamadas)
    _chamar_lote(cliente)
    assert [tipo for tipo, _ in chamadas] == ["ciclo", "simulado", "nota"]


def test_grupo_que_falha_interrompe_o_lote(db, monkeypatch):
    """Um Assignment não entra num Assignment Group que não existe."""
    cliente = FakeCliente(db)
    chamadas: list[tuple[str, str]] = []
    _mockar(monkeypatch, cliente, chamadas=chamadas, grupo_ok=False)
    resumo = _chamar_lote(cliente)
    assert [tipo for tipo, _ in chamadas] == ["ciclo"]
    assert resumo["interrompido"]
    assert resumo["falhas"] == 1


def test_resultado_e_por_item_nunca_um_ok_agregado(db, monkeypatch):
    cliente = FakeCliente(db)
    chamadas: list[tuple[str, str]] = []
    _mockar(monkeypatch, cliente, chamadas=chamadas, simulado="falhou")
    resumo = _chamar_lote(cliente)
    assert resumo["total"] == 3
    assert resumo["enviados"] == 2   # grupo e nota
    assert resumo["falhas"] == 1     # o simulado
    falhou = [i for i in resumo["itens"] if not i["ok"]]
    assert len(falhou) == 1
    assert falhou[0]["tipo"] == "simulado"
    assert falhou[0]["erro"]


def test_cada_item_vira_evento_de_auditoria_mais_um_do_lote(db, monkeypatch):
    cliente = FakeCliente(db)
    _mockar(monkeypatch, cliente, chamadas=[])
    _chamar_lote(cliente)
    # 3 itens + 1 do lote.
    assert len(db["evento_auditoria"]) == 4


def test_nada_truncado_em_silencio(db, monkeypatch):
    """Com mais notas que o teto, a resposta DIZ quantas ficaram de fora."""
    for i in range(rota_ciclos.TETO_NOTAS_POR_LOTE + 5):
        db["nota"][(f"x{i}", "s1")] = {
            "aluno_id": f"x{i}", "simulado_id": "s1",
            "pontuacao_sas": 9, "pontuacao_canvas": 1,
        }
    cliente = FakeCliente(db)
    _mockar(monkeypatch, cliente, chamadas=[])
    resumo = _chamar_lote(cliente)
    assert resumo["notasAlemDoTeto"] > 0


def test_ciclo_inexistente_e_404(db, monkeypatch):
    from fastapi import HTTPException

    cliente = FakeCliente(db)
    monkeypatch.setattr(rota_ciclos, "get_supabase", lambda: cliente)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(rota_ciclos.pendencias_canvas("nao-existe", COORD))
    assert exc.value.status_code == 404
