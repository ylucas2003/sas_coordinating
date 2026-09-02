"""A resposta da sessão de treino (`listas.atualizar_estudo`, migration 0042).

Até a 0042 a alternativa escolhida morria no `useState` da tela. Agora ela é
gravada — e as regras que a gravação precisa honrar são todas do tipo que erra
em silêncio:

  1. **Quem confere é o servidor.** `acertou` sai da comparação com o gabarito
     do banco, e não do corpo da requisição. É dele que sairá a leitura de em
     que assunto o aluno erra; aceitá-lo de fora poria essa leitura a um `curl`
     de distância de discordar da prova.
  2. **`None` não é `False`.** Questão sem gabarito — dissertativa, ou objetiva
     cujo gabarito não foi importado — não tem como ser conferida. "Não dá para
     dizer" e "errou" são conselhos de estudo opostos.
  3. **Responder não é marcar resolvida.** As duas colunas dizem coisas
     diferentes e a tela as separa; encadeá-las aqui apagaria a distinção que a
     tela de progresso é obrigada a fazer.
  4. **Campo ausente não mexe em nada.** É o contrato do PUT desde a 0029, e
     agora vale para três campos em vez de dois.
"""

from __future__ import annotations

import pytest

from app.banco import listas
from app.schemas.banco import AtualizarEstudo

from .fake_postgrest import FakeCliente

ALUNO = "aluno-a"
OUTRO = "aluno-b"


def questao(id_: str, *, gabarito: str | None, dissertativa: bool = False) -> dict:
    return {
        "id": id_,
        "vestibular": "ITA",
        "ano": 2019,
        "fase": 2 if dissertativa else 1,
        "materia": "Matemática",
        "numero": 1,
        "dissertativa": dissertativa,
        "enunciado_md": "…",
        "gabarito": gabarito,
        "gabarito_origem": "banca" if gabarito else None,
        "gabarito_confianca": None,
        "imagem_url": None,
        "usa_imagem_no_render": False,
        "resolucao_url": None,
        "resolucao_md": None,
        "resolucao_origem": None,
        "extraido_por": "pipeline",
        "revisado": False,
    }


ACERVO = [
    questao("objetiva_com_gabarito", gabarito="B"),
    questao("objetiva_sem_gabarito", gabarito=None),
    questao("dissertativa_q03", gabarito=None, dissertativa=True),
]


@pytest.fixture
def cliente() -> FakeCliente:
    return FakeCliente(
        {
            "questao_vestibular": {q["id"]: dict(q) for q in ACERVO},
            "questao_vestibular_topico": {},
            "topico_taxonomia": {},
            "questao_estudo_aluno": {},
        }
    )


# ─── 1 · Quem confere é o servidor ───────────────────────────────────────


def test_o_corpo_da_requisicao_nao_tem_como_declarar_acertou():
    """A trava do contrato: `acertou` não é campo de entrada. Mandá-lo é
    ignorado pelo Pydantic, e o servidor calcula o seu."""
    corpo = AtualizarEstudo.model_validate({"alternativaEscolhida": "A", "acertou": True})

    assert corpo.alternativaEscolhida == "A"
    assert not hasattr(corpo, "acertou")


def test_letra_certa_e_letra_errada(cliente):
    certa = listas.atualizar_estudo(
        cliente, ALUNO, "objetiva_com_gabarito", alternativa_escolhida="B"
    )
    errada = listas.atualizar_estudo(
        cliente, OUTRO, "objetiva_com_gabarito", alternativa_escolhida="D"
    )

    assert (certa.alternativaEscolhida, certa.acertou) == ("B", True)
    assert (errada.alternativaEscolhida, errada.acertou) == ("D", False)


def test_a_letra_e_normalizada(cliente):
    """O que chega da tela é a letra de um botão, mas a rota é pública para
    quem tiver token: " b " tem de virar "B" antes de encostar no gabarito."""
    estudo = listas.atualizar_estudo(
        cliente, ALUNO, "objetiva_com_gabarito", alternativa_escolhida=" b "
    )

    assert estudo.alternativaEscolhida == "B"
    assert estudo.acertou is True


# ─── 2 · `None` não é `False` ────────────────────────────────────────────


@pytest.mark.parametrize("questao_id", ["objetiva_sem_gabarito", "dissertativa_q03"])
def test_questao_sem_gabarito_grava_a_letra_e_deixa_acertou_nulo(cliente, questao_id):
    """420 das 934 originais são dissertativas, e isso é o esperado, não dado
    faltando (docs/22 §8, risco 4). Marcar `False` aqui diria ao aluno que ele
    errou uma questão que ninguém corrigiu."""
    estudo = listas.atualizar_estudo(cliente, ALUNO, questao_id, alternativa_escolhida="A")

    assert estudo.alternativaEscolhida == "A"
    assert estudo.acertou is None


def test_pular_a_questao_limpa_a_resposta(cliente):
    """String vazia é o mesmo idioma de `anotacao` desde a 0029: limpa o campo,
    para que "não respondeu" tenha uma representação só no banco. E limpa o
    `acertou` junto — o CHECK da 0042 não admite acerto sem resposta."""
    listas.atualizar_estudo(cliente, ALUNO, "objetiva_com_gabarito", alternativa_escolhida="B")
    depois = listas.atualizar_estudo(
        cliente, ALUNO, "objetiva_com_gabarito", alternativa_escolhida=""
    )

    assert depois.alternativaEscolhida is None
    assert depois.acertou is None


# ─── 3 · Responder não é marcar resolvida ────────────────────────────────


def test_responder_nao_marca_a_questao_como_resolvida(cliente):
    """A marca é auto-declarada e o aluno é quem a dá, no pé do cartão. Se
    responder marcasse sozinho, "o que você marcou como feito" viraria "o que
    passou na sua frente" — e a tela de progresso mentiria sobre o que é."""
    estudo = listas.atualizar_estudo(
        cliente, ALUNO, "objetiva_com_gabarito", alternativa_escolhida="B"
    )
    assert estudo.resolvida is False


def test_marcar_resolvida_nao_apaga_a_resposta(cliente):
    listas.atualizar_estudo(cliente, ALUNO, "objetiva_com_gabarito", alternativa_escolhida="B")
    depois = listas.atualizar_estudo(cliente, ALUNO, "objetiva_com_gabarito", resolvida=True)

    assert depois.resolvida is True
    assert depois.alternativaEscolhida == "B"
    assert depois.acertou is True


# ─── 4 · Campo ausente não mexe em nada ──────────────────────────────────


def test_anotar_preserva_a_resposta(cliente):
    listas.atualizar_estudo(cliente, ALUNO, "objetiva_com_gabarito", alternativa_escolhida="B")
    depois = listas.atualizar_estudo(
        cliente, ALUNO, "objetiva_com_gabarito", anotacao="errei o sinal"
    )

    assert depois.anotacao == "errei o sinal"
    assert (depois.alternativaEscolhida, depois.acertou) == ("B", True)


def test_refazer_a_questao_sobrescreve_a_tentativa_anterior(cliente):
    """Só a última resposta sobrevive (0042). É o que se quer para "em que
    assunto ele erra HOJE"; histórico de tentativas seria outra tabela."""
    listas.atualizar_estudo(cliente, ALUNO, "objetiva_com_gabarito", alternativa_escolhida="D")
    depois = listas.atualizar_estudo(
        cliente, ALUNO, "objetiva_com_gabarito", alternativa_escolhida="B"
    )

    assert (depois.alternativaEscolhida, depois.acertou) == ("B", True)
    linhas = [
        l
        for l in cliente.db["questao_estudo_aluno"].values()
        if l["aluno_id"] == ALUNO and l["questao_id"] == "objetiva_com_gabarito"
    ]
    assert len(linhas) == 1


def test_a_resposta_de_um_aluno_nao_encosta_na_de_outro(cliente):
    """A PK é composta (aluno_id, questao_id). O upsert tem de casar as DUAS
    colunas — casar só uma sobrescreveria a linha de outra pessoa."""
    listas.atualizar_estudo(cliente, ALUNO, "objetiva_com_gabarito", alternativa_escolhida="B")
    listas.atualizar_estudo(cliente, OUTRO, "objetiva_com_gabarito", alternativa_escolhida="D")

    do_aluno = [e for e in listas.listar_estudo(cliente, ALUNO)]
    do_outro = [e for e in listas.listar_estudo(cliente, OUTRO)]

    assert [(e.alternativaEscolhida, e.acertou) for e in do_aluno] == [("B", True)]
    assert [(e.alternativaEscolhida, e.acertou) for e in do_outro] == [("D", False)]


def test_questao_inexistente_recusa(cliente):
    with pytest.raises(ValueError, match="inexistente"):
        listas.atualizar_estudo(cliente, ALUNO, "nao_existe", alternativa_escolhida="A")
