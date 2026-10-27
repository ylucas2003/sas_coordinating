"""Extrações de dados individuais do aluno, compartilhadas entre os endpoints
/me (routes/me.py) e as tools do chat do aluno (chat/tools_aluno.py).

Funções síncronas — o client Supabase é síncrono; os handlers FastAPI são
async só por convenção e delegam para cá. Situações de "não encontrado"
retornam {"erro": "..."} (as tools mostram ao LLM; as rotas convertem em 404).

⚠️ `arquivo_do_simulado_do_aluno` SAIU em 04/09 com a rota que a chamava
(docs/35 §8b): o aluno deixou de ter o botão "Abrir a prova", e a extração que
resolvia o caminho do PDF no Storage foi junto para a porta não ficar entreaberta
— ver o cabeçalho de routes/me.py. `simulado.arquivo_storage_path` continua no
banco e continua servindo a coordenação; o que saiu é o caminho do ALUNO até ele.
"""

from __future__ import annotations

import html as _html
import re
import statistics as st
from collections import defaultdict
from typing import Any

from supabase import Client

from .metricas import mapa_metrica_geral_por_simulado
from .utils import como_float, filtro_nota_valida, nota_real, simulado_entra_no_agregado

# ─── O piso de anonimato (docs/27 §9, regra 4) ────────────────────────────

#: Abaixo de tantas notas numa prova, nenhum número sobre a TURMA sai para o
#: aluno: nem média, nem grupo de 15%, nem posição, nem percentil, nem o tempo
#: médio da prova. Com duas pessoas na prova, "a média da turma" é a nota da
#: colega a uma conta de distância — 2 × média − a sua nota —, e "2º de 2" diz
#: que ela tirou mais. "Comparações só com agregados" (docs/27 §9, regra 4)
#: deixa de ser verdade sem erro nenhum na tela.
#:
#: ⚠️ O piso mora AQUI, nas funções de domínio, e não na rota nem na tool: as
#: rotas /me (routes/me.py) e as tools do chat do aluno (chat/tools_aluno.py)
#: leem estas mesmas funções, e o payload do insight vai também à OpenAI. Até
#: 26/10 não havia piso nenhum, e a média de uma prova com duas notas saía por
#: GET /me/simulados, /me/simulado/{id}, /me/evolucao e /me/insight. Piso posto
#: numa porta só deixa a mesma média sair inteira pelas outras.
#:
#: O histograma do Tio Léo (`distribuicao_do_simulado`, chat/tools_aluno_situacao.py)
#: usa este mesmo piso, importado daqui: abaixo dele, a distribuição não sai.
#:
#: ⚠️ O LIMITE, conhecido: o piso protege UMA leitura, e não a diferença entre
#: duas. Quem lê a mesma prova com 10 e depois com 11 notas tira a 11ª de
#: 11·média₂ − 10·média₁ (com a média em duas casas, o erro fica perto de 0,1).
#: Esconder a contagem não basta, e arredondar a média mais grosso só alarga o
#: erro. O conserto de verdade é publicar a comparação só com a prova FECHADA —
#: o que pede decidir quando uma prova fecha, e é decisão de produto, não desta
#: camada.
#:
#: O histograma alarga esse limite: as duas leituras entregam também a faixa de
#: 0,5 de quem entrou, e por isso esconder a contagem exata não bastaria — o
#: histograma sozinho já dá a faixa. Até a prova fechar, o risco é de quem tem a
#: nota lançada DEPOIS do piso, e só diante de quem acompanha a prova sync a sync.
PISO_DE_ANONIMATO = 10

#: O top 15% e o inferior 15% só saem quando o GRUPO tem pelo menos isto. Com a
#: turma acima do piso o grupo ainda pode ser uma pessoa — `max(1, int(n·0,15))`
#: é 1 até 13 notas — e a "média do top 15%" é a nota exata do melhor da sala.
#: Três e não dois: o aluno pode estar no grupo, e tirando a nota dele sobram
#: duas, cuja média não devolve a nota de ninguém.
MINIMO_DO_GRUPO_DE_15 = 3


def turma_acima_do_piso(n: int | None) -> bool:
    """`n` notas bastam para um número da turma ser agregado, e não a nota de alguém?"""
    return n is not None and n >= PISO_DE_ANONIMATO


def conta_como_desempenho(item: dict[str, Any]) -> bool:
    """Esta prova, um item de `simulados_do_aluno`, conta como desempenho do aluno?

    É a pergunta de `utils.filtro_nota_valida` com `utils.simulado_entra_no_agregado`,
    feita a uma linha já lida — o filtro é de CONSULTA e não serve a um item na
    mão, e esta lista não pode usá-lo, porque mostra também o que não conta.
    Não conta:

      * a falta, e a nota que não se calcula (`nota` None);
      * a nota `computavel = false` — a evidência de `stats/computavel.py` de
        que o número não é desempenho: o quiz aberto sem nenhuma alternativa
        marcada, ou o zero que aquela prova lançou para quem faltou (docs/32
        §1.4). É a "provável ausência": lida como nota, ela vira "você zerou
        Química" na boca do Tio Léo;
      * a prova com `nota_confiavel = false`, cuja coluna inteira não
        representa desempenho.

    Quem não conta continua NA LISTA, com a marca: é o histórico do aluno, e um
    número que o produto decidiu ignorar tem de dizer que ignorou (docs/32
    §1.5). O que esta função decide é que ele não entra em delta, em média nem
    em comparação, e que o modelo não o lê como nota.
    """
    return (
        bool(item.get("presente"))
        and item.get("nota") is not None
        and item.get("computavel", True) is not False
        and item.get("notaConfiavel", True) is not False
    )


def simulados_do_aluno(
    cliente: Client, aluno_id: str, *, incluir_faltas: bool = False
) -> list[dict[str, Any]]:
    """Lista de simulados do aluno com nota, delta vs próprio padrão e média
    da turma — mesma resposta de GET /me/simulados (ordenada do mais recente
    para o mais antigo, com flag `novo` no primeiro).

    `incluir_faltas=True` traz também os simulados em que o aluno não
    compareceu, com `nota: None` e `presente: False` — são os quadrados vazados
    da corrente (docs/36 §2.1).

    ⚠️ O default é `False` de propósito. Hoje, Provas e Jornada já consomem
    esta função e calculam média e delta sobre a lista que ela devolve; ligar a
    falta por default mudaria número em tela sem ninguém ter pedido. Quem quer
    a ausência pede por ela.

    Cada item leva as duas marcas do SAS sobre a nota — `computavel` (com
    `motivoNaoComputavel`) e `notaConfiavel`, da prova — e quem pergunta se ele
    conta é `conta_como_desempenho`. A nota que não conta fica na lista, mas
    sem `deltaSelf` e fora da base do delta das outras: o zero de provável
    ausência puxaria para cima o delta de toda prova seguinte.

    `mediaGeral` passa pelo piso de anonimato (`turma_acima_do_piso`): `None`
    com menos de `PISO_DE_ANONIMATO` notas na prova. `nPresentes` fica — é
    contagem, e é ela que deixa a tela dizer por que a média não está lá.

    `anoLetivoId` é o do ciclo — a ordem do ciclo se repete entre anos (ver
    `aluno_jornada._ciclo_corrente`).
    """
    consulta = (
        cliente.table("nota")
        .select(
            "pontuacao, presente, computavel, motivo_nao_computavel, simulado("
            "id, nome, rotulo_curto, data_aplicacao, nota_maxima, materia_id, tipo, anulado, e_agregado, "
            "nota_confiavel, motivo_nota_nao_confiavel, "
            "ciclo:ciclo_id(id, ordem, vestibular_alvo, ano_letivo_id)"
            ")"
        )
        .eq("aluno_id", aluno_id)
    )
    # Sem `filtro_nota_valida` de propósito: esta é a ficha do aluno, e uma
    # nota que saiu da média tem de continuar visível, com a marca. Quem
    # some daqui é a ausência, não a nota que o SAS decidiu não somar.
    if not incluir_faltas:
        consulta = consulta.eq("presente", True)
    resp = consulta.execute()

    metricas = mapa_metrica_geral_por_simulado(cliente)
    mats_resp = cliente.table("materia").select("id, nome").execute()
    nome_mat = {m["id"]: m["nome"] for m in (mats_resp.data or [])}

    itens: list[dict[str, Any]] = []
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        # Só anulado e agregado saem da LISTA. Prova não confiável fica: o
        # aluno de 2023 não perde o histórico, e a tela põe a ressalva.
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        presente = bool(linha.get("presente"))
        nota = nota_real(como_float(linha.get("pontuacao")), como_float(sim.get("nota_maxima")))
        # Quem compareceu e não tem nota calculável não é falta — é dado
        # quebrado, e sai da lista como sempre saiu. Quem faltou entra sem
        # nota: é isso que o quadrado vazado desenha.
        if nota is None and presente:
            continue
        ciclo = sim.get("ciclo") or {}
        met = metricas.get(sim["id"]) or {}
        # O piso de anonimato, prova a prova, contado pela mesma métrica que
        # deu a média: com poucas notas, "a média da turma" é a nota de colega
        # a uma conta de distância.
        media_turma = met.get("media") if turma_acima_do_piso(met.get("n_presentes")) else None
        itens.append(
            {
                "id": sim["id"],
                "nome": sim.get("nome"),
                "rotulo": sim.get("rotulo_curto") or sim.get("nome"),
                "dataAplicacao": sim.get("data_aplicacao"),
                "tipo": sim.get("tipo"),
                "materia": nome_mat.get(sim.get("materia_id")),
                "nota": round(nota, 2) if presente and nota is not None else None,
                "presente": presente,
                # Ausente = true, como em `simulado_entra_no_agregado`: é o
                # default do banco, e presumir o contrário esvaziaria a lista.
                "computavel": linha.get("computavel", True) is not False,
                "motivoNaoComputavel": linha.get("motivo_nao_computavel"),
                "notaConfiavel": sim.get("nota_confiavel", True) is not False,
                "deltaSelf": None,
                "mediaGeral": round(media_turma, 2) if media_turma is not None else None,
                "nPresentes": met.get("n_presentes", 0),
                "cicloId": ciclo.get("id"),
                "cicloOrdem": ciclo.get("ordem"),
                "anoLetivoId": ciclo.get("ano_letivo_id"),
                "vestibularAlvo": ciclo.get("vestibular_alvo"),
                "novo": False,
            }
        )

    # Ordena ASC para calcular delta acumulativo. A falta não entra no
    # "próprio padrão" nem recebe delta: ausência não é desempenho, e somá-la
    # como zero puxaria a régua do aluno para baixo por não ter feito a prova.
    # A nota que não conta como desempenho (`conta_como_desempenho`) também
    # não: é a provável ausência escrita como zero.
    itens.sort(key=lambda s: s.get("dataAplicacao") or "")
    notas_ant: list[float] = []
    for item in itens:
        if not conta_como_desempenho(item):
            continue
        if notas_ant:
            item["deltaSelf"] = round(item["nota"] - sum(notas_ant) / len(notas_ant), 2)
        notas_ant.append(item["nota"])

    # Ordena DESC para a resposta; marca o mais recente COM NOTA — "novo" é o
    # selo de nota que acabou de sair, e uma falta não é novidade nenhuma.
    itens.sort(key=lambda s: s.get("dataAplicacao") or "", reverse=True)
    for item in itens:
        if item["nota"] is not None:
            item["novo"] = True
            break

    return itens


def _ciclos_acima_da_media_da_turma(itens: list[dict[str, Any]]) -> int:
    """Ciclos consecutivos recentes com média do aluno acima da média da turma.

    ⚠️ NÃO é "a sequência do aluno" — essa é `aluno_jornada.sequencia_do_aluno`,
    e mede simulados sem faltar. Esta aqui é relativa: premia posição contra a
    turma, não progresso (docs/24 §1.1). Sobrou só como um número entre outros
    no payload que o insight manda ao LLM, e o nome da chave diz o que ela é
    justamente para o modelo não a ler como sequência.

    `itens` são só os que contam como desempenho (`conta_como_desempenho`).
    `mediaGeral` já chega pelo piso de anonimato de `simulados_do_aluno`: a
    prova pequena não entra no lado da turma.
    """
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


def _notas_da_prova(cliente: Client, simulado_id: str, nota_maxima: float) -> list[tuple[str, float]]:
    """(aluno_id, nota 0–10) de quem tem nota que conta nesta prova.

    É a contagem do piso de anonimato da prova, e por isso uma só: a ficha
    (`detalhe_simulado_do_aluno`) e o tempo médio das questões
    (`questoes_do_aluno_no_simulado`) saem na mesma tela (ProvaFicha.tsx), e um
    piso contado de dois jeitos deixaria um número da turma de pé ao lado dos
    que ele tirou.
    """
    resp = (
        filtro_nota_valida(
            cliente.table("nota")
            .select("aluno_id, pontuacao")
            .eq("simulado_id", simulado_id)
        )
        .execute()
    )
    notas: list[tuple[str, float]] = []
    for linha in resp.data or []:
        n = nota_real(como_float(linha.get("pontuacao")), nota_maxima)
        if n is not None:
            notas.append((linha["aluno_id"], n))
    return notas


def detalhe_simulado_do_aluno(
    cliente: Client, aluno_id: str, simulado_id: str
) -> dict[str, Any]:
    """Detalhe de um simulado: nota, ranking e comparação com grupos —
    mesma resposta de GET /me/simulado/{id}.

    Posição, percentil e os três números da turma passam pelo piso de
    anonimato e vêm `None` abaixo dele; `total` fica sempre.
    """
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

    notas = _notas_da_prova(cliente, simulado_id, nota_maxima)
    todas_notas = [n for _, n in notas]
    minha_nota = dict(notas).get(aluno_id)

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
    # O piso de anonimato: abaixo dele a "comparação com a turma" é a nota de
    # colegas, e os três números saem `None` — a ficha da prova já diz que
    # ainda não há gente suficiente para comparar quando `geral` vem nulo
    # (ProvaFicha.tsx). Os grupos de 15% têm, além disso, o piso próprio.
    # Posição e percentil saem junto: com duas notas, "2º de 2" diz que o
    # colega tirou mais — é comparação com uma pessoa, não com agregado.
    # `total` fica: é contagem, e é ela que deixa a tela dizer POR QUE não há
    # comparação.
    turma_ok = turma_acima_do_piso(total)
    grupos_ok = turma_ok and n15 >= MINIMO_DO_GRUPO_DE_15

    # Delta vs média de todos os outros simulados do aluno
    outras_resp = (
        filtro_nota_valida(
            cliente.table("nota")
            .select(
                "pontuacao, presente, "
                "simulado(nota_maxima, anulado, e_agregado, nota_confiavel)"
            )
            .eq("aluno_id", aluno_id)
        )
        .neq("simulado_id", simulado_id)
        .execute()
    )
    outras: list[float] = []
    for linha in outras_resp.data or []:
        s = linha.get("simulado") or {}
        if not simulado_entra_no_agregado(s):
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
        "posicao": posicao if turma_ok else None,
        "total": total,
        "percentil": percentil if turma_ok else None,
        "grupos": {
            "voce": round(minha_nota, 2),
            "geral": round(geral, 2) if turma_ok else None,
            "top15": round(top15, 2) if grupos_ok else None,
            "bottom15": round(bottom15, 2) if grupos_ok else None,
        },
    }


def trajetoria_do_aluno(
    cliente: Client, aluno_id: str, limite: int | None = None
) -> list[dict[str, Any]]:
    """As notas do aluno em ordem cronológica, em escala 0–10 — a trajetória.

    Esta leitura existia em TRÊS cópias — `GET /alunos/{id}/trajetoria` (que
    `/me/trajetoria` reaproveita), a tool `trajetoria_aluno` da coordenação e o
    gráfico `linha_temporal` de aluno do assistente — e se juntou aqui antes de
    nascer a quarta (docs/43 §4.3). Cada consumidor escolhe os campos e os
    nomes que devolve; quem entra na série é decidido aqui, e só aqui:

      * só nota `computavel` — o zero sem resposta não é desempenho, e
        afundaria a série de quem não fez a prova;
      * a prova não confiável FICA: quem a perde é a estatística, não o
        histórico da pessoa (`utils.simulado_entra_no_agregado`);
      * sai simulado anulado, simulado agregado, falta e nota que não se
        calcula (`nota_real` devolve None).

    `limite` corta depois de ordenar e guarda as MAIS RECENTES; `None` traz
    todas. ⚠️ O corte é o de sempre (`pontos[-limite:]` quando passa do
    limite), e com zero ou negativo ele não faz o que o nome promete: quem
    expõe `limite` ao modelo o valida antes — o despacho não confere `minimum`.

    Cada ponto: `{simuladoId, simulado, rotuloCurto, dataAplicacao, materiaId,
    materia, tipo, cicloId, nota}`. `simulado` é o nome completo; `materia` é o
    nome da matéria, None na prova multi-matéria; `nota` vem com duas casas.
    Uma ida ao PostgREST: o nome da matéria vem embutido no simulado.
    """
    resp = (
        cliente.table("nota")
        .select(
            "pontuacao, presente, simulado("
            "id, nome, rotulo_curto, data_aplicacao, anulado, e_agregado, "
            "nota_maxima, materia_id, tipo, ciclo_id, materia:materia_id(nome)"
            ")"
        )
        .eq("aluno_id", aluno_id)
        .eq("computavel", True)
        .execute()
    )

    pontos: list[dict[str, Any]] = []
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        if not linha.get("presente"):
            continue
        nota = nota_real(como_float(linha.get("pontuacao")), como_float(sim.get("nota_maxima")))
        if nota is None:
            continue
        pontos.append(
            {
                "simuladoId": sim.get("id"),
                "simulado": sim.get("nome"),
                "rotuloCurto": sim.get("rotulo_curto"),
                "dataAplicacao": sim.get("data_aplicacao"),
                "materiaId": sim.get("materia_id"),
                "materia": (sim.get("materia") or {}).get("nome") if sim.get("materia_id") else None,
                "tipo": sim.get("tipo"),
                "cicloId": sim.get("ciclo_id"),
                "nota": round(nota, 2),
            }
        )
    pontos.sort(key=lambda p: p["dataAplicacao"] or "")

    if limite is not None and len(pontos) > limite:
        pontos = pontos[-limite:]
    return pontos


def evolucao_do_aluno(cliente: Client, aluno_id: str) -> dict[str, Any]:
    """Séries aluno × turma por matéria/ciclo — mesma resposta de GET /me/evolucao.

    O lado da turma passa pelo piso de anonimato prova a prova: a média de uma
    prova com menos de `PISO_DE_ANONIMATO` notas não entra. Num ciclo em que a
    única prova da matéria era pequena, `turma` fica `None` ali com `aluno`
    preenchido — com duas notas na prova, a média da turma menos a do aluno
    era a nota da colega. Num ciclo com uma prova grande e uma pequena, a
    série usa só a grande.
    """
    resp = (
        filtro_nota_valida(
            cliente.table("nota")
            .select(
                "pontuacao, presente, simulado("
                "id, nota_maxima, materia_id, anulado, e_agregado, nota_confiavel, "
                "ciclo:ciclo_id(id, ordem)"
                ")"
            )
            .eq("aluno_id", aluno_id)
        )
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
        if not simulado_entra_no_agregado(sim):
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
        met = metricas.get(sim["id"]) or {}
        if met.get("media") is not None and turma_acima_do_piso(met.get("n_presentes")):
            dados[ordem][materia]["turma"].append(met["media"])

    if not dados:
        return {"ciclos": [], "materias": {}}

    ordens = sorted(dados.keys())
    ciclos = [{"ordem": o, "label": f"C{o}"} for o in ordens]
    todas_mats = sorted({m for cd in dados.values() for m in cd})

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
        .select("id, quiz_id, duracao_media_segundos, nota_maxima")
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    if not sim_resp.data:
        return {"erro": "Simulado não encontrado"}
    sim = sim_resp.data[0]

    # O tempo médio é número da TURMA (o `duration_average` das Quiz
    # Statistics do Canvas, gravado por canvas_sync/questoes.py na coluna da
    # migration 0010): com duas pessoas na prova, é o tempo da colega a uma
    # conta de distância — o aluno sabe o próprio. Passa
    # pelo mesmo piso da ficha desta prova, contado do mesmo jeito
    # (`_notas_da_prova`), porque os dois saem na mesma tela (ProvaFicha.tsx):
    # média, posição e percentil nulos ao lado de um tempo da turma era a
    # comparação que o piso tira. A consulta extra só roda quando há tempo.
    duracao = como_float(sim.get("duracao_media_segundos"))
    if duracao is not None:
        nota_maxima = como_float(sim.get("nota_maxima")) or 10.0
        if not turma_acima_do_piso(len(_notas_da_prova(cliente, simulado_id, nota_maxima))):
            duracao = None

    vazio = {
        "temGabarito": False,
        "temMinhasRespostas": False,
        "duracaoMediaSegundos": duracao,
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
        "duracaoMediaSegundos": duracao,
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

    `mediaTurma` (geral e por matéria) já vem pelo piso de anonimato de
    `simulados_do_aluno`: este payload vai à OpenAI, e com duas notas na prova
    a média da turma era a nota da colega a uma conta de distância. Como o
    payload é a chave do cache (`insight_aluno.gerar_para_aluno_ciclo` faz hash
    dele), os bullets gerados com a média vazada não voltam mais do cache: o
    hash mudou junto com o número.

    Mais dois recortes, e os dois são regra de outro lugar, aplicada aqui:

      * só entra o que conta como desempenho (`conta_como_desempenho`): o zero
        de provável ausência viraria "você caiu em Química" no texto do modelo;
      * o ciclo é do ano letivo da prova mais recente: a ordem do ciclo se
        repete entre anos (`aluno_jornada._ciclo_corrente`), e o maior número
        de todos podia ser o ciclo 30 do ano passado.
    """
    itens = [i for i in simulados_do_aluno(cliente, aluno_id) if conta_como_desempenho(i)]
    # A lista vem do mais recente para o mais antigo.
    ano = next((i["anoLetivoId"] for i in itens if i.get("anoLetivoId")), None)
    if ano is not None:
        itens = [i for i in itens if i.get("anoLetivoId") == ano]
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
            "ciclosAcimaDaMediaDaTurma": _ciclos_acima_da_media_da_turma(itens),
        },
        "porMateria": por_materia,
        "temCicloAnterior": bool(do_anterior),
    }
    return ciclo, payload
