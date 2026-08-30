"""As réguas que a coordenação cria — leitura, validação e versionamento.

O que estes testes protegem, em ordem de importância:

  1. **A régua embutida vem do ARQUIVO.** É a decisão da 0023, e a que impede
     alguém de editar "ITA — Fase 1" pela tela e mudar o edital.
  2. **Editar cria versão.** Sem isso, mexer numa régua muda retroativamente os
     números de quem já a usou — em silêncio.
  3. **A validação recusa régua que não corta ninguém.** Ela não falha: ela
     classifica errado, calada.
"""

import pytest

from app.stats import criterios, criterios_repo

from .fake_postgrest import FakeCliente


def banco_vazio() -> FakeCliente:
    return FakeCliente({"criterio_classificacao": {}, "predicado_criterio": {}})


META_7 = {
    "slug": "meta-7-exatas",
    "nome": "Meta 7 nas exatas",
    "descricao": "7 em Mat/Fís/Quím e acima de 4 em Português.",
    "combinador": "algum",
    "fase": None,
    "desempate": ["media", "matematica"],
    "predicados": [
        {"materia": "matematica", "operador": ">=", "valor_nota": 7.0},
        {"materia": "fisica", "operador": ">=", "valor_nota": 7.0},
        {"materia": "quimica", "operador": ">=", "valor_nota": 7.0},
        {"materia": "portugues", "operador": ">", "valor_nota": 4.0},
    ],
}


# ─── Fonte da verdade ─────────────────────────────────────────────────────


class TestFonteDaVerdade:
    def test_regua_embutida_vem_do_arquivo_e_nao_do_banco(self):
        """A tabela guarda uma cópia como semente; ela nunca é consultada."""
        cliente = banco_vazio()
        assert criterios_repo.resolver(cliente, "ita-f1") is criterios.ITA_FASE_1

    def test_banco_fora_do_ar_nao_derruba_as_cinco_embutidas(self):
        class ClienteQuebrado:
            def table(self, _nome):
                raise RuntimeError("sem banco")

        quebrado = ClienteQuebrado()
        assert criterios_repo.resolver(quebrado, "tio-leo") is criterios.TIO_LEO
        assert len(criterios_repo.listar(quebrado)) == len(criterios.CRITERIOS)

    def test_slug_desconhecido_lista_o_que_existe(self):
        with pytest.raises(KeyError) as e:
            criterios_repo.resolver(banco_vazio(), "nao-existe")
        assert "tio-leo" in str(e.value)


# ─── Ida e volta pelo banco ───────────────────────────────────────────────


class TestCriar:
    def test_regua_criada_volta_como_criterio_avaliavel(self):
        cliente = banco_vazio()
        criterios_repo.criar(cliente, META_7, criado_por="leo@ari")

        regua = criterios_repo.resolver(cliente, "meta-7-exatas")
        assert regua.nome == "Meta 7 nas exatas"
        assert regua.combinador == "algum"

        # E o avaliador aplica sem saber que ela veio do banco.
        n = criterios.NotaDaMateria
        bate = {"matematica": n(7.5), "fisica": n(7.0), "quimica": n(8.0), "portugues": n(4.5)}
        nao = {"matematica": n(7.5), "fisica": n(6.9), "quimica": n(8.0), "portugues": n(9.0)}
        assert criterios.avaliar(regua, bate).aprovado is True
        assert criterios.avaliar(regua, nao).aprovado is False

    def test_criada_aparece_na_lista_depois_das_embutidas(self):
        cliente = banco_vazio()
        criterios_repo.criar(cliente, META_7)
        slugs = [c.slug for c in criterios_repo.listar(cliente)]
        assert slugs[: len(criterios.CRITERIOS)] == list(criterios.CRITERIOS)
        assert slugs[-1] == "meta-7-exatas"

    def test_mesmo_slug_duas_vezes_e_recusado(self):
        cliente = banco_vazio()
        criterios_repo.criar(cliente, META_7)
        with pytest.raises(criterios_repo.CriterioInvalido, match="já existe"):
            criterios_repo.criar(cliente, META_7)

    def test_acertos_sobrevivem_a_ida_e_volta(self):
        cliente = banco_vazio()
        criterios_repo.criar(cliente, {
            **META_7, "slug": "por-acertos",
            "predicados": [
                {"materia": "matematica", "valor_acertos": 5, "valor_de": 12},
                {"materia": None, "valor_nota": 5.0},
            ],
        })
        regua = criterios_repo.resolver(cliente, "por-acertos")
        assert regua.predicados[0].valor == criterios.Acertos(5, 12)


# ─── Imutabilidade ────────────────────────────────────────────────────────


class TestVersionamento:
    def test_editar_cria_versao_2_e_desativa_a_1(self):
        cliente = banco_vazio()
        criterios_repo.criar(cliente, META_7)

        mais_dura = {k: v for k, v in META_7.items() if k != "slug"}
        mais_dura["predicados"] = [
            {**p, "valor_nota": 8.0} if p["materia"] == "matematica" else p
            for p in META_7["predicados"]
        ]
        nova = criterios_repo.nova_versao(cliente, "meta-7-exatas", mais_dura)
        assert nova["versao"] == 2

        historico = criterios_repo.versoes(cliente, "meta-7-exatas")
        assert [(l["versao"], l["ativo"]) for l in historico] == [(2, True), (1, False)]

        # A resolução pega a versão que está valendo.
        regua = criterios_repo.resolver(cliente, "meta-7-exatas")
        assert criterios.corte_da_materia(regua, "matematica") == 8.0

    def test_regua_embutida_nao_se_edita(self):
        cliente = banco_vazio()
        with pytest.raises(criterios_repo.CriterioInvalido, match="não se editam"):
            criterios_repo.nova_versao(cliente, "ita-f1", META_7)

    def test_desativar_tira_do_seletor_sem_apagar_o_historico(self):
        cliente = banco_vazio()
        criterios_repo.criar(cliente, META_7)
        criterios_repo.desativar(cliente, "meta-7-exatas")

        assert "meta-7-exatas" not in [c.slug for c in criterios_repo.listar(cliente)]
        assert len(criterios_repo.versoes(cliente, "meta-7-exatas")) == 1

    def test_desativar_embutida_e_recusado(self):
        with pytest.raises(criterios_repo.CriterioInvalido, match="embutidas"):
            criterios_repo.desativar(banco_vazio(), "tio-leo")


# ─── Validação ────────────────────────────────────────────────────────────


class TestValidacao:
    def test_regua_sem_requisito_nao_passa(self):
        with pytest.raises(criterios_repo.CriterioInvalido, match="pelo menos um requisito"):
            criterios_repo.validar({**META_7, "predicados": []})

    def test_combinador_todos_so_com_eliminatorias_nunca_cortaria_ninguem(self):
        """O caso silencioso: a régua não falha, ela aprova a base inteira."""
        with pytest.raises(criterios_repo.CriterioInvalido, match="nunca corta"):
            criterios_repo.validar({
                **META_7, "combinador": "todos",
                "predicados": [{"materia": "ingles", "valor_nota": 4.0, "eliminatorio": True}],
            })

    def test_materia_inexistente_e_recusada_com_a_lista_do_que_existe(self):
        with pytest.raises(criterios_repo.CriterioInvalido, match="matematica"):
            criterios_repo.validar({
                **META_7, "predicados": [{"materia": "filosofia", "valor_nota": 5.0}],
            })

    def test_nota_e_acertos_juntos_e_recusado(self):
        with pytest.raises(criterios_repo.CriterioInvalido, match="nunca os dois"):
            criterios_repo.validar({
                **META_7,
                "predicados": [
                    {"materia": "matematica", "valor_nota": 5.0,
                     "valor_acertos": 5, "valor_de": 12},
                ],
            })

    def test_nota_fora_de_0_a_10_e_recusada(self):
        with pytest.raises(criterios_repo.CriterioInvalido, match="entre 0 e 10"):
            criterios_repo.validar({
                **META_7, "predicados": [{"materia": "matematica", "valor_nota": 70}],
            })

    def test_slug_com_espaco_ou_acento_e_recusado(self):
        for ruim in ("Meta 7", "meta_7", "métrica", "-meta", ""):
            with pytest.raises(criterios_repo.CriterioInvalido, match="slug"):
                criterios_repo.validar({**META_7, "slug": ruim})

    def test_slug_de_regua_embutida_e_recusado(self):
        with pytest.raises(criterios_repo.CriterioInvalido, match="embutida"):
            criterios_repo.validar({**META_7, "slug": "tio-leo"})

    def test_a_regua_do_pedido_original_passa(self):
        """'nota 7 em Mat/Fís/Quím e maior que 4 em Português' (docs/18 §1.10)."""
        criterios_repo.validar(META_7)


# ─── O que a revisão adversarial de 30/08 encontrou ──────────────────────


class TestBuracosDaRevisao:
    def test_nota_e_acertos_pela_metade_nao_chega_ao_CHECK_do_banco(self):
        """`valor_nota` + `valor_acertos` sem `valor_de` passava pela validação.

        O XOR antigo só reconhecia acertos quando o PAR estava completo, então
        este payload contava como "só nota" — e ia morrer no CHECK da 0023 no
        insert dos predicados, com o critério já gravado e órfão.
        """
        with pytest.raises(criterios_repo.CriterioInvalido, match="nunca os dois"):
            criterios_repo.validar({
                **META_7,
                "predicados": [{"materia": "matematica", "valor_nota": 7, "valor_acertos": 5}],
            })

    def test_meio_par_de_acertos_diz_o_que_falta(self):
        with pytest.raises(criterios_repo.CriterioInvalido, match="precisa dos dois"):
            criterios_repo.validar({
                **META_7,
                "predicados": [{"materia": "matematica", "valor_acertos": 5}],
            })

    def test_requisito_sem_valor_nenhum_e_recusado(self):
        with pytest.raises(criterios_repo.CriterioInvalido, match="informe uma nota"):
            criterios_repo.validar({**META_7, "predicados": [{"materia": "matematica"}]})

    def test_peso_zero_e_recusado_em_vez_de_virar_um(self):
        """`float(peso or 1)` engolia o zero antes da guarda que o recusa."""
        with pytest.raises(criterios_repo.CriterioInvalido, match="maior que zero"):
            criterios_repo.validar({
                **META_7,
                "predicados": [{"materia": "matematica", "valor_nota": 7, "peso": 0}],
            })

    def test_peso_ausente_continua_valendo_um(self):
        criterios_repo.validar(META_7)   # nenhum predicado declara peso

    def test_predicado_que_falha_desfaz_o_criterio_em_vez_de_deixar_regua_vazia(self):
        """Régua ativa sem requisito APROVA TODO MUNDO — não pode sobrar uma.

        São dois requests PostgREST sem transação entre eles. Se o segundo
        falhar, o primeiro já gravou.
        """
        cliente = banco_vazio()

        original = cliente.table

        def table_que_falha_nos_predicados(nome):
            if nome == "predicado_criterio":
                class Recusa:
                    def insert(self, *_a, **_kw):
                        raise RuntimeError("PostgREST caiu no meio")
                return Recusa()
            return original(nome)

        cliente.table = table_que_falha_nos_predicados
        with pytest.raises(RuntimeError):
            criterios_repo.criar(cliente, META_7)

        cliente.table = original
        assert criterios_repo.versoes(cliente, "meta-7-exatas") == []
        assert "meta-7-exatas" not in [c.slug for c in criterios_repo.listar(cliente)]

    def test_versao_anterior_so_sai_de_cena_depois_de_a_nova_entrar_inteira(self):
        cliente = banco_vazio()
        criterios_repo.criar(cliente, META_7)
        original = cliente.table
        chamadas = {"n": 0}

        def falha_no_segundo_insert(nome):
            if nome == "predicado_criterio":
                chamadas["n"] += 1
                class Recusa:
                    def insert(self, *_a, **_kw):
                        raise RuntimeError("caiu")
                return Recusa()
            return original(nome)

        cliente.table = falha_no_segundo_insert
        with pytest.raises(RuntimeError):
            criterios_repo.nova_versao(
                cliente, "meta-7-exatas", {k: v for k, v in META_7.items() if k != "slug"},
            )
        cliente.table = original

        # A v1 continua ativa: quem estava usando a régua não ficou sem ela.
        historico = criterios_repo.versoes(cliente, "meta-7-exatas")
        assert [(l["versao"], l["ativo"]) for l in historico] == [(1, True)]
