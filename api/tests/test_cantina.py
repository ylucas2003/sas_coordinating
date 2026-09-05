"""Cantina — o terceiro tipo de sessão, o prazo e o teto de escolhas (docs/38).

Duas metades, e a primeira é a que existe por causa de um bug que já aconteceu
neste projeto uma vez.

**A metade de segurança.** Até 05/09 o SAS tinha exatamente DOIS tipos de
sessão, e vários lugares dividiam o mundo em "aluno" e "todo o resto" — com o
"resto" caindo no ramo de COORDENAÇÃO. Enquanto só existiam dois tipos, o
`else` estava certo. Com a cantina, cada um desses `else` vira uma escalada de
privilégio: `foto_perfil._entidade_do_usuario` daria a ela `UPDATE` em
`usuario_coordenacao`. É a mesma forma da vulnerabilidade do token de download
(PR #7, `test_auth_chat.py`), e por isso os testes daqui são irmãos daqueles.

**A metade de regra.** O backend nunca escreve SQL (CLAUDE.md), então prazo,
teto por bloco e mínimo por bloco são Python — não `CHECK`. Regra que só existe
em Python é regra que só existe se tiver teste.

Rodar:  cd api && ./.venv/bin/python -m pytest tests/test_cantina.py -q
"""

import asyncio
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.auth import (
    TIPOS_DE_SESSAO,
    get_current_administrador,
    get_current_aluno,
    get_current_cantina,
    get_current_coordenador,
    papel_da_sessao,
)
from app.routes.cantina import (
    _estado,
    _instante,
    _prazo_pela_regra,
    _validar_escolhas,
)

SESSAO_CANTINA = {"tipo": "cantina", "sub": "conta-1", "cantina_id": "cant-1", "nome": "Copa"}


def _chamar(guard, usuario):
    """Roda um guard `async def` com o payload já decodificado.

    `asyncio.run` e não `pytest.mark.asyncio`: o projeto não tem
    `pytest-asyncio` instalado, e um `async def test_` sem ele é SILENCIOSAMENTE
    PULADO — que num arquivo de teste de segurança é pior que não existir. É o
    mesmo padrão de `test_papeis.py`.
    """
    return asyncio.run(guard(usuario))


# ─── Segurança · a cantina não vaza para os outros papéis ────────────────


def test_cantina_e_um_tipo_de_sessao():
    """Se não estiver aqui, `get_current_user` recusa o token e ninguém entra."""
    assert "cantina" in TIPOS_DE_SESSAO


def test_cantina_nao_passa_por_guard_de_coordenacao():
    """O motivo de a cantina ser `tipo` e não `papel`.

    `get_current_coordenador` aceita TODO papel de propósito (administrador é
    coordenador com mais poderes). Um `papel: "cantina"` dentro de
    `usuario_coordenacao` passaria por aqui e abriria as 39 rotas de
    coordenação para quem trabalha na copa.
    """
    with pytest.raises(HTTPException) as erro:
        _chamar(get_current_coordenador, SESSAO_CANTINA)
    assert erro.value.status_code == 403


def test_cantina_nao_passa_por_guard_de_aluno():
    with pytest.raises(HTTPException) as erro:
        _chamar(get_current_aluno, SESSAO_CANTINA)
    assert erro.value.status_code == 403


def test_cantina_nao_passa_por_guard_de_administrador():
    """Duas camadas: ela nem chega ao teste de papel, porque
    `get_current_administrador` depende do guard de coordenação."""
    with pytest.raises(HTTPException) as erro:
        _chamar(get_current_administrador, SESSAO_CANTINA)
    assert erro.value.status_code == 403


def test_papel_da_sessao_ignora_a_cantina():
    """`papel` é atributo de sessão de COORDENAÇÃO. Devolver 'coordenador' aqui
    — o fallback tolerante para tokens anteriores à 0045 — daria à cantina o
    papel base da coordenação."""
    assert papel_da_sessao(SESSAO_CANTINA) is None


def test_coordenacao_nao_passa_por_guard_de_cantina():
    """A recusa vale nos DOIS sentidos: um coordenador publicando cardápio em
    nome da cantina apagaria a autoria de `cardapio.criado_por`."""
    with pytest.raises(HTTPException) as erro:
        _chamar(get_current_cantina, {"tipo": "coordenador", "sub": "c1", "papel": "administrador"})
    assert erro.value.status_code == 403


def test_token_de_cantina_sem_estabelecimento_e_recusado():
    """Fail-closed: toda consulta da cantina filtra por `cantina_id`, e um
    token sem o claim não filtraria nada — que numa rota de listagem é
    vazamento entre cantinas, não erro de digitação."""
    with pytest.raises(HTTPException) as erro:
        _chamar(get_current_cantina, {"tipo": "cantina", "sub": "c1"})
    assert erro.value.status_code == 403


def test_foto_de_perfil_nao_cai_no_ramo_da_coordenacao():
    """⚠️ O teste mais importante do arquivo.

    `_entidade_do_usuario` devolvia `("coordenador", "usuario_coordenacao",
    user["sub"])` para tudo que não fosse aluno. Com a cantina existindo, isso
    daria a ela leitura E ESCRITA em `usuario_coordenacao` pelo próprio `sub` —
    foto de perfil é `UPDATE`.
    """
    from app.routes.foto_perfil import _entidade_do_usuario

    with pytest.raises(HTTPException) as erro:
        _entidade_do_usuario(SESSAO_CANTINA)
    assert erro.value.status_code == 403

    # Os dois ramos legítimos continuam intactos.
    assert _entidade_do_usuario({"tipo": "aluno", "aluno_id": "a1"})[1] == "aluno"
    assert _entidade_do_usuario({"tipo": "coordenador", "sub": "c1"})[1] == "usuario_coordenacao"


def test_chat_recusa_a_cantina():
    """Já era fail-closed antes da cantina existir, e é por isso que
    `chat/rotas.py` não precisou de conserto — este teste tranca o
    comportamento para que ninguém o "conserte" para um `else`."""
    from app.chat.rotas import _usuario_do_token

    with pytest.raises(HTTPException) as erro:
        _usuario_do_token(SESSAO_CANTINA)
    assert erro.value.status_code == 403


# ─── O prazo ─────────────────────────────────────────────────────────────


def test_prazo_pela_regra_usa_o_fuso_da_escola():
    """"Véspera às 20h" é 20h EM FORTALEZA, não em UTC.

    Sem o fuso, o prazo de um almoço de terça cairia às 17h de segunda para
    quem lê — três horas a menos de janela, todo dia, sem ninguém entender por
    quê.
    """
    cantina = {"prazo_padrao_dias_antes": 1, "prazo_padrao_hora": "20:00:00"}
    prazo = _prazo_pela_regra(cantina, date(2026, 9, 8))
    # Fortaleza é UTC-3 o ano inteiro (o Brasil não tem mais horário de verão).
    assert prazo == datetime(2026, 9, 7, 23, 0, tzinfo=UTC)


def test_prazo_com_zero_dias_antes_e_no_proprio_dia():
    """A regra aceita "no mesmo dia, às 9h" — cantina que decide de manhã."""
    cantina = {"prazo_padrao_dias_antes": 0, "prazo_padrao_hora": "09:00:00"}
    prazo = _prazo_pela_regra(cantina, date(2026, 9, 8))
    assert prazo == datetime(2026, 9, 8, 12, 0, tzinfo=UTC)


def test_prazo_cai_para_o_padrao_da_migration_quando_a_linha_vem_sem_regra():
    """Linha sem os campos não pode explodir a criação do cardápio, e o
    fallback tem de ser o MESMO default da 0047 — véspera às 20h. Um fallback
    diferente aqui faria o prazo mudar conforme a origem da linha."""
    prazo = _prazo_pela_regra({}, date(2026, 9, 8))
    assert prazo == datetime(2026, 9, 7, 23, 0, tzinfo=UTC)


# ─── Os cinco estados ────────────────────────────────────────────────────


AGORA = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
FUTURO = "2026-09-07T23:00:00+00:00"
PASSADO = "2026-09-06T23:00:00+00:00"


@pytest.mark.parametrize(
    ("cardapio", "esperado"),
    [
        ({"sem_refeicao": True, "publicado_em": None, "pedidos_ate": None}, "sem-refeicao"),
        # Dia marcado como sem refeição vence a publicação: a cantina disse que
        # não haverá comida, e um "aberto" aqui convidaria o aluno a pedir nada.
        ({"sem_refeicao": True, "publicado_em": "2026-09-01", "pedidos_ate": FUTURO}, "sem-refeicao"),
        ({"sem_refeicao": False, "publicado_em": None, "pedidos_ate": FUTURO}, "rascunho"),
        ({"sem_refeicao": False, "publicado_em": "2026-09-01", "pedidos_ate": FUTURO}, "aberto"),
        ({"sem_refeicao": False, "publicado_em": "2026-09-01", "pedidos_ate": PASSADO}, "fechado"),
        # Publicado sem prazo não deveria existir (a rota de publicar recusa),
        # mas se existir vale como FECHADO — o lado seguro: um cardápio sem
        # prazo aceitando pedido para sempre é o que a decisão 8.0.5 proíbe.
        ({"sem_refeicao": False, "publicado_em": "2026-09-01", "pedidos_ate": None}, "fechado"),
    ],
)
def test_estados_do_cardapio(cardapio, esperado):
    assert _estado(cardapio, AGORA) == esperado


def test_instante_aceita_o_z_do_postgrest():
    assert _instante("2026-09-07T23:00:00Z") == datetime(2026, 9, 7, 23, 0, tzinfo=UTC)
    assert _instante(None) is None


# ─── O teto de escolhas por bloco ────────────────────────────────────────


def _cardapio_de_teste() -> dict:
    """Um recorte do cardápio da foto: guarnição com teto 2, proteína obrigatória."""
    return {
        "blocos": [
            {
                "nome": "Guarnição",
                "escolhas_minimas": 0,
                "escolhas_maximas": 2,
                "opcoes": [
                    {"id": "arroz", "disponivel": True},
                    {"id": "feijao", "disponivel": True},
                    {"id": "macarrao", "disponivel": True},
                ],
            },
            {
                "nome": "Proteínas",
                "escolhas_minimas": 1,
                "escolhas_maximas": 1,
                "opcoes": [
                    {"id": "frango", "disponivel": True},
                    {"id": "suino", "disponivel": False},
                ],
            },
        ]
    }


def test_escolha_valida_passa():
    _validar_escolhas(_cardapio_de_teste(), ["arroz", "feijao", "frango"])


def test_estourar_o_teto_do_bloco_e_recusado():
    with pytest.raises(HTTPException) as erro:
        _validar_escolhas(_cardapio_de_teste(), ["arroz", "feijao", "macarrao", "frango"])
    assert erro.value.status_code == 422
    # A mensagem diz QUAL bloco: sem isso o aluno adivinha em qual das quatro
    # listas ele errou.
    assert "Guarnição" in erro.value.detail


def test_bloco_obrigatorio_vazio_e_recusado():
    with pytest.raises(HTTPException) as erro:
        _validar_escolhas(_cardapio_de_teste(), ["arroz"])
    assert erro.value.status_code == 422
    assert "Proteínas" in erro.value.detail


def test_opcao_indisponivel_e_recusada():
    """Acabou o suíno às 11h40, com o prazo ainda aberto. O servidor recusa —
    a tela do aluno pode estar aberta desde antes."""
    with pytest.raises(HTTPException) as erro:
        _validar_escolhas(_cardapio_de_teste(), ["suino"])
    assert erro.value.status_code == 422


def test_opcao_de_outro_cardapio_e_recusada():
    """Não é paranoia: `opcao_ids` vem do cliente, e sem esta checagem um id
    colado de outro dia entraria no pedido e apareceria na contagem da cantina."""
    with pytest.raises(HTTPException) as erro:
        _validar_escolhas(_cardapio_de_teste(), ["frango", "sobremesa-de-outro-dia"])
    assert erro.value.status_code == 422


def test_mesma_opcao_duas_vezes_e_recusada():
    """A PK composta de `pedido_refeicao_item` já impediria, mas com um 500 do
    PostgREST em vez de uma frase — e o aluno mandaria de novo."""
    with pytest.raises(HTTPException) as erro:
        _validar_escolhas(_cardapio_de_teste(), ["arroz", "arroz", "frango"])
    assert erro.value.status_code == 422


def test_bloco_sem_minimo_aceita_lista_vazia():
    """Guarnição é opcional. Quem não quer acompanhamento não é obrigado a
    escolher um só porque o bloco existe."""
    _validar_escolhas(
        {"blocos": [_cardapio_de_teste()["blocos"][0]]},
        [],
    )


# ─── A janela do aluno ───────────────────────────────────────────────────


def test_janela_do_aluno_tem_teto():
    """"Todos os dias publicados" tem limite, e o limite é a armadilha 2: sem
    janela, a resposta cresce em silêncio no dia em que alguém lançar o
    semestre inteiro."""
    from app.routes.cantina import DIAS_VISIVEIS_PARA_O_ALUNO

    assert DIAS_VISIVEIS_PARA_O_ALUNO == 30
    hoje = date(2026, 9, 5)
    assert hoje + timedelta(days=DIAS_VISIVEIS_PARA_O_ALUNO) == date(2026, 10, 5)
