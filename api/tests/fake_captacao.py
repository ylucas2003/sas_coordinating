"""A captação externa na escola sintética: as linhas e a função da 0068 em Python.

O fake de PostgREST não sabe agregar nem roda SQL. Por isso as duas views
entram semeadas com os números prontos, como se tivessem rodado, e a busca por
conquista ganha aqui uma emulação de `buscar_candidatos_por_conquista` (0068),
na mesma linha de `gatilho_da_0072_aceita` em tests/test_mcp_tokens.py: o que se
testa com ela é o CONTRATO da tool com a função — parâmetros, a regra de UMA
MESMA conquista casar todos os critérios, o público, a ordem e a forma do que
volta. A SQL de verdade se prova contra o Postgres
(`scripts/verificar_papeis_do_mcp.py --ferramentas`), e o que a emulação pode
divergir dela é o motivo de `test_a_emulacao_cita_o_que_a_funcao_cita`
conferir o texto da migration.

Dados 100% sintéticos.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

#: Quem aparece nos testes. De propósito sem nada em comum com os alunos
#: sintéticos: a captação é outra população, e um teste confere que ela não se
#: mistura à deles.
ANA = "CANDIDATA EXTERNA ANA"
BRUNO = "CANDIDATO EXTERNO BRUNO"
CAIO = "CANDIDATO EXTERNO CAIO"

#: O texto livre que nenhuma tool pode devolver (docs/43 §5.2; 0076).
OBSERVACAO_COM_TELEFONE = "liguei para a mãe, tel. 85 99999-0000, pediu retorno em março"
#: O nome como a fonte escreveu: bastidor da raspagem, fora da lista branca.
NOME_RASPADO = "ANA EXTERNA COMO A FONTE ESCREVEU"


def _id(classe: int, n: int) -> str:
    return str(uuid.UUID(int=(classe << 64) | n))


OBF, ITA, OBMEP, NAVAL = (_id(20, n) for n in range(1, 5))
PERFIL_ANA, PERFIL_ANA_HOMONIMA, PERFIL_BRUNO, PERFIL_CAIO = (_id(21, n) for n in range(1, 5))


def semear(por: Callable[..., dict]) -> None:
    """As linhas da captação, pelo `por(tabela, **linha)` de `nova_escola`."""
    por("prova_externa", id=OBF, nome="OBF", categoria="olimpiada", abrangencia="nacional",
        fonte_resultado="https://exemplo.invalid/obf")
    por("prova_externa", id=OBMEP, nome="OBMEP", categoria="olimpiada", abrangencia="nacional",
        fonte_resultado="https://exemplo.invalid/obmep")
    por("prova_externa", id=ITA, nome="ITA", categoria="vestibular", abrangencia="nacional",
        fonte_resultado="https://exemplo.invalid/ita")
    por("prova_externa", id=NAVAL, nome="Escola Naval", categoria="colegio_militar", abrangencia="nacional",
        fonte_resultado=None)

    def perfil(pid: str, nome: str, *, serie: int | None = None, ano: int | None = None, **campos: Any) -> None:
        por("candidato_externo", id=pid, nome=nome.title(), nome_normalizado=nome,
            escola=campos.get("escola"), cidade=campos.get("cidade"), uf=campos.get("uf"),
            serie_referencia_min=serie, serie_referencia_max=serie, ano_referencia_serie=ano,
            status_captacao=campos.get("status", "novo"), observacoes=campos.get("observacoes"),
            retrato_editado_a_mao=False, criado_em=campos.get("criado_em", "2026-01-01T00:00:00+00:00"),
            atualizado_em="2026-02-01T00:00:00+00:00")

    perfil(PERFIL_ANA, ANA, serie=9, ano=2025, escola="Colégio Exemplo", cidade="Fortaleza", uf="CE",
           status="interessado", observacoes=OBSERVACAO_COM_TELEFONE)
    # A homônima, separada à mão: mesmo nome, outro perfil, criado depois.
    perfil(PERFIL_ANA_HOMONIMA, ANA, ano=2024, uf="SP", criado_em="2026-03-01T00:00:00+00:00")
    perfil(PERFIL_BRUNO, BRUNO, ano=2025, escola="Escola Teste", cidade="Recife", uf="PE")
    perfil(PERFIL_CAIO, CAIO, serie=8, ano=2024, escola="Escola Caio", cidade="Sobral", uf="CE")

    def conquista(n: int, candidato: str, prova: str, ano: int, faixa: str, resultado: str,
                  serie: int | None = None, **campos: Any) -> None:
        por("conquista_externa", id=_id(22, n), prova_id=prova, candidato_id=candidato, ano=ano,
            nivel_texto=campos.get("nivel"), serie_referencia_min=serie, serie_referencia_max=serie,
            resultado=resultado, faixa=faixa, nome_informado=campos.get("informado", NOME_RASPADO),
            escola_informada=campos.get("escola", "Colégio Exemplo"), cidade_informada=campos.get("cidade", "Fortaleza"),
            uf_informada=campos.get("uf", "CE"), fonte_url=f"https://exemplo.invalid/resultado/{n}",
            raspado_em="2026-01-15T00:00:00+00:00", notas_por_materia=campos.get("notas"),
            ano_conclusao_min=None if serie is None else ano + 12 - serie,
            ano_conclusao_max=None if serie is None else ano + 12 - serie)

    conquista(1, PERFIL_ANA, OBF, 2025, "ouro", "MEDALHA DE OURO", serie=9, nivel="9º ano")
    conquista(2, PERFIL_ANA, OBF, 2024, "prata", "MEDALHA DE PRATA", serie=8, nivel="8º ano")
    conquista(3, PERFIL_ANA, OBMEP, 2023, "bronze", "Bronze", serie=7, nivel="Nível 2")
    conquista(4, PERFIL_ANA_HOMONIMA, ITA, 2024, "participou", "Realizou a 1ª fase",
              escola="Outra", cidade="São Paulo", uf="SP", notas={"mat": 8.3, "fis": 7.5})
    conquista(5, PERFIL_BRUNO, ITA, 2025, "passou_de_fase", "Convocado — 2ª fase",
              escola="Escola Teste", cidade="Recife", uf="PE")
    conquista(6, PERFIL_CAIO, OBF, 2024, "ouro", "MEDALHA DE OURO", serie=8, nivel="8º ano",
              escola="Escola Caio", cidade="Sobral")

    def por_nome(nome: str, *, escolas: list[str], cidades: list[str], ufs: list[str], status: list[str],
                 conquistas: int, provas: int, participacoes: int, perfis: int, ano: int) -> None:
        por("v_candidato_externo_por_nome", id=nome, nome_normalizado=nome, nome=nome.title(), escolas=escolas,
            cidades=cidades, ufs=ufs, status_captacao=status, conquistas_total=conquistas,
            provas_distintas=provas, participacoes=participacoes, perfis_no_grupo=perfis,
            ano_mais_recente=ano, criado_em="2026-01-01T00:00:00+00:00", atualizado_em="2026-02-01T00:00:00+00:00")

    por_nome(ANA, escolas=["Colégio Exemplo", "Outra"], cidades=["Fortaleza", "São Paulo"], ufs=["CE", "SP"],
             status=["interessado", "novo"], conquistas=3, provas=2, participacoes=1, perfis=2, ano=2025)
    por_nome(BRUNO, escolas=["Escola Teste"], cidades=["Recife"], ufs=["PE"], status=["novo"],
             conquistas=1, provas=1, participacoes=0, perfis=1, ano=2025)
    por_nome(CAIO, escolas=["Escola Caio"], cidades=["Sobral"], ufs=["CE"], status=["novo"],
             conquistas=1, provas=1, participacoes=0, perfis=1, ano=2024)

    for nome, categoria, ano_min, ano_max, total in (
        ("OBF", "olimpiada", 2024, 2025, 3), ("OBMEP", "olimpiada", 2023, 2023, 1),
        ("ITA", "vestibular", 2024, 2025, 2), ("Escola Naval", "colegio_militar", None, None, 0),
    ):
        por("v_prova_externa_resumo", id=nome, nome=nome, categoria=categoria, ano_min=ano_min,
            ano_max=ano_max, conquistas_total=total)


#: A força da faixa, só para ordenar (o CASE da 0068): força de LEAD, não de
#: resultado — `aprovado` abaixo de quem chegou ao fim sem vaga.
_FORCA = {
    "ouro": 5, "classificado_final": 5, "prata": 4, "passou_de_fase": 4, "bronze": 3, "aprovado": 3,
    "mencao": 2, "finalista": 1, "participou": 1,
}


def _casa_o_publico(ce: dict, prova: dict, publicos: list[str], ingresso: int) -> bool:
    minimo, maximo = ce.get("ano_conclusao_min"), ce.get("ano_conclusao_max")
    toca = lambda de, ate: minimo is not None and minimo <= ate and maximo >= de  # noqa: E731
    return (
        ("fundamental" in publicos and toca(ingresso + 3, ingresso + 6))
        or ("medio" in publicos and toca(ingresso, ingresso + 2))
        or ("pre_vestibular" in publicos and (
            toca(ingresso - 2, ingresso - 1)
            or (minimo is None and prova["categoria"] == "vestibular" and ingresso - 2 <= ce["ano"] <= ingresso - 1)
        ))
    )


def buscar_candidatos_por_conquista(
    db: dict[str, dict[Any, dict]], p: dict[str, Any], *, casa_like: Callable[[Any, Any, bool], bool]
) -> list[dict[str, Any]]:
    """`buscar_candidatos_por_conquista` (0068) sobre o `db` do fake.

    `casa_like` é a leitura de LIKE do fake rico, passada por quem chama para
    a do `p_busca` ser a mesma do ILIKE da lista (barra invertida é ESCAPE).
    """
    ingresso = p["p_ano_ingresso"]
    casadas: dict[str, list[dict]] = {}
    for ce in db.get("conquista_externa", {}).values():
        prova = db["prova_externa"][ce["prova_id"]]
        candidato = db["candidato_externo"].get(ce["candidato_id"])
        if candidato is None:
            continue
        if p.get("p_provas") and prova["nome"] not in p["p_provas"]:
            continue
        if p.get("p_faixas") and ce.get("faixa") not in p["p_faixas"]:
            continue
        if p.get("p_ano_min") is not None and ce["ano"] < p["p_ano_min"]:
            continue
        if p.get("p_ano_max") is not None and ce["ano"] > p["p_ano_max"]:
            continue
        if p.get("p_publicos") and not _casa_o_publico(ce, prova, p["p_publicos"], ingresso):
            continue
        casadas.setdefault(candidato["nome_normalizado"], []).append({
            "prova": prova["nome"], "ano": ce["ano"], "faixa": ce.get("faixa"), "resultado": ce["resultado"],
            "nivel": ce.get("nivel_texto") or None, "_forca": _FORCA.get(ce.get("faixa"), 0),
        })

    linhas = []
    for nome, conquistas in casadas.items():
        v = db["v_candidato_externo_por_nome"][nome]
        if p.get("p_uf") and p["p_uf"] not in v["ufs"]:
            continue
        if p.get("p_status") and p["p_status"] not in v["status_captacao"]:
            continue
        if p.get("p_conquistas_min") is not None and v["conquistas_total"] < p["p_conquistas_min"]:
            continue
        if p.get("p_busca") and not casa_like(nome, f"%{p['p_busca']}%", False):
            continue
        ordenadas = sorted(conquistas, key=lambda c: (-c["_forca"], -c["ano"]))
        linhas.append({
            **{k: valor for k, valor in v.items() if k != "id"},
            "conquistas_casadas": len(conquistas),
            "evidencias": [{k: c[k] for k in ("prova", "ano", "faixa", "resultado", "nivel")} for c in ordenadas[:3]],
            "_ordem": (-ordenadas[0]["_forca"], -ordenadas[0]["ano"], -len(conquistas), -v["provas_distintas"], nome),
        })
    linhas.sort(key=lambda l: l.pop("_ordem"))
    total = len(linhas)
    inicio = p.get("p_deslocamento") or 0
    return [{**l, "total_filtrado": total} for l in linhas[inicio : inicio + p["p_limite"]]]
