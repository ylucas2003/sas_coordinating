"""Nome de aluno → matrícula no que o MCP devolve (LGPD, docs/43 §5.4).

Os nove casos do protótipo do levantamento de LGPD de 24/10, que rodou as 30
tools da coordenação contra dados sintéticos. Aqui os retornos são LITERAIS,
no formato que cada tool devolve (o mapa cita arquivo e linha de cada um), e
não a tool rodando: a regra é uma função pura, e um teste que dependesse dos
handlers mudaria a cada tool reescrita sem a regra ter mudado.

⚠️ O que estes testes NÃO provam: que uma tool NOVA exposta ao MCP tenha um
formato que a regra entende. Toda tool que entrar no catálogo do MCP precisa
de um caso aqui com o formato real dela, passando pelo portão.

Dados 100% sintéticos.

Rodar:  cd api && APP_ENV=dev ./.venv/bin/python -m pytest tests/test_mcp_pseudonimo.py -q
"""

from __future__ import annotations

import copy
import json
import re

import pytest

from app.mcp.pseudonimo import (
    Cadastro,
    CadastroDeAlunos,
    PseudonimoRecusado,
    pseudonimizar,
    rotulo,
)
from tests.fake_postgrest import FakeCliente

A, B, C, D = (f"a1111111-0000-4000-8000-00000000000{i}" for i in range(1, 5))
NOMES = {A: "ALUNA SINTETICA UM", B: "ALUNO SINTETICO DOIS", C: "ALUNA SINTETICA TRES", D: "ALUNO SINTÉTICO QUATRO"}
MATRICULAS = {A: "9000001", B: "9000002", C: "9000003", D: "9000004"}
C2, S1 = "c2222222-0000-4000-8000-000000000002", "51111111-0000-4000-8000-000000000001"
T_AD = "71111111-0000-4000-8000-000000000001"


def p(resultado, *, mats=None, nomes=None):
    return pseudonimizar(
        resultado,
        matricula_por_id=MATRICULAS if mats is None else mats,
        nomes_de_alunos=NOMES.values() if nomes is None else nomes,
    )


def _classificacao(aid):
    return {"zona": "risco" if aid == D else "top", "perfil": "regular", "tendencia": "estavel", "mediaRecente": 6.1}


# ─── Os retornos, no formato de cada tool ────────────────────────────────


def ret_buscar_aluno_por_nome():   # lookup.py — id + matricula
    return {"total": 2, "alunos": [{"id": a, "nome": NOMES[a], "matricula": MATRICULAS[a], "ativo": True} for a in (A, C)]}


def ret_obter_aluno():   # lookup.py — raiz com id + matricula; turma SEM `nome`
    return {
        "id": A, "nome": NOMES[A], "matricula": MATRICULAS[A], "ativo": True, "vestibularesAlvo": ["ITA"],
        "turma": {"id": T_AD, "serie": 3, "trilha": "ITA", "sectionOriginal": "3o ITA AD", "sede": "Aldeota"},
        "classificacao": {**_classificacao(A), "desvioRecente": 1.0, "coefTendencia": -0.5},
    }


def ret_notas_simulado():   # stats.py — alunoId SEM matrícula no dict
    return {"total": 3, "truncado": False, "notas": [
        {"alunoId": a, "nome": NOMES[a], "pontuacao": 7.0, "presente": True} for a in (A, B, D)
    ]}


def ret_comparar_alunos(ids=(A, B)):   # comparar.py — maior/menor só com {nome, media}
    alunos = [{"alunoId": a, "nome": NOMES[a], **_classificacao(a), "media": 6.0, "porMateria": {"fisica": 6.0}} for a in ids]
    return {
        "alunos": alunos,
        "maioresDiferencas": [{
            "materia": "Física",
            "maior": {"nome": NOMES[ids[1]], "media": 8.0},
            "menor": {"nome": NOMES[ids[0]], "media": 3.0},
            "diferenca": 5.0,
        }],
    }


def ret_alunos_similares():   # comparar.py — alunoId na raiz, sem nome
    return {"alunoId": A, "k": 2, "similares": [
        {"alunoId": a, "nome": NOMES[a], "distancia": 1.2, **_classificacao(a), "media": 6.0} for a in (B, C)
    ]}


def ret_alunos_por_zona(zona):   # heuristicas.py — alunos_em_risco / alunos_destaque
    return {"zona": zona, "total": 1, "truncado": False, "alunos": [{"alunoId": D, "nome": NOMES[D], **_classificacao(D)}]}


def ret_relatorio_aluno():   # relatorios.py — `simulado` é nome de simulado
    return {
        "aluno": {"id": A, "nome": NOMES[A], "matricula": MATRICULAS[A], "ativo": True,
                  "turma": {"serie": 3, "trilha": "ITA", "sede": "Aldeota", "sectionOriginal": "3o ITA AD"}},
        "classificacao": _classificacao(A),
        "ultimasNotas": [{"simulado": "C2_P5 - Matematica - 10/05", "pontuacao": 3.0}],
    }


def ret_historico_aluno():   # relatorios.py — ciclos[].ciclo é {id, nome} de CICLO
    return {
        "aluno": {"id": A, "nome": NOMES[A], "matricula": MATRICULAS[A]},
        "ciclos": [{"ciclo": {"id": C2, "nome": "Ciclo 2 · ITA · 2026"}, "notas": [{"simulado": "C2_P5", "pontuacao": 3.0}]}],
    }


def ret_listar_alunos():   # contexto.py — alunoId + matricula
    return {"total": 4, "alunos": [
        {"alunoId": a, "nome": NOMES[a], "matricula": MATRICULAS[a], **_classificacao(a)} for a in (A, B, C, D)
    ]}


def ret_relatorio_ciclo():   # relatorios.py — alunosRisco SEM identidade nenhuma
    return {
        "ciclo": {"id": C2, "nome": "Ciclo 2 · ITA · 2026"},
        "alunosRisco": [{"nome": NOMES[D], **_classificacao(D)}],
        "alunosDestaque": [{"nome": NOMES[A], **_classificacao(A)}],
        "simuladosMaisDificeis": [{"id": S1, "nome": "C2_P5 - Fisica - 11/05", "media": 3.1}],
    }


def ret_listar_alertas(nome=NOMES[A]):   # contexto.py + stats/alertas.py — nome interpolado no título
    return {"total": 1, "alertas": [{
        "id": "e1", "categoria": "QUEDA_RENDIMENTO", "severidade": "vermelho", "entidade_tipo": "aluno",
        "entidade_id": A, "titulo": f"{nome} caiu 6.0 pontos", "subtitulo": "Média 3.0 vs 9.0",
    }]}


def ret_gerar_grafico_aluno():   # artefato.py — fonte=aluno
    return {"tipo": "linha_temporal", "titulo": f"Evolução — {NOMES[A]}",
            "payload": {"alunoId": A, "alunoNome": NOMES[A], "pontos": [{"x": "C1", "y": 9.0}]}}


def ret_exportar_csv(fonte):   # artefato.py — o nome DENTRO da string do CSV
    linhas = "\n".join(f"{MATRICULAS[a]},{NOMES[a]},7.0" for a in (A, B))
    return {"tipo": "csv", "titulo": f"Exportação {fonte}",
            "payload": {"nomeArquivo": f"{fonte}.csv", "conteudo": f"matricula,nome,pontuacao\n{linhas}\n"}}


def ret_navegar_para_aluno():   # contexto.py + navegacao.py — rótulo É o nome
    return {"tipo": "navegacao", "titulo": NOMES[A], "payload": {"rota": f"/alunos/{A}", "rotulo": NOMES[A]}}


# As dez tools com nome em campo estruturado E identidade no mesmo dict.
COM_IDENTIDADE = {
    "buscar_aluno_por_nome": ret_buscar_aluno_por_nome,
    "obter_aluno": ret_obter_aluno,
    "notas_simulado": ret_notas_simulado,
    "comparar_alunos": ret_comparar_alunos,
    "alunos_similares": ret_alunos_similares,
    "alunos_em_risco": lambda: ret_alunos_por_zona("risco"),
    "alunos_destaque": lambda: ret_alunos_por_zona("top"),
    "relatorio_aluno": ret_relatorio_aluno,
    "historico_aluno": ret_historico_aluno,
    "listar_alunos": ret_listar_alunos,
}

# Tools SEM dado de aluno, com dicts {id, nome} de outra entidade.
SEM_ALUNO = {
    "listar_ciclos": lambda: {"total": 1, "ciclos": [{"id": C2, "nome": "Ciclo 2 · ITA · 2026", "ordem": 2, "ano": 2026}]},
    "listar_simulados": lambda: {"total": 1, "simulados": [{"id": S1, "nome": "C2_P5 - Fisica - 11/05", "cicloId": C2,
                                                             "materia": {"codigo": "fisica", "nome": "Física"}}]},
    "comparar_simulados": lambda: {"simulados": [{"simuladoId": S1, "nome": "C2_P5 - Fisica", "media": 5.0}],
                                   "resumo": {"maiorMedia": {"nome": "C2_P5 - Fisica", "media": 5.0},
                                              "menorMedia": {"nome": "C2_P6 - Matematica", "media": 4.0}}},
    "listar_sedes": lambda: {"sedes": [{"id": "s1", "nome": "Aldeota", "codigo": "AD", "modalidade": "presencial"}]},
    "listar_turmas": lambda: {"turmas": [{"id": T_AD, "nome": "3o ITA AD", "sede": "Aldeota"}]},
    "listar_materias": lambda: {"materias": [{"codigo": "fisica", "nome": "Física"}]},
    "estatisticas_ciclo": lambda: {"ciclo": {"id": C2, "nome": "Ciclo 2 · ITA · 2026"}, "criterio": "Tio Leo",
                                   "estatisticas": {"media": 6.2, "n": 4}},
}


def _folhas(no, caminho="$"):
    if isinstance(no, dict):
        for k, v in no.items():
            yield from _folhas(v, f"{caminho}.{k}")
    elif isinstance(no, list):
        for i, v in enumerate(no):
            yield from _folhas(v, f"{caminho}[{i}]")
    else:
        yield caminho, no


def _tem_nome(resultado) -> bool:
    texto = json.dumps(resultado, ensure_ascii=False).upper()
    return any(n.upper() in texto for n in NOMES.values()) or "SINTETIC" in texto


# ─── Os nove casos do protótipo ──────────────────────────────────────────


@pytest.mark.parametrize("tool", sorted(COM_IDENTIDADE))
def test_1_as_dez_tools_com_identidade_saem_com_rotulo_e_sem_nome(tool):
    saida = p(COM_IDENTIDADE[tool]())
    assert not _tem_nome(saida), tool
    assert re.search(r"Aluno 900000\d", json.dumps(saida, ensure_ascii=False)), tool


def test_2_a_mesma_pessoa_tem_o_mesmo_rotulo_em_toda_tool():
    """O mapa id → matrícula é o que segura isto: notas_simulado e
    comparar_alunos trazem alunoId SEM matrícula no dict."""
    def rotulos(saida, lista):
        return {d["alunoId"]: d["nome"] for d in saida[lista]}

    la = rotulos(p(ret_listar_alunos()), "alunos")
    ns = rotulos(p(ret_notas_simulado()), "notas")
    ca = rotulos(p(ret_comparar_alunos()), "alunos")
    for aid in ca:
        assert la[aid] == ns[aid] == ca[aid] == f"Aluno {MATRICULAS[aid]}"


def test_3_sem_o_mapa_o_dict_sem_matricula_cai_no_hash_do_id():
    saida = p(ret_notas_simulado(), mats={})
    assert re.fullmatch(r"Aluno #[0-9a-f]{10}", saida["notas"][0]["nome"])
    assert saida["notas"][0]["nome"] == rotulo(A, None)
    # Quem traz a matrícula no próprio dict não depende do mapa.
    assert p(ret_listar_alunos(), mats={})["alunos"][0]["nome"] == "Aluno 9000001"


def test_4_idempotente_e_sem_tocar_a_entrada():
    entrada = ret_comparar_alunos((A, B))
    original = copy.deepcopy(entrada)
    uma = p(entrada)
    assert p(uma) == uma
    assert entrada == original


def test_5_homonimos_lado_a_lado_recusam():
    """Dois alunos com o MESMO nome: o `maior`/`menor` só tem {nome, media}, e
    não há como saber de qual dos dois é."""
    nomes = {**NOMES, C: NOMES[A]}
    resultado = {
        "alunos": [{"alunoId": a, "nome": nomes[a], "media": 6.0} for a in (A, C)],
        "maioresDiferencas": [{"materia": "Física", "maior": {"nome": nomes[C], "media": 8.0},
                               "menor": {"nome": nomes[A], "media": 3.0}}],
    }
    with pytest.raises(PseudonimoRecusado) as erro:
        p(resultado, nomes=nomes.values())
    # O motivo vai para o log: diz ONDE, nunca o nome nem a matrícula.
    assert "SINTETICA" not in str(erro.value) and "9000" not in str(erro.value)


def test_6_relatorio_ciclo_recusa_nome_sem_identidade():
    with pytest.raises(PseudonimoRecusado, match="alunosRisco"):
        p(ret_relatorio_ciclo())


@pytest.mark.parametrize(
    "retorno",
    [
        ret_listar_alertas,
        ret_gerar_grafico_aluno,
        lambda: ret_exportar_csv("notas_simulado"),
        lambda: ret_exportar_csv("alunos_por_zona"),
        ret_navegar_para_aluno,
    ],
    ids=["listar_alertas", "gerar_grafico_aluno", "csv_notas_simulado", "csv_alunos_por_zona", "navegar_para_aluno"],
)
def test_7_nome_em_texto_livre_recusa_no_portao(retorno):
    with pytest.raises(PseudonimoRecusado, match="texto com nome de aluno"):
        p(retorno())


def test_8_nas_que_passam_nada_que_nao_seja_nome_de_aluno_muda():
    nomes = {n.upper() for n in NOMES.values()}
    for tool, fazer in {**COM_IDENTIDADE, **SEM_ALUNO}.items():
        antes = dict(_folhas(fazer()))
        depois = dict(_folhas(p(fazer())))
        assert antes.keys() == depois.keys(), tool
        mudou = {c for c in antes if antes[c] != depois[c]}
        assert all(isinstance(antes[c], str) and antes[c].upper() in nomes for c in mudou), (tool, mudou)
        if tool in SEM_ALUNO:
            assert not mudou, tool


def test_9_o_limite_documentado_nome_corrigido_depois_do_alerta_passa():
    """Por que `listar_alertas` fica FORA do MCP em vez de "protegida pelo
    portão": o título foi gravado com o nome de antes, e o portão só conhece o
    nome de agora. Se este teste quebrar porque a regra passou a pegar o caso,
    ótimo — mas aí revise a decisão no mapa de LGPD, não só o teste."""
    nome_antigo = NOMES[A]
    nomes_atuais = {**NOMES, A: "ALUNA SINTETICA DA SILVA UM"}.values()
    saida = p(ret_listar_alertas(nome_antigo), nomes=nomes_atuais)
    assert nome_antigo in saida["alertas"][0]["titulo"]


# ─── Além do protótipo ───────────────────────────────────────────────────


def test_nome_em_chave_de_dict_tambem_recusa():
    """O protótipo só olhava VALOR: `{"porAluno": {"<nome>": 7.5}}` passava."""
    with pytest.raises(PseudonimoRecusado):
        p({"porAluno": {NOMES[B]: 7.5}})


def test_o_portao_ignora_acento_caixa_e_espaco():
    with pytest.raises(PseudonimoRecusado):
        p({"titulo": "aluno   sintetico quatro subiu"})   # o cadastro tem "SINTÉTICO"


def test_nome_de_uma_palavra_so_nao_dispara_o_portao():
    """Um nome de uma palavra casaria com texto comum ("Física")."""
    assert p({"texto": "Física foi bem"}, nomes=["Física"]) == {"texto": "Física foi bem"}


def test_matricula_inteira_tambem_marca_dict_de_aluno():
    saida = p({"alunos": [{"matricula": 9000001, "nome": NOMES[A]}]})
    assert saida["alunos"][0]["nome"] == "Aluno 9000001"


def test_erro_de_dominio_passa_pela_regra_igual():
    assert p({"erro": "aluno não encontrado"}) == {"erro": "aluno não encontrado"}
    with pytest.raises(PseudonimoRecusado):
        p({"erro": f"{NOMES[A]} não tem nota neste ciclo"})


def test_rotulo_sem_nada_recusa():
    with pytest.raises(PseudonimoRecusado):
        rotulo(None, None)


# ─── A forma em que o resultado sai (revisão de 24/10) ───────────────────


class _Objeto:
    def __init__(self, nome):
        self.nome = nome

    def __repr__(self):
        return f"_Objeto(nome={self.nome!r})"


@pytest.mark.parametrize(
    "resultado",
    [
        {"pares": [(NOMES[A], 7.5)]},
        {"t": (NOMES[A],)},
        {"s": {NOMES[A]}},
        {"b": NOMES[A].encode()},
        {"objeto": _Objeto(NOMES[A])},
        {"fs": frozenset({NOMES[B]})},
    ],
    ids=["lista_de_tuplas", "tupla", "set", "bytes", "objeto", "frozenset"],
)
def test_nome_fora_de_dict_e_list_tambem_recusa(resultado):
    """O portão só descia em dict e list e só conferia str; o serializador
    (`default=str`) escreve o resto — e o nome saía sem recusa."""
    with pytest.raises(PseudonimoRecusado, match="texto com nome de aluno"):
        p(resultado)


def test_dict_de_aluno_dentro_de_tupla_e_rotulado():
    saida = p({"alunos": ({"alunoId": A, "nome": NOMES[A]}, {"alunoId": B, "nome": NOMES[B]})})
    assert saida == {"alunos": [{"alunoId": A, "nome": "Aluno 9000001"}, {"alunoId": B, "nome": "Aluno 9000002"}]}


def test_a_saida_e_o_que_o_serializador_escreveria():
    """O portão confere a forma do `serializar_para_modelo`, e é ela que sai:
    sem nome de aluno, a cópia serializa IGUAL ao original."""
    import datetime
    import decimal
    import uuid

    from app.chat.ferramentas import serializar_para_modelo

    resultado = {
        "ciclo": ("C2", 2026), "quando": datetime.date(2026, 10, 24), "media": decimal.Decimal("6.25"),
        "id": uuid.UUID(C2), "faixas": [(1, 2), (3, 4)], "contagens": {1: 3, 2: 5}, "vazio": set(),
    }
    saida = p(resultado)
    assert serializar_para_modelo(saida) == serializar_para_modelo(resultado)
    assert saida["ciclo"] == ["C2", 2026] and saida["quando"] == "2026-10-24"


def test_resultado_que_nao_vira_json_sobe_em_vez_de_passar():
    """Chave tupla: o json não a escreve, e o que não se serializa não se
    confere. Quem chama (servidor._despachar) transforma em falha."""
    with pytest.raises(TypeError):
        p({(NOMES[A], 1): 7.5})


@pytest.mark.parametrize(
    "resultado",
    [
        {"porAluno": {NOMES[A]: {"nome": "x", "zona": "risco"}}},
        {"porAluno": {NOMES[A]: [{"nome": "y", "zona": "top"}]}},
        {"porMatricula": {MATRICULAS[A]: {"obs": f"ver {NOMES[B]}"}}},
        {"porAluno": {NOMES[C]: 7.5}},
    ],
)
def test_o_motivo_nunca_traz_a_chave_que_nao_e_campo(resultado):
    """O motivo vai ao log; com a chave crua no caminho, o nome (ou a
    matrícula) da chave ia junto."""
    with pytest.raises(PseudonimoRecusado) as erro:
        p(resultado)
    motivo = str(erro.value)
    assert "SINTETIC" not in motivo.upper() and "9000" not in motivo
    assert motivo.startswith(("$.porAluno", "$.porMatricula"))   # o campo continua lá
    assert "<chave>" in motivo


# ─── O cadastro ──────────────────────────────────────────────────────────


class _Relogio:
    def __init__(self):
        self.agora = 1000.0

    def __call__(self):
        return self.agora


def _alunos():
    return {"aluno": {a: {"id": a, "matricula": MATRICULAS[a], "nome": NOMES[a], "email": "x@y"} for a in NOMES}}


def test_cadastro_le_id_matricula_e_nome_e_fica_em_cache():
    db, criados, relogio = _alunos(), [], _Relogio()

    def criar():
        criados.append(1)
        return FakeCliente(db)

    cadastro = CadastroDeAlunos(validade_s=60, relogio=relogio)
    primeiro = cadastro.obter(criar)
    assert primeiro.matricula_por_id == MATRICULAS
    assert primeiro.nomes == frozenset(NOMES.values())
    assert cadastro.obter(criar) is primeiro and len(criados) == 1

    relogio.agora += 61
    db["aluno"]["novo"] = {"id": "novo", "matricula": "9000099", "nome": "ALUNO NOVO DO SYNC"}
    assert cadastro.obter(criar).matricula_por_id["novo"] == "9000099"
    assert len(criados) == 2


def test_cadastro_que_nao_rele_sobe_o_erro_em_vez_de_usar_o_velho():
    relogio = _Relogio()
    cadastro = CadastroDeAlunos(validade_s=60, relogio=relogio)
    cadastro.obter(lambda: FakeCliente(_alunos()))
    relogio.agora += 61

    class _Caido:
        def table(self, _nome):
            raise RuntimeError("PostgREST fora")

    with pytest.raises(RuntimeError):
        cadastro.obter(lambda: _Caido())


def test_cadastro_das_linhas_ignora_linha_sem_matricula():
    c = Cadastro.das_linhas([{"id": "x", "matricula": None, "nome": "SEM MATRICULA ALGUMA"}])
    assert c.matricula_por_id == {}
    assert "SEM MATRICULA ALGUMA" in c.nomes   # o portão ainda conhece o nome
