"""O avaliador de critérios, provado contra os editais — sem banco.

Cada teste carrega um caso do edital ou da conversa com a coordenação. Se
algum quebrar, ou a regra foi mal lida, ou o edital mudou: os dois merecem
olhar o docs/18 §1.5 antes de "consertar" o teste.
"""

import pytest

from app.stats.classificacao import _classificar_zona_por_materia
from app.stats.criterios import (
    IME_FASE_1,
    IME_FASE_2,
    ITA_FASE_1,
    ITA_FASE_2,
    TIO_LEO,
    TODAS,
    Acertos,
    Criterio,
    NotaDaMateria,
    Predicado,
    avaliar,
    corte_da_materia,
    corte_da_media,
    e_eliminatoria,
    endurecer,
    media_do_criterio,
    por_slug,
    tom_da_nota,
)
from app.stats.metricas import corte_aplicavel
from app.stats.utils import taxas_por_corte


def _zona(notas_por_materia, *, media: float = 6.0, criterio: Criterio | None = None) -> str:
    """A zona do aluno, com as notas já em 0–10 e a régua da casa por padrão."""
    return _classificar_zona_por_materia(
        notas_por_materia_codigo={k: v.nota for k, v in notas_por_materia.items()},
        media_recente=media,
        criterio=criterio or TIO_LEO,
    )


def n(nota: float, acertos: float | None = None, total: float | None = None) -> NotaDaMateria:
    return NotaDaMateria(nota=nota, acertos=acertos, total=total)


def de(acertos: int, total: int) -> NotaDaMateria:
    return NotaDaMateria(nota=acertos / total * 10, acertos=acertos, total=total)


# ─── Tio Leo — a régua do colégio ─────────────────────────────────────────


class TestTioLeo:
    def test_e_nao_ou_uma_materia_baixa_com_media_boa_passa(self):
        """O caso dos ~50 alunos: Química 3,2 mas média 6,7. Com E, passa.

        Confirmado pela coordenação em 22/08: "tá certo assim mesmo".
        """
        notas = {
            "matematica": n(8.5), "fisica": n(8.0), "quimica": n(3.2), "portugues": n(7.0),
        }
        v = avaliar(TIO_LEO, notas)
        assert v.aprovado is True
        assert v.motivo is None

    def test_corta_quando_falha_materia_e_media(self):
        notas = {"matematica": n(3.0), "fisica": n(4.5), "quimica": n(5.0)}
        v = avaliar(TIO_LEO, notas)
        assert v.aprovado is False
        assert "Matematica 3,0" in v.motivo
        assert "Média geral" in v.motivo

    def test_media_baixa_sozinha_nao_corta(self):
        """Todas acima de 4, mas média 4,5: só UM dos dois requisitos falhou."""
        notas = {"matematica": n(4.2), "fisica": n(4.5), "quimica": n(4.8)}
        assert avaliar(TIO_LEO, notas).aprovado is True

    def test_ingles_elimina_sozinho_mesmo_com_tudo_otimo(self):
        notas = {"matematica": n(9.0), "fisica": n(9.0), "quimica": n(9.0), "ingles": n(3.9)}
        v = avaliar(TIO_LEO, notas)
        assert v.aprovado is False
        assert v.motivo.startswith("Ingles 3,9")

    def test_ingles_fica_fora_da_media(self):
        notas = {"matematica": n(6.0), "fisica": n(6.0), "ingles": n(10.0)}
        assert media_do_criterio(TIO_LEO, notas) == 6.0

    def test_sem_nota_nenhuma_nao_e_cortado(self):
        """Ausência de dado não é mau desempenho (o KPI já inflou por isso)."""
        v = avaliar(TIO_LEO, {})
        assert v.aprovado is True
        assert v.media is None

    def test_desempate_segue_a_ordem_ditada(self):
        assert TIO_LEO.desempate == ("media", "matematica", "fisica", "quimica", "ingles")


# ─── ITA ──────────────────────────────────────────────────────────────────


class TestITAFase1:
    def test_ingles_e_cobrado_mas_nao_entra_na_media(self):
        """§4.6.2.1 cobra 5 de 12 em Inglês; §4.6.5 o tira da média."""
        notas = {
            "matematica": de(8, 12), "fisica": de(8, 12), "quimica": de(8, 12),
            "ingles": de(4, 12),
        }
        v = avaliar(ITA_FASE_1, notas)
        assert v.aprovado is False
        assert "Ingles" in v.motivo and "5 de 12" in v.motivo
        # A média é só Mat+Fís+Quím: 24/36*10 = 6,67 — o inglês de 4/12 não puxa.
        assert round(v.media, 2) == 6.67

    def test_minimo_em_acertos_nao_em_nota(self):
        """4 de 12 = 3,33 reprova; 5 de 12 = 4,17 aprova. A fronteira é o acerto."""
        # Fís e Quím altas para a média (§4.6.2.2) não interferir: o que
        # está em teste é só o mínimo por matéria.
        base = {"fisica": de(10, 12), "quimica": de(10, 12), "ingles": de(6, 12)}
        assert avaliar(ITA_FASE_1, {**base, "matematica": de(4, 12)}).aprovado is False
        assert avaliar(ITA_FASE_1, {**base, "matematica": de(5, 12)}).aprovado is True

    def test_media_final_e_acertos_sobre_36(self):
        """§4.6.5: (acertos de Mat+Fís+Quím) ÷ 36 × 10."""
        notas = {"matematica": de(10, 12), "fisica": de(6, 12), "quimica": de(8, 12)}
        assert round(media_do_criterio(ITA_FASE_1, notas), 4) == round(24 / 36 * 10, 4)

    def test_e_ou_media_abaixo_de_5_corta_mesmo_com_minimos_ok(self):
        """§4.6.2.2: todos os mínimos de acerto batidos, mas média 4,7 → corta."""
        notas = {
            "matematica": de(5, 12), "fisica": de(6, 12), "quimica": de(6, 12),
            "ingles": de(12, 12),
        }
        v = avaliar(ITA_FASE_1, notas)
        assert v.aprovado is False
        assert "Média geral" in v.motivo


class TestITAFase2:
    def test_qualquer_materia_abaixo_de_4_reprova(self):
        """§4.6.6.5 — e é OU, diferente do Tio Leo: o mesmo aluno aqui É cortado."""
        notas = {
            "matematica": n(8.5), "fisica": n(8.0), "quimica": n(3.2), "portugues": n(7.0),
            "fase_1": n(7.0), "redacao": n(6.0),
        }
        v = avaliar(ITA_FASE_2, notas)
        assert v.aprovado is False
        assert v.motivo.startswith("Quimica 3,2")

    def test_mesmo_aluno_passa_no_tio_leo_e_cai_no_ita(self):
        """O critério de pronto do docs/18 §1.11, literalmente."""
        notas = {"matematica": n(8.5), "fisica": n(8.0), "quimica": n(3.2), "portugues": n(7.0)}
        assert avaliar(TIO_LEO, notas).aprovado is True
        assert avaliar(ITA_FASE_2, notas).aprovado is False

    def test_redacao_elimina_sozinha_e_fica_fora_da_media(self):
        """§4.6.6.3.1 — redação < 4 elimina; §4.7 — os cinco 20% não a incluem."""
        notas = {
            "matematica": n(9.0), "fisica": n(9.0), "quimica": n(9.0), "portugues": n(9.0),
            "fase_1": n(9.0), "redacao": n(3.9),
        }
        v = avaliar(ITA_FASE_2, notas)
        assert v.aprovado is False
        assert "Redacao 3,9" in v.motivo
        assert v.media == 9.0

    def test_cinco_componentes_de_20_por_cento(self):
        """§4.7: a 1ª fase pesa exatamente como cada prova da 2ª."""
        notas = {
            "matematica": n(10.0), "fisica": n(10.0), "quimica": n(10.0), "portugues": n(10.0),
            "fase_1": n(0.0),
        }
        assert media_do_criterio(ITA_FASE_2, notas) == 8.0

    def test_desempate_do_edital(self):
        """§4.9.1.3: Mat → Fís → Quím → Port. Data de nascimento fica para a rota."""
        assert ITA_FASE_2.desempate == ("media", "matematica", "fisica", "quimica", "portugues")


# ─── IME ──────────────────────────────────────────────────────────────────


class TestIMEFase1:
    def test_quimica_e_4_de_10_nao_5(self):
        """Art. 40, IV — o mínimo de Química é menor que o de Mat/Fís."""
        base = {"matematica": de(10, 15), "fisica": de(10, 15)}
        assert avaliar(IME_FASE_1, {**base, "quimica": de(3, 10)}).aprovado is False
        assert avaliar(IME_FASE_1, {**base, "quimica": de(4, 10)}).aprovado is True

    def test_media_e_acertos_totais_sobre_40(self):
        """Art. 40, I: "inferior a cinco, correspondendo a menos de vinte acertos"."""
        notas = {"matematica": de(6, 15), "fisica": de(6, 15), "quimica": de(7, 10)}
        # 19 acertos de 40 = 4,75 → corta, mesmo com os mínimos por matéria ok.
        v = avaliar(IME_FASE_1, notas)
        assert round(v.media, 3) == 4.75
        assert v.aprovado is False
        assert "Média geral" in v.motivo
        # 20 de 40 = 5,00 → passa.
        v2 = avaliar(IME_FASE_1, {**notas, "quimica": de(8, 10)})
        assert v2.media == 5.0 and v2.aprovado is True

    def test_nao_cobra_portugues_nem_ingles(self):
        """Art. 38 — Português e Inglês não existem na 1ª fase do IME."""
        notas = {
            "matematica": de(10, 15), "fisica": de(10, 15), "quimica": de(8, 10),
            "portugues": n(0.0), "ingles": n(0.0),
        }
        v = avaliar(IME_FASE_1, notas)
        assert v.aprovado is True
        assert round(v.media, 2) == 7.0


class TestIMEFase2:
    def test_media_ponderada_3_25_25_1_1(self):
        """Art. 37 III e Art. 63."""
        notas = {
            "matematica": n(10.0), "fisica": n(0.0), "quimica": n(0.0),
            "portugues": n(0.0), "ingles": n(0.0),
        }
        assert media_do_criterio(IME_FASE_2, notas) == 3.0  # 30 / 10

    def test_ingles_entra_na_media_ao_contrario_do_ita(self):
        notas = {"matematica": n(6.0), "fisica": n(6.0), "quimica": n(6.0), "portugues": n(6.0)}
        sem = media_do_criterio(IME_FASE_2, notas)
        com = media_do_criterio(IME_FASE_2, {**notas, "ingles": n(10.0)})
        assert com > sem

    def test_redacao_inapta_reprova(self):
        """Art. 50 §2º e Art. 65."""
        notas = {
            "matematica": n(9.0), "fisica": n(9.0), "quimica": n(9.0),
            "portugues": n(9.0), "ingles": n(9.0), "redacao": n(3.5),
        }
        assert avaliar(IME_FASE_2, notas).aprovado is False

    def test_desempate_inclui_ingles(self):
        """Art. 70 §2º — o IME desempata por Inglês; o ITA não."""
        assert IME_FASE_2.desempate[-1] == "ingles"
        assert "ingles" not in ITA_FASE_2.desempate


# ─── Ordenação em dois blocos ─────────────────────────────────────────────


class TestOrdenacao:
    def test_cortado_com_a_maior_nota_fica_atras_de_todo_aprovado(self):
        """'O cara pode ter a maior nota; se levou corte, fica depois' (Leo, 19h03)."""
        estrela_cortado = {"matematica": n(10.0), "fisica": n(10.0), "quimica": n(3.0),
                           "portugues": n(10.0), "fase_1": n(10.0)}
        mediano_aprovado = {"matematica": n(5.0), "fisica": n(5.0), "quimica": n(5.0),
                            "portugues": n(5.0), "fase_1": n(5.0)}
        a = avaliar(ITA_FASE_2, estrela_cortado)
        b = avaliar(ITA_FASE_2, mediano_aprovado)
        assert a.media > b.media
        assert a.ordenacao < b.ordenacao  # maior é melhor → o aprovado vem antes

    def test_desempate_em_cascata(self):
        """Mesma média; quem tem Matemática maior vem antes."""
        x = {"matematica": n(8.0), "fisica": n(6.0), "quimica": n(7.0), "portugues": n(7.0)}
        y = {"matematica": n(6.0), "fisica": n(8.0), "quimica": n(7.0), "portugues": n(7.0)}
        vx, vy = avaliar(ITA_FASE_2, x), avaliar(ITA_FASE_2, y)
        assert vx.media == vy.media
        assert vx.ordenacao > vy.ordenacao

    def test_empate_total_permanece_empate(self):
        x = {"matematica": n(7.0), "fisica": n(7.0), "quimica": n(7.0), "portugues": n(7.0)}
        assert avaliar(ITA_FASE_2, x).ordenacao == avaliar(ITA_FASE_2, dict(x)).ordenacao


# ─── Cor ──────────────────────────────────────────────────────────────────


class TestTom:
    def test_4_0_e_ambar_nao_vermelho(self):
        """A reclamação literal do Leo às 18h56."""
        assert tom_da_nota(TIO_LEO, "matematica", 4.0) == "ambar"
        assert tom_da_nota(TIO_LEO, "matematica", 3.9) == "vermelho"
        assert tom_da_nota(TIO_LEO, "matematica", 5.0) == "verde"

    def test_corte_por_materia_segue_o_criterio(self):
        assert corte_da_materia(IME_FASE_1, "quimica") == 4.0
        assert round(corte_da_materia(ITA_FASE_1, "matematica"), 4) == round(5 / 12 * 10, 4)
        assert corte_da_materia(TIO_LEO, "fisica") == 4.0  # via TODAS


# ─── Formato genérico (o que o coordenador criará no futuro) ──────────────


class TestCriterioPersonalizado:
    def test_exemplo_da_conversa_7_nas_exatas_e_4_em_portugues(self):
        meta = Criterio(
            slug="meta-7",
            nome="Meta 7 nas exatas",
            combinador="algum",
            predicados=(
                Predicado("matematica", 7.0),
                Predicado("fisica", 7.0),
                Predicado("quimica", 7.0),
                Predicado("portugues", 4.0),
            ),
        )
        bate = {"matematica": n(7.5), "fisica": n(7.0), "quimica": n(8.0), "portugues": n(4.0)}
        nao = {"matematica": n(7.5), "fisica": n(6.9), "quimica": n(8.0), "portugues": n(9.0)}
        assert avaliar(meta, bate).aprovado is True
        assert avaliar(meta, nao).aprovado is False
        assert "Fisica 6,9" in avaliar(meta, nao).motivo

    def test_acertos_sem_total_informado_cai_para_nota(self):
        """Sem saber quantas questões a prova tinha, compara na escala 0–10."""
        c = Criterio("x", "x", "algum", (Predicado("matematica", Acertos(5, 12)),))
        assert avaliar(c, {"matematica": n(4.2)}).aprovado is True
        assert avaliar(c, {"matematica": n(4.1)}).aprovado is False

    def test_por_slug_lista_o_que_existe(self):
        assert por_slug("ita-f1") is ITA_FASE_1
        try:
            por_slug("nao-existe")
        except KeyError as e:
            assert "tio-leo" in str(e)


# ─── Uma régua só: os consumidores que antes tinham a própria cópia ───────
#
# A Sprint 2 tirou a regra de corte do Painel; ela sobreviveu em quatro outros
# lugares — `zona`, as métricas de simulado, as estatísticas de ciclo e a tool
# `materias_problematicas` — cada um com o seu 4,0 ou 5,0 escrito à mão
# (docs/31 §1.1). Os testes abaixo existem para que essas cópias não voltem:
# mexer no corte de UMA régua tem que mover os quatro de uma vez.


class TestReguaUnica:
    def test_endurecer_sobe_todos_os_minimos(self):
        duro = endurecer(TIO_LEO, 1.0)
        assert corte_da_materia(duro, "matematica") == 5.0
        assert corte_da_media(duro) == 6.0

    def test_endurecer_converte_acertos_para_nota_antes_de_somar(self):
        """'5 de 12 + 1,0' não existe em acertos; 4,17 + 1,0 existe em nota."""
        duro = endurecer(ITA_FASE_1, 1.0)
        assert corte_da_materia(duro, "matematica") == pytest.approx(5 / 12 * 10 + 1.0)

    def test_zona_sai_do_mesmo_avaliador_que_o_painel(self):
        """Cortado pela régua ⇒ risco. Aprovado com folga ⇒ top."""
        # Tio Leo corta com E: falha matéria E falha média.
        cortado = {"matematica": n(3.0), "fisica": n(3.5), "quimica": n(3.2)}
        assert avaliar(TIO_LEO, cortado).aprovado is False
        assert _zona(cortado) == "risco"

        folgado = {"matematica": n(8.0), "fisica": n(8.5), "quimica": n(9.0)}
        assert _zona(folgado) == "top"

        # Passa na régua — o "E" do Tio Leo perdoa a Matemática porque a média
        # está boa —, mas 4,5 não tem a margem de 1,0 sobre o corte de 4,0.
        # Aprovado sem folga é exatamente a faixa cinzenta.
        justo = {"matematica": n(4.5), "fisica": n(7.0), "quimica": n(7.5)}
        assert avaliar(TIO_LEO, justo).aprovado is True
        assert _zona(justo) == "cinzenta"

    def test_folga_e_pergunta_de_E_mesmo_numa_regua_de_E(self):
        """UMA matéria sem margem já tira do topo, ainda que a régua perdoe.

        Se a régua endurecida fosse avaliada com o combinador original do Tio
        Leo ("todos"), um aluno com 4,5 em Matemática e 9,0 no resto seria
        "top": a falha isolada não fecha o E. Folga não funciona assim.
        """
        quase = {"matematica": n(4.5), "fisica": n(9.0), "quimica": n(9.5)}
        assert avaliar(TIO_LEO, quase).aprovado is True
        assert avaliar(endurecer(TIO_LEO, 1.0), quase).aprovado is True   # o E perdoa
        assert _zona(quase) == "cinzenta"                                  # a zona não

    def test_zona_sem_nota_por_materia_usa_o_corte_da_media_da_regua(self):
        assert _zona({}, media=8.0) == "top"       # ≥ 5,0 + 1,0
        assert _zona({}, media=5.5) == "cinzenta"  # ≥ 5,0, sem folga
        assert _zona({}, media=3.0) == "risco"     # < 5,0

    def test_corte_do_simulado_vem_da_regua_e_nao_do_par_4_e_5(self):
        """O 5,0 do Inglês ITA F1 era fóssil: nem a casa nem o edital dizem 5,0.

        A régua da casa põe o Inglês em 4,0 (e o marca eliminatório); o ITA
        pede 5 de 12 (§4.6.2.1), que é 4,17.
        """
        ingles_ita_f1 = {
            "materia": {"codigo": "ingles"},
            "tipo": "fase_1",
            "ciclo": {"vestibular_alvo": "ITA"},
        }
        assert corte_aplicavel(ingles_ita_f1) == 4.0
        assert corte_aplicavel(ingles_ita_f1, ITA_FASE_1) == pytest.approx(5 / 12 * 10)

    def test_corte_do_simulado_cai_na_media_quando_a_regua_nao_cobra_a_materia(self):
        so_exatas = Criterio(
            slug="so-exatas", nome="Só exatas", combinador="algum",
            predicados=(Predicado("matematica", 7.0), Predicado(None, 5.0)),
        )
        sim = {"materia": {"codigo": "portugues"}, "tipo": "fase_2", "ciclo": {}}
        assert corte_aplicavel(sim, so_exatas) == 5.0

    def test_eliminatoria_e_propriedade_da_regua_nao_do_vestibular(self):
        """Era `is_ita and codigo == 'ingles'` no módulo de estatísticas."""
        assert e_eliminatoria(TIO_LEO, "ingles") is True
        assert e_eliminatoria(TIO_LEO, "matematica") is False
        assert e_eliminatoria(ITA_FASE_2, "redacao") is True

    def test_mexer_no_corte_da_regua_move_zona_e_corte_do_simulado_juntos(self):
        """A prova de que não sobrou cópia: uma régua, dois consumidores."""
        dura = Criterio(
            slug="dura", nome="Dura", combinador="algum",
            predicados=(Predicado(TODAS, 7.0), Predicado(None, 7.0)),
        )
        notas = {"matematica": n(5.0), "fisica": n(5.0)}
        assert _zona(notas, criterio=dura) == "risco"          # 5,0 < 7,0
        assert _zona(notas, criterio=TIO_LEO) == "cinzenta"    # ≥ 4,0, sem folga na média
        sim = {"materia": {"codigo": "matematica"}, "tipo": "fase_2", "ciclo": {}}
        assert corte_aplicavel(sim, dura) == 7.0
        assert corte_aplicavel(sim, TIO_LEO) == 4.0

    def test_regua_que_nao_cobra_a_materia_nao_inventa_corte(self):
        """Sem opinião é `None`, nunca 0,0.

        Um corte 0,0 desenha a linha no chão do gráfico e faz `pctAprovados`
        dar 100% — o produto afirmando que a turma inteira passou numa matéria
        que a régua sequer menciona. Foi assim que "Meta 7 nas exatas" reportou
        100% de aprovação em Inglês contra dados reais.
        """
        so_exatas = Criterio(
            slug="so-exatas", nome="Só exatas", combinador="algum",
            predicados=(Predicado("matematica", 7.0),),   # sem predicado de média
        )
        sim_ingles = {"materia": {"codigo": "ingles"}, "tipo": "fase_2", "ciclo": {}}
        assert corte_aplicavel(sim_ingles, so_exatas) is None
        assert taxas_por_corte([5.0, 6.0, 8.0], corte=None) == (None, None, pytest.approx(33.33))
