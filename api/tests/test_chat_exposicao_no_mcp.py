"""A política do MCP: quais tools da coordenação saem do SAS (docs/43 §5.4).

Quem decide é o `METADADOS` de cada módulo de `app/chat/tools/`, tool por
tool; este arquivo trava a decisão inteira num lugar só. A lista é a do mapa
de LGPD de 24/10, que rodou as 30 tools de então contra dados sintéticos:

  * 13 "expor" — catálogo e agregado, sem pessoa;
  * 11 "expor com pseudônimo" — dado de aluno com chave de identidade no
    mesmo dict, que o MCP troca por "Aluno <matrícula>" quando o pseudônimo
    está ligado (app/mcp/pseudonimo.py);
  * mais `relatorio_ciclo` (depois que os alunos dele ganharam `alunoId` e
    `matricula`), `buscar_aluno_por_matricula` (a porta de entrada no lugar
    da busca por nome) e as três do banco de questões (prova pública);
  * e as duas de 26/10: `buscar_aluno_por_nome` e `listar_alertas`, que só
    ficavam fora por causa do pseudônimo e entraram quando o dono decidiu que
    o MCP mostra o NOME do aluno (app/mcp/configuracao.py). Com o pseudônimo
    ligado de novo, o catálogo as tira (app.mcp.catalogo.SO_COM_NOME_DO_ALUNO);
  * e as sete da cantina, da decisão de 30/10 de que a IA lê o que a
    coordenação lê: três sem pessoa, duas com a identidade ao lado do nome e
    duas que só existem com o nome real — `custos_da_cantina` (o nome é rótulo
    da soma) e `restricoes_alimentares` (dado de saúde, LGPD art. 11).
São 38.

Tudo o mais fica FORA: os artefatos de UI (`gerar_grafico`, `exportar_csv`,
`navegar_para`), sem uso fora do app, e as novas de régua, rotinas e trilha,
que são decisão aberta (docs/43 §6).

E a invariante que torna o pseudônimo possível — para as 29 que o MCP serve
também com ele ligado —, provada rodando cada tool pelo REGISTRO de verdade
contra a escola sintética de test_chat_tools_coordenacao.py: **nome de aluno
só sai em campo de nome, num dict que traz a identidade (`alunoId` ou
`matricula`) da mesma pessoa.** Nome dentro de texto livre, em chave de dict
ou sem identidade ao lado faria o pseudonimizador recusar a chamada — ou,
pior, deixar passar. É exatamente o que `listar_alertas` faz (o título), e
por isso ela só existe no MCP com o nome real.

Toda tool que entrar no MCP entra também em `CHAMADAS` aqui: o teste da
política reprova se faltar.

Rodar:  cd api && APP_ENV=dev ./.venv/bin/python -m pytest tests/test_chat_exposicao_no_mcp.py -q
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

import pytest

from app.chat.ferramentas import REGISTRO
from app.mcp.catalogo import SO_COM_NOME_DO_ALUNO, Catalogo
from app.mcp.pseudonimo import PseudonimoRecusado, pseudonimizar
from tests.test_chat_tools_cantina import semear_cantina
from tests.test_chat_tools_coordenacao import (
    C1,
    C2,
    MATRICULA,
    NOME,
    A,
    B,
    C,
    S,
    chamar,
    nova_escola,
)

#: As 13 que o mapa de LGPD classificou "expor": não devolvem pessoa.
EXPOSTAS_SEM_PESSOA = frozenset({
    "listar_ciclos", "listar_simulados", "obter_simulado", "listar_materias",
    "estatisticas_ciclo", "histograma_simulado", "comparar_ciclos", "comparar_simulados",
    "materias_problematicas", "insights_do_ciclo", "listar_sedes", "listar_turmas",
    "questoes_do_simulado",
})
#: As 11 "expor com pseudônimo": dado de aluno com a identidade no mesmo dict.
EXPOSTAS_COM_PSEUDONIMO = frozenset({
    "obter_aluno", "trajetoria_aluno", "notas_simulado", "comparar_alunos", "alunos_similares",
    "alunos_em_risco", "alunos_destaque", "tendencia_aluno", "relatorio_aluno",
    "historico_aluno", "listar_alunos",
})
#: As que entraram depois dos consertos de 24/10, e as do banco de questões.
EXPOSTAS_NOVAS = frozenset({
    "relatorio_ciclo", "buscar_aluno_por_matricula",
    "topicos_do_edital", "buscar_questoes_do_banco", "recorrencia_no_banco",
})
#: As de 26/10, que só servem com o nome real (decisão do dono), e as duas da
#: cantina que o MCP só serve assim (o comentário de `SO_COM_NOME_DO_ALUNO`).
EXPOSTAS_COM_O_NOME = frozenset({
    "buscar_aluno_por_nome", "listar_alertas", "custos_da_cantina", "restricoes_alimentares",
})
#: As da cantina que não devolvem pessoa nenhuma (30/10).
EXPOSTAS_DA_CANTINA_SEM_PESSOA = frozenset({
    "cantinas_e_regras", "calendario_da_cantina", "cardapio_da_cantina",
})
#: As da cantina com o aluno, identidade ao lado: passam pelo pseudônimo (30/10).
EXPOSTAS_DA_CANTINA_COM_PSEUDONIMO = frozenset({"pedidos_da_refeicao", "direitos_a_refeicao"})
EXPOSTAS = (
    EXPOSTAS_SEM_PESSOA | EXPOSTAS_COM_PSEUDONIMO | EXPOSTAS_NOVAS | EXPOSTAS_COM_O_NOME
    | EXPOSTAS_DA_CANTINA_SEM_PESSOA | EXPOSTAS_DA_CANTINA_COM_PSEUDONIMO
)
#: As que o MCP serve também com o pseudônimo ligado: as que têm de cumprir a
#: invariante do nome com a identidade ao lado.
EXPOSTAS_TAMBEM_COM_PSEUDONIMO = EXPOSTAS - EXPOSTAS_COM_O_NOME

#: Fora, de propósito — cada uma com o motivo no METADADOS do módulo dela.
FORA_DO_MCP = frozenset({
    "gerar_grafico", "exportar_csv", "navegar_para",
    # Decisão aberta (docs/43 §6):
    "reguas_de_corte", "cortados_pela_regua", "estado_do_sync_canvas",
    "pendencias_canvas_do_ciclo", "estado_das_gravacoes", "lembretes_agendados",
    "historico_de_alteracoes",
    # Os roteiros vão ao MCP como `prompts`, não como tool (docs/43 §4.3).
    "roteiro_da_coordenacao",
})

#: Uma chamada que devolve dado de verdade, para cada tool exposta.
CHAMADAS: dict[str, dict[str, Any]] = {
    "buscar_aluno_por_nome": {"nome": "SINTETICA"},
    "listar_alertas": {},
    "buscar_aluno_por_matricula": {"matricula": MATRICULA[A]},
    "obter_aluno": {"aluno_id": A},
    "listar_ciclos": {},
    "listar_simulados": {},
    "obter_simulado": {"simulado_id": S["MAT_F2"]},
    "listar_materias": {},
    "estatisticas_ciclo": {"ciclo_id": C2},
    "trajetoria_aluno": {"aluno_id": A},
    "histograma_simulado": {"simulado_id": S["MAT_F2"]},
    "notas_simulado": {"simulado_id": S["MAT_F2"]},
    "comparar_ciclos": {"ciclo_id_a": C2, "ciclo_id_b": C1},
    "comparar_alunos": {"aluno_ids": [A, B, C]},
    "comparar_simulados": {"simulado_ids": [S["MAT_F2"], S["FIS_F2"]]},
    "alunos_similares": {"aluno_id": A},
    "alunos_em_risco": {},
    "alunos_destaque": {},
    "tendencia_aluno": {"aluno_id": A},
    "materias_problematicas": {"ciclo_id": C2},
    "relatorio_aluno": {"aluno_id": A},
    "historico_aluno": {"aluno_id": A},
    "relatorio_ciclo": {"ciclo_id": C2},
    "insights_do_ciclo": {"ciclo_id": C2},
    "listar_alunos": {},
    "listar_sedes": {},
    "listar_turmas": {},
    "questoes_do_simulado": {"simulado_id": S["FIS_F2"]},
    "topicos_do_edital": {},
    "buscar_questoes_do_banco": {"materia": "Física"},
    "recorrencia_no_banco": {"materia": "Física"},
    "cantinas_e_regras": {},
    "calendario_da_cantina": {},
    "cardapio_da_cantina": {},
    "pedidos_da_refeicao": {"refeicao": "almoco"},
    "custos_da_cantina": {},
    "direitos_a_refeicao": {},
    "restricoes_alimentares": {},
}

#: Onde o nome do aluno pode estar — as mesmas chaves que o pseudonimizador troca.
CHAVES_DE_NOME = ("nome", "alunoNome")
CHAVES_DE_IDENTIDADE = ("alunoId", "matricula")


def _norm(texto: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())


_NOME_POR_NORM = {_norm(nome): aid for aid, nome in NOME.items()}
_ALUNO_POR_MATRICULA = {mat: aid for aid, mat in MATRICULA.items()}
_PADRAO = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(n) for n in sorted(_NOME_POR_NORM, key=len, reverse=True)) + r")(?!\w)"
)


def _tem_nome(texto: str) -> bool:
    return bool(_PADRAO.search(_norm(texto)))


def _violacoes(resultado: Any) -> list[str]:
    """Cada lugar em que um nome de aluno sai sem a identidade DA MESMA pessoa ao lado."""
    erros: list[str] = []

    def visitar(no: Any, caminho: str) -> None:
        if isinstance(no, dict):
            for chave, valor in no.items():
                if isinstance(chave, str) and _tem_nome(chave):
                    erros.append(f"{caminho}.<chave>: nome de aluno como chave de dict")
                if isinstance(valor, str) and _tem_nome(valor):
                    erros.extend(_conferir_campo(no, chave, valor, f"{caminho}.{chave}"))
                else:
                    visitar(valor, f"{caminho}.{chave}")
        elif isinstance(no, list):
            for i, item in enumerate(no):
                if isinstance(item, str) and _tem_nome(item):
                    erros.append(f"{caminho}[{i}]: nome de aluno solto numa lista")
                else:
                    visitar(item, f"{caminho}[{i}]")

    visitar(resultado, "$")
    return erros


def _conferir_campo(dono: dict, chave: str, valor: str, caminho: str) -> list[str]:
    if chave not in CHAVES_DE_NOME:
        return [f"{caminho}: nome de aluno fora de campo de nome"]
    dono_do_nome = _NOME_POR_NORM.get(_norm(valor))
    if dono_do_nome is None:
        return [f"{caminho}: nome de aluno dentro de texto livre"]
    if dono.get("alunoId"):
        identidade = dono["alunoId"]
    elif dono.get("matricula"):
        identidade = _ALUNO_POR_MATRICULA.get(str(dono["matricula"]))
    else:
        return [f"{caminho}: nome de aluno sem {' nem '.join(CHAVES_DE_IDENTIDADE)} no mesmo dict"]
    if identidade != dono_do_nome:
        return [f"{caminho}: o nome é de um aluno e a identidade ao lado é de outro"]
    return []


@pytest.fixture(scope="module")
def resultados() -> dict[str, dict]:
    """Cada tool exposta, uma vez, pelo REGISTRO, contra a mesma escola sintética."""
    escola = nova_escola()
    semear_cantina(escola.db)
    return {nome: chamar(escola.cliente(), nome, **args) for nome, args in CHAMADAS.items()}


# ─── A política ──────────────────────────────────────────────────────────


class TestPolitica:
    def test_o_conjunto_exposto_e_exatamente_o_decidido(self):
        expostas = {f.nome for f in REGISTRO.catalogo("coordenacao") if f.expor_no_mcp}
        assert expostas == EXPOSTAS
        assert len(EXPOSTAS) == 38

    def test_com_o_pseudonimo_o_catalogo_tira_as_que_so_servem_com_o_nome(self):
        """As que só servem com o nome são exatamente as que o catálogo do MCP
        tira com o pseudônimo ligado — as listas de lá e daqui não podem divergir."""
        assert SO_COM_NOME_DO_ALUNO == EXPOSTAS_COM_O_NOME
        assert set(Catalogo(REGISTRO, teto_de_linhas=50).nomes()) == EXPOSTAS
        com_pseudonimo = Catalogo(REGISTRO, teto_de_linhas=50, com_nome_do_aluno=False)
        assert set(com_pseudonimo.nomes()) == EXPOSTAS_TAMBEM_COM_PSEUDONIMO
        assert len(EXPOSTAS_TAMBEM_COM_PSEUDONIMO) == 34

    def test_tudo_o_mais_da_coordenacao_fica_fora(self):
        """Tool nova na coordenação reprova aqui até alguém decidir se ela sai
        do SAS — por escrito, no METADADOS do módulo e numa das listas acima."""
        todas = {f.nome for f in REGISTRO.catalogo("coordenacao")}
        assert todas - EXPOSTAS == FORA_DO_MCP

    def test_toda_exposta_e_da_coordenacao_e_so_le(self):
        assert not [f.nome for f in REGISTRO.catalogo("aluno") if f.expor_no_mcp]
        for f in REGISTRO.catalogo("coordenacao"):
            if f.expor_no_mcp:
                assert f.escopo == "coordenacao" and f.somente_leitura, f.nome

    def test_toda_exposta_tem_chamada_neste_teste(self):
        assert set(CHAMADAS) == EXPOSTAS


# ─── O nome de aluno, tool por tool ──────────────────────────────────────


@pytest.mark.parametrize("nome", sorted(EXPOSTAS))
def test_a_chamada_devolve_dado_e_nao_erro(resultados, nome):
    """Sem isto, as conferências abaixo passariam olhando um `{"erro": ...}`."""
    assert "erro" not in resultados[nome], resultados[nome]


@pytest.mark.parametrize("nome", sorted(EXPOSTAS_TAMBEM_COM_PSEUDONIMO))
def test_nome_de_aluno_so_sai_com_a_identidade_da_mesma_pessoa(resultados, nome):
    assert _violacoes(resultados[nome]) == []


def test_listar_alertas_e_por_que_ela_so_existe_com_o_nome_real(resultados):
    """O título traz o nome em texto livre: com o pseudônimo ligado, o portão
    recusaria toda chamada — e é por isso que o catálogo a tira nesse modo."""
    assert _violacoes(resultados["listar_alertas"])
    with pytest.raises(PseudonimoRecusado):
        pseudonimizar(
            resultados["listar_alertas"], matricula_por_id=MATRICULA, nomes_de_alunos=frozenset(NOME.values())
        )


def test_custos_e_por_que_ela_so_existe_com_o_nome_real(resultados):
    """A soma por aluno traz o nome como `rotulo`, sem identidade ao lado: com
    o pseudônimo ligado, o portão recusaria a chamada inteira."""
    assert _violacoes(resultados["custos_da_cantina"])
    with pytest.raises(PseudonimoRecusado):
        pseudonimizar(
            resultados["custos_da_cantina"], matricula_por_id=MATRICULA, nomes_de_alunos=frozenset(NOME.values())
        )


def test_a_restricao_sai_do_catalogo_com_o_pseudonimo_mesmo_passando_pelo_portao(resultados):
    """Ela tem a identidade ao lado do nome, e o portão a deixaria passar: quem
    a tira é a decisão. "Aluno <matrícula>" ao lado de um dado de saúde continua
    dado pessoal sensível (LGPD art. 5º, I e II; art. 11)."""
    assert _violacoes(resultados["restricoes_alimentares"]) == []
    assert "restricoes_alimentares" in SO_COM_NOME_DO_ALUNO
    assert Catalogo(REGISTRO, teto_de_linhas=50, com_nome_do_aluno=False).obter("restricoes_alimentares") is None


@pytest.mark.parametrize("nome", sorted(EXPOSTAS - {"restricoes_alimentares"}))
def test_so_uma_tool_exposta_devolve_a_restricao_alimentar(resultados, nome):
    """O GRANT é do papel, não da tool: nada no Postgres impede outra exposta de
    ler a coluna. Quem segura são isto e o --ferramentas do verificador."""
    texto = json.dumps(resultados[nome], ensure_ascii=False)
    assert "SENTINELA-SAUDE" not in texto and "restricaoAlimentar" not in texto


@pytest.mark.parametrize("nome", sorted(EXPOSTAS_SEM_PESSOA | EXPOSTAS_DA_CANTINA_SEM_PESSOA | {
    "topicos_do_edital", "buscar_questoes_do_banco", "recorrencia_no_banco",
}))
def test_as_que_nao_sao_de_pessoa_nao_devolvem_nome_de_aluno(resultados, nome):
    texto = json.dumps(resultados[nome], ensure_ascii=False)
    assert not _tem_nome(texto)


@pytest.mark.parametrize("nome", sorted(
    (
        EXPOSTAS_COM_PSEUDONIMO | EXPOSTAS_COM_O_NOME | EXPOSTAS_DA_CANTINA_COM_PSEUDONIMO
        | {"relatorio_ciclo", "buscar_aluno_por_matricula"}
    )
    - {"trajetoria_aluno", "tendencia_aluno"}
))
def test_as_de_aluno_de_fato_devolvem_nome(resultados, nome):
    """O contrário do anterior, para a conferência não passar no vazio.
    `trajetoria_aluno` e `tendencia_aluno` não devolvem nome nenhum."""
    assert _tem_nome(json.dumps(resultados[nome], ensure_ascii=False))


@pytest.mark.parametrize("nome", sorted(EXPOSTAS_TAMBEM_COM_PSEUDONIMO))
def test_o_pseudonimizador_do_mcp_aceita_e_nao_sobra_nome(resultados, nome):
    """O consumidor de verdade: `app/mcp/pseudonimo.py`, com o cadastro da escola."""
    saida = pseudonimizar(
        resultados[nome], matricula_por_id=MATRICULA, nomes_de_alunos=frozenset(NOME.values())
    )
    texto = json.dumps(saida, ensure_ascii=False)
    assert not _tem_nome(texto)
    if _tem_nome(json.dumps(resultados[nome], ensure_ascii=False)):
        assert re.search(r"Aluno 900000\d", texto)
