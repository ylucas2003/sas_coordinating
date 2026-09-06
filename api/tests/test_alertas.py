"""O desfazer do alerta — `POST /alertas/{id}/reabrir` (docs/39 §3, fase 1).

Resolver um alerta era a única ação do Painel sem volta: o cartão sumia da
faixa e o caminho de retorno era um UPDATE à mão no banco. Enquanto o Painel
tinha 900 linhas editáveis ao lado, isso passava; no Painel novo sobram DUAS
coisas que se pode fazer — entrar por uma porta ou resolver um alerta — e a
segunda ganhou o desfazer que a prancheta desenhou.

O que estes testes guardam é o par: resolver e reabrir são a mesma linha do
banco vista dos dois lados, e a listagem tem de concordar com o estado nas
duas direções. Um `reabrir` que esquecesse `resolvido_em` passaria em qualquer
teste que olhasse só `resolvido` — e deixaria um alerta ABERTO carregando a
hora em que foi resolvido, contradição que só apareceria meses depois, num
relatório.

Chamamos os handlers direto, com um `FakeCliente` no lugar do PostgREST:
passar por HTTP só acrescentaria ruído, e é o padrão de `test_papeis.py`.

Rodar:  cd api && ./.venv/bin/python -m pytest tests/test_alertas.py -q
"""

import asyncio

import pytest
from fastapi import HTTPException

from app.routes import alertas
from tests.fake_postgrest import FakeCliente


def _alerta(id_: str, *, resolvido: bool = False, resolvido_em: str | None = None) -> dict:
    return {
        "id": id_,
        "categoria": "QUEDA_RENDIMENTO",
        "severidade": "vermelho",
        "entidade_tipo": "aluno",
        "entidade_id": "A023",
        "titulo": "Aluno caindo",
        "subtitulo": "média dos últimos 3 abaixo do histórico",
        "dados_brutos": {"sparkline": [7.1, 6.4, 5.2]},
        "disparado_em": "2026-09-05T12:00:00+00:00",
        "resolvido": resolvido,
        "resolvido_em": resolvido_em,
        "hash_dedup": "queda:A023",
    }


@pytest.fixture
def banco(monkeypatch) -> dict:
    db = {"alerta": {"al-1": _alerta("al-1"), "al-2": _alerta("al-2")}}
    monkeypatch.setattr(alertas, "get_supabase", lambda: FakeCliente(db))
    return db


def _listar() -> list:
    return asyncio.run(alertas.listar_alertas())


def _resolver(alerta_id: str) -> dict:
    return asyncio.run(alertas.resolver_alerta(alerta_id))


def _reabrir(alerta_id: str) -> dict:
    return asyncio.run(alertas.reabrir_alerta(alerta_id))


# ─── O par ────────────────────────────────────────────────────────────────


def test_reabrir_devolve_o_alerta_a_listagem(banco):
    """O desfazer só vale se a próxima leitura trouxer o cartão de volta.

    O cartão resolvido que fica na tela é estado da TELA (`AlertCard`); quem
    decide se ele volta ou não é `GET /alertas`, que filtra por `resolvido`.
    """
    _resolver("al-1")
    assert [a.id for a in _listar()] == ["al-2"]

    _reabrir("al-1")
    assert {a.id for a in _listar()} == {"al-1", "al-2"}


def test_reabrir_apaga_a_hora_do_resolver(banco):
    """`resolvido_em` sem par com `resolvido` é dado que mente.

    Um alerta aberto guardando a hora em que foi resolvido não quebra tela
    nenhuma hoje — e é exatamente por isso que passaria despercebido até alguém
    ler a coluna como verdade.
    """
    _resolver("al-1")
    assert banco["alerta"]["al-1"]["resolvido_em"] is not None

    assert _reabrir("al-1") == {"id": "al-1", "resolvido": False}
    assert banco["alerta"]["al-1"]["resolvido"] is False
    assert banco["alerta"]["al-1"]["resolvido_em"] is None


def test_reabrir_alerta_inexistente_e_404(banco):
    """404 e não 200 silencioso: o desfazer que não achou o que reabrir
    precisa dizer isso à tela, senão o cartão sai da faixa como se tivesse
    voltado."""
    with pytest.raises(HTTPException) as erro:
        _reabrir("nao-existe")
    assert erro.value.status_code == 404


def test_resolver_reabrir_resolver_termina_resolvido(banco):
    """A ida e volta é a sequência real do arrependimento — clicar, desfazer,
    clicar de novo — e ela não pode deixar resíduo: o estado final é o mesmo do
    primeiro resolver, na MESMA linha (`hash_dedup` é UNIQUE, o motor faz
    upsert com `ignore_duplicates`, então reabrir nunca produz um segundo
    alerta igual)."""
    _resolver("al-1")
    _reabrir("al-1")
    assert _resolver("al-1") == {"id": "al-1", "resolvido": True}

    assert len(banco["alerta"]) == 2
    linha = banco["alerta"]["al-1"]
    assert linha["resolvido"] is True
    assert linha["resolvido_em"] is not None
    assert [a.id for a in _listar()] == ["al-2"]


# ─── O guard ──────────────────────────────────────────────────────────────


def _guards(rota) -> set[str]:
    """Nomes das dependências que a rota realmente atravessa.

    Anda a árvore já montada pelo FastAPI, e não a lista do decorador, pelo
    mesmo motivo de `test_papeis.py::_piso`: a dependência declarada no
    `APIRouter` só aparece aqui. A raiz fica de fora porque o `call` dela é o
    próprio handler — incluí-lo faria duas rotas com o MESMO guard parecerem
    diferentes, que é justo o contrário do que este teste pergunta.
    """
    nomes, pilha = set(), list(rota.dependant.dependencies)
    while pilha:
        dependencia = pilha.pop()
        if dependencia.call is not None:
            nomes.add(getattr(dependencia.call, "__name__", ""))
        pilha.extend(dependencia.dependencies)
    return nomes


def _rota(caminho: str):
    return next(r for r in alertas.router.routes if r.path == caminho)


def test_reabrir_exige_a_mesma_credencial_do_resolver():
    """Este router é misto de propósito: `/alertas/verificar` é rota de MÁQUINA
    e se protege por `X-Scheduler-Secret`, não por JWT (o comentário acima de
    `listar_alertas` explica). Reabrir é ação de gente e tem de cair do lado do
    resolver — herdar o guard do vizinho errado abriria o desfazer a quem só
    tem o segredo do cron."""
    assert "get_current_coordenador" in _guards(_rota("/alertas/{alerta_id}/reabrir"))
    assert _guards(_rota("/alertas/{alerta_id}/reabrir")) == _guards(
        _rota("/alertas/{alerta_id}/resolver")
    )
