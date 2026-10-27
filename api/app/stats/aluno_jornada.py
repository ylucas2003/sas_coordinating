"""Presença, agenda, sequência e meta do ciclo — o que a corrente desenha.

As quatro fontes que docs/30 listava como "dado existe, rota não" e que
docs/36 §2 destravou. Todas saem de `nota.presente` e de `evento_agenda`; o
que faltava não era dado, era a regra de quem pode ser chamado de falta.

⚠️ **A regra da falta mora aqui, num lugar só** (docs/36 §1.1). Medindo o
banco em 05/09: 58,7% das notas são `presente = false` e 440 alunos de 1.229
têm 100% de falta. O número bruto não é ausência — é ausência misturada com
"esta prova nunca foi minha". Duas condições separam uma coisa da outra:

  1. o aluno tem matrícula ativa (`matricula_turma.ativo_ate IS NULL`);
  2. o simulado foi aplicado depois da entrada dele (`ativo_desde`).

Sem a 2, quem entrou no meio do ano abre a Jornada com a corrente vazada por
provas que aconteceram antes de ele existir no colégio.

A trilha NÃO entra no filtro, de propósito: `INDEFINIDA` são 664 alunos reais
cuja `section` do Canvas o parser não entendeu (commit 59cc7ce), e excluí-los
seria punir o aluno por um defeito de ingest.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from supabase import Client

from ..banco.missao import hoje_na_escola
from .aluno_dados import simulados_do_aluno

#: O contrato do front (`ProximoSimulado.fase`) é numérico; o banco guarda
#: `simulado.tipo`. A coluna `simulado.fase` ('1a'/'2a') foi removida na
#: migration 0003 — quem sabe a fase hoje é `tipo`, e a tradução fica aqui,
#: na borda, nunca no front.
_FASE_POR_TIPO = {"fase_1": 1, "fase_2": 2}


# ─── A regra da falta ─────────────────────────────────────────────────────


def _matriculas_ativas(cliente: Client, aluno_id: str) -> list[dict[str, Any]]:
    resp = (
        cliente.table("matricula_turma")
        .select("turma_id, ativo_desde")
        .eq("aluno_id", aluno_id)
        .is_("ativo_ate", "null")
        .execute()
    )
    return resp.data or []


def aplicar_regra_da_falta(
    itens: list[dict[str, Any]], matriculas: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """A regra de docs/36 §1.1, pura — é aqui que se decide o que é falta.

    Devolve ordenado do mais antigo para o mais recente: é a ordem em que a
    corrente é lida, e todas as contagens daqui dependem dela.

    Aluno sem matrícula ativa fica só com o que ele FEZ. Sem vínculo vivo não
    há como afirmar que ele devia estar na prova, e quadrado vazado é uma
    acusação — perder a corrente é melhor que inventá-la.

    Função pura e separada do I/O de propósito, pela mesma razão que
    `criterios.py`: é a regra que erra em silêncio, e um teste que passasse
    pelo PostgREST estaria testando o cliente, não a régua.
    """
    desde = min(
        (m["ativo_desde"] for m in matriculas if m.get("ativo_desde")),
        default=None,
    )
    if not matriculas:
        itens = [i for i in itens if i.get("presente")]
    elif desde:
        itens = [
            i
            for i in itens
            if i.get("presente") or (i.get("dataAplicacao") or "") >= desde
        ]
    return sorted(itens, key=lambda i: i.get("dataAplicacao") or "")


def _do_ano_letivo_corrente(itens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Os itens do ano letivo do simulado mais recente, na mesma ordem.

    O ano é o do CICLO (`anoLetivoId`, de `simulados_do_aluno`), e não o da
    data: o ano letivo é o que a escola diz que é. Mais recente e não "hoje"
    pela mesma razão de `_ciclo_corrente`: é a corrente que o aluno vê, e ela
    não se esvazia em fevereiro antes da primeira prova do ano novo.

    Item sem `anoLetivoId` — lista montada à mão, sem o embed do ciclo — deixa
    a lista inteira: sem como saber o ano, cortar seria inventar o recorte.
    """
    ano = next((i["anoLetivoId"] for i in reversed(itens) if i.get("anoLetivoId")), None)
    if ano is None:
        return itens
    return [i for i in itens if i.get("anoLetivoId") == ano]


def contar_sequencia(itens: list[dict[str, Any]]) -> tuple[int, int]:
    """(corrente, recorde) sobre itens já em ordem cronológica.

    Os dois cobrem o ANO INTEIRO, não o ciclo (docs/36 §1.3): recorde que zera
    na virada de ciclo não é recorde. E o ano é o ano LETIVO do simulado mais
    recente (`_do_ano_letivo_corrente`): até 25/10 a contagem corria o
    histórico inteiro, e quem tem nota de 2025 e de 2026 recebia um recorde de
    dois anos que o prompt do Tio Léo e o preâmbulo do turno chamam de
    "recorde do ano".
    """
    itens = _do_ano_letivo_corrente(itens)
    atual = 0
    for item in reversed(itens):
        if not item.get("presente"):
            break
        atual += 1

    melhor = corrida = 0
    for item in itens:
        corrida = corrida + 1 if item.get("presente") else 0
        melhor = max(melhor, corrida)
    return atual, melhor


def historico_com_presenca(
    cliente: Client, aluno_id: str, *, itens: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """Os simulados do aluno com a falta junto, já sob a regra de docs/36 §1.1.

    `itens` é `simulados_do_aluno(..., incluir_faltas=True)` já lido, para quem
    compõe várias leituras do aluno (`aluno_panorama.py`) não pagar a mesma
    leitura duas vezes. A regra é a mesma nos dois caminhos: `aplicar_regra_da_falta`
    não altera os itens, só filtra e ordena.
    """
    if itens is None:
        itens = simulados_do_aluno(cliente, aluno_id, incluir_faltas=True)
    return aplicar_regra_da_falta(itens, _matriculas_ativas(cliente, aluno_id))


# ─── Sequência (GET /me/jogo) ─────────────────────────────────────────────


def _ciclo_corrente(itens: list[dict[str, Any]]) -> str | None:
    """O ID do ciclo do simulado mais recente do aluno.

    ⚠️ ID e não `cicloOrdem`. A ordem se REPETE entre anos letivos — existe um
    ciclo 29 de 2025 e outro de 2026 —, e agrupar por ela colocava na mesma
    fita provas de setembro de 2025 e de setembro de 2026. Foi o que apareceu
    ao rodar a rota contra o banco de verdade, e nenhum teste de unidade pegaria:
    os dois ciclos são ordem 29, e a comparação estava certa para o campo errado.
    """
    for item in reversed(itens):
        if item.get("cicloId"):
            return item["cicloId"]
    return None


def sequencia_do_aluno(cliente: Client, aluno_id: str) -> dict[str, Any]:
    """Mesma resposta de GET /me/jogo.

    As duas janelas são diferentes de propósito (docs/36 §1.3): a FITA cobre o
    ciclo corrente, porque é o que cabe no cartão da Hoje; os dois NÚMEROS
    cobrem o ano inteiro, porque um recorde que zera na virada de ciclo não é
    recorde.
    """
    itens = historico_com_presenca(cliente, aluno_id)
    # O histórico já lido vai junto: sem ele, o próximo simulado o relia
    # inteiro só para achar a data da última prova feita.
    proximo = proximo_simulado_do_aluno(cliente, aluno_id, historico=itens)
    return sequencia_do_historico(itens, proximo)


def sequencia_do_historico(
    itens: list[dict[str, Any]], proximo: dict[str, Any] | None
) -> dict[str, Any]:
    """A resposta de `sequencia_do_aluno` a partir do que já foi lido — pura.

    `itens` é `historico_com_presenca`, em ordem cronológica; `proximo` é
    `proximo_simulado_do_aluno`. Separada para quem já tem as duas leituras
    (`aluno_panorama.py`) montar a mesma fita sem relê-las.
    """
    atual, melhor = contar_sequencia(itens)
    ciclo_id = _ciclo_corrente(itens)
    fita = [
        {
            "simuladoId": i["id"],
            "rotulo": i.get("rotulo") or i.get("nome") or "",
            "data": i.get("dataAplicacao"),
            "presente": bool(i.get("presente")),
        }
        for i in itens
        if ciclo_id is not None and i.get("cicloId") == ciclo_id
    ]

    # O elo anelado: o simulado que ainda vai acontecer. `presente: null` é
    # "ainda não aconteceu", que a tela desenha diferente de falta.
    if proximo:
        fita.append(
            {
                "simuladoId": None,
                "rotulo": proximo["rotulo"],
                "data": proximo["data"],
                "presente": None,
            }
        )

    return {"simulados": atual, "melhor": melhor, "corrente": fita}


# ─── Agenda (GET /me/agenda) ──────────────────────────────────────────────


def _anos_letivos_do_aluno(cliente: Client, aluno_id: str) -> set[str]:
    turma_ids = [m["turma_id"] for m in _matriculas_ativas(cliente, aluno_id)]
    if not turma_ids:
        return set()
    resp = (
        cliente.table("turma").select("id, ano_letivo_id").in_("id", turma_ids).execute()
    )
    return {t["ano_letivo_id"] for t in (resp.data or []) if t.get("ano_letivo_id")}


def proximo_simulado_do_aluno(
    cliente: Client,
    aluno_id: str,
    *,
    historico: list[dict[str, Any]] | None = None,
    hoje: date | None = None,
) -> dict[str, Any] | None:
    """Mesma resposta de GET /me/agenda — o próximo simulado, ou `None`.

    ⚠️ Só enxerga evento com `simulado` apontando para ele. `evento_agenda` não
    tem turma, sede nem vestibular: quem dá escopo ao evento é o simulado que o
    referencia (`simulado.evento_agenda_id`), pelo ciclo e pelo ano letivo. É
    exatamente o caminho que o motor de lembretes já percorre para decidir a
    audiência — então a tela passa a saber o que o e-mail sabia (docs/29 §A.1),
    nem mais nem menos. Evento sem simulado não alcança ninguém nos dois.

    ⚠️ "Hoje" é o dia da ESCOLA (`banco.missao.hoje_na_escola`, America/Fortaleza),
    e não `date.today()`: este dependia do fuso do container — produção roda
    com TZ=America/Fortaleza, o compose de desenvolvimento não —, e à noite a
    prova de hoje sumia da agenda em UTC. `hoje` existe para quem já fixou o dia
    (o panorama diz a data junto) e para o teste empurrar o relógio.

    `historico` é `historico_com_presenca` já lido, para quem o tem não pagar a
    mesma leitura de novo; sem ele, é lido aqui, como sempre.
    """
    anos = _anos_letivos_do_aluno(cliente, aluno_id)
    if not anos:
        return None

    ciclos = (
        cliente.table("ciclo")
        .select("id, vestibular_alvo")
        .in_("ano_letivo_id", list(anos))
        .execute()
    ).data or []
    if not ciclos:
        return None
    vestibular_por_ciclo = {c["id"]: c.get("vestibular_alvo") for c in ciclos}

    agendados = (
        cliente.table("simulado")
        .select("id, nome, rotulo_curto, tipo, ciclo_id, evento_agenda_id")
        .in_("ciclo_id", list(vestibular_por_ciclo))
        .not_.is_("evento_agenda_id", "null")
        .execute()
    ).data or []
    if not agendados:
        return None
    simulado_por_evento = {s["evento_agenda_id"]: s for s in agendados}

    dia = (hoje or hoje_na_escola()).isoformat()
    eventos = (
        cliente.table("evento_agenda")
        .select("id, titulo, data_evento")
        .in_("id", list(simulado_por_evento))
        .is_("cancelado_em", "null")
        .gte("data_evento", dia)
        .order("data_evento")
        .limit(1)
        .execute()
    ).data or []
    if not eventos:
        return None

    evento = eventos[0]
    simulado = simulado_por_evento[evento["id"]]

    # A barra da contagem regressiva mede o intervalo inteiro, então precisa do
    # ponto de partida: o último simulado que o aluno FEZ.
    if historico is None:
        historico = historico_com_presenca(cliente, aluno_id)
    feitos = [i for i in historico if i.get("presente")]
    anterior = feitos[-1].get("dataAplicacao") if feitos else None

    return {
        "id": evento["id"],
        "rotulo": simulado.get("rotulo_curto") or simulado.get("nome") or evento["titulo"],
        "data": evento["data_evento"],
        "vestibular": vestibular_por_ciclo.get(simulado.get("ciclo_id")),
        "fase": _FASE_POR_TIPO.get(simulado.get("tipo") or ""),
        "dataAnterior": anterior,
    }


def dias_ate(data: str | None, hoje: date) -> int | None:
    """Quantos dias de `hoje` até `data` (ISO), ou `None` sem data.

    Conta de calendário, e não regra: está aqui porque o modelo erra conta de
    data, e o Tio Léo diz "daqui a N dias" a partir do mesmo `hoje` com que a
    agenda foi lida — o dia da escola.
    """
    if not data:
        return None
    return (date.fromisoformat(str(data)[:10]) - hoje).days


# ─── Meta do ciclo (GET /me/meta) ─────────────────────────────────────────


def meta_do_ciclo_do_aluno(
    cliente: Client, aluno_id: str, *, historico: list[dict[str, Any]] | None = None
) -> dict[str, Any] | None:
    """Mesma resposta de GET /me/meta — a meta é presença (docs/36 §1.5).

    O alvo sai do CALENDÁRIO do ciclo, não do que o aluno fez: são todos os
    simulados marcados naquele ciclo. Contar só os que ele já viu faria a meta
    andar junto com o aluno e sempre parecer cumprida.

    `historico` é `historico_com_presenca` já lido (ver `proximo_simulado_do_aluno`).
    """
    itens = historico if historico is not None else historico_com_presenca(cliente, aluno_id)
    ciclo_id = _ciclo_corrente(itens)
    if not ciclo_id:
        return None

    do_ciclo = [i for i in itens if i.get("cicloId") == ciclo_id]

    do_calendario = (
        cliente.table("simulado")
        .select("id, anulado, e_agregado")
        .eq("ciclo_id", ciclo_id)
        .execute()
    ).data or []
    alvo = sum(1 for s in do_calendario if not s.get("anulado") and not s.get("e_agregado"))
    if not alvo:
        return None

    feitos = sum(1 for i in do_ciclo if i.get("presente"))
    return {
        "alvo": alvo,
        "feitos": feitos,
        "rotulo": f"Comparecer aos {alvo} simulados do ciclo",
    }
