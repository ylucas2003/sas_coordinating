"""O script que devolve à fila as aulas que o S3 derrubou.

O que estes testes trancam são as recusas: não tocar em nada com o S3 ainda
fora, não reabrir aula cuja gravação já saiu do Canvas, e nunca encostar numa
aula que pode ter vídeo no canal.
"""

import sys
from typing import Any

import pytest

from scripts import reabrir_aulas_com_erro as script
from tests.fake_postgrest import FakeCliente

_BUCKET = "sas-gravacoes"

# Mensagens no formato que `rotas._descrever` grava: "Classe: mensagem".
_ERRO_BUCKET_RECUSANDO = (
    "S3UploadFailedError: Failed to upload /tmp/aula-123/composto.mp4 to "
    "sas-gravacoes/aulas/692/123.mp4: An error occurred (AllAccessDisabled) when "
    "calling the PutObject operation: All access to this object has been disabled"
)
_ERRO_REDE = (
    'EndpointConnectionError: Could not connect to the endpoint URL: '
    '"https://sas-gravacoes.s3.amazonaws.com/aulas/692/123.mp4?uploads"'
)
_ERRO_CANVAS = "GravacaoIndisponivel: a conferência 123 não tem recordings"


def _aula(id_: str, *, status: str = "erro", erro: str = _ERRO_BUCKET_RECUSANDO,
          conf: str = "123", tentativas: int = 3) -> dict[str, Any]:
    return {
        "id": id_, "curso_id": "692", "conferencia_id": conf, "titulo": f"AULA {id_}",
        "iniciada_em": "2026-09-28T20:00:00+00:00", "status": status,
        "tentativas": tentativas, "erro_detalhe": erro,
    }


# ─── O que conta como falha de S3 ───────────────────────────────────────────

@pytest.mark.parametrize("erro", [_ERRO_BUCKET_RECUSANDO, _ERRO_REDE,
                                  "S3NaoConfigurado: S3_BUCKET_GRAVACOES não configurado",
                                  "ClientError: bucket sas-gravacoes inacessível"])
def test_reconhece_falha_de_s3(erro: str) -> None:
    assert script.parece_falha_de_s3(erro, _BUCKET)


@pytest.mark.parametrize("erro", [_ERRO_CANVAS, "ReadTimeout", "", None,
                                  "não foi possível conferir se já estava publicado: HttpError 503"])
def test_nao_confunde_outras_falhas_com_s3(erro: str | None) -> None:
    assert not script.parece_falha_de_s3(erro, _BUCKET)


# ─── Triagem ────────────────────────────────────────────────────────────────

def test_triagem_separa_os_quatro_destinos() -> None:
    aulas = [
        _aula("viva", conf="1"),
        _aula("expirada", conf="2"),
        _aula("canvas", conf="1", erro=_ERRO_CANVAS),
        {**_aula("curso-mudo", conf="9"), "curso_id": "693"},
    ]
    t = script.triar(aulas, {"692": {"1"}, "693": None}, bucket=_BUCKET, todas=False)
    assert [a["id"] for a in t.reabrir] == ["viva"]
    assert [a["id"] for a in t.gravacao_expirada] == ["expirada"]
    assert [a["id"] for a in t.outro_erro] == ["canvas"]
    assert [a["id"] for a in t.nao_conferidas] == ["curso-mudo"]


def test_todas_inclui_outro_erro_mas_ainda_exige_a_gravacao() -> None:
    aulas = [_aula("a", conf="1", erro=_ERRO_CANVAS), _aula("b", conf="2", erro=_ERRO_CANVAS)]
    t = script.triar(aulas, {"692": {"1"}}, bucket=_BUCKET, todas=True)
    assert [a["id"] for a in t.reabrir] == ["a"]
    assert [a["id"] for a in t.gravacao_expirada] == ["b"]


# ─── Escrita ────────────────────────────────────────────────────────────────

def test_reabrir_zera_tentativas_e_volta_para_pendente() -> None:
    db = {"aula_gravacao": {"a": _aula("a")}}
    assert script.reabrir(FakeCliente(db), [db["aula_gravacao"]["a"]]) == 1
    linha = db["aula_gravacao"]["a"]
    assert linha["status"] == "pendente"
    assert linha["tentativas"] == 0
    assert linha["erro_detalhe"] is None


def test_reabrir_nao_arranca_aula_que_uma_rodada_pegou() -> None:
    """Lida em 'erro', mas uma rodada a pegou antes da escrita."""
    lida = _aula("a")
    db = {"aula_gravacao": {"a": {**lida, "status": "baixando"}}}
    assert script.reabrir(FakeCliente(db), [lida]) == 0
    assert db["aula_gravacao"]["a"]["status"] == "baixando"


# ─── Ponta a ponta, com S3 e Canvas falsos ──────────────────────────────────

def _rodar(monkeypatch: pytest.MonkeyPatch, db: dict, *args: str,
           s3: str | None = None, gravacoes: dict | None = None) -> int:
    monkeypatch.setattr(script, "_s3_respondendo", lambda: s3)
    monkeypatch.setattr(script, "criar_cliente_supabase", lambda: FakeCliente(db))
    monkeypatch.setattr(script, "_gravacoes_no_canvas",
                        lambda _ids: gravacoes if gravacoes is not None else {"692": {"123"}})

    def nao_dispara() -> str:
        raise AssertionError("não devia ter disparado rodada")

    monkeypatch.setattr(script, "_disparar_rodada", nao_dispara)
    monkeypatch.setattr(sys, "argv", ["reabrir_aulas_com_erro", *args])
    return script.main()


def _db() -> dict:
    return {
        "aula_gravacao": {
            "erro": _aula("erro"),
            # Os três estados em que pode existir vídeo no canal.
            "pub": _aula("pub", status="publicado"),
            "sem-conf": _aula("sem-conf", status="publicado_sem_confirmacao"),
            "publicando": _aula("publicando", status="publicando"),
        }
    }


def test_com_o_s3_ainda_fora_nada_e_tocado(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _db()

    def nao_le_o_banco() -> None:
        raise AssertionError("com o S3 fora, nem devia ler o banco")

    monkeypatch.setattr(script, "_s3_respondendo", lambda: "S3UploadFailedError: AllAccessDisabled")
    monkeypatch.setattr(script, "criar_cliente_supabase", nao_le_o_banco)
    monkeypatch.setattr(sys, "argv", ["reabrir_aulas_com_erro", "--aplicar"])
    assert script.main() == 1
    assert db["aula_gravacao"]["erro"]["status"] == "erro"


def test_ensaio_nao_grava(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _db()
    assert _rodar(monkeypatch, db) == 0
    assert db["aula_gravacao"]["erro"]["status"] == "erro"
    assert db["aula_gravacao"]["erro"]["tentativas"] == 3


def test_aplicar_reabre_so_o_erro(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _db()
    assert _rodar(monkeypatch, db, "--aplicar") == 0
    assert db["aula_gravacao"]["erro"]["status"] == "pendente"
    assert db["aula_gravacao"]["pub"]["status"] == "publicado"
    assert db["aula_gravacao"]["sem-conf"]["status"] == "publicado_sem_confirmacao"
    assert db["aula_gravacao"]["publicando"]["status"] == "publicando"


def test_gravacao_que_saiu_do_canvas_nao_e_reaberta(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _db()
    assert _rodar(monkeypatch, db, "--aplicar", gravacoes={"692": set()}) == 0
    assert db["aula_gravacao"]["erro"]["status"] == "erro"


def test_disparar_so_depois_de_reabrir(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _db()
    disparos: list[int] = []
    monkeypatch.setattr(script, "_s3_respondendo", lambda: None)
    monkeypatch.setattr(script, "criar_cliente_supabase", lambda: FakeCliente(db))
    monkeypatch.setattr(script, "_gravacoes_no_canvas", lambda _ids: {"692": {"123"}})
    monkeypatch.setattr(script, "_disparar_rodada", lambda: disparos.append(1) or "aceito")
    monkeypatch.setattr(sys, "argv", ["reabrir_aulas_com_erro", "--disparar"])
    script.main()
    assert disparos == [], "no ensaio --disparar não pode pedir rodada"

    monkeypatch.setattr(sys, "argv", ["reabrir_aulas_com_erro", "--aplicar", "--disparar"])
    script.main()
    assert disparos == [1]
