"""Casamento aula → página do Canvas.

Os títulos aqui são LITERAIS, copiados da API do Canvas em 29/08/2026. É de
propósito: o valor destes testes vem de reproduzirem a bagunça real de
nomenclatura dos professores, não um formato idealizado.
"""

from datetime import date

from app.gravacoes_aula.pagina_canvas import (
    Ambigua,
    Escolhida,
    Nenhuma,
    corpo_com_embed,
    escolher_pagina,
    ja_tem_este_video,
    montar_iframe,
    parse_titulo_pagina,
    tem_outro_embed_youtube,
    titulo_pagina_padrao,
)


def _pagina(titulo: str, *, criada: str = "2026-08-20T12:00:00Z", url: str = "u"):
    return {"title": titulo, "url": url, "created_at": criada, "html_url": f"/x/{url}"}


# ─── parse dos 4 formatos reais ──────────────────────────────────────────

def test_formato_do_692():
    t = parse_titulo_pagina("Aula 06 - 21/08/2026 - MCUV e Aceleração angular")
    assert (t.numero, t.dia, t.mes, t.ano) == (6, 21, 8, 2026)
    assert t.resto == "MCUV e Aceleração angular"


def test_formato_do_691_com_espaco_duplo():
    t = parse_titulo_pagina("Aula 07 - 24/08/2026 -  Trigonometria: Soma de Arcos")
    assert (t.numero, t.ano) == (7, 2026)
    assert t.resto == "Trigonometria: Soma de Arcos"  # espaço duplo normalizado


def test_formato_do_693_maiusculo():
    t = parse_titulo_pagina("AULA 20 - 19/08/2026 - Funções Inorgânicas")
    assert (t.numero, t.dia, t.mes) == (20, 19, 8)


def test_formato_do_693_sem_ano():
    t = parse_titulo_pagina("AULA 14 - 17/06 - Anotações | Resolução do Simulado 03")
    assert (t.numero, t.dia, t.mes, t.ano) == (14, 17, 6, None)


def test_titulo_com_espaco_a_esquerda():
    assert parse_titulo_pagina("  Aula 06 - 18/08/2026 - Complexos").numero == 6


def test_titulo_que_nao_e_de_aula():
    assert parse_titulo_pagina("Prova - Teste de Seleção SAS - 10/02/2026") is None
    assert parse_titulo_pagina("Notas da Aula 02 - Propagação de calor") is None


# ─── A ARMADILHA DO SEMESTRE ────────────────────────────────────────────

def test_nao_casa_aula_de_outro_semestre_com_mesmo_numero():
    """O caso que motiva o desenho inteiro: no 692 existem três "Aula 07".
    Casar por número colaria o vídeo de agosto na aula de abril."""
    paginas = [
        _pagina("Aula 07 - 15/04/2026 - 2ª Lei da Termodinâmica", criada="2026-04-10T12:00:00Z"),
        _pagina("Aula 07 -  15/05/2026 - Lançamentos", criada="2026-05-10T12:00:00Z"),
    ]
    escolha = escolher_pagina(paginas, numero_aula=7, data_aula=date(2026, 8, 27))
    assert isinstance(escolha, Nenhuma), "casou com aula de outro semestre!"


def test_casa_quando_a_data_bate_exatamente():
    paginas = [
        _pagina("Aula 07 - 15/04/2026 - 2ª Lei"),
        _pagina("Aula 06 - 21/08/2026 - MCUV", url="certa"),
    ]
    escolha = escolher_pagina(paginas, numero_aula=6, data_aula=date(2026, 8, 21))
    assert isinstance(escolha, Escolhida) and escolha.pagina["url"] == "certa"


def test_duas_paginas_na_mesma_data_sao_ambiguas():
    """Empate não escreve: chama gente."""
    paginas = [
        _pagina("Aula 06 - 21/08/2026 - MCUV", url="a"),
        _pagina("Aula 06 - 21/08/2026 - MCUV (cópia)", url="b"),
    ]
    assert isinstance(escolher_pagina(paginas, numero_aula=6, data_aula=date(2026, 8, 21)), Ambigua)


def test_sem_ano_exige_criacao_proxima():
    """'17/06' sozinho não distingue este ano do semestre passado."""
    antiga = [_pagina("AULA 14 - 17/06 - Anotações", criada="2025-06-15T12:00:00Z")]
    assert isinstance(escolher_pagina(antiga, numero_aula=14, data_aula=date(2026, 6, 17)), Nenhuma)

    recente = [_pagina("AULA 14 - 17/06 - Anotações", criada="2026-06-18T12:00:00Z")]
    assert isinstance(escolher_pagina(recente, numero_aula=14, data_aula=date(2026, 6, 17)), Escolhida)


def test_sem_created_at_nao_arrisca():
    paginas = [{"title": "AULA 14 - 17/06 - Anotações", "url": "u"}]
    assert isinstance(escolher_pagina(paginas, numero_aula=14, data_aula=date(2026, 6, 17)), Nenhuma)


# ─── embed ──────────────────────────────────────────────────────────────

def test_iframe_reproduz_o_padrao_manual():
    """String literal copiada de uma página real do curso 692."""
    esperado = (
        '<p style="text-align: center;"><iframe title="SAS ITA/IME 2026 - Turma 1 e 2 - '
        'Prof Renan - Aula 6 (21/08/2026)" src="https://www.youtube.com/embed/KM2MbMnJ0E8" '
        'width="780" height="420" allowfullscreen="allowfullscreen" '
        'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; '
        'picture-in-picture; web-share" frameborder="0" loading="lazy"></iframe></p>'
    )
    gerado = montar_iframe(
        "SAS ITA/IME 2026 - Turma 1 e 2 - Prof Renan - Aula 6 (21/08/2026)", "KM2MbMnJ0E8"
    )
    assert gerado == esperado


def test_aspas_no_titulo_nao_quebram_o_atributo():
    g = montar_iframe('Aula "especial" de Física', "abc123")
    assert '&quot;' in g and g.count('title="') == 1


def test_reconhece_o_proprio_embed():
    corpo = montar_iframe("x", "KM2MbMnJ0E8")
    assert ja_tem_este_video(corpo, "KM2MbMnJ0E8")
    assert not ja_tem_este_video(corpo, "OUTRO123")


def test_detecta_outro_video_na_pagina():
    corpo = montar_iframe("x", "VIDEO_ANTIGO")
    assert tem_outro_embed_youtube(corpo, "VIDEO_NOVO")
    assert not tem_outro_embed_youtube(corpo, "VIDEO_ANTIGO")


def test_corpo_do_professor_e_preservado_byte_a_byte():
    aula = "<h2>Resumo</h2><p>Conteúdo do professor</p>"
    novo = corpo_com_embed(aula, montar_iframe("t", "vid"))
    assert aula in novo, "conteúdo do professor foi alterado"
    assert novo.index("iframe") < novo.index("Resumo"), "vídeo deve vir ANTES"


def test_corpo_vazio_recebe_so_o_iframe():
    iframe = montar_iframe("t", "vid")
    assert corpo_com_embed(None, iframe) == iframe
    assert corpo_com_embed("   ", iframe) == iframe


# ─── criação de página ──────────────────────────────────────────────────

def test_titulo_criado_e_reconhecido_pelo_proprio_parser():
    """Fecha a janela do POST sem retry: se o POST deu timeout mas criou a
    página, a varredura seguinte precisa encontrá-la em vez de duplicar."""
    t = titulo_pagina_padrao(8, date(2026, 8, 25), "Complexos: Forma Trigonométrica")
    assert t == "Aula 08 - 25/08/2026 - Complexos: Forma Trigonométrica"
    lido = parse_titulo_pagina(t)
    assert (lido.numero, lido.dia, lido.mes, lido.ano) == (8, 25, 8, 2026)


# ─── Escolha do módulo ──────────────────────────────────────────────────────
#
# Os itens abaixo são os títulos REAIS dos dois módulos do curso 691, lidos da
# API do Canvas em 29/08/2026. São eles que provam por que a escolha não pode
# ser por data.

from app.gravacoes_aula.pagina_canvas import (  # noqa: E402
    ItemModulo,
    ModuloCanvas,
    ModuloEscolhido,
    SemModulo,
    chave_de_assunto,
    escolher_modulo,
)

_TRIGONOMETRIA = ModuloCanvas(
    id="2730",
    nome="Aulas - Trigonometria",
    itens=(
        ItemModulo("Aula 01 - 03/08/2026 - Trigonometria: Arcos e ângulos", 1),
        ItemModulo("Aula 03 - 10/08/2026 - Trigonometria: Triângulo Retângulo", 2),
        ItemModulo("Aula 05 - 17/08/2026 - Trigonometria: Ciclo Trigonométrico", 3),
        ItemModulo("Aula 07 - 24/08/2026 -  Trigonometria: Soma de Arcos", 4),
        ItemModulo("Aula 26 - 22/06/2026 - Geometria: Questões Diversas", 22),
    ),
)

_COMPLEXOS = ModuloCanvas(
    id="2731",
    nome="Aulas - Números Complexos",
    itens=(
        ItemModulo("Aula 02 - 04/08/2026 - Complexos: Forma Algébrica", 1),
        ItemModulo("Aula 04 - 11/08/2026 - Complexos: Forma Trigonométrica", 2),
        ItemModulo(" Aula 06 - 18/08/2026 - Complexos: Forma Trigonométrica (Parte 2)", 3),
        ItemModulo(" Aula 27 - 23/06/2026 - Conjuntos e Funções: Questões Diversas", 19),
    ),
)

_MODULOS_691 = (_TRIGONOMETRIA, _COMPLEXOS)


def test_assunto_decide_e_a_data_enganaria():
    """O caso que motiva a função inteira.

    "Aula 08 - 25/08/2026 - Complexos: ..." é de Complexos, mas a aula anterior
    POR DATA é a 07 de 24/08, que é de Trigonometria. Escolher pelo vizinho de
    data penduraria Complexos na trilha errada."""
    r = escolher_modulo(
        _MODULOS_691,
        titulo_pagina="Aula 08 - 25/08/2026 - Complexos: Forma Trigonométrica (pt3)",
        data_aula=date(2026, 8, 25),
        modulo_padrao_id=None,
    )
    assert isinstance(r, ModuloEscolhido)
    assert r.nome == "Aulas - Números Complexos"
    # Logo depois da Aula 06 (18/08), não no fim depois do bloco de junho.
    assert r.posicao == 4


def test_a_outra_trilha_tambem_acerta():
    r = escolher_modulo(
        _MODULOS_691,
        titulo_pagina="Aula 09 - 31/08/2026 - Trigonometria: Equações",
        data_aula=date(2026, 8, 31),
        modulo_padrao_id=None,
    )
    assert isinstance(r, ModuloEscolhido)
    assert r.nome == "Aulas - Trigonometria"
    assert r.posicao == 5


def test_chave_ignora_a_palavra_da_outra_trilha_no_resto():
    """"Complexos: Forma TRIGONOMÉTRICA" contém a palavra da outra trilha.
    Por isso o corte é nos dois-pontos, não uma busca no título inteiro."""
    assert chave_de_assunto("Aula 04 - 11/08/2026 - Complexos: Forma Trigonométrica") == "complexos"


def test_chave_ignora_acento_e_caixa():
    """O 693 escreve "AULA 20" em maiúsculo; os títulos são datilografados."""
    assert chave_de_assunto("AULA 20 - 19/08/2026 - FÍSICA: Óptica") == "fisica"
    assert chave_de_assunto("Aula 20 - 19/08/2026 - Física: Óptica") == "fisica"


def test_assunto_em_dois_modulos_nao_escolhe():
    """Empate não vira chute — melhor página fora de módulo, que dá para
    arrastar, que página na trilha errada."""
    duplicado = ModuloCanvas("9", "Aulas - Cópia", (ItemModulo("Aula 02 - 04/08/2026 - Complexos: x", 1),))
    r = escolher_modulo(
        (*_MODULOS_691, duplicado),
        titulo_pagina="Aula 08 - 25/08/2026 - Complexos: y",
        data_aula=date(2026, 8, 25),
        modulo_padrao_id=None,
    )
    assert isinstance(r, SemModulo) and "mais de um módulo" in r.motivo


def test_sem_assunto_cai_no_modulo_do_curso():
    """Física e Química não escrevem assunto na conferência, e a página nasce
    "Aula 07 - 27/08/2026 - Física". Nenhum item antigo tem essa chave."""
    fisica = ModuloCanvas(
        "2738",
        "Aulas - Física 2 - Professores Logam e Renan",
        (
            ItemModulo("Aula 05 - 20/08/2026 - Movimento Circular", 5),
            ItemModulo("Aula 06 - 21/08/2026 - MCUV e Aceleração angular", 6),
            ItemModulo("Aula 07 - 15/04/2026 - 2ª Lei da Termodinâmica", 7),
        ),
    )
    r = escolher_modulo(
        (fisica,),
        titulo_pagina="Aula 07 - 27/08/2026 - Física",
        data_aula=date(2026, 8, 27),
        modulo_padrao_id="2738",
    )
    assert isinstance(r, ModuloEscolhido)
    # Depois da Aula 06 (21/08), ANTES do bloco de abril que está no fim.
    assert r.posicao == 7


def test_sem_assunto_e_sem_padrao_nao_pendura():
    r = escolher_modulo(
        (_TRIGONOMETRIA,),
        titulo_pagina="Aula 07 - 27/08/2026 - Física",
        data_aula=date(2026, 8, 27),
        modulo_padrao_id=None,
    )
    assert isinstance(r, SemModulo)


def test_modulo_padrao_apagado_no_canvas_nao_estoura():
    r = escolher_modulo(
        (_TRIGONOMETRIA,),
        titulo_pagina="Aula 07 - 27/08/2026 - Física",
        data_aula=date(2026, 8, 27),
        modulo_padrao_id="9999",
    )
    assert isinstance(r, SemModulo) and "não existe mais" in r.motivo


def test_modulo_sem_aula_anterior_anexa_no_fim():
    """O 581 tem só "LINK PARA AULA AO VIVO", que não tem data."""
    ao_vivo = ModuloCanvas("2609", "AULA AO VIVO", (ItemModulo("LINK PARA AULA AO VIVO", 1),))
    r = escolher_modulo(
        (ao_vivo,),
        titulo_pagina="Aula - 28/08/2026 - Inglês",
        data_aula=date(2026, 8, 28),
        modulo_padrao_id="2609",
    )
    assert isinstance(r, ModuloEscolhido) and r.posicao is None
