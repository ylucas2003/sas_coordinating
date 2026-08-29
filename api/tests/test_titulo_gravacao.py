"""Título do vídeo no padrão do canal, a partir do título livre do Canvas.

Os casos abaixo são os formatos REAIS encontrados nos três cursos monitorados
em 27/08/2026 — cada professor nomeia a conferência do seu jeito.
"""

from datetime import UTC, datetime

from app.gravacoes_aula.titulo import (
    compor_titulo,
    extrair_numero_aula,
    extrair_professor,
)


def _em(ano: int, mes: int, dia: int, hora: int = 20) -> datetime:
    return datetime(ano, mes, dia, hora, 0, tzinfo=UTC)


def test_formato_da_fisica_tem_professor_no_titulo():
    assert (
        compor_titulo(
            titulo_canvas="Física - Prof. Renan - AULA 5 - 17:30 (20/08/2026)",
            nome_curso="2026 SAS ITA/IME Física (2º SEMESTRE)",
            iniciada_em=_em(2026, 8, 20),
        )
        == "SAS ITA/IME 2026 - Turma 1 e 2 - Prof Renan - Aula 5 (20/08/2026)"
    )


def test_formato_da_quimica_professor_no_meio():
    assert (
        compor_titulo(
            titulo_canvas="Química - AULA 19 - 26/08/2026 - Prof. José Marques - 17:30",
            nome_curso="2026 SAS ITA/IME Química (2º SEMESTRE)",
            iniciada_em=_em(2026, 8, 26),
        )
        == "SAS ITA/IME 2026 - Turma 1 e 2 - Prof José Marques - Aula 19 (26/08/2026)"
    )


def test_formato_da_matematica_cai_no_professor_padrao():
    """A Matemática não escreve o professor no título — é o único caso em que
    o padrão do curso entra."""
    assert (
        compor_titulo(
            titulo_canvas="Aula 07 - 24/08/2026 - Trigonometria: Soma de Arcos",
            nome_curso="2026 SAS ITA/IME Matemática (2º SEMESTRE)",
            iniciada_em=_em(2026, 8, 24),
            professor_padrao="Alexandre César",
        )
        == "SAS ITA/IME 2026 - Turma 1 e 2 - Prof Alexandre César - Aula 7 (24/08/2026)"
    )


def test_professor_do_titulo_vence_o_padrao_do_curso():
    """Física teve Renan e Ryan em semanas diferentes: quem manda é o título."""
    assert "Prof Ryan" in compor_titulo(
        titulo_canvas="FISICA 1 - AULA 10 - 26/06/2026 - 17:30 (Prof. Ryan)",
        nome_curso="2026 SAS ITA/IME Física (2º SEMESTRE)",
        iniciada_em=_em(2026, 6, 26),
        professor_padrao="Renan",
    )


def test_zero_a_esquerda_some():
    assert extrair_numero_aula("Aula 08 - 25/08/2026") == 8


def test_data_usa_o_fuso_do_colegio_e_nao_utc():
    """Aula das 21h BRT já é o dia seguinte em UTC — sem converter, o título
    sairia com a data errada."""
    titulo = compor_titulo(
        titulo_canvas="Aula 3",
        nome_curso="x (2º SEMESTRE)",
        iniciada_em=datetime(2026, 8, 21, 0, 30, tzinfo=UTC),  # 21:30 de 20/08 BRT
    )
    assert "(20/08/2026)" in titulo


def test_sem_numero_de_aula_usa_o_assunto():
    """Tira-dúvidas não tem número; o assunto é o que diferencia na listagem."""
    titulo = compor_titulo(
        titulo_canvas="Química - TIRA-DÚVIDAS - Prof. José Marques",
        nome_curso="2026 SAS ITA/IME Química (2º SEMESTRE)",
        iniciada_em=_em(2026, 8, 26),
    )
    assert "TIRA-DÚVIDAS" in titulo and "Aula " not in titulo


def test_turma_sai_do_nome_do_curso():
    assert "Turma 1 e 2" in compor_titulo(
        titulo_canvas="Aula 1", nome_curso="x (2º SEMESTRE)", iniciada_em=_em(2026, 8, 1)
    )
    assert "- Turma 1 -" in compor_titulo(
        titulo_canvas="Aula 1", nome_curso="y (TURMA 1)", iniciada_em=_em(2026, 8, 1)
    )


def test_sem_professor_em_lugar_nenhum_omite_o_segmento():
    """Melhor lacuna honesta que "Prof ?"."""
    titulo = compor_titulo(
        titulo_canvas="Aula 07 - Trigonometria",
        nome_curso="x (2º SEMESTRE)",
        iniciada_em=_em(2026, 8, 24),
    )
    assert titulo == "SAS ITA/IME 2026 - Turma 1 e 2 - Aula 7 (24/08/2026)"
    assert extrair_professor("Aula 07 - Trigonometria") is None


# ─── Curso 581 (SAS Preparatório): a conferência JÁ vem no padrão do canal ───
#
# Os títulos abaixo são literais, copiados da API do Canvas em 29/08/2026.
# Sem tratamento, compor_titulo somaria prefixo ao prefixo e produziria
# "SAS ITA/IME 2026 - Turma 1 e 2 - Prof Daniel - SAS ITA/IME 2026 - ... (28/08/2026) (28/08/2026)".

_TITULO_581 = "SAS ITA/IME 2026 - Turma 1 e 2 - Inglês - Prof Daniel Nicolas - 17:30 (28/08/2026)"


def test_titulo_ja_no_padrao_nao_ganha_prefixo_duplicado():
    resultado = compor_titulo(
        titulo_canvas=_TITULO_581,
        nome_curso="SAS Preparatório ITA/IME 2026",
        iniciada_em=_em(2026, 8, 28),
    )
    assert resultado == "SAS ITA/IME 2026 - Turma 1 e 2 - Inglês - Prof Daniel Nicolas (28/08/2026)"
    assert resultado.count("SAS ITA/IME") == 1
    assert resultado.count("Prof") == 1


def test_compor_titulo_e_idempotente():
    """Aplicar sobre o próprio resultado não pode empilhar prefixo — a saída
    daqui sempre começa com "SAS ITA/IME", então ela reentra pelo mesmo ramo."""
    kw = {"nome_curso": "2026 SAS ITA/IME Física (2º SEMESTRE)", "iniciada_em": _em(2026, 8, 21)}
    uma_vez = compor_titulo(titulo_canvas="Física - Prof. Renan - AULA 5 - 17:30", **kw)
    assert compor_titulo(titulo_canvas=uma_vez, **kw) == uma_vez


def test_data_do_texto_e_substituida_pela_real():
    """O título é digitado à mão e já veio errado na prática (conferência de
    25/06 intitulada "AULA 13 - 11/06"). Quem manda é `iniciada_em`."""
    assert "(29/08/2026)" in compor_titulo(
        titulo_canvas="SAS ITA/IME 2026 - Turma 1 e 2 - Redação - Prof Camila (11/06/2026)",
        nome_curso="SAS Preparatório ITA/IME 2026",
        iniciada_em=_em(2026, 8, 29),
    )


def test_aula_por_materia_preserva_a_materia():
    """No 581 a aula é identificada pela matéria, não por número. Ela não pode
    sumir nem virar "Aula N"."""
    r = compor_titulo(
        titulo_canvas="SAS ITA/IME 2026 - Turma 1 e 2 - Redação - Prof Camila Oliveira - 09:00 (29/08/2026)",
        nome_curso="SAS Preparatório ITA/IME 2026",
        iniciada_em=_em(2026, 8, 29),
    )
    assert "Redação" in r and "Aula " not in r


def test_titulo_cabe_no_limite_do_youtube():
    """publicador_youtube.publicar corta em 100 caracteres SEM avisar."""
    r = compor_titulo(
        titulo_canvas=_TITULO_581,
        nome_curso="SAS Preparatório ITA/IME 2026",
        iniciada_em=_em(2026, 8, 28),
    )
    assert len(r) <= 100, f"{len(r)} caracteres: seria truncado em silêncio"
