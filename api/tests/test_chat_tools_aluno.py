"""As tools do Tio Léo de 24/10 (docs/43 §4.3; docs/27 §7, §9 e §10).

O que se trava aqui:

  1. cada tool responde COM dado e SEM dado — sem dado é `null` com observação
     ou `{"erro"}` de domínio, nunca a falha genérica do registro;
  2. o `aluno_id` do argumento é ignorado: as chamadas passam por
     `REGISTRO.despachar` com uma `Sessao` de aluno, e o resultado é do aluno
     do token;
  3. nenhum resultado traz nome ou nota de outro aluno (docs/27 §9);
  4. o cartão vai ANINHADO, no formato que `ArtefatoAluno.tsx` lê, e passa no
     catálogo do registro;
  5. o piso de anonimato do lado das tools — histograma, ficha da prova e
     média da turma; o do domínio e o das rotas /me são de
     test_piso_de_anonimato.py;
  6. "hoje" é o dia da escola, não o do container;
  7. o panorama só compõe, e custa menos da metade das idas ao PostgREST;
  8. as regras novas do prompt e do insight.

O banco é o de mentira (`fake_postgrest.FakeCliente`), com duas coisas a mais,
só aqui: o filtro `neq` e a contagem de idas. Embed (`simulado(...)` dentro de
`nota`) vem pré-montado na linha, como em test_dominio_trajetoria.py. Nada
chama a OpenAI: o insight é trocado por um dublê.

Rodar:  cd api && APP_ENV=dev ./.venv/bin/python -m pytest tests/test_chat_tools_aluno.py -q
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import json
import pathlib
import re
import statistics
from collections import Counter
from datetime import UTC, date, datetime

import pytest

from app.banco import missao as banco_missao
from app.chat import (
    contexto_do_turno,
    ferramentas,
    roteiros,
    tools_aluno,
    tools_aluno_banco,
    tools_aluno_situacao,
)
from app.chat.ferramentas import REGISTRO, TIPOS_DE_ARTEFATO, Sessao, artefatos_do_resultado
from app.chat.prompt_aluno import SYSTEM_PROMPT_ALUNO
from app.routes import me as rotas_me
from app.stats import (
    aluno_dados,
    aluno_jornada,
    aluno_panorama,
    aluno_zona,
    computavel,
    insight_aluno,
)
from app.stats.utils import hash_payload_estavel

from .fake_postgrest import FakeCliente, Query, Tabela

HOJE = date(2026, 10, 24)
ANA = "a-ana"
BIA = "a-bia"
SESSAO = Sessao(tipo="aluno", usuario=f"aluno:{ANA}", aluno_id=ANA, nome="Ana")

#: As notas da colega, e o nome dela. Nenhum resultado das tools pode trazê-los.
NOME_DA_COLEGA = "Beatriz"
NOTAS_DA_COLEGA = (9.37, 7.77, 9.12, 8.88, 6.66)

#: Vinte colegas sem nome, para as provas passarem do piso de anonimato.
COLEGAS = [f"a-{i:02d}" for i in range(1, 21)]
VALORES = [2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.5, 7.0, 7.5,
           8.0, 8.5, 3.2, 4.4, 5.6, 6.8, 7.2, 2.8, 5.1, 6.3]


# ─── O cliente que conta ─────────────────────────────────────────────────


class _Consulta(Query):
    """A consulta do fake, com `neq` e com a ida contada no `execute`."""

    def __init__(self, cliente, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cliente = cliente

    def neq(self, coluna, valor):
        self.filtros.append(("neq", coluna, valor))
        return self

    def _bate(self, linha):
        if any(t == "neq" and linha.get(c) == v for t, c, v in self.filtros):
            return False
        return super()._bate(linha)

    def execute(self):
        self._cliente.idas.append(self.tabela)
        return super().execute()


class _Tabela(Tabela):
    def __init__(self, cliente, nome):
        super().__init__(cliente.db, nome)
        self._cliente = cliente

    def select(self, *colunas, count=None):
        consulta = _Consulta(self._cliente, self.db, self.nome, "select")
        consulta.colunas = ",".join(colunas)
        consulta.contagem = count
        return consulta

    # As escritas são anotadas: "tool só lê" se prova pelo que o cliente
    # RECEBE, em qualquer nível da chamada — o grep do catálogo só vê o
    # módulo da tool, e a escrita do insight mora dois níveis abaixo.
    def insert(self, json, **kw):
        self._cliente.escritas.append((self.nome, "insert"))
        return super().insert(json, **kw)

    def upsert(self, json, **kw):
        self._cliente.escritas.append((self.nome, "upsert"))
        return super().upsert(json, **kw)

    def update(self, json, **kw):
        self._cliente.escritas.append((self.nome, "update"))
        return super().update(json, **kw)

    def delete(self, **kw):
        self._cliente.escritas.append((self.nome, "delete"))
        return super().delete(**kw)


class Cliente(FakeCliente):
    def __init__(self, db):
        super().__init__(db)
        self.idas: list[str] = []
        self.escritas: list[tuple[str, str]] = []

    def table(self, nome):
        return _Tabela(self, nome)


# ─── O banco do aluno ────────────────────────────────────────────────────

MATERIAS = {
    "m-mat": {"id": "m-mat", "codigo": "matematica", "nome": "Matemática"},
    "m-fis": {"id": "m-fis", "codigo": "fisica", "nome": "Física"},
    "m-qui": {"id": "m-qui", "codigo": "quimica", "nome": "Química"},
}
CICLOS = {
    "c-2": {"id": "c-2", "ordem": 2, "nome": "Ciclo 2", "vestibular_alvo": "ITA", "ano_letivo_id": "al-26"},
    "c-3": {"id": "c-3", "ordem": 3, "nome": "Ciclo 3", "vestibular_alvo": "ITA", "ano_letivo_id": "al-26"},
    # O ciclo 3 de 2025 — a MESMA ordem do c-3 de 2026, de propósito: a ordem se
    # repete entre anos letivos (aluno_jornada._ciclo_corrente). Só entra no
    # banco nos testes que o lançam.
    "c-25": {"id": "c-25", "ordem": 3, "nome": "Ciclo 3", "vestibular_alvo": "ITA", "ano_letivo_id": "al-25"},
}


def _simulado(id_, rotulo, data, tipo, materia_id, ciclo_id, evento=None) -> dict:
    ciclo = CICLOS[ciclo_id]
    return {
        "id": id_, "nome": f"Simulado {rotulo}", "rotulo_curto": rotulo, "data_aplicacao": data,
        "nota_maxima": 10, "materia_id": materia_id, "tipo": tipo, "anulado": False,
        "e_agregado": False, "nota_confiavel": True, "motivo_nota_nao_confiavel": None,
        "ciclo_id": ciclo_id, "evento_agenda_id": evento, "quiz_id": None,
        "duracao_media_segundos": None,
        # Os embeds que o PostgREST resolveria; o fake devolve a linha como está.
        "ciclo": {"id": ciclo_id, "ordem": ciclo["ordem"], "vestibular_alvo": ciclo["vestibular_alvo"],
                  "ano_letivo_id": ciclo["ano_letivo_id"]},
        "materia": {"nome": MATERIAS[materia_id]["nome"]} if materia_id else None,
    }


def _metrica(simulado_id: str, notas: list[float], ausentes: int = 0) -> dict:
    contagens = [0] * 20
    for n in notas:
        contagens[min(19, int(n / 0.5))] += 1
    return {
        "id": f"met-{simulado_id}", "simulado_id": simulado_id, "recorte_tipo": "geral",
        "recorte_id": None, "media": statistics.mean(notas), "mediana": statistics.median(notas),
        "desvio_padrao": statistics.pstdev(notas), "n_presentes": len(notas),
        "n_ausentes": ausentes,
        "histograma": {"maximo": 10.0, "largura_bin": 0.5, "contagens": contagens},
    }


def banco_do_aluno() -> dict:
    """Ana (o aluno do token), Beatriz (a colega que nada pode vazar) e vinte
    colegas sem nome. Ana mira o ITA, tem matrícula ativa e um simulado marcado
    para 30/10; faltou a uma prova; e uma prova tem só três notas."""
    sims = {
        "s-peq": _simulado("s-peq", "P Pequena", "2026-08-10", "fase_2", "m-mat", "c-2"),
        "s-f1": _simulado("s-f1", "ITA F1", "2026-09-20", "fase_1", None, "c-3"),
        "s-falta": _simulado("s-falta", "ITA P1 Fís", "2026-09-25", "fase_2", "m-fis", "c-3"),
        "s-fis": _simulado("s-fis", "ITA P2 Fís", "2026-10-01", "fase_2", "m-fis", "c-3"),
        "s-qui": _simulado("s-qui", "ITA P2 Quí", "2026-10-02", "fase_2", "m-qui", "c-3"),
        "s-futuro": _simulado("s-futuro", "ITA P3", "2026-10-30", "fase_1", None, "c-3", "ev-1"),
    }
    notas: dict = {}
    metricas: dict = {}

    def lancar(sim_id: str, por_aluno: dict[str, float | None]) -> None:
        presentes = []
        for aluno, valor in por_aluno.items():
            notas[f"n-{aluno}-{sim_id}"] = {
                "id": f"n-{aluno}-{sim_id}", "aluno_id": aluno, "simulado_id": sim_id,
                "pontuacao": valor, "presente": valor is not None, "computavel": valor is not None,
                "simulado": sims[sim_id],
            }
            if valor is not None:
                presentes.append(valor)
        metricas[sim_id] = _metrica(sim_id, presentes, ausentes=len(por_aluno) - len(presentes))

    colegas = dict(zip(COLEGAS, VALORES, strict=True))
    lancar("s-fis", {ANA: 6.0, BIA: 9.37, **colegas})
    lancar("s-qui", {ANA: 3.8, BIA: 7.77, **colegas})
    lancar("s-f1", {ANA: 5.5, BIA: 9.12, **colegas})
    lancar("s-falta", {ANA: None, BIA: 6.66, **colegas})
    lancar("s-peq", {ANA: 7.0, BIA: 8.88, COLEGAS[0]: 4.0})

    return {
        "aluno": {ANA: {"id": ANA, "nome": "Ana Aluna"}, BIA: {"id": BIA, "nome": "Beatriz Colega"}},
        "materia": dict(MATERIAS),
        "ciclo": dict(CICLOS),
        "simulado": sims,
        "nota": notas,
        "metrica_simulado": metricas,
        "matricula_turma": {
            "mt-ana": {"id": "mt-ana", "aluno_id": ANA, "turma_id": "t-1",
                       "ativo_desde": "2026-01-01", "ativo_ate": None},
        },
        "turma": {"t-1": {"id": "t-1", "ano_letivo_id": "al-26"}},
        "evento_agenda": {
            "ev-1": {"id": "ev-1", "titulo": "Simulado ITA P3", "data_evento": "2026-10-30",
                     "cancelado_em": None},
        },
        "vestibular_alvo_aluno": {"va-ana": {"id": "va-ana", "aluno_id": ANA, "vestibular": "ITA"}},
    }


# ─── O banco de questões ─────────────────────────────────────────────────


def _questao(id_, vestibular, ano, fase, materia, numero, *, dissertativa=False,
             resolucao_url=None, resolucao_md=None, resolucao_origem=None,
             enunciado="Um gás ideal passa por um ciclo.", imagem=False) -> dict:
    return {
        "id": id_, "vestibular": vestibular, "ano": ano, "fase": fase, "materia": materia,
        "numero": numero, "dissertativa": dissertativa, "enunciado_md": enunciado,
        "gabarito": None if dissertativa else "A",
        "gabarito_origem": None if dissertativa else "banca", "gabarito_confianca": None,
        "imagem_url": "https://bucket.exemplo/figura.png" if imagem else None,
        "usa_imagem_no_render": imagem, "resolucao_url": resolucao_url,
        "resolucao_md": resolucao_md, "resolucao_origem": resolucao_origem,
        "extraido_por": "pipeline", "revisado": True,
    }


def banco_de_questoes() -> dict:
    """Doze de Termodinâmica (o único assunto com lastro para a missão), duas
    dissertativas de Ondas, uma sem classificação, e a 1 da 2ª fase do ITA 2017
    em Física E em Química — o endereço que só a matéria desempata."""
    ari = "https://www.aridesa.com.br/resolucao"
    questoes = [
        _questao("ita_2019_fase1_q01", "ITA", 2019, 1, "Física", 1,
                 resolucao_url=f"{ari}/q01", resolucao_origem="ari"),
        _questao("ita_2019_fase1_q02", "ITA", 2019, 1, "Física", 2,
                 resolucao_md="Pela primeira lei, ΔU = Q − W. Ver https://exemplo.com/x",
                 resolucao_origem="sugerida"),
        _questao("ita_2020_fase1_q03", "ITA", 2020, 1, "Física", 3,
                 resolucao_md="Texto de origem desconhecida.", resolucao_origem=None),
        _questao("ita_2020_fase1_q04", "ITA", 2020, 1, "Física", 4),
        _questao("ita_2021_fase1_q05", "ITA", 2021, 1, "Física", 5, imagem=True,
                 enunciado="![gráfico](https://bucket.exemplo/f5.png) Veja o gráfico " + "pV " * 120,
                 resolucao_url=f"{ari}/q05", resolucao_origem="ari"),
        *(
            _questao(f"ita_{ano}_fase1_q{n:02d}", "ITA", ano, 1, "Física", n,
                     resolucao_url=f"{ari}/q{n:02d}", resolucao_origem="ari")
            for ano, n in ((2021, 6), (2022, 7), (2022, 8), (2023, 9), (2023, 10), (2023, 11), (2023, 12))
        ),
        _questao("ime_2004_fase2_fis_q01", "IME", 2004, 2, "Física", 1, dissertativa=True),
        _questao("ime_2004_fase2_fis_q02", "IME", 2004, 2, "Física", 2, dissertativa=True),
        _questao("ita_2018_fase1_q30", "ITA", 2018, 1, "Física", 30),
        _questao("ita_2017_fase2_fis_q01", "ITA", 2017, 2, "Física", 1, dissertativa=True),
        _questao("ita_2017_fase2_qui_q01", "ITA", 2017, 2, "Química", 1, dissertativa=True),
        _questao("ita_2019_fase1_q25", "ITA", 2019, 1, "Química", 25),
        _questao("ita_2019_fase1_q40", "ITA", 2019, 1, "Matemática", 40),
    ]
    ligacoes = [
        *((q["id"], "Física", "9.1") for q in questoes[:12]),
        ("ime_2004_fase2_fis_q01", "Física", "7.2"),
        ("ime_2004_fase2_fis_q02", "Física", "7.2"),
        ("ita_2017_fase2_fis_q01", "Física", "7.2"),
        ("ita_2017_fase2_qui_q01", "Química", "1.1"),
        ("ita_2019_fase1_q25", "Química", "1.1"),
        ("ita_2019_fase1_q40", "Matemática", "1.1"),
    ]

    def topico(materia, codigo, nome, bloco, ordem, assuntos=()):
        return {
            "materia": materia, "codigo": codigo, "nome": nome, "bloco_codigo": bloco,
            "bloco_nome": f"Bloco {bloco}", "ordem": ordem,
            "topico_taxonomia_assunto": [{"ordem": i, "texto": t} for i, t in enumerate(assuntos, 1)],
        }

    taxonomia = [
        topico("Física", "9.1", "Termodinâmica", "9", 1, ("Primeira lei", "Máquinas térmicas")),
        topico("Física", "8.1", "Óptica Geométrica", "8", 2, ("Espelhos planos",)),
        topico("Física", "8.2", "Óptica Física", "8", 3, ("Interferência",)),
        topico("Física", "7.2", "Ondas e Acústica", "7", 4, ("Efeito Doppler",)),
        topico("Química", "1.1", "Estrutura Atômica", "1", 1),
        topico("Matemática", "1.1", "Conjuntos e Lógica", "1", 1),
    ]

    def estudo(aluno, questao, quando, *, alternativa=None, acertou=None, anotacao=None):
        return {
            "aluno_id": aluno, "questao_id": questao, "resolvida": True, "anotacao": anotacao,
            "alternativa_escolhida": alternativa, "acertou": acertou, "atualizado_em": quando,
        }

    return {
        "questao_vestibular": {q["id"]: q for q in questoes},
        "questao_vestibular_alternativa": {
            f"{q['id']}-{letra}": {"id": f"{q['id']}-{letra}", "questao_id": q["id"],
                                   "letra": letra, "texto": f"alternativa {letra}"}
            for q in questoes if not q["dissertativa"] for letra in "ABCDE"
        },
        "questao_vestibular_topico": {
            f"{qid}:{codigo}": {"questao_id": qid, "materia": materia, "topico_codigo": codigo,
                                "confianca": "alta", "observacao": None}
            for qid, materia, codigo in ligacoes
        },
        "topico_taxonomia": {f"{t['materia']}:{t['codigo']}": t for t in taxonomia},
        "questao_estudo_aluno": {
            "e1": estudo(ANA, "ita_2019_fase1_q01", "2026-10-20", alternativa="A", acertou=True,
                         anotacao="anotação da Ana"),
            "e2": estudo(ANA, "ita_2020_fase1_q03", "2026-10-19"),
            "e3": estudo(BIA, "ita_2019_fase1_q01", "2026-10-18", alternativa="C", acertou=False,
                         anotacao="Beatriz: perguntar ao Fulano"),
            "e4": estudo(BIA, "ita_2019_fase1_q02", "2026-10-17"),
            "e5": estudo(BIA, "ita_2021_fase1_q05", "2026-10-16"),
        },
    }


# ─── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def relogio(monkeypatch):
    """O dia da escola, fixo. Cada módulo importou o nome, então troca-se em cada um."""
    for modulo in (aluno_jornada, aluno_panorama, tools_aluno_situacao, tools_aluno_banco):
        monkeypatch.setattr(modulo, "hoje_na_escola", lambda agora=None: HOJE)


@pytest.fixture(autouse=True)
def sem_openai(monkeypatch):
    """O insight do ciclo chamaria a OpenAI; aqui ele é um dublê."""
    monkeypatch.setattr(tools_aluno, "gerar_para_aluno_ciclo", lambda *a, **k: ["um bullet"])


@pytest.fixture
def cliente() -> Cliente:
    return Cliente({**banco_do_aluno(), **banco_de_questoes()})


@pytest.fixture
def vazio() -> Cliente:
    return Cliente({})


def chamar(cliente, tool: str, /, **args) -> dict:
    """Pelo caminho de verdade: o registro, com a sessão da Ana. Posicionais só,
    porque `nome` é argumento de `roteiro_do_mentor`."""
    return REGISTRO.despachar(SESSAO, tool, cliente, args)


def _sem_falha(resultado: dict) -> None:
    assert "falhou do nosso lado" not in json.dumps(resultado, ensure_ascii=False), resultado


#: Uma chamada com dado para cada tool do Tio Léo. Tool nova sem linha aqui
#: reprova `test_toda_tool_do_aluno_esta_na_varredura`.
CHAMADAS: dict[str, dict] = {
    "meu_panorama": {},
    "minha_zona": {},
    "minha_agenda_do_ciclo": {},
    "minha_trajetoria": {"materia": "Física"},
    "distribuicao_do_simulado": {"simulado_id": "s-fis"},
    "minhas_notas": {},
    "meu_desempenho_em_simulado": {"simulado_id": "s-fis"},
    "minhas_questoes_erradas": {"simulado_id": "s-fis"},
    "minha_evolucao": {},
    "meu_streak": {},
    "meu_insight_do_ciclo": {},
    "o_que_mais_cai": {"materia": "Física"},
    "missao_de_hoje": {},
    "questoes_do_banco": {"materia": "Física", "assunto": "termodinâmica"},
    "resolucao_oficial": {"questao_id": "ita_2019_fase1_q01"},
    "meu_progresso_no_banco": {},
    "roteiro_do_mentor": {"nome": "revisar_simulado"},
}

NOVAS = {
    "meu_panorama", "minha_zona", "minha_agenda_do_ciclo", "minha_trajetoria",
    "distribuicao_do_simulado", "o_que_mais_cai", "missao_de_hoje", "questoes_do_banco",
    "resolucao_oficial", "meu_progresso_no_banco",
}


# ─── O catálogo ──────────────────────────────────────────────────────────


class TestCatalogo:
    def test_as_tools_encomendadas_estao_no_escopo_do_aluno(self):
        aluno = {f.nome for f in REGISTRO.catalogo("aluno")}
        coordenacao = {f.nome for f in REGISTRO.catalogo("coordenacao")}
        assert aluno >= NOVAS
        assert not NOVAS & coordenacao
        # Decisão de 24/10: `minhas_listas` não entra nesta rodada.
        assert "minhas_listas" not in aluno

    def test_toda_tool_do_aluno_esta_na_varredura(self):
        assert set(CHAMADAS) == {f.nome for f in REGISTRO.catalogo("aluno")}

    def test_o_panorama_abre_o_catalogo(self):
        """A primeira chamada de pergunta aberta é a primeira que o modelo lê."""
        assert REGISTRO.catalogo("aluno")[0].nome == "meu_panorama"

    @pytest.mark.parametrize("nome", sorted(NOVAS))
    def test_a_descricao_segue_o_padrao_e_e_curta(self, nome):
        descricao = next(f.descricao for f in REGISTRO.catalogo("aluno") if f.nome == nome)
        for bloco in ("Quando usar", "Antes de chamar", "Definições", "Exemplo"):
            assert bloco in descricao, f"{nome}: falta '{bloco}'"
        assert len(descricao) <= 1100

    def test_nenhum_modulo_das_tools_escreve_no_banco(self):
        """O mesmo grep de test_chat_tools.py, nos módulos do Tio Léo — e no da
        composição, que é leitura pura. `dict.update` também reprova: o grep não
        sabe a diferença, então o código não usa."""
        suspeitas = []
        for modulo in (tools_aluno, tools_aluno_situacao, tools_aluno_banco, aluno_panorama):
            fonte = inspect.getsource(modulo)
            for escrita in (".insert(", ".update(", ".upsert(", ".delete("):
                if escrita in fonte:
                    suspeitas.append(f"{modulo.__name__}{escrita}")
        assert not suspeitas, f"tool escrevendo no banco: {suspeitas}"

    def test_nenhuma_tool_do_aluno_tem_metadados_de_mcp(self):
        assert not getattr(tools_aluno, "METADADOS", {}) or not any(
            m.get("expor_no_mcp") for m in tools_aluno.METADADOS.values()
        )


# ─── 1 · Com dado e sem dado ─────────────────────────────────────────────


class TestSemDado:
    @pytest.mark.parametrize("nome", sorted(CHAMADAS))
    def test_banco_vazio_nao_e_falha(self, vazio, nome):
        resultado = chamar(vazio, nome, **CHAMADAS[nome])
        assert isinstance(resultado, dict)
        _sem_falha(resultado)

    def test_panorama_vazio_e_nulo_com_observacao(self, vazio):
        r = chamar(vazio, "meu_panorama")
        assert "erro" not in r
        assert (r["zona"], r["proximoSimulado"], r["metaDoCiclo"]) == (None, None, None)
        assert r["ultimasNotas"] == [] and r["vestibularesAlvo"] == []
        assert r["sequencia"] == {"simulados": 0, "melhor": 0, "corrente": []}
        assert len(r["observacoes"]) == 4
        assert "artefato" not in r

    def test_zona_vazia_e_erro_de_dominio(self, vazio):
        assert "erro" in chamar(vazio, "minha_zona")

    def test_agenda_vazia_e_nula_com_observacao(self, vazio):
        r = chamar(vazio, "minha_agenda_do_ciclo")
        assert (r["proximoSimulado"], r["diasAteOProximo"], r["metaDoCiclo"]) == (None, None, None)
        assert any("não invente data" in o for o in r["observacoes"])

    def test_trajetoria_vazia_nao_anexa_grafico(self, vazio):
        r = chamar(vazio, "minha_trajetoria")
        assert (r["total"], r["trajetoria"]) == (0, [])
        assert "artefato" not in r and r["observacao"]

    def test_banco_de_questoes_vazio(self, vazio):
        assert chamar(vazio, "o_que_mais_cai")["topicos"] == []
        assert chamar(vazio, "missao_de_hoje")["missao"] is None
        progresso = chamar(vazio, "meu_progresso_no_banco")
        assert (progresso["feitas"], progresso["total"], progresso["porAssunto"]) == (0, 0, [])
        assert "erro" in chamar(vazio, "resolucao_oficial", questao_id="ita_2019_fase1_q01")
        assert "erro" in chamar(vazio, "questoes_do_banco", materia="Física", assunto="óptica")
        sem = chamar(vazio, "questoes_do_banco", materia="Física", topico_codigo="9.1")
        assert sem["questoes"] == [] and "artefato" not in sem


# ─── 2 · O aluno do token ────────────────────────────────────────────────


class TestIdentidade:
    """O `aluno_id` plantado no argumento é o da colega; tudo tem de sair da Ana."""

    def test_panorama(self, cliente):
        r = chamar(cliente, "meu_panorama", aluno_id=BIA)
        assert [n["nota"] for n in r["ultimasNotas"]] == [3.8, 6.0, 5.5, 7.0]
        assert r["vestibularesAlvo"] == ["ITA"]

    def test_zona_e_agenda(self, cliente):
        assert chamar(cliente, "minha_zona", aluno_id=BIA)["vestibularesAlvo"] == ["ITA"]
        # A colega não tem matrícula: se fosse ela, não haveria agenda.
        assert chamar(cliente, "minha_agenda_do_ciclo", aluno_id=BIA)["proximoSimulado"] is not None

    def test_trajetoria_e_distribuicao(self, cliente):
        trajetoria = chamar(cliente, "minha_trajetoria", aluno_id=BIA, materia="Física")
        assert [p["nota"] for p in trajetoria["trajetoria"]] == [6.0]
        assert chamar(cliente, "distribuicao_do_simulado", aluno_id=BIA, simulado_id="s-fis")[
            "minhaNota"
        ] == 6.0

    def test_banco_de_questoes(self, cliente):
        assert chamar(cliente, "meu_progresso_no_banco", aluno_id=BIA)["feitas"] == 2
        treino = chamar(cliente, "resolucao_oficial", aluno_id=BIA, questao_id="ita_2019_fase1_q01")
        assert treino["meuTreino"] == {"resolvida": True, "alternativaEscolhida": "A", "acertou": True}
        lista = chamar(cliente, "questoes_do_banco", aluno_id=BIA, materia="Física",
                       topico_codigo="9.1", quantidade=10)
        resolvidas = {q["id"] for q in lista["questoes"] if q["resolvida"]}
        assert resolvidas == {"ita_2020_fase1_q03"}  # a q01 da Ana é de 2019, na página 2

    def test_desempenho(self, cliente):
        assert chamar(cliente, "meu_desempenho_em_simulado", aluno_id=BIA, simulado_id="s-fis")[
            "nota"
        ] == 6.0


# ─── 3 · Nada da colega ──────────────────────────────────────────────────


def _numeros(valor):
    if isinstance(valor, bool):
        return
    if isinstance(valor, (int, float)):
        yield float(valor)
    elif isinstance(valor, dict):
        for v in valor.values():
            yield from _numeros(v)
    elif isinstance(valor, list):
        for v in valor:
            yield from _numeros(v)


class TestPrivacidade:
    @pytest.mark.parametrize("nome", sorted(CHAMADAS))
    def test_nenhum_resultado_traz_nome_ou_nota_da_colega(self, cliente, nome):
        resultado = chamar(cliente, nome, aluno_id=BIA, **CHAMADAS[nome])
        _sem_falha(resultado)
        texto = json.dumps(resultado, ensure_ascii=False)
        assert NOME_DA_COLEGA not in texto and "Fulano" not in texto
        vazados = [n for n in _numeros(resultado) for c in NOTAS_DA_COLEGA if abs(n - c) < 0.005]
        assert not vazados, f"{nome} devolveu nota da colega: {vazados}"

    def test_nenhum_endereco_vai_ao_modelo(self, cliente):
        for nome, args in (
            ("questoes_do_banco", {"materia": "Física", "topico_codigo": "9.1", "quantidade": 10}),
            ("resolucao_oficial", {"questao_id": "ita_2021_fase1_q05"}),
            ("resolucao_oficial", {"questao_id": "ita_2019_fase1_q02"}),
            ("resolucao_oficial", {"questao_id": "ita_2019_fase1_q01"}),
        ):
            texto = json.dumps(chamar(cliente, nome, **args), ensure_ascii=False)
            assert "://" not in texto, f"{nome}{args} deixou passar um endereço"

    def test_a_anotacao_do_aluno_fica_fora(self, cliente):
        """Texto livre do aluno pode ter nome de terceiro; nenhuma tool o devolve."""
        for nome, args in (
            ("questoes_do_banco", {"materia": "Física", "topico_codigo": "9.1", "pagina": 2}),
            ("resolucao_oficial", {"questao_id": "ita_2019_fase1_q01"}),
        ):
            assert "anotação da Ana" not in json.dumps(chamar(cliente, nome, **args), ensure_ascii=False)


# ─── 4 · Os cartões ──────────────────────────────────────────────────────

RAIZ = pathlib.Path(__file__).resolve().parents[2]
ARTEFATO_ALUNO = RAIZ / "web/src/telas/Aluno/TioLeo/ArtefatoAluno.tsx"
ARTEFATO_COORDENACAO = RAIZ / "web/src/componentes/chat/Artefato.tsx"

#: O que o front lê de cada payload, e em que arquivo — conferido na fonte pelo
#: teste abaixo, para este mapa não envelhecer calado.
LIDO_PELO_FRONT = {
    "barras_corte": (ARTEFATO_ALUNO, {"materias": "p.materias"}),
    "lista_questoes": (ARTEFATO_ALUNO, {"itens": "p.itens"}),
    "questao": (ARTEFATO_ALUNO, {"id": "bruto.id"}),
    "prova": (ARTEFATO_ALUNO, {"simuladoId": "p.simuladoId"}),
    "histograma": (
        ARTEFATO_COORDENACAO,
        {"histograma": "histograma?:", "media": "media?:", "mediana": "mediana?:",
         "nPresentes": "nPresentes?:"},
    ),
    "linha_temporal": (ARTEFATO_COORDENACAO, {"pontos": "pontos?:"}),
}
#: O que o payload leva a mais, e por quê.
A_MAIS = {
    # O nome da régua, que o cartão vai mostrar (docs/24 §2): veredito sem
    # régua é só a má notícia. O front ainda não o lê.
    "barras_corte": {"regua"},
    # A marca do aluno, lida em ArtefatoAluno.tsx (HistogramaComMinhaNota).
    "histograma": {"minhaNota"},
}


def _artefatos(cliente) -> list[tuple[str, dict, dict]]:
    """(tool, resultado, artefato) de cada tool que anexa cartão."""
    pedidos = [
        ("meu_panorama", {}),
        ("minha_zona", {}),
        ("minha_trajetoria", {}),
        ("distribuicao_do_simulado", {"simulado_id": "s-fis"}),
        ("meu_desempenho_em_simulado", {"simulado_id": "s-fis"}),
        ("o_que_mais_cai", {"materia": "Física"}),
        ("o_que_mais_cai", {"vestibular": "ITA"}),
        ("missao_de_hoje", {}),
        ("questoes_do_banco", {"materia": "Física", "assunto": "termodinamica"}),
        ("questoes_do_banco", {"materia": "Física", "topico_codigo": "9.1", "quantidade": 1}),
        ("resolucao_oficial", {"questao_id": "ita_2019_fase1_q01"}),
        ("meu_progresso_no_banco", {}),
    ]
    saida = []
    for nome, args in pedidos:
        resultado = chamar(cliente, nome, **args)
        assert "artefato" in resultado, f"{nome}{args} não anexou cartão"
        saida.append((nome, resultado, resultado["artefato"]))
    return saida


class TestArtefatos:
    def test_o_cartao_vai_aninhado_e_passa_no_catalogo(self, cliente):
        for nome, resultado, artefato in _artefatos(cliente):
            assert set(artefato) == {"tipo", "titulo", "payload"}, nome
            # Nunca `tipo` de cartão no topo: o topo é do resultado.
            assert resultado.get("tipo") not in TIPOS_DE_ARTEFATO["aluno"], nome
            assert "payload" not in resultado, nome
            gravados = artefatos_do_resultado(nome, resultado, "aluno")
            assert gravados == [artefato], f"{nome}: o registro descartaria o cartão"
            assert artefato["tipo"] != "extrato_xp"

    def test_o_payload_e_o_que_o_front_le(self, cliente):
        for nome, _, artefato in _artefatos(cliente):
            _, campos = LIDO_PELO_FRONT[artefato["tipo"]]
            esperado = set(campos) | A_MAIS.get(artefato["tipo"], set())
            assert set(artefato["payload"]) <= esperado, nome
            assert set(campos) <= set(artefato["payload"]), nome

    def test_o_mapa_bate_com_a_fonte_do_front(self):
        if not ARTEFATO_ALUNO.exists():
            pytest.skip("sem o front ao lado (imagem só da API)")
        fontes = {arquivo: arquivo.read_text(encoding="utf-8") for arquivo, _ in LIDO_PELO_FRONT.values()}
        for tipo, (arquivo, campos) in LIDO_PELO_FRONT.items():
            for trecho in campos.values():
                assert trecho in fontes[arquivo], f"{tipo}: '{trecho}' sumiu de {arquivo.name}"
        aluno = fontes[ARTEFATO_ALUNO]
        for trecho in ("m.materia", "m.nota", "m.corte", "m.eliminatoria", "i.assunto",
                       "i.materia", "i.quantidade", "i.topicoCodigo", "p.minhaNota"):
            assert trecho in aluno, f"'{trecho}' sumiu de ArtefatoAluno.tsx"
        linha = fontes[ARTEFATO_COORDENACAO]
        for trecho in ("simuladoId?:", "rotulo?:", "data?:", "nota:", "materia?:"):
            assert trecho in linha, f"'{trecho}' sumiu do PayloadLinha de Artefato.tsx"

    def test_barras_corte_leva_a_regua(self, cliente):
        zona = chamar(cliente, "minha_zona")
        artefato = zona["artefato"]
        assert artefato["payload"]["regua"] == zona["regua"] == "ITA — Fase 2"
        assert artefato["titulo"] == "Régua ITA — Fase 2"
        assert artefato["payload"]["materias"] == zona["materias"]
        for materia in artefato["payload"]["materias"]:
            assert set(materia) == {"materia", "nota", "corte", "eliminatoria"}
            assert isinstance(materia["materia"], str) and isinstance(materia["eliminatoria"], bool)

    def test_lista_questoes_so_com_materia_e_codigo_que_viram_treino(self, cliente):
        for nome, _, artefato in _artefatos(cliente):
            if artefato["tipo"] != "lista_questoes":
                continue
            itens = artefato["payload"]["itens"]
            assert 1 <= len(itens) <= 3, nome
            for item in itens:
                assert item["materia"] in ("Física", "Química", "Matemática"), nome
                assert re.fullmatch(r"\d+(\.\d+)*", item["topicoCodigo"]), nome

    def test_o_id_da_questao_vem_do_banco(self, cliente):
        ids = set(banco_de_questoes()["questao_vestibular"])
        for _, _, artefato in _artefatos(cliente):
            if artefato["tipo"] == "questao":
                assert artefato["payload"]["id"] in ids

    def test_prova_e_so_o_id(self, cliente):
        r = chamar(cliente, "meu_desempenho_em_simulado", simulado_id="s-fis")
        assert r["artefato"] == {"tipo": "prova", "titulo": None, "payload": {"simuladoId": "s-fis"}}
        assert r["tipo"] == "fase_2"  # o tipo do SIMULADO continua no topo

    def test_linha_temporal_com_um_ponto_nao_sai(self, cliente):
        assert "artefato" not in chamar(cliente, "minha_trajetoria", materia="Química")


# ─── 5 · O piso de anonimato ─────────────────────────────────────────────


def _uma_prova(n_notas: int) -> Cliente:
    """Uma prova de Física com a Ana e mais `n_notas - 1` colegas."""
    sim = _simulado("s-1", "P1", "2026-10-01", "fase_2", "m-fis", "c-3")
    valores = [6.0] + [round(2 + i * 0.37, 2) for i in range(n_notas - 1)]
    alunos = [ANA, *(f"x-{i}" for i in range(n_notas - 1))]
    return Cliente({
        "materia": dict(MATERIAS),
        "simulado": {"s-1": sim},
        "nota": {
            f"n-{a}": {"id": f"n-{a}", "aluno_id": a, "simulado_id": "s-1", "pontuacao": v,
                       "presente": True, "computavel": True, "simulado": sim}
            for a, v in zip(alunos, valores, strict=True)
        },
        "metrica_simulado": {"s-1": _metrica("s-1", valores)},
    })


class TestPisoDeAnonimato:
    # A ficha e o tempo médio da turma no DOMÍNIO, nos limites de 2 a 20 notas,
    # são de test_piso_de_anonimato.py (`TestLimitesDoPiso`), junto das rotas
    # /me. Aqui fica o lado das tools: a frase que explica o null, o histograma
    # e o roteiro.
    def test_a_tool_diz_por_que_veio_null(self):
        r = chamar(_uma_prova(9), "meu_desempenho_em_simulado", simulado_id="s-1")
        assert r["grupos"]["geral"] is None and "colegas" in r["observacao"]
        assert "observacao" not in chamar(_uma_prova(20), "meu_desempenho_em_simulado", simulado_id="s-1")

    def test_o_histograma_recusa_abaixo_do_piso(self):
        r = chamar(_uma_prova(aluno_dados.PISO_DE_ANONIMATO - 1), "distribuicao_do_simulado",
                   simulado_id="s-1")
        assert "erro" in r and str(aluno_dados.PISO_DE_ANONIMATO) in r["erro"]
        ok = chamar(_uma_prova(aluno_dados.PISO_DE_ANONIMATO), "distribuicao_do_simulado",
                    simulado_id="s-1")
        assert ok["artefato"]["payload"]["minhaNota"] == 6.0
        assert ok["nPresentes"] == aluno_dados.PISO_DE_ANONIMATO

    def test_o_histograma_recusa_com_a_metrica_atrasada(self):
        """A métrica ainda conta 10, mas uma nota saiu desde o cálculo: a ficha
        tem 9 e anula o percentil pelo piso. O histograma não sai ao lado de um
        percentil nulo que nenhuma frase explica."""
        cliente = _uma_prova(aluno_dados.PISO_DE_ANONIMATO - 1)
        cliente.db["metrica_simulado"]["s-1"]["n_presentes"] = aluno_dados.PISO_DE_ANONIMATO
        r = chamar(cliente, "distribuicao_do_simulado", simulado_id="s-1")
        assert "erro" in r and str(aluno_dados.PISO_DE_ANONIMATO) in r["erro"]

    def test_o_roteiro_da_revisao_diz_o_que_fazer_com_a_media_null(self):
        """O roteiro carregado justamente na revisão da prova mandava dizer a
        média da turma sem a ressalva do piso, enquanto a tool a devolvia null
        pedindo para não estimar."""
        texto = roteiros.obter("aluno", "revisar_simulado").texto
        assert "Se a média vier null" in texto and "sem estimar" in texto

    def test_prova_que_o_aluno_nao_fez_e_recusada(self, cliente):
        assert "erro" in chamar(cliente, "distribuicao_do_simulado", simulado_id="s-falta")

    def test_a_media_da_turma_some_na_prova_pequena(self, cliente):
        panorama = {n["id"]: n for n in chamar(cliente, "meu_panorama", ultimas_notas=10)["ultimasNotas"]}
        notas = {s["id"]: s for s in chamar(cliente, "minhas_notas")["simulados"]}
        assert panorama["s-peq"]["mediaGeral"] is None and notas["s-peq"]["mediaGeral"] is None
        assert panorama["s-fis"]["mediaGeral"] is not None and notas["s-fis"]["mediaGeral"] is not None


# ─── 5b · O piso mora no DOMÍNIO ─────────────────────────────────────────
#
# A revisão de 25/10 (scratchpad revisao-paralela/tioleo/repro_piso.py) achou
# o piso só na SAÍDA de duas tools: minha_evolucao e meu_insight_do_ciclo — e
# GET /me/simulados, /me/evolucao e /me/insight — entregavam a média de uma
# prova com duas notas, e 2·7,94 − 7,0 = 8,88, a nota exata da colega.
# TestPrivacidade procura a nota LITERAL; aqui se procura a DERIVADA.

NOTA_DA_ANA_NA_DUPLA, NOTA_DA_BIA_NA_DUPLA = 7.0, 8.88


def _com_prova_dupla(db: dict) -> dict:
    """Uma prova de Matemática do ciclo ATUAL em que só a Ana e a Beatriz têm nota."""
    sim = _simulado("s-dupla", "ITA P2 Mat", "2026-10-05", "fase_2", "m-mat", "c-3")
    db["simulado"]["s-dupla"] = sim
    for aluno, valor in ((ANA, NOTA_DA_ANA_NA_DUPLA), (BIA, NOTA_DA_BIA_NA_DUPLA)):
        db["nota"][f"n-{aluno}-s-dupla"] = {
            "id": f"n-{aluno}-s-dupla", "aluno_id": aluno, "simulado_id": "s-dupla",
            "pontuacao": valor, "presente": True, "computavel": True, "simulado": sim,
        }
    db["metrica_simulado"]["s-dupla"] = _metrica("s-dupla", [NOTA_DA_ANA_NA_DUPLA, NOTA_DA_BIA_NA_DUPLA])
    return db


@pytest.fixture
def dupla() -> Cliente:
    return Cliente(_com_prova_dupla({**banco_do_aluno(), **banco_de_questoes()}))


def _da_qual_sai_a_colega(resultado) -> list[float]:
    """Os números de que a nota da colega sai por conta: a média das duas notas."""
    media_das_duas = (NOTA_DA_ANA_NA_DUPLA + NOTA_DA_BIA_NA_DUPLA) / 2
    return [n for n in _numeros(resultado) if abs(n - media_das_duas) < 0.006]


class TestPisoNoDominio:
    def test_nenhuma_porta_deixa_derivar_a_nota_da_colega(self, dupla):
        portas = {
            "GET /me/simulados": aluno_dados.simulados_do_aluno(dupla, ANA),
            "GET /me/simulados?incluirFaltas": aluno_dados.simulados_do_aluno(
                dupla, ANA, incluir_faltas=True
            ),
            "GET /me/evolucao": aluno_dados.evolucao_do_aluno(dupla, ANA),
            "GET /me/simulado/s-dupla": aluno_dados.detalhe_simulado_do_aluno(dupla, ANA, "s-dupla"),
            # A entrada do insight — e o que vai à OpenAI. Lista, porque
            # `_numeros` não desce em tupla.
            "GET /me/insight": list(aluno_dados.payload_insight_ciclo(dupla, ANA)),
            "meu_desempenho(s-dupla)": chamar(dupla, "meu_desempenho_em_simulado", simulado_id="s-dupla"),
            "distribuicao(s-dupla)": chamar(dupla, "distribuicao_do_simulado", simulado_id="s-dupla"),
            **{nome: chamar(dupla, nome, **args) for nome, args in CHAMADAS.items()},
        }
        for porta, resultado in portas.items():
            assert not _da_qual_sai_a_colega(resultado), f"{porta} deixa derivar a nota da colega"

    # O contrato abaixo do piso — `mediaGeral` null na lista, a série `turma`
    # null na evolução, `mediaTurma` null no insight — é de
    # test_piso_de_anonimato.py (`test_o_que_cada_rota_devolve`), pelas rotas.

    def test_posicao_e_percentil_saem_com_a_media(self, dupla):
        r = chamar(dupla, "meu_desempenho_em_simulado", simulado_id="s-dupla")
        assert (r["posicao"], r["percentil"], r["total"]) == (None, None, 2)
        assert r["grupos"]["geral"] is None
        assert "posição e percentil" in r["observacao"] and "sem estimar" in r["observacao"]

    def test_a_evolucao_diz_o_que_o_null_da_turma_quer_dizer(self, dupla):
        assert "turma pequena demais" in chamar(dupla, "minha_evolucao")["observacao"]
        # Com toda prova acima do piso, a frase não aparece.
        completo = Cliente({**banco_do_aluno(), **banco_de_questoes()})
        completo.db["nota"] = {k: v for k, v in completo.db["nota"].items() if "s-peq" not in k}
        assert "observacao" not in chamar(completo, "minha_evolucao")

    def test_as_tools_nao_reaplicam_o_piso(self):
        """A regra é do domínio: cópia dela na tool é o que deixou três portas
        abertas enquanto duas estavam fechadas."""
        for modulo in (tools_aluno, aluno_panorama):
            assert "turma_acima_do_piso" not in inspect.getsource(modulo), modulo.__name__


# ─── 5c · A nota que não conta como desempenho ───────────────────────────
#
# repro_computavel.py: o zero de quem abriu a prova e não marcou nada
# (`nota.computavel = false`, docs/32 §1.4) saía em meu_panorama e em
# minhas_notas como nota 0,0, com deltaSelf de −5,58 e sem marca — "você zerou
# Química" na boca do Tio Léo —, enquanto a zona e a trajetória já o tiravam.


def _com_prova_que_nao_conta(db: dict, *, motivo=computavel.TODAS_EM_BRANCO, confiavel=True) -> dict:
    zero = _simulado("s-zero", "ITA P3 Quí", "2026-10-10", "fase_2", "m-qui", "c-3")
    zero["nota_confiavel"] = confiavel
    depois = _simulado("s-depois", "ITA P4 Fís", "2026-10-15", "fase_2", "m-fis", "c-3")
    db["simulado"].update({"s-zero": zero, "s-depois": depois})
    db["nota"]["n-ana-zero"] = {
        "id": "n-ana-zero", "aluno_id": ANA, "simulado_id": "s-zero", "pontuacao": 0,
        "presente": True, "computavel": motivo is None, "motivo_nao_computavel": motivo,
        "simulado": zero,
    }
    db["nota"]["n-ana-depois"] = {
        "id": "n-ana-depois", "aluno_id": ANA, "simulado_id": "s-depois", "pontuacao": 6.0,
        "presente": True, "computavel": True, "simulado": depois,
    }
    return db


@pytest.fixture
def zero() -> Cliente:
    return Cliente(_com_prova_que_nao_conta({**banco_do_aluno(), **banco_de_questoes()}))


def _itens_da_prova(valor, simulado_id: str):
    """Todo dict, em qualquer profundidade, que fala da prova `simulado_id`."""
    if isinstance(valor, dict):
        if simulado_id in (valor.get("id"), valor.get("simuladoId")):
            yield valor
        for v in valor.values():
            yield from _itens_da_prova(v, simulado_id)
    elif isinstance(valor, list):
        for v in valor:
            yield from _itens_da_prova(v, simulado_id)


class TestNotaQueNaoConta:
    def test_a_lista_mostra_com_a_marca_e_sem_delta(self, zero):
        """GET /me/simulados: a nota fica (é o histórico), com a marca, sem
        delta — e fora da base do delta das provas seguintes."""
        lista = {s["id"]: s for s in aluno_dados.simulados_do_aluno(zero, ANA)}
        z = lista["s-zero"]
        assert (z["nota"], z["computavel"], z["motivoNaoComputavel"], z["deltaSelf"]) == (
            0.0, False, computavel.TODAS_EM_BRANCO, None,
        )
        assert z["notaConfiavel"] is True and aluno_dados.conta_como_desempenho(z) is False
        esperado = round(6.0 - statistics.mean([7.0, 5.5, 6.0, 3.8]), 2)
        assert lista["s-depois"]["deltaSelf"] == esperado, "o zero entrou na base do delta"

    def test_o_panorama_tira_o_zero_das_ultimas_notas_e_diz_por_que(self, zero):
        r = chamar(zero, "meu_panorama", ultimas_notas=10)
        assert "s-zero" not in {n["id"] for n in r["ultimasNotas"]}
        assert "s-depois" in {n["id"] for n in r["ultimasNotas"]}
        (fora,) = r["naoContam"]
        assert fora["id"] == "s-zero" and "provável ausência" in fora["porQueNaoConta"]
        assert tools_aluno_situacao.NAO_CONTAM in r["observacoes"]

    def test_minhas_notas_tira_o_zero_e_diz_por_que(self, zero):
        r = chamar(zero, "minhas_notas")
        assert "s-zero" not in {s["id"] for s in r["simulados"]}
        assert [p["id"] for p in r["naoContam"]] == ["s-zero"]
        assert r["observacao"] == tools_aluno_situacao.NAO_CONTAM
        assert r["total"] == len(r["simulados"])
        # As marcas já fizeram o trabalho: não ocupam o contexto do modelo.
        assert not {"computavel", "notaConfiavel", "anoLetivoId"} & set(r["simulados"][0])

    def test_nenhuma_tool_entrega_o_zero_como_nota(self, zero):
        for nome, args in CHAMADAS.items():
            for item in _itens_da_prova(chamar(zero, nome, **args), "s-zero"):
                assert not {"nota", "minhaNota", "deltaSelf"} & set(item), f"{nome}: {item}"

    def test_o_insight_nao_le_o_zero(self, zero):
        _, payload = aluno_dados.payload_insight_ciclo(zero, ANA)
        quimica = next(p for p in payload["porMateria"] if p["materia"] == "Química")
        assert quimica["minhaNota"] == 3.8, "o zero de provável ausência entrou na média do ciclo"

    @pytest.mark.parametrize(
        "motivo,confiavel,trecho",
        [
            (computavel.TODAS_EM_BRANCO, True, "nenhuma alternativa"),
            (computavel.ZERO_POR_FALTA_LANCADA, True, "é falta"),
            ("motivo_que_ainda_nao_existe", True, "não é desempenho"),
            (None, False, "não confiável"),
        ],
    )
    def test_cada_motivo_em_palavras(self, motivo, confiavel, trecho):
        cliente = Cliente(_com_prova_que_nao_conta(
            {**banco_do_aluno(), **banco_de_questoes()}, motivo=motivo, confiavel=confiavel,
        ))
        (fora,) = chamar(cliente, "minhas_notas")["naoContam"]
        assert fora["id"] == "s-zero" and trecho in fora["porQueNaoConta"]


# ─── 5d · A régua que não cobra média ────────────────────────────────────
#
# repro_ime_sem_distancia.py: aluno só-IME com nota de Fase 2 cai na régua
# ime-f2, que só tem mínimo por matéria. Em zona cinzenta, distancia,
# corteProximaZona e materiaMaisCurta vinham os três null e nada explicava.


@pytest.fixture
def so_ime() -> Cliente:
    db = {**banco_do_aluno(), **banco_de_questoes()}
    db["vestibular_alvo_aluno"] = {"va": {"id": "va", "aluno_id": ANA, "vestibular": "IME"}}
    db["nota"][f"n-{ANA}-s-qui"]["pontuacao"] = 4.5
    return Cliente(db)


class TestReguaSemMedia:
    def test_minha_zona_diz_que_nao_ha_distancia(self, so_ime):
        r = chamar(so_ime, "minha_zona")
        assert (r["regua"], r["zona"], r["reguaCobraMedia"]) == ("IME — Fase 2", "cinzenta", False)
        assert (r["distancia"], r["corteProximaZona"], r["materiaMaisCurta"]) == (None, None, None)
        assert r["materiaComMenosFolga"] == {"materia": "Química", "folga": 0.5}
        (frase,) = [o for o in r["observacoes"] if "não cobra média" in o]
        assert "não invente" in frase and "1,0 acima do corte" in frase
        assert "Química, 0,50 acima do corte" in frase

    def test_o_panorama_explica_o_mesmo(self, so_ime):
        r = chamar(so_ime, "meu_panorama")
        assert any("não cobra média" in o for o in r["observacoes"])

    def test_a_regua_que_cobra_media_nao_ganha_a_frase(self, cliente):
        r = chamar(cliente, "minha_zona")
        assert r["reguaCobraMedia"] is True
        assert not any("não cobra média" in o for o in r.get("observacoes", []))

    def test_as_descricoes_cobrem_o_caso(self):
        for nome in ("meu_panorama", "minha_zona"):
            descricao = next(f.descricao for f in REGISTRO.catalogo("aluno") if f.nome == nome)
            assert "reguaCobraMedia" in descricao and "materiaComMenosFolga" in descricao, nome

    def test_os_roteiros_que_pedem_a_zona_cobrem_o_caso(self):
        """O roteiro que manda dizer "a distância que a tool trouxe" diz também
        o que fazer quando ela não existe; senão desmente a observação da tool."""
        com_zona = [r for r in roteiros.listar("aluno") if "`minha_zona`" in r.texto]
        assert {r.nome for r in com_zona} >= {"antes_da_prova", "revisar_simulado"}
        for roteiro in com_zona:
            assert "reguaCobraMedia=false" in roteiro.texto, roteiro.nome
            assert "não há distância" in roteiro.texto, roteiro.nome

    def test_a_margem_e_a_do_dominio(self, so_ime, monkeypatch):
        """O número da frase sai de `criterios.MARGEM_CONFORTAVEL`, não de cópia."""
        monkeypatch.setattr(tools_aluno_situacao.criterios, "MARGEM_CONFORTAVEL", 1.5)
        r = chamar(so_ime, "minha_zona")
        assert any("1,5 acima do corte" in o for o in r["observacoes"])


# ─── 5e · O ano letivo ───────────────────────────────────────────────────
#
# O recorde de `meu_streak` e do preâmbulo é "do ano" (docs/36 §1.3), e corria
# o histórico inteiro; o insight escolhia o ciclo pela maior ORDEM de todos os
# anos, e a ordem 3 de 2025 caía junto com a 3 de 2026.


@pytest.fixture
def dois_anos() -> Cliente:
    db = {**banco_do_aluno(), **banco_de_questoes()}
    db["ciclo"]["c-25"] = CICLOS["c-25"]
    for i, data in enumerate(("2025-08-01", "2025-09-01", "2025-10-01")):
        sim = _simulado(f"s-25-{i}", f"P{i} 2025", data, "fase_2", "m-qui", "c-25")
        db["simulado"][sim["id"]] = sim
        db["nota"][f"n-ana-25-{i}"] = {
            "id": f"n-ana-25-{i}", "aluno_id": ANA, "simulado_id": sim["id"], "pontuacao": 9.0,
            "presente": True, "computavel": True, "simulado": sim,
        }
    return Cliente(db)


class TestAnoLetivo:
    def test_o_recorde_e_do_ano_letivo(self, dois_anos):
        """Três presenças de 2025 emendadas nas duas primeiras de 2026 davam um
        recorde de cinco que o Tio Léo chamava de "recorde do ano"."""
        r = chamar(dois_anos, "meu_streak")
        assert (r["simulados"], r["melhor"]) == (2, 2)
        assert aluno_jornada.sequencia_do_aluno(dois_anos, ANA)["melhor"] == 2

    def test_lista_sem_o_ano_conta_tudo(self):
        """Sem `anoLetivoId` não há como saber o ano, e cortar seria inventar."""
        itens = [{"presente": True, "dataAplicacao": f"2026-0{m}-01"} for m in range(1, 4)]
        assert aluno_jornada.contar_sequencia(itens) == (3, 3)

    def test_o_insight_e_do_ciclo_deste_ano(self, dois_anos):
        ciclo, payload = aluno_dados.payload_insight_ciclo(dois_anos, ANA)
        assert ciclo["id"] == "c-3"
        quimica = next(p for p in payload["porMateria"] if p["materia"] == "Química")
        assert quimica["minhaNota"] == 3.8, "o 9,0 de 2025 entrou no ciclo 3 de 2026"


# ─── 5f · O cache do insight e o prompt ──────────────────────────────────
#
# repro_insight_cache.py: a chave era hash({stats, ctx}), sem o prompt. Os
# bullets do prompt antigo — corte 5,0 cravado, "streak" de ciclos acima da
# média — saíam do cache enquanto os números do ciclo não mudassem.


@pytest.fixture
def modelo_de_mentira(monkeypatch) -> list[dict]:
    """O insight de verdade, com o modelo trocado por um dublê que conta as
    chamadas. Nada chama a OpenAI."""
    chamadas: list[dict] = []
    monkeypatch.setattr(tools_aluno, "gerar_para_aluno_ciclo", insight_aluno.gerar_para_aluno_ciclo)
    monkeypatch.setattr(insight_aluno, "_disponivel", lambda chave: True)

    def chamar_llm(**argumentos):
        chamadas.append(argumentos)
        return ["bullet do prompt novo"]

    monkeypatch.setattr(insight_aluno, "_chamar_llm", chamar_llm)
    return chamadas


class TestCacheDoInsight:
    def test_os_bullets_do_prompt_antigo_nao_saem_mais(self, cliente, modelo_de_mentira):
        ciclo, payload = aluno_dados.payload_insight_ciclo(cliente, ANA)
        chave_antiga = hash_payload_estavel({"stats": payload, "ctx": {"nomeAluno": "Ana Aluna"}})
        cliente.db["insight_aluno_ciclo"] = {
            "velho": {
                "id": "velho", "aluno_id": ANA, "ciclo_id": ciclo["id"], "hash_payload": chave_antiga,
                "bullets": ["Sua streak: 3 ciclos acima da média da turma!",
                            "Inglês está 0,8 abaixo do corte eliminatório de 5,0 — priorize."],
                "modelo": "gpt-4o-mini",
            },
        }
        assert chamar(cliente, "meu_insight_do_ciclo")["bullets"] == ["bullet do prompt novo"]
        assert len(modelo_de_mentira) == 1
        # O que acabou de ser gerado sai do cache na segunda vez, sem modelo.
        assert chamar(cliente, "meu_insight_do_ciclo")["bullets"] == ["bullet do prompt novo"]
        assert len(modelo_de_mentira) == 1

    def test_mexer_no_prompt_muda_a_chave(self, monkeypatch):
        antes = insight_aluno._chave_do_cache({"x": 1}, {"nomeAluno": "Ana"})
        monkeypatch.setattr(insight_aluno, "PROMPT_ALUNO", insight_aluno.PROMPT_ALUNO + " ")
        assert insight_aluno._chave_do_cache({"x": 1}, {"nomeAluno": "Ana"}) != antes

    def test_o_prompt_diz_o_que_o_null_da_turma_quer_dizer(self):
        assert "`mediaTurma` null" in insight_aluno.PROMPT_ALUNO


# ─── 5g · Tool só lê — em qualquer nível ─────────────────────────────────


class TestSoLeitura:
    def test_a_unica_escrita_e_o_cache_do_insight(self, cliente, modelo_de_mentira):
        """O grep de `test_nenhum_modulo_das_tools_escreve_no_banco` só vê o
        módulo da tool. Aqui conta o que chega ao cliente: a única escrita que
        uma tool do aluno faz é o cache do insight (`insight_aluno._salvar_cache`),
        a exceção documentada em ferramentas.py."""
        for nome, args in CHAMADAS.items():
            chamar(cliente, nome, **args)
        assert set(cliente.escritas) == {("insight_aluno_ciclo", "upsert")}


# ─── 5h · O preâmbulo de verdade ─────────────────────────────────────────
#
# medir_custo.py: com cache frio, o preâmbulo fazia 19 idas ao PostgREST antes
# do SSE começar — o histórico lido duas vezes, os alvos lidos duas vezes.

#: 15h de sábado, 24/10, em Fortaleza.
AGORA = datetime(2026, 10, 24, 18, 0, tzinfo=UTC)


@pytest.fixture
def cache_limpo():
    contexto_do_turno.limpar_cache()
    yield
    contexto_do_turno.limpar_cache()


class TestPreambuloDeVerdade:
    def test_quatorze_idas_frio_e_nenhuma_quente(self, cliente, cache_limpo):
        texto = contexto_do_turno.preambulo_do_aluno(cliente, SESSAO, agora=AGORA)
        assert len(cliente.idas) <= 14, Counter(cliente.idas)
        assert cliente.idas.count("nota") == 3, "as duas da zona e UMA do histórico"
        assert cliente.idas.count("vestibular_alvo_aluno") == 1, "os alvos vêm da zona"
        cliente.idas.clear()
        assert contexto_do_turno.preambulo_do_aluno(cliente, SESSAO, agora=AGORA) == texto
        assert cliente.idas == []

    def test_diz_o_mesmo_que_as_tools(self, cliente, cache_limpo):
        texto = contexto_do_turno.preambulo_do_aluno(cliente, SESSAO, agora=AGORA)
        zona = chamar(cliente, "minha_zona")
        streak = chamar(cliente, "meu_streak")
        assert f"Régua em vigor: {zona['regua']}. Zona: {zona['zona']}" in texto
        assert "Vestibulares-alvo que declarou: ITA." in texto
        assert "Próximo simulado: ITA P3 (ITA, Fase 1), em 30/10/2026 — daqui a 6 dias." in texto
        assert (
            f"Sequência: {streak['simulados']} simulados seguidos sem faltar; "
            f"recorde do ano: {streak['melhor']}."
        ) in texto

    def test_o_recorde_do_preambulo_e_do_ano(self, dois_anos, cache_limpo):
        texto = contexto_do_turno.preambulo_do_aluno(dois_anos, SESSAO, agora=AGORA)
        assert "recorde do ano: 2." in texto


# ─── 5i · O portão do onboarding, num lugar só ───────────────────────────


class TestOnboarding:
    def test_a_rota_e_a_tool_usam_a_mesma_funcao(self):
        """`bool(alvos)` em duas cópias divergiria no primeiro portão novo."""
        assert "onboarding_completo(" in inspect.getsource(tools_aluno_situacao.minha_zona)
        assert "onboarding_completo(" in inspect.getsource(rotas_me.me_vestibulares)
        assert "onboarding_completo(" in inspect.getsource(rotas_me.me_definir_vestibulares)

    @pytest.mark.parametrize("alvos", [[], ["ITA"], ["IME", "ITA"]])
    def test_a_rota_e_a_tool_concordam(self, cliente, monkeypatch, alvos):
        cliente.db["vestibular_alvo_aluno"] = {
            f"va-{v}": {"id": f"va-{v}", "aluno_id": ANA, "vestibular": v} for v in alvos
        }
        monkeypatch.setattr(rotas_me, "get_supabase", lambda: cliente)
        rota = asyncio.run(rotas_me.me_vestibulares({"aluno_id": ANA}))
        assert rota["completo"] is chamar(cliente, "minha_zona")["onboardingCompleto"] is bool(alvos)


# ─── 6 · Hoje é o dia da escola ──────────────────────────────────────────


class TestHoje:
    def test_a_agenda_usa_o_dia_da_escola(self, monkeypatch):
        cliente = Cliente(banco_do_aluno())
        # 01h30 em UTC do dia 31 ainda é 22h30 do dia 30 em Fortaleza: a prova
        # do dia 30 continua na agenda — com `date.today()` em UTC, sumia.
        agora = datetime(2026, 10, 31, 1, 30, tzinfo=UTC)
        monkeypatch.setattr(
            aluno_jornada, "hoje_na_escola", lambda: banco_missao.hoje_na_escola(agora)
        )
        proximo = aluno_jornada.proximo_simulado_do_aluno(cliente, ANA)
        assert proximo is not None and proximo["data"] == "2026-10-30"

        monkeypatch.setattr(aluno_jornada, "hoje_na_escola", lambda: date(2026, 10, 31))
        assert aluno_jornada.proximo_simulado_do_aluno(cliente, ANA) is None

    def test_o_modulo_nao_usa_mais_date_today(self):
        """No código, e não no comentário que conta por que saiu."""
        arvore = ast.parse(inspect.getsource(aluno_jornada))
        chamadas = [
            no for no in ast.walk(arvore)
            if isinstance(no, ast.Attribute) and no.attr == "today"
        ]
        assert not chamadas

    def test_dias_ate_o_proximo(self, cliente):
        agenda = chamar(cliente, "minha_agenda_do_ciclo")
        assert agenda["hoje"] == "2026-10-24"
        assert (agenda["proximoSimulado"]["data"], agenda["diasAteOProximo"]) == ("2026-10-30", 6)
        assert agenda["metaDoCiclo"] == {
            "alvo": 5, "feitos": 3, "rotulo": "Comparecer aos 5 simulados do ciclo",
        }
        assert aluno_jornada.dias_ate(None, HOJE) is None


# ─── 7 · O panorama só compõe ────────────────────────────────────────────


class TestPanorama:
    def test_cada_pedaco_e_o_da_rota_de_origem(self, cliente):
        """Sem segunda regra: o panorama devolve exatamente o que cada função de
        domínio devolveria sozinha — as mesmas de /me/zona, /me/jogo, /me/meta,
        /me/agenda e /me/simulados."""
        p = aluno_panorama.panorama_do_aluno(cliente, ANA, ultimas_notas=3, hoje=HOJE)
        assert p["zona"] == aluno_zona.zona_do_aluno(cliente, ANA)
        assert p["sequencia"] == aluno_jornada.sequencia_do_aluno(cliente, ANA)
        assert p["metaDoCiclo"] == aluno_jornada.meta_do_ciclo_do_aluno(cliente, ANA)
        assert p["proximoSimulado"] == aluno_jornada.proximo_simulado_do_aluno(cliente, ANA)
        assert p["vestibularesAlvo"] == aluno_zona.vestibulares_alvo(cliente, ANA)
        recentes = aluno_dados.simulados_do_aluno(cliente, ANA)[:3]
        assert [n["id"] for n in p["ultimasNotas"]] == [s["id"] for s in recentes]
        assert [n["nota"] for n in p["ultimasNotas"]] == [s["nota"] for s in recentes]

    def test_a_sequencia_continua_a_de_sempre(self, cliente):
        s = aluno_jornada.sequencia_do_aluno(cliente, ANA)
        assert (s["simulados"], s["melhor"]) == (2, 2)
        assert [e["presente"] for e in s["corrente"]] == [True, False, True, True, None]

    def test_custa_menos_da_metade_das_idas(self, cliente):
        """Medido no FakeCliente, contando `execute`. Somadas uma a uma, as seis
        funções relêem as notas e o histórico a cada passo."""
        cliente.idas.clear()
        aluno_panorama.panorama_do_aluno(cliente, ANA, hoje=HOJE)
        do_panorama = len(cliente.idas)

        cliente.idas.clear()
        aluno_dados.simulados_do_aluno(cliente, ANA)
        aluno_zona.zona_do_aluno(cliente, ANA)
        aluno_jornada.sequencia_do_aluno(cliente, ANA)
        aluno_jornada.proximo_simulado_do_aluno(cliente, ANA)
        aluno_jornada.meta_do_ciclo_do_aluno(cliente, ANA)
        aluno_zona.vestibulares_alvo(cliente, ANA)
        uma_a_uma = len(cliente.idas)

        assert do_panorama <= 15, cliente.idas
        assert do_panorama * 2 <= uma_a_uma
        # As notas do aluno: uma leitura para a jornada e as duas da zona.
        cliente.idas.clear()
        aluno_panorama.panorama_do_aluno(cliente, ANA, hoje=HOJE)
        assert cliente.idas.count("nota") == 3

    def test_o_panorama_explica_a_zona_e_anexa_as_barras(self, cliente):
        r = chamar(cliente, "meu_panorama")
        assert r["hoje"] == "2026-10-24" and r["diasAteOProximo"] == 6
        assert r["zona"]["reguaDoColegio"] is False
        assert r["artefato"]["tipo"] == "barras_corte"
        assert "observacoes" not in r

    def test_sem_vestibular_vale_a_regua_do_colegio(self, cliente):
        cliente.db["vestibular_alvo_aluno"] = {}
        r = chamar(cliente, "minha_zona")
        assert r["reguaDoColegio"] is True and r["onboardingCompleto"] is False
        assert r["regua"] == "Tio Leo" and r["reguaSlug"] == "tio-leo"
        assert any("régua do colégio" in o for o in r["observacoes"])
        assert r["artefato"]["payload"]["regua"] == "Tio Leo"

    def test_ultimas_notas_fica_entre_1_e_10(self, cliente):
        assert len(chamar(cliente, "meu_panorama", ultimas_notas=0)["ultimasNotas"]) == 1
        assert len(chamar(cliente, "meu_panorama", ultimas_notas=99)["ultimasNotas"]) == 4


# ─── O banco de questões ─────────────────────────────────────────────────


class TestQuestoesDoBanco:
    def test_assunto_sem_acento_acha_o_topico(self, cliente):
        r = chamar(cliente, "questoes_do_banco", materia="Física", assunto="termodinamica")
        assert r["topico"] == {"codigo": "9.1", "nome": "Termodinâmica"}
        assert r["total"] == 12 and len(r["questoes"]) == 5
        assert r["artefato"]["payload"]["itens"] == [
            {"assunto": "Termodinâmica", "materia": "Física", "topicoCodigo": "9.1", "quantidade": 12}
        ]

    def test_assunto_do_edital_dentro_do_topico(self, cliente):
        assert chamar(cliente, "questoes_do_banco", materia="Física", assunto="doppler")["topico"][
            "codigo"
        ] == "7.2"

    def test_assunto_ambiguo_devolve_candidatos(self, cliente):
        r = chamar(cliente, "questoes_do_banco", materia="Física", assunto="óptica")
        assert "erro" in r
        assert {c["codigo"] for c in r["candidatos"]} == {"8.1", "8.2"}

    def test_a_questao_resumida_nao_traz_gabarito(self, cliente):
        r = chamar(cliente, "questoes_do_banco", materia="Física", topico_codigo="9.1", quantidade=10)
        for q in r["questoes"]:
            assert "gabarito" not in q and "anotacao" not in q
            assert len(q["enunciadoResumo"]) <= 200
        longa = next(q for q in r["questoes"] if q["id"] == "ita_2021_fase1_q05")
        assert longa["enunciadoResumo"].startswith("[figura]") and longa["enunciadoResumo"].endswith("…")

    def test_com_recorte_o_cartao_nao_conta(self, cliente):
        r = chamar(cliente, "questoes_do_banco", materia="Física", topico_codigo="9.1", vestibular="ITA")
        assert "quantidade" not in r["artefato"]["payload"]["itens"][0]

    def test_uma_so_vira_o_cartao_da_questao(self, cliente):
        r = chamar(cliente, "questoes_do_banco", materia="Física", topico_codigo="9.1", quantidade=1)
        assert r["artefato"]["tipo"] == "questao"
        assert r["artefato"]["payload"] == {"id": r["questoes"][0]["id"]}


class TestResolucaoOficial:
    def test_do_professor_nao_vai_texto(self, cliente):
        r = chamar(cliente, "resolucao_oficial", questao_id="ita_2019_fase1_q01")
        assert r["resolucao"]["doProfessor"] is True and r["resolucao"]["textoSugerido"] is None
        assert "professor do Ari" in r["resolucao"]["aviso"]
        assert r["artefato"] == {"tipo": "questao", "titulo": "Questão 1",
                                 "payload": {"id": "ita_2019_fase1_q01"}}

    def test_gerada_por_ia_vai_com_o_aviso(self, cliente):
        r = chamar(cliente, "resolucao_oficial", questao_id="ita_2019_fase1_q02")["resolucao"]
        assert (r["origem"], r["doProfessor"]) == ("sugerida", False)
        assert r["textoSugerido"].startswith("Pela primeira lei")
        assert "gerada por IA" in r["aviso"] and "conferir" in r["aviso"]

    def test_sem_origem_e_sem_resolucao(self, cliente):
        sem_origem = chamar(cliente, "resolucao_oficial", questao_id="ita_2020_fase1_q03")["resolucao"]
        assert sem_origem["origem"] is None and "não tem origem registrada" in sem_origem["aviso"]
        nenhuma = chamar(cliente, "resolucao_oficial", questao_id="ita_2020_fase1_q04")["resolucao"]
        assert nenhuma["noCartao"] is False and "pode ter erro" in nenhuma["aviso"]

    def test_pelo_endereco_da_prova(self, cliente):
        r = chamar(cliente, "resolucao_oficial", vestibular="ITA", ano=2019, fase=1, numero=2)
        assert r["id"] == "ita_2019_fase1_q02"

    def test_endereco_que_so_a_materia_desempata(self, cliente):
        ambigua = chamar(cliente, "resolucao_oficial", vestibular="ITA", ano=2017, fase=2, numero=1)
        assert {c["materia"] for c in ambigua["candidatos"]} == {"Física", "Química"}
        quimica = chamar(cliente, "resolucao_oficial", vestibular="ITA", ano=2017, fase=2,
                         numero=1, materia="Química")
        assert quimica["id"] == "ita_2017_fase2_qui_q01"

    def test_endereco_incompleto_diz_o_que_falta(self, cliente):
        r = chamar(cliente, "resolucao_oficial", vestibular="ITA", ano=2019)
        assert "fase" in r["erro"] and "numero" in r["erro"]

    def test_a_figura_que_o_modelo_nao_ve(self, cliente):
        r = chamar(cliente, "resolucao_oficial", questao_id="ita_2021_fase1_q05")
        assert r["dependeDeFigura"] is True and r["enunciadoMd"].startswith("[figura]")


class TestOQueMaisCaiMissaoEProgresso:
    def test_o_que_mais_cai_ordena_pelo_indice(self, cliente):
        r = chamar(cliente, "o_que_mais_cai", materia="Física")
        importancias = [t["importancia"] for t in r["topicos"]]
        assert importancias == sorted(importancias, reverse=True)
        assert r["topicos"][0]["codigo"] == "9.1"
        assert all(t["total"] > 0 for t in r["topicos"])
        assert r["artefato"]["payload"]["itens"][0]["quantidade"] == 12

    def test_o_que_mais_cai_junta_as_tres_materias(self, cliente):
        r = chamar(cliente, "o_que_mais_cai")
        assert [m["materia"] for m in r["porMateria"]] == ["Física", "Química", "Matemática"]

    def test_a_missao_e_a_mesma_para_todos(self, cliente):
        ana = chamar(cliente, "missao_de_hoje")
        assert ana["hoje"] == "2026-10-24"
        assert (ana["missao"]["materia"], ana["missao"]["topicoCodigo"]) == ("Física", "9.1")
        assert ana["artefato"]["payload"]["itens"] == [
            {"assunto": "Termodinâmica", "materia": "Física", "topicoCodigo": "9.1", "quantidade": 10}
        ]
        bia = REGISTRO.despachar(
            Sessao(tipo="aluno", usuario=f"aluno:{BIA}", aluno_id=BIA), "missao_de_hoje", cliente, {}
        )
        assert bia["missao"] == ana["missao"]

    def test_o_progresso_conta_o_que_o_aluno_marcou(self, cliente):
        r = chamar(cliente, "meu_progresso_no_banco", materia="Física", por_ano=True)
        # Os totais são do acervo inteiro; a matéria recorta os assuntos.
        assert (r["feitas"], r["total"]) == (2, 19)
        fisica = next(m for m in r["porMateria"] if m["materia"] == "Física")
        assert (fisica["feitas"], fisica["total"]) == (2, 16)
        codigos = [a["codigo"] for a in r["porAssunto"]]
        assert codigos[-1] == "sem-assunto"  # a das não classificadas vai sempre
        assert {a["materia"] for a in r["porAssunto"]} == {"Física"}
        assert r["porAno"] and {a["materia"] for a in r["porAno"]} == {"Física"}
        item = r["artefato"]["payload"]["itens"][0]
        assert (item["topicoCodigo"], item["quantidade"]) == ("9.1", 10)


# ─── 8 · O prompt e o insight ────────────────────────────────────────────


class TestPrompt:
    def test_a_resolucao_oficial_com_a_dureza_de_nunca_invente_notas(self):
        regra = next(
            linha for linha in SYSTEM_PROMPT_ALUNO.splitlines() if "`resolucao_oficial`" in linha
        )
        assert "nunca invente notas" in regra
        for trecho in ("professor do Ari", "gerada por IA", "nunca derive", "pode ter erro"):
            assert trecho in regra

    def test_as_regras_novas(self):
        for trecho in (
            "`meu_panorama` primeiro",
            "`o_que_mais_cai`",
            "`roteiro_do_mentor`",
            "logo abaixo",
            "não o redesenhe",
            "anexado: true",
            "NÃO existem",
            "Contexto do aluno",
            "não instrução",
            "A data dele é a de hoje",
        ):
            assert trecho in SYSTEM_PROMPT_ALUNO, trecho
        for inexistente in ("XP", "liga", "conquistas", "extrato"):
            assert inexistente in SYSTEM_PROMPT_ALUNO

    def test_as_regras_de_antes_continuam(self):
        for trecho in (
            "Nunca invente notas",
            "Comparações só com agregados",
            "`minhas_questoes_erradas`",
            "Matéria eliminatória reprova sozinha",
            "não decore número",
            "simulados SEGUIDOS",
        ):
            assert trecho in SYSTEM_PROMPT_ALUNO, trecho

    def test_nenhum_corte_de_memoria(self):
        assert not re.search(r"\b[45],0\b", SYSTEM_PROMPT_ALUNO)

    def test_toda_tool_citada_existe_no_escopo_do_aluno(self):
        citadas = set(re.findall(r"`([a-z][a-z0-9_]*)`", SYSTEM_PROMPT_ALUNO))
        do_aluno = {f.nome for f in REGISTRO.catalogo("aluno")}
        # Entre crases sem ser tool: campos de resultado e o exemplo de id.
        assert citadas - {"artefato", "anexado", "id", "ita_2019_fase1_q12"} <= do_aluno
        assert "roteiro_do_mentor" in {s["name"] for s, _ in roteiros.TOOLS_ALUNO}


class TestInsight:
    def test_o_prompt_do_insight_nao_crava_corte(self):
        assert not re.search(r"\b[45],0\b", insight_aluno.PROMPT_ALUNO)
        assert "Não cite número de corte" in insight_aluno.PROMPT_ALUNO

    def test_a_sequencia_e_a_nova(self):
        assert "Streak = ciclos consecutivos" not in insight_aluno.PROMPT_ALUNO
        assert "Sequência = quantos simulados SEGUIDOS" in insight_aluno.PROMPT_ALUNO
        assert "`ciclosAcimaDaMediaDaTurma` NÃO é a sequência" in insight_aluno.PROMPT_ALUNO


def test_o_registro_continua_montando():
    """Os dois módulos irmãos entram pela porta de sempre."""
    assert ferramentas._montar_registro().catalogo("aluno")
