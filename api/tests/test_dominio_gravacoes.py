"""Gravações: `painel(cliente)` e o espelho do mapa de situação (docs/43 §4.3).

A leitura do `GET /gravacoes-aula` virou `consulta.painel(cliente)`, síncrona e
sem `get_supabase()` por dentro, para a tool do assistente ler o mesmo que a
tela. E o mapa `status → situação`, que só existia em TypeScript, ganhou espelho
em Python — com este teste LENDO o .ts, porque duas cópias de uma regra só
continuam iguais se alguém reprovar quando divergirem. O que se trava:

  1. o mapa, os degraus e o fallback são os mesmos do front;
  2. todo `status` que o banco aceita tem situação — senão ele cairia calado
     em "aguardando";
  3. o painel devolve o que a tela sempre recebeu, mais `situacao`, e a rota é
     o painel;
  4. quem leva o painel a um modelo lê a view da 0074, e nem pede a coluna do
     link.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.gravacoes_aula import consulta

from .fake_postgrest import FakeCliente

RAIZ = Path(__file__).resolve().parents[2]
GRAVACOES_TS = RAIZ / "web" / "src" / "dominio" / "gravacoes.ts"
MIGRATIONS = RAIZ / "api" / "migrations"


def _fonte_do_front() -> str:
    assert GRAVACOES_TS.exists(), (
        f"{GRAVACOES_TS} não existe: o teste confere o espelho contra o front e "
        "precisa do checkout inteiro (api/ e web/)"
    )
    return GRAVACOES_TS.read_text(encoding="utf-8")


# ─── 1 · O espelho bate com o front ──────────────────────────────────────


def test_o_mapa_status_situacao_e_o_mesmo_do_front():
    bloco = re.search(
        r"const POR_STATUS\s*:\s*Record<StatusGravacao,\s*Situacao>\s*=\s*\{(?P<corpo>.*?)\n\};",
        _fonte_do_front(),
        re.S,
    )
    assert bloco, "POR_STATUS sumiu de gravacoes.ts (ou mudou de forma): o espelho perdeu a referência"
    corpo = re.sub(r"//[^\n]*", "", bloco["corpo"])
    linhas = [linha.strip() for linha in corpo.splitlines() if linha.strip()]
    pares = re.findall(r"^(\w+)\s*:\s*'(\w+)',?$", "\n".join(linhas), re.M)
    # Uma linha que a expressão não entende (chave entre aspas, spread) faria o
    # teste comparar um mapa menor sem perceber. Melhor reprovar.
    assert len(pares) == len(linhas), f"linhas que o teste não sabe ler: {linhas}"

    assert dict(pares) == consulta.SITUACAO_POR_STATUS


def test_os_degraus_sao_os_mesmos_e_na_mesma_ordem():
    lista = re.search(r"export const SITUACOES = \[(?P<itens>[^\]]*)\] as const", _fonte_do_front())
    assert lista, "SITUACOES sumiu de gravacoes.ts"
    assert tuple(re.findall(r"'(\w+)'", lista["itens"])) == consulta.SITUACOES
    assert set(consulta.SITUACAO_POR_STATUS.values()) <= set(consulta.SITUACOES)


def test_o_status_desconhecido_cai_no_mesmo_degrau_do_front():
    fallback = re.search(r"POR_STATUS\[a\.status\]\s*\?\?\s*'(\w+)'", _fonte_do_front())
    assert fallback, "o fallback de situacaoDe mudou de forma em gravacoes.ts"
    assert fallback[1] == consulta.SITUACAO_DESCONHECIDA
    assert consulta.situacao_de("status_que_nao_existe") == consulta.SITUACAO_DESCONHECIDA
    assert consulta.situacao_de(None) == consulta.SITUACAO_DESCONHECIDA


# ─── 2 · Todo status do banco tem situação ───────────────────────────────


def test_todo_status_que_o_banco_aceita_tem_situacao():
    """A CHECK de `aula_gravacao.status` mais recente é a lista do banco."""
    ultima = None
    for arquivo in sorted(MIGRATIONS.glob("*.sql")):
        if arquivo.name.endswith(".down.sql"):
            continue
        texto = arquivo.read_text(encoding="utf-8")
        if "ADD CONSTRAINT aula_gravacao_status_check" in texto:
            ultima = texto.split("ADD CONSTRAINT aula_gravacao_status_check", 1)[1]
    assert ultima, "não achei a CHECK de aula_gravacao.status nas migrations"
    lista = re.search(r"CHECK \(status IN \((?P<itens>[^)]*)\)\)", ultima)
    assert lista
    assert set(re.findall(r"'(\w+)'", lista["itens"])) == set(consulta.SITUACAO_POR_STATUS)


# ─── 3 · O painel e a rota ───────────────────────────────────────────────


def _cliente() -> FakeCliente:
    return FakeCliente(
        {
            "curso_monitorado_gravacao": {
                "581": {"curso_id": "581", "nome": "Turma 2", "ativo": True,
                        "publicar_no_canvas": False, "canvas_modulo_id": None},
                "580": {"curso_id": "580", "nome": "Turma 1", "ativo": True,
                        "publicar_no_canvas": True, "canvas_modulo_id": 77},
            },
            "aula_gravacao": {
                "a-velha": {
                    "id": "a-velha", "curso_id": "580", "conferencia_id": "conf-1",
                    "titulo": "Física - Prof X", "iniciada_em": "2026-10-20T09:00:00+00:00",
                    "duracao_minutos": 90, "status": "publicado_sem_confirmacao",
                    "tentativas": 1, "youtube_video_id": "abc123",
                    "youtube_titulo": "Física · Prof X", "erro_detalhe": None,
                    "canvas_estado": "publicado", "canvas_pagina_url": "https://canvas/p/1",
                    "canvas_modulo_nome": None, "canvas_erro": None,
                    "atualizado_em": "2026-10-20T11:00:00+00:00",
                    # Localização do vídeo de menor no bucket: nunca sai daqui.
                    "s3_bucket": "privado", "s3_chave_composto": "aulas/a-velha.mp4",
                },
                "a-nova": {
                    "id": "a-nova", "curso_id": "581", "conferencia_id": "conf-2",
                    "titulo": "Química", "iniciada_em": "2026-10-23T09:00:00+00:00",
                    "duracao_minutos": None, "status": "compondo", "tentativas": None,
                    "youtube_video_id": None, "youtube_titulo": None,
                    "erro_detalhe": "x" * 400, "canvas_estado": None,
                    "canvas_pagina_url": None, "canvas_modulo_nome": None,
                    "canvas_erro": "", "atualizado_em": "2026-10-23T10:00:00+00:00",
                },
            },
        }
    )


def test_o_painel_devolve_o_que_a_tela_recebe_mais_a_situacao():
    painel = consulta.painel(_cliente())

    assert painel["cursos"] == [
        {"cursoId": "580", "nome": "Turma 1", "ativo": True,
         "publicarNoCanvas": True, "canvasModuloId": 77},
        {"cursoId": "581", "nome": "Turma 2", "ativo": True,
         "publicarNoCanvas": False, "canvasModuloId": None},
    ]
    nova, velha = painel["aulas"]
    assert nova == {
        "id": "a-nova", "cursoId": "581", "conferenciaId": "conf-2", "titulo": "Química",
        "iniciadaEm": "2026-10-23T09:00:00+00:00", "duracaoMinutos": None,
        "status": "compondo", "situacao": "processando", "tentativas": 0,
        "youtubeVideoId": None, "youtubeTitulo": None, "youtubeUrl": None,
        "erroDetalhe": "x" * 300, "canvasEstado": "pendente", "canvasUrl": None,
        "canvasModulo": None, "canvasErro": None, "atualizadoEm": "2026-10-23T10:00:00+00:00",
    }
    # Subiu sem confirmação ainda é "no YouTube": reprocessar duplicaria o vídeo.
    assert (velha["status"], velha["situacao"]) == ("publicado_sem_confirmacao", "publicado")
    assert velha["youtubeUrl"] == "https://youtu.be/abc123"
    assert not any(chave.startswith("s3") for chave in velha)


def test_a_rota_e_o_painel(monkeypatch):
    cliente = _cliente()
    monkeypatch.setattr(consulta, "get_supabase", lambda: cliente)
    assert consulta.listar_gravacoes() == consulta.painel(cliente)


# ─── 4 · A leitura para um modelo ────────────────────────────────────────


def _cliente_da_ia() -> FakeCliente:
    return FakeCliente(
        {
            "curso_monitorado_gravacao": {
                "580": {"curso_id": "580", "nome": "Turma 1", "ativo": True, "publicar_no_canvas": True},
            },
            consulta.VIEW_PARA_IA: {
                "a-1": {
                    "id": "a-1", "curso_id": "580", "titulo": "Física", "status": "erro",
                    "iniciada_em": "2026-10-20T09:00:00+00:00", "tentativas": 2,
                    "erro_detalhe": "falhou em [vídeo]", "canvas_estado": "pendente",
                    "canvas_modulo_nome": None, "canvas_erro": None,
                    "atualizado_em": "2026-10-20T11:00:00+00:00",
                },
            },
        }
    )


def test_para_ia_le_a_view_e_nao_a_tabela():
    painel = consulta.painel(_cliente_da_ia(), limite_do_erro=None, para_ia=True)
    (aula,) = painel["aulas"]
    assert (aula["id"], aula["situacao"], aula["erroDetalhe"]) == ("a-1", "erro", "falhou em [vídeo]")
    assert aula["youtubeVideoId"] is None and aula["youtubeUrl"] is None and aula["canvasUrl"] is None
    assert aula["conferenciaId"] is None
    assert painel["cursos"][0]["canvasModuloId"] is None


def test_para_ia_pede_o_link_e_nunca_o_s3():
    """O link vai à IA por decisão da coordenação em 30/10 (docs/43 §0.3), como a
    tela o mostra. O S3, onde o vídeo mora, não vai de jeito nenhum."""
    for campos in (consulta._CAMPOS_PARA_IA, consulta._CAMPOS_DO_CURSO_PARA_IA):
        assert not re.search(r"s3_|conferencia|professor|modulo_id|pagina_slug", campos)
    for coluna in ("youtube_video_id", "youtube_titulo", "canvas_pagina_url"):
        assert coluna in consulta._CAMPOS_PARA_IA
