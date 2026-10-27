"""A leitura da trilha de auditoria fora da rota: `consultar` e `nomes_dos_atores`.

Desceram de `routes/auditoria.py` para `app/auditoria.py` porque a tool que
conta "quem mudou o quê" (docs/43 §4.3) faz a mesma consulta. O cliente aqui é
o `SyncPostgrestClient` DE VERDADE — o mesmo de produção (supabase_client.py) —
sobre um transporte falso do httpx: o teste confere a URL que iria ao
PostgREST, que é onde um filtro errado mora sem dar erro. O que se trava:

  1. **A rota faz a mesma requisição de sempre**, filtro por filtro, e devolve
     a mesma forma — com `canais` agora completo.
  2. **Listas viram `in`/`or`**, e um prefixo com vírgula ou aspas não parte o
     `or` ao meio; um item só continua `eq`/`like`.
  3. **Os nomes só consultam o que podem**: o tipo decide a tabela, e o e-mail
     digitado em `login_falhou` nunca vai a um `in` de coluna uuid.
  4. **A leitura do MCP fica fora da linha do tempo padrão**, como os logins:
     é uma linha por chamada de tool, e misturada às edições humanas ela as
     soterraria (revisão paralela de 25/10).
"""

from __future__ import annotations

import httpx
import pytest
from postgrest import SyncPostgrestClient
from postgrest.utils import SyncClient

from app import auditoria
from app.mcp import auditoria_mcp
from app.routes import auditoria as rota_auditoria

COORD = "11111111-1111-1111-1111-111111111111"
ALUNO = "22222222-2222-2222-2222-222222222222"
CANTINA = "33333333-3333-3333-3333-333333333333"
COLUNAS = "id, ocorrido_em, acao, canal, ator_tipo, ator_id, recurso, ip, detalhe, request_id"
#: O que não altera nada sai por padrão: os logins e a leitura do MCP.
SEM_LOGINS = ("acao", "not.in.(login_ok,login_falhou,primeiro_acesso_bloqueado,mcp_ferramenta_chamada)")


class _Gravador(SyncPostgrestClient):
    """PostgREST de mentira: guarda cada requisição e devolve as linhas da tabela."""

    def __init__(self, tabelas: dict[str, list[dict]] | None = None):
        self.pedidos: list[httpx.Request] = []
        self._tabelas = tabelas or {}
        super().__init__("http://postgrest.teste")

    def create_session(self, base_url, headers, timeout, verify=True):
        def responder(pedido: httpx.Request) -> httpx.Response:
            self.pedidos.append(pedido)
            return httpx.Response(200, json=self._tabelas.get(pedido.url.path.strip("/"), []))

        return SyncClient(base_url=base_url, headers=headers, transport=httpx.MockTransport(responder))

    def parametros(self, tabela: str) -> list[tuple[str, str]]:
        (pedido,) = [p for p in self.pedidos if p.url.path.strip("/") == tabela]
        return list(pedido.url.params.multi_items())

    def tabelas_lidas(self) -> list[str]:
        return [p.url.path.strip("/") for p in self.pedidos]


# ─── 1 · A rota ──────────────────────────────────────────────────────────


EVENTOS = [
    {"id": 41, "acao": "nota_editada", "canal": "nota", "ator_tipo": "coordenador",
     "ator_id": COORD, "recurso": f"nota/{ALUNO}/sim-1", "detalhe": {"de": 4, "para": 5}},
    {"id": 40, "acao": "foto_perfil_definida", "canal": "acesso", "ator_tipo": "aluno",
     "ator_id": ALUNO, "recurso": f"aluno/{ALUNO}", "detalhe": None},
]


def _rota(gravador, monkeypatch, **filtros):
    monkeypatch.setattr(rota_auditoria, "get_supabase", lambda: gravador)
    argumentos = {
        "canal": None, "ator_id": None, "recurso": None, "desde": None, "ate": None,
        "limite": 100, "antes_de_id": None, "incluir_logins": False,
    }
    return rota_auditoria.listar_eventos(**{**argumentos, **filtros})


class TestRota:
    def test_a_requisicao_e_a_de_sempre_filtro_por_filtro(self, monkeypatch):
        gravador = _Gravador()
        _rota(
            gravador, monkeypatch, canal="nota", ator_id=COORD, recurso=f"nota/{ALUNO}",
            desde="2026-10-01", ate="2026-10-24T23:59:59Z", limite=2, antes_de_id=99,
        )
        assert gravador.parametros("evento_auditoria") == [
            ("select", COLUNAS),
            ("order", "id.desc"),
            ("limit", "2"),
            SEM_LOGINS,
            ("canal", "eq.nota"),
            ("ator_id", f"eq.{COORD}"),
            ("recurso", f"like.nota/{ALUNO}%"),
            ("ocorrido_em", "gte.2026-10-01"),
            ("ocorrido_em", "lte.2026-10-24T23:59:59Z"),
            ("id", "lt.99"),
        ]

    def test_sem_filtro_so_tira_o_que_nao_altera_nada(self, monkeypatch):
        gravador = _Gravador()
        _rota(gravador, monkeypatch)
        assert gravador.parametros("evento_auditoria") == [
            ("select", COLUNAS), ("order", "id.desc"), ("limit", "100"), SEM_LOGINS,
        ]

    def test_com_logins_nao_ha_filtro_de_acao(self, monkeypatch):
        gravador = _Gravador()
        _rota(gravador, monkeypatch, incluir_logins=True)
        assert SEM_LOGINS not in gravador.parametros("evento_auditoria")

    def test_a_resposta_tem_a_forma_de_sempre(self, monkeypatch):
        gravador = _Gravador({
            "evento_auditoria": [dict(e) for e in EVENTOS],
            "usuario_coordenacao": [{"id": COORD, "nome": "Leo", "foto_perfil_storage": "f/leo"}],
            "aluno": [{"id": ALUNO, "nome": "Ana", "foto_perfil_storage": None}],
        })
        resposta = _rota(gravador, monkeypatch, limite=2)

        assert [(e["id"], e["ator_nome"], e["ator_tem_foto"]) for e in resposta["eventos"]] == [
            (41, "Leo", True),
            (40, "Ana", False),
        ]
        assert resposta["canais"] == list(rota_auditoria.CANAIS)
        # `limite` eventos de volta = há mais; o cursor é o id do último.
        assert resposta["proximo_antes_de_id"] == 40
        assert set(resposta) == {"eventos", "canais", "proximo_antes_de_id"}

    def test_pagina_incompleta_nao_tem_cursor(self, monkeypatch):
        gravador = _Gravador({"evento_auditoria": [dict(EVENTOS[0])]})
        assert _rota(gravador, monkeypatch, limite=2)["proximo_antes_de_id"] is None

    def test_os_canais_que_a_trilha_grava_estao_todos(self):
        assert {"criterio", "cantina", "captacao", "mcp"} <= set(rota_auditoria.CANAIS)
        assert rota_auditoria.CANAIS[:5] == ("acesso", "nota", "simulado", "ciclo", "canvas")

    def test_o_canal_do_mcp_tambem_nao_traz_a_leitura_sem_pedir(self, monkeypatch):
        """Como `canal=acesso` não traz login: o canal `mcp` mostra as conexões
        emitidas e revogadas, e as leituras só com `incluir_logins`."""
        gravador = _Gravador()
        _rota(gravador, monkeypatch, canal="mcp")
        assert SEM_LOGINS in gravador.parametros("evento_auditoria")


# ─── 2 · Listas e filtros novos ──────────────────────────────────────────


def _consulta(**filtros) -> list[tuple[str, str]]:
    gravador = _Gravador()
    auditoria.consultar(gravador, **filtros)
    return gravador.parametros("evento_auditoria")


class TestConsultar:
    def test_varios_canais_e_atores_viram_in(self):
        params = _consulta(canais=["nota", "simulado"], ator_ids=[COORD, ALUNO])
        assert ("canal", "in.(nota,simulado)") in params
        assert ("ator_id", f"in.({COORD},{ALUNO})") in params

    def test_acao_soma_com_o_corte_dos_logins(self):
        params = _consulta(acao="nota_editada")
        assert ("acao", "eq.nota_editada") in params
        assert SEM_LOGINS in params

    def test_varios_prefixos_viram_um_or_de_likes(self):
        params = _consulta(recurso_prefixos=["simulado/sim-1", "nota/%/sim-1"])
        assert ("or", '(recurso.like."simulado/sim-1%",recurso.like."nota/%/sim-1%")') in params
        assert not [p for p in params if p[0] == "recurso"]

    def test_virgula_e_aspas_no_prefixo_nao_partem_o_or(self):
        params = _consulta(recurso_prefixos=['criterio/a,b', 'x"y'])
        assert ("or", '(recurso.like."criterio/a,b%",recurso.like."x\\"y%")') in params

    def test_vazio_nao_filtra(self):
        assert _consulta(canais=[], ator_ids=[None, ""], recurso_prefixos=[""]) == [
            ("select", COLUNAS), ("order", "id.desc"), ("limit", "100"), SEM_LOGINS,
        ]

    @pytest.mark.parametrize(("pedido", "vai"), [(0, "1"), (-5, "1"), (500, "500"), (10_000, "500")])
    def test_o_limite_fica_entre_1_e_o_maximo(self, pedido, vai):
        assert ("limit", vai) in _consulta(limite=pedido)

    def test_devolve_as_linhas_cruas(self):
        gravador = _Gravador({"evento_auditoria": [dict(e) for e in EVENTOS]})
        assert auditoria.consultar(gravador) == EVENTOS


# ─── 4 · A leitura do MCP ────────────────────────────────────────────────


class TestLeituraDoMcp:
    def test_a_acao_e_a_que_o_mcp_grava(self):
        """Espelho: quem grava é `auditoria_mcp`, quem esconde é `auditoria`.
        Se o nome mudar de um lado só, a leitura volta para a linha do tempo."""
        assert auditoria.ACAO_LEITURA_DO_MCP == auditoria_mcp.ACAO_CHAMADA
        assert auditoria_mcp.CANAL == "mcp"

    def test_so_a_leitura_sai_e_a_conexao_fica(self):
        """Emitir e revogar uma conexão de IA é alteração: fica na linha do tempo."""
        assert auditoria_mcp.ACAO_CHAMADA in auditoria.ACOES_SEM_ALTERACAO
        assert set(auditoria.ACOES_DE_ACESSO) < set(auditoria.ACOES_SEM_ALTERACAO)
        for acao in (auditoria_mcp.ACAO_CONEXAO_EMITIDA, auditoria_mcp.ACAO_CONEXAO_REVOGADA):
            assert acao not in auditoria.ACOES_SEM_ALTERACAO

    def test_com_logins_a_leitura_volta(self):
        assert not [p for p in _consulta(incluir_logins=True) if p[0] == "acao"]


# ─── 3 · Nomes dos atores ────────────────────────────────────────────────


class TestNomesDosAtores:
    def test_o_tipo_decide_a_tabela(self):
        gravador = _Gravador({
            "usuario_coordenacao": [{"id": COORD, "nome": "Leo", "foto_perfil_storage": None}],
            "aluno": [{"id": ALUNO, "nome": "Ana", "foto_perfil_storage": "f/ana"}],
        })
        nomes, tem_foto = auditoria.nomes_dos_atores(
            gravador, [("coordenador", COORD), ("aluno", ALUNO), ("cantina", CANTINA)]
        )
        assert nomes == {COORD: "Leo", ALUNO: "Ana"}
        assert tem_foto == {COORD: False, ALUNO: True}
        assert gravador.parametros("usuario_coordenacao")[-1] == ("id", f"in.({COORD})")
        assert gravador.parametros("aluno")[-1] == ("id", f"in.({ALUNO})")

    def test_email_digitado_nunca_vai_a_consulta(self):
        gravador = _Gravador()
        nomes, tem_foto = auditoria.nomes_dos_atores(
            gravador, [("coordenador", "alguem@aridesa.com.br"), ("coordenador", None), (None, COORD)]
        )
        assert (nomes, tem_foto, gravador.pedidos) == ({}, {}, [])

    def test_repetido_vai_uma_vez_e_ordenado(self):
        outro = "00000000-0000-0000-0000-000000000000"
        gravador = _Gravador()
        auditoria.nomes_dos_atores(gravador, [("coordenador", COORD), ("coordenador", outro),
                                              ("coordenador", COORD)])
        assert gravador.tabelas_lidas() == ["usuario_coordenacao"]
        assert gravador.parametros("usuario_coordenacao")[-1] == ("id", f"in.({outro},{COORD})")

    def test_ator_que_sumiu_fica_de_fora(self):
        gravador = _Gravador({"usuario_coordenacao": []})
        assert auditoria.nomes_dos_atores(gravador, [("coordenador", COORD)]) == ({}, {})
