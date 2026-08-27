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
