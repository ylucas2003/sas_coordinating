"""O inventário de tools do coordenador — higiene e escolha.

Duas camadas, de propósito:

  **Higiene** roda sempre e não custa nada. São 30 tools; a chance de duas
  ganharem o mesmo nome, ou de um `required` apontar para um parâmetro que não
  existe, cresce a cada uma que se acrescenta — e o sintoma é o modelo chamando
  a tool errada, que ninguém liga ao commit que causou.

  **Escolha** é a resposta à pergunta que o docs/10 §2.8 deixou aberta —
  *"existe teto de quantas tools cabem num prompt antes de a escolha
  degradar?"*. Ela chama a OpenAI de verdade, então só roda quando alguém
  pede: `SAS_TESTE_ESCOLHA_TOOL=1 pytest -k escolha`. Rodar antes e depois de
  acrescentar tool é o que transforma "acho que degradou" em medida
  (docs/31 §3.2).
"""

import os

import pytest

from app.chat.tools import HANDLERS, SCHEMAS


def nomes() -> list[str]:
    return [s["function"]["name"] for s in SCHEMAS]


# ─── Higiene do inventário ────────────────────────────────────────────────


class TestInventario:
    def test_nome_de_tool_e_unico(self):
        todos = nomes()
        assert len(todos) == len(set(todos)), "duas tools com o mesmo nome — uma some do registry"

    def test_todo_schema_tem_handler_e_vice_versa(self):
        assert set(nomes()) == set(HANDLERS)

    def test_toda_tool_se_explica(self):
        """Descrição curta é a causa mais comum de o modelo escolher errado."""
        curtas = [
            s["function"]["name"]
            for s in SCHEMAS
            if len(s["function"].get("description", "")) < 40
        ]
        assert not curtas, f"descrição curta demais: {curtas}"

    def test_required_aponta_para_parametro_que_existe(self):
        erros = []
        for s in SCHEMAS:
            fn = s["function"]
            params = fn.get("parameters") or {}
            props = set(params.get("properties") or {})
            for req in params.get("required") or []:
                if req not in props:
                    erros.append(f"{fn['name']}.{req}")
        assert not erros, f"required sem propriedade: {erros}"

    def test_as_lacunas_do_docs_10_estao_fechadas(self):
        """A tabela da §1.6.3: o que era navegável e o chat não alcançava."""
        for tool in (
            "listar_alertas",        # o proativo do produto
            "insights_do_ciclo",
            "listar_alunos",         # a tela mais usada
            "listar_sedes",
            "listar_turmas",
            "questoes_do_simulado",  # a assimetria com o aluno
            "comparar_alunos",
            "comparar_simulados",
            "navegar_para",          # chat → página
        ):
            assert tool in HANDLERS, f"{tool} sumiu do registry"

    def test_nenhuma_tool_escreve_no_banco(self):
        """Convenção do registry: toda tool é READ-ONLY.

        Uma tool de escrita passaria despercebida — o agente chamaria, o
        resultado voltaria bonito, e a alteração fantasma só apareceria depois.

        ⚠️ O que este teste garante e o que não garante: ele é um grep textual
        no PRIMEIRO nível, sobre os módulos que o registry de fato carrega.
        Escrita feita por helper importado de outro módulo (`_classif.
        recalcular_tudo(cliente)`, por exemplo) passa invisível — para isso não
        há atalho, só revisão. O que ele pega é o descuido comum: alguém
        escrever `.insert(` dentro de uma tool.
        """
        import inspect

        from app.chat.tools import _MODULOS

        suspeitas = []
        # Iterar sobre `_MODULOS`, e não sobre uma tupla escrita à mão: módulo
        # novo no registry entra no teste sozinho. A lista fixa anterior não
        # varreria um `tools/questoes.py` acrescentado amanhã.
        for mod in _MODULOS:
            fonte = inspect.getsource(mod)
            for escrita in (".insert(", ".update(", ".upsert(", ".delete("):
                if escrita in fonte:
                    suspeitas.append(f"{mod.__name__}{escrita}")
        assert not suspeitas, f"tool escrevendo no banco: {suspeitas}"


# ─── Escolha de tool (custa dinheiro; opt-in) ─────────────────────────────

#: Pergunta → tools que resolvem. Aceita mais de uma quando a escolha é
#: legitimamente ambígua: o que se mede é degradação, não gosto.
CASOS: list[tuple[str, set[str]]] = [
    ("Como está a aluna Ana Souza?", {"buscar_aluno_por_nome", "obter_aluno", "relatorio_aluno"}),
    ("Quais alunos estão em risco no momento?", {"alunos_em_risco", "listar_alunos"}),
    ("Tem algum alerta pendente?", {"listar_alertas"}),
    ("Em quais matérias devo focar agora?", {"materias_problematicas", "listar_ciclos"}),
    ("Quais simulados tiveram no ciclo mais recente?", {"listar_simulados", "listar_ciclos"}),
    ("Compare o ciclo mais recente com o anterior", {"listar_ciclos", "comparar_ciclos"}),
    ("Compare a Ana com o Pedro", {"buscar_aluno_por_nome", "comparar_alunos"}),
    ("O P22 foi mais difícil que o P21?", {"listar_simulados", "comparar_simulados"}),
    ("Quais questões o pessoal mais errou no último simulado?",
     {"questoes_do_simulado", "listar_simulados"}),
    ("Quem tem desempenho parecido com a Ana?", {"buscar_aluno_por_nome", "alunos_similares"}),
    ("Quais turmas existem na sede Aldeota?", {"listar_sedes", "listar_turmas"}),
    ("Monte o relatório do ciclo atual", {"relatorio_ciclo", "listar_ciclos"}),
    ("Exporte os alunos em zona de risco em CSV", {"exportar_csv", "alunos_em_risco"}),
    ("Me mostre o histograma do último simulado", {"gerar_grafico", "listar_simulados", "histograma_simulado"}),
    ("Me leva pra ficha da Ana", {"buscar_aluno_por_nome", "navegar_para"}),
]


@pytest.mark.skipif(
    not os.getenv("SAS_TESTE_ESCOLHA_TOOL"),
    reason="chama a OpenAI de verdade; rode com SAS_TESTE_ESCOLHA_TOOL=1",
)
@pytest.mark.parametrize("pergunta,esperadas", CASOS)
def test_escolha_de_tool_nao_degradou(pergunta, esperadas):
    from openai import OpenAI

    from app.chat.perfis import perfil_coordenador

    perfil = perfil_coordenador()
    resposta = OpenAI().chat.completions.create(
        model=perfil.modelo,
        temperature=0,
        messages=[perfil.system_message, {"role": "user", "content": pergunta}],
        tools=perfil.schemas,
        tool_choice="auto",
    )
    chamadas = resposta.choices[0].message.tool_calls or []
    escolhidas = {c.function.name for c in chamadas}
    assert escolhidas & esperadas, (
        f"{pergunta!r} → {escolhidas or 'nenhuma tool'}; esperava alguma de {esperadas}"
    )
