"""Banco de questões: a guarda do filtro e o estudo do aluno, fora da rota.

As duas regras moravam em `routes/banco.py` e desceram para `banco/consultas.py`
para a tool do assistente não ter uma cópia delas (docs/43 §4.3). O que se trava:

  1. **Tópico exige matéria**, no domínio (`validar_filtros`) — e a rota
     continua devolvendo o MESMO 400, com a mesma mensagem, antes de ler
     qualquer coisa do banco.
  2. **O estudo é o do aluno pedido.** `anexar_estudo_do_aluno` lê o estudo uma
     vez para a página inteira e nunca mistura o de outro aluno; a rota só o
     anexa para sessão de aluno, e para a coordenação os campos ficam None.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.banco import consultas
from app.routes import banco as rota_banco
from app.schemas.banco import QuestaoVestibular

from .fake_postgrest import FakeCliente

#: A mensagem que a tela já conhece. Mudar o texto é mudar o contrato do 400.
MENSAGEM_DO_400 = "Filtrar por tópico exige `materia`: o mesmo código existe nas três matérias"

ALUNO = "aluno-a"
OUTRO = "aluno-b"


def _questao(id_: str) -> QuestaoVestibular:
    return QuestaoVestibular(
        id=id_,
        vestibular="ITA",
        ano=2020,
        fase=1,
        materia="Física",
        numero=1,
        dissertativa=False,
        enunciadoMd="",
        usaImagemNoRender=False,
        topicos=[],
        revisado=True,
    )


class _ClienteContado(FakeCliente):
    """O fake de sempre, contando quantas vezes cada tabela foi aberta."""

    def __init__(self, db):
        super().__init__(db)
        self.aberturas: dict[str, int] = {}

    def table(self, nome):
        self.aberturas[nome] = self.aberturas.get(nome, 0) + 1
        return super().table(nome)


def _cliente_com_estudo() -> _ClienteContado:
    return _ClienteContado(
        {
            "questao_estudo_aluno": {
                (ALUNO, "q1"): {"aluno_id": ALUNO, "questao_id": "q1", "resolvida": True,
                                "anotacao": "refazer a conta", "atualizado_em": "2026-10-20"},
                (ALUNO, "q2"): {"aluno_id": ALUNO, "questao_id": "q2", "resolvida": False,
                                "anotacao": None, "atualizado_em": "2026-10-21"},
                # Só o OUTRO aluno resolveu a q3 — não pode vazar para o ALUNO.
                (OUTRO, "q3"): {"aluno_id": OUTRO, "questao_id": "q3", "resolvida": True,
                                "anotacao": "do outro", "atualizado_em": "2026-10-22"},
            }
        }
    )


# ─── 1 · Tópico exige matéria ────────────────────────────────────────────


class TestValidarFiltros:
    def test_topico_sem_materia_e_recusado_com_a_mensagem_de_sempre(self):
        with pytest.raises(consultas.FiltroInvalido) as exc:
            consultas.validar_filtros(consultas.FiltrosQuestoes(topico="1.1"))
        assert str(exc.value) == MENSAGEM_DO_400

    def test_e_um_value_error(self):
        """Quem já trata `ValueError` como entrada ruim não precisa conhecer a classe."""
        assert issubclass(consultas.FiltroInvalido, ValueError)

    @pytest.mark.parametrize(
        "filtros",
        [
            consultas.FiltrosQuestoes(),
            consultas.FiltrosQuestoes(materia="Física", topico="1.1"),
            # "Sem assunto" não é código do edital: não muda de sentido entre matérias.
            consultas.FiltrosQuestoes(topico=consultas.TOPICO_SEM_CLASSIFICACAO),
            consultas.FiltrosQuestoes(vestibular="ITA", anos=[2024], fase=1, busca="lente"),
        ],
    )
    def test_o_resto_passa(self, filtros):
        consultas.validar_filtros(filtros)

    def test_a_rota_devolve_o_mesmo_400_antes_de_abrir_o_banco(self, monkeypatch):
        def sem_banco():
            raise AssertionError("a guarda tem de vir antes de qualquer leitura")

        monkeypatch.setattr(rota_banco, "get_supabase", sem_banco)
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                rota_banco.listar_questoes(
                    materia=None, vestibular=None, anos=None, fase=None, topico="7.2",
                    colecao=None, busca=None, pagina=1, por_pagina=20,
                    user={"tipo": "coordenador", "sub": "coord-1"},
                )
            )
        assert exc.value.status_code == 400
        assert exc.value.detail == MENSAGEM_DO_400


# ─── 2 · O estudo é o do aluno pedido ────────────────────────────────────


class TestAnexarEstudoDoAluno:
    def test_anexa_o_estudo_deste_aluno_e_so_dele(self):
        cliente = _cliente_com_estudo()
        q1, q2, q3, q4 = (_questao(i) for i in ("q1", "q2", "q3", "q4"))

        saida = consultas.anexar_estudo_do_aluno(cliente, [q1, q2, q3, q4], ALUNO)

        assert [q.id for q in saida] == ["q1", "q2", "q3", "q4"]
        assert (q1.resolvida, q1.anotacao) == (True, "refazer a conta")
        assert (q2.resolvida, q2.anotacao) == (False, None)
        # Resolvida pelo OUTRO: para este aluno é questão não tocada.
        assert (q3.resolvida, q3.anotacao) == (False, None)
        # Sem linha de estudo = não tocada, e a leitura certa é `false`, não None.
        assert (q4.resolvida, q4.anotacao) == (False, None)

    def test_uma_leitura_do_estudo_para_a_pagina_inteira(self):
        cliente = _cliente_com_estudo()
        consultas.anexar_estudo_do_aluno(cliente, [_questao(f"q{i}") for i in range(20)], ALUNO)
        assert cliente.aberturas == {"questao_estudo_aluno": 1}

    def test_sem_questao_nao_le_nada(self):
        cliente = _cliente_com_estudo()
        assert consultas.anexar_estudo_do_aluno(cliente, [], ALUNO) == []
        assert cliente.aberturas == {}


class TestARotaSoAnexaParaAluno:
    def test_coordenacao_fica_com_none_e_nao_le_o_estudo(self):
        cliente = _cliente_com_estudo()
        q1 = _questao("q1")
        rota_banco._com_estudo_do_aluno(cliente, {"tipo": "coordenador", "sub": "c"}, [q1])
        assert (q1.resolvida, q1.anotacao) == (None, None)
        assert cliente.aberturas == {}

    def test_aluno_recebe_o_proprio_estudo_pela_rota_inteira(self, monkeypatch):
        """Pela rota de verdade: o filtro, a página e o estudo do aluno da sessão."""
        cliente = _ClienteContado(
            {
                "questao_vestibular": {
                    "q1": {"id": "q1", "vestibular": "ITA", "ano": 2020, "fase": 1,
                           "materia": "Física", "numero": 1, "enunciado_md": "...",
                           "usa_imagem_no_render": False, "revisado": True},
                },
                "questao_vestibular_alternativa": {},
                "questao_vestibular_topico": {},
                "topico_taxonomia": {},
                **_cliente_com_estudo().db,
            }
        )
        monkeypatch.setattr(rota_banco, "get_supabase", lambda: cliente)

        pagina = asyncio.run(
            rota_banco.listar_questoes(
                materia=None, vestibular=None, anos=None, fase=None, topico=None,
                colecao=None, busca=None, pagina=1, por_pagina=20,
                user={"tipo": "aluno", "sub": "s", "aluno_id": ALUNO},
            )
        )
        assert [(q.id, q.resolvida, q.anotacao) for q in pagina.questoes] == [
            ("q1", True, "refazer a conta")
        ]
