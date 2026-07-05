"""Extrações de dados individuais do aluno, compartilhadas entre os endpoints
/me (routes/me.py) e as tools do chat do aluno (chat/tools_aluno.py).

Funções síncronas — o client Supabase é síncrono; os handlers FastAPI são
async só por convenção e delegam para cá. Situações de "não encontrado"
retornam {"erro": "..."} (as tools mostram ao LLM; as rotas convertem em 404).
"""

from __future__ import annotations

import html as _html
import re
import statistics as st
from collections import defaultdict
from typing import Any

from supabase import Client

from .metricas import mapa_metrica_geral_por_simulado
from .utils import como_float, nota_real


def simulados_do_aluno(cliente: Client, aluno_id: str) -> list[dict[str, Any]]:
    """Lista de simulados do aluno com nota, delta vs próprio padrão e média
    da turma — mesma resposta de GET /me/simulados (ordenada do mais recente
    para o mais antigo, com flag `novo` no primeiro)."""
    resp = (
        cliente.table("nota")
        .select(
            "pontuacao, presente, simulado("
            "id, nome, rotulo_curto, data_aplicacao, nota_maxima, materia_id, tipo, anulado, e_agregado, "
            "ciclo:ciclo_id(id, ordem, vestibular_alvo)"
            ")"
        )
        .eq("aluno_id", aluno_id)
        .eq("presente", True)
        .execute()
    )

    metricas = mapa_metrica_geral_por_simulado(cliente)
    mats_resp = cliente.table("materia").select("id, nome").execute()
    nome_mat = {m["id"]: m["nome"] for m in (mats_resp.data or [])}

    itens: list[dict[str, Any]] = []
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        nota = nota_real(como_float(linha.get("pontuacao")), como_float(sim.get("nota_maxima")))
        if nota is None:
            continue
        ciclo = sim.get("ciclo") or {}
        met = metricas.get(sim["id"]) or {}
        itens.append(
            {
                "id": sim["id"],
                "nome": sim.get("nome"),
                "rotulo": sim.get("rotulo_curto") or sim.get("nome"),
                "dataAplicacao": sim.get("data_aplicacao"),
                "tipo": sim.get("tipo"),
                "materia": nome_mat.get(sim.get("materia_id")),
                "nota": round(nota, 2),
                "deltaSelf": None,
                "mediaGeral": round(met["media"], 2) if met.get("media") is not None else None,
                "nPresentes": met.get("n_presentes", 0),
                "cicloId": ciclo.get("id"),
                "cicloOrdem": ciclo.get("ordem"),
                "vestibularAlvo": ciclo.get("vestibular_alvo"),
                "novo": False,
            }
        )

    # Ordena ASC para calcular delta acumulativo
    itens.sort(key=lambda s: s.get("dataAplicacao") or "")
    notas_ant: list[float] = []
    for item in itens:
        if notas_ant:
            item["deltaSelf"] = round(item["nota"] - sum(notas_ant) / len(notas_ant), 2)
        notas_ant.append(item["nota"])

    # Ordena DESC para a resposta; marca o mais recente
    itens.sort(key=lambda s: s.get("dataAplicacao") or "", reverse=True)
    if itens:
        itens[0]["novo"] = True

    return itens


def _streak_de_itens(itens: list[dict[str, Any]]) -> int:
    """Ciclos consecutivos recentes com média do aluno acima da média da turma."""
    por_ciclo: dict[int, dict[str, list[float]]] = {}
    for item in itens:
        ordem = item.get("cicloOrdem")
        if ordem is None:
            continue
        d = por_ciclo.setdefault(ordem, {"minhas": [], "turma": []})
        d["minhas"].append(item["nota"])
        if item.get("mediaGeral") is not None:
            d["turma"].append(item["mediaGeral"])

    streak = 0
    for ordem in sorted(por_ciclo.keys(), reverse=True):
        d = por_ciclo[ordem]
        if not d["minhas"] or not d["turma"]:
            break
        if st.mean(d["minhas"]) > st.mean(d["turma"]):
            streak += 1
        else:
            break
    return streak


def streak_do_aluno(cliente: Client, aluno_id: str) -> dict[str, Any]:
    """Mesma resposta de GET /me/streak."""
    itens = simulados_do_aluno(cliente, aluno_id)
    return {"count": _streak_de_itens(itens), "label": "ciclos acima da média da turma"}


def detalhe_simulado_do_aluno(
    cliente: Client, aluno_id: str, simulado_id: str
) -> dict[str, Any]:
    """Detalhe de um simulado: nota, ranking e comparação com grupos —
    mesma resposta de GET /me/simulado/{id}."""
    sim_resp = (
        cliente.table("simulado")
        .select(
            "id, nome, rotulo_curto, data_aplicacao, nota_maxima, materia_id, tipo, "
            "ciclo:ciclo_id(vestibular_alvo)"
        )
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    if not sim_resp.data:
        return {"erro": "Simulado não encontrado"}

    sim = sim_resp.data[0]
    nota_maxima = como_float(sim.get("nota_maxima")) or 10.0

    mats_resp = cliente.table("materia").select("id, nome").execute()
    nome_mat = {m["id"]: m["nome"] for m in (mats_resp.data or [])}

    notas_resp = (
        cliente.table("nota")
        .select("aluno_id, pontuacao")
        .eq("simulado_id", simulado_id)
        .eq("presente", True)
        .execute()
    )

    todas_notas: list[float] = []
    minha_nota: float | None = None
    for linha in notas_resp.data or []:
        n = nota_real(como_float(linha.get("pontuacao")), nota_maxima)
        if n is None:
            continue
        todas_notas.append(n)
        if linha["aluno_id"] == aluno_id:
            minha_nota = n

    if minha_nota is None:
        return {"erro": "Nota não encontrada para este simulado"}

    total = len(todas_notas)
    desc = sorted(todas_notas, reverse=True)
    # Posição = posição do aluno entre os melhores (1 = melhor)
    posicao = next((i + 1 for i, v in enumerate(desc) if v <= minha_nota + 0.001), total)
    percentil = round((total - posicao) / total * 100) if total > 1 else 50

    n15 = max(1, int(total * 0.15))
    geral = st.mean(todas_notas)
    top15 = st.mean(sorted(todas_notas)[-n15:])
    bottom15 = st.mean(sorted(todas_notas)[:n15])

    # Delta vs média de todos os outros simulados do aluno
    outras_resp = (
        cliente.table("nota")
        .select("pontuacao, presente, simulado(nota_maxima, anulado, e_agregado)")
        .eq("aluno_id", aluno_id)
        .eq("presente", True)
        .neq("simulado_id", simulado_id)
        .execute()
    )
    outras: list[float] = []
    for linha in outras_resp.data or []:
        s = linha.get("simulado") or {}
        if s.get("anulado") or s.get("e_agregado"):
            continue
        n = nota_real(como_float(linha.get("pontuacao")), como_float(s.get("nota_maxima")))
        if n is not None:
            outras.append(n)
    delta_self = round(minha_nota - st.mean(outras), 2) if outras else None

    return {
        "id": sim["id"],
        "nome": sim.get("nome"),
        "rotulo": sim.get("rotulo_curto") or sim.get("nome"),
        "dataAplicacao": sim.get("data_aplicacao"),
        "tipo": sim.get("tipo"),
        "materia": nome_mat.get(sim.get("materia_id")),
        "vestibularAlvo": (sim.get("ciclo") or {}).get("vestibular_alvo"),
        "nota": round(minha_nota, 2),
        "deltaSelf": delta_self,
        "posicao": posicao,
        "total": total,
        "percentil": percentil,
        "grupos": {
            "voce": round(minha_nota, 2),
            "geral": round(geral, 2),
            "top15": round(top15, 2),
            "bottom15": round(bottom15, 2),
        },
    }


def evolucao_do_aluno(cliente: Client, aluno_id: str) -> dict[str, Any]:
    """Séries aluno × turma por matéria/ciclo — mesma resposta de GET /me/evolucao."""
    resp = (
        cliente.table("nota")
        .select(
            "pontuacao, presente, simulado("
            "id, nota_maxima, materia_id, anulado, e_agregado, "
            "ciclo:ciclo_id(id, ordem)"
            ")"
        )
        .eq("aluno_id", aluno_id)
        .eq("presente", True)
        .execute()
    )

    metricas = mapa_metrica_geral_por_simulado(cliente)
    mats_resp = cliente.table("materia").select("id, nome").execute()
    nome_mat = {m["id"]: m["nome"] for m in (mats_resp.data or [])}

    # {ciclo_ordem: {materia_nome: {aluno: [...], turma: [...]}}}
    dados: dict[int, dict[str, dict]] = defaultdict(
        lambda: defaultdict(lambda: {"aluno": [], "turma": []})
    )

    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        ciclo = sim.get("ciclo") or {}
        ordem = ciclo.get("ordem")
        if ordem is None:
            continue
        materia = nome_mat.get(sim.get("materia_id"))
        if not materia:
            continue
        nota = nota_real(como_float(linha.get("pontuacao")), como_float(sim.get("nota_maxima")))
        if nota is None:
            continue
        dados[ordem][materia]["aluno"].append(nota)
        media_turma = (metricas.get(sim["id"]) or {}).get("media")
        if media_turma is not None:
            dados[ordem][materia]["turma"].append(media_turma)

    if not dados:
        return {"ciclos": [], "materias": {}}

    ordens = sorted(dados.keys())
    ciclos = [{"ordem": o, "label": f"C{o}"} for o in ordens]
    todas_mats = sorted({m for cd in dados.values() for m in cd.keys()})

    materias_out: dict[str, dict] = {}
    for mat in todas_mats:
        aluno_vals = []
        turma_vals = []
        for ordem in ordens:
            vals = dados[ordem].get(mat, {})
            al = vals.get("aluno", [])
            tu = vals.get("turma", [])
            aluno_vals.append(round(st.mean(al), 2) if al else None)
            turma_vals.append(round(st.mean(tu), 2) if tu else None)
        materias_out[mat] = {"aluno": aluno_vals, "turma": turma_vals}

    return {"ciclos": ciclos, "materias": materias_out}


_LIMITE_TEXTO_RESUMO = 160


def texto_resumo_questao(texto_html: str | None) -> str:
    """Enunciado HTML do Canvas → texto puro curto para listas/dot grid."""
    if not texto_html:
        return ""
    texto = re.sub(r"<[^>]+>", " ", texto_html)
    texto = _html.unescape(texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    if len(texto) > _LIMITE_TEXTO_RESUMO:
        texto = texto[: _LIMITE_TEXTO_RESUMO - 1].rstrip() + "…"
    return texto


def questoes_do_aluno_no_simulado(
    cliente: Client, aluno_id: str, simulado_id: str
) -> dict[str, Any]:
    """Resultado questão a questão — mesma resposta de GET /me/simulado/{id}/questoes.

    temGabarito=False quando o simulado não é um quiz sincronizado;
    temMinhasRespostas=False quando há gabarito mas nenhuma resposta do aluno.
    """
    # O aluno só consulta simulados em que tem nota (mesma guarda do detalhe).
    nota_resp = (
        cliente.table("nota")
        .select("aluno_id")
        .eq("aluno_id", aluno_id)
        .eq("simulado_id", simulado_id)
        .eq("presente", True)
        .limit(1)
        .execute()
    )
    if not nota_resp.data:
        return {"erro": "Nota não encontrada para este simulado"}

    sim_resp = (
        cliente.table("simulado")
        .select("id, quiz_id, duracao_media_segundos")
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    if not sim_resp.data:
        return {"erro": "Simulado não encontrado"}
    sim = sim_resp.data[0]

    vazio = {
        "temGabarito": False,
        "temMinhasRespostas": False,
        "duracaoMediaSegundos": como_float(sim.get("duracao_media_segundos")),
        "totalQuestoes": 0,
        "acertos": 0,
        "erros": 0,
        "emBranco": 0,
        "questoes": [],
    }
    if not sim.get("quiz_id"):
        return vazio

    questoes_resp = (
        cliente.table("questao")
        .select("id, posicao, texto, pontos, assunto")
        .eq("simulado_id", simulado_id)
        .order("posicao")
        .execute()
    )
    questoes = questoes_resp.data or []
    if not questoes:
        return vazio

    questao_ids = [q["id"] for q in questoes]
    alternativas_resp = (
        cliente.table("questao_alternativa")
        .select("id, questao_id, texto, correta")
        .in_("questao_id", questao_ids)
        .execute()
    )
    alternativa_por_id: dict[str, dict] = {}
    correta_por_questao: dict[str, dict] = {}
    for alt in alternativas_resp.data or []:
        alternativa_por_id[alt["id"]] = alt
        if alt.get("correta"):
            correta_por_questao[alt["questao_id"]] = alt

    respostas_resp = (
        cliente.table("questao_resposta_aluno")
        .select("questao_id, alternativa_id, correta")
        .eq("aluno_id", aluno_id)
        .in_("questao_id", questao_ids)
        .execute()
    )
    resposta_por_questao = {r["questao_id"]: r for r in (respostas_resp.data or [])}

    itens: list[dict] = []
    acertos = erros = em_branco = 0
    for questao in questoes:
        resposta = resposta_por_questao.get(questao["id"])
        if resposta is None:
            resultado = None
        elif resposta.get("correta"):
            resultado = "correta"
            acertos += 1
        elif resposta.get("alternativa_id"):
            resultado = "errada"
            erros += 1
        else:
            resultado = "em_branco"
            em_branco += 1

        marcada = alternativa_por_id.get((resposta or {}).get("alternativa_id"))
        correta = correta_por_questao.get(questao["id"])
        itens.append(
            {
                "questaoId": questao["id"],
                "posicao": questao.get("posicao"),
                "pontos": como_float(questao.get("pontos")),
                "assunto": questao.get("assunto"),
                "resultado": resultado,
                "textoResumo": texto_resumo_questao(questao.get("texto")),
                "alternativaMarcada": texto_resumo_questao(marcada.get("texto")) if marcada else None,
                "alternativaCorreta": texto_resumo_questao(correta.get("texto")) if correta else None,
            }
        )

    return {
        "temGabarito": True,
        "temMinhasRespostas": bool(resposta_por_questao),
        "duracaoMediaSegundos": como_float(sim.get("duracao_media_segundos")),
        "totalQuestoes": len(questoes),
        "acertos": acertos,
        "erros": erros,
        "emBranco": em_branco,
        "questoes": itens,
    }


def payload_insight_ciclo(
    cliente: Client, aluno_id: str
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Monta o payload de estatísticas individuais do ciclo mais recente do
    aluno — a entrada (e a chave de cache, via hash) do insight de IA.

    Devolve (ciclo, payload); None se o aluno não tem notas em ciclo nenhum.
    """
    itens = simulados_do_aluno(cliente, aluno_id)
    com_ciclo = [i for i in itens if i.get("cicloOrdem") is not None and i.get("cicloId")]
    if not com_ciclo:
        return None

    ordem_atual = max(i["cicloOrdem"] for i in com_ciclo)
    do_ciclo = [i for i in com_ciclo if i["cicloOrdem"] == ordem_atual]
    do_anterior = [i for i in com_ciclo if i["cicloOrdem"] == ordem_atual - 1]

    ciclo_id = do_ciclo[0]["cicloId"]
    ciclo_resp = (
        cliente.table("ciclo").select("id, nome, vestibular_alvo").eq("id", ciclo_id).limit(1).execute()
    )
    ciclo_linha = (ciclo_resp.data or [{}])[0]
    ciclo = {
        "id": ciclo_id,
        "ordem": ordem_atual,
        "nome": ciclo_linha.get("nome") or f"Ciclo {ordem_atual}",
        "vestibularAlvo": ciclo_linha.get("vestibular_alvo"),
    }

    def _media(valores: list[float]) -> float | None:
        return round(st.mean(valores), 2) if valores else None

    por_materia: list[dict[str, Any]] = []
    materias = sorted({i["materia"] for i in do_ciclo if i.get("materia")})
    for materia in materias:
        minhas = [i["nota"] for i in do_ciclo if i.get("materia") == materia]
        turma = [i["mediaGeral"] for i in do_ciclo if i.get("materia") == materia and i.get("mediaGeral") is not None]
        anteriores = [i["nota"] for i in do_anterior if i.get("materia") == materia]
        por_materia.append(
            {
                "materia": materia,
                "minhaNota": _media(minhas),
                "mediaTurma": _media(turma),
                "minhaNotaCicloAnterior": _media(anteriores),
            }
        )

    payload = {
        "ciclo": {"ordem": ordem_atual, "nome": ciclo["nome"], "vestibularAlvo": ciclo["vestibularAlvo"]},
        "geral": {
            "minhaMedia": _media([i["nota"] for i in do_ciclo]),
            "mediaTurma": _media([i["mediaGeral"] for i in do_ciclo if i.get("mediaGeral") is not None]),
            "streak": _streak_de_itens(itens),
        },
        "porMateria": por_materia,
        "temCicloAnterior": bool(do_anterior),
    }
    return ciclo, payload
