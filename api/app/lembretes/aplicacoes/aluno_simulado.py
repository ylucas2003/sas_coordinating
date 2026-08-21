"""Lembrete de aluno — o digest da véspera (P3).

Três decisões desta aplicação, e todas as três são a razão de ela existir
separada do motor (docs/13 §1):

1. **Um e-mail por DIA, não por prova.** Em dia de três provas o aluno recebe
   uma mensagem com as três — 873 envios, não 2.6k. O disparo é por
   (aluno, dia) e pendura na regra ÂNCORA do dia (a do evento mais cedo).

2. **Materialização tardia.** A regra nasce no agendamento; os disparos, na
   véspera. O elenco de alunos de daqui a 40 dias não é o de hoje — matrícula
   entra, matrícula sai, e-mail é descoberto pelo sync. Materializar cedo é
   congelar uma lista errada.

3. **A guarda é sobre o DIA, não sobre o evento.** Cancelar uma das três
   provas tira a linha da lista; só quando o dia esvazia é que `preparar`
   devolve None e o disparo é cancelado sem sair nada.

A varredura é reconciliação, não "criar uma vez": roda em todo tick e
converge — cria o que falta, re-ancora o que perdeu a regra, cancela quem
saiu da audiência.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from supabase import Client

from ...config import get_settings
from .. import supressao
from ..descadastro import montar_link
from ..motor import FUSO_BRASIL, _ESTADOS_VIVOS
from . import Mensagem

CHAVE_PREFIXO = "aluno-dia"
DIAS_ANTES = 1          # fixo em P3; cadência (N disparos por regra) é P4
_LOTE_INSERT = 200      # o INSERT do PostgREST vai no corpo, mas mantém o log legível


# ─── Funções puras — o que os testes cobrem ──────────────────────────────


def chave_idempotencia(dia: date, aluno_id: str) -> str:
    """Identidade natural do disparo. Estável por (dia, aluno) de propósito:
    trocar o e-mail do aluno NÃO gera um segundo lembrete do mesmo dia."""
    return f"{CHAVE_PREFIXO}:{dia.isoformat()}:{aluno_id}"


def aluno_id_da_chave(chave: str) -> str | None:
    partes = (chave or "").split(":")
    return partes[2] if len(partes) == 3 and partes[0] == CHAVE_PREFIXO else None


def ocupa_chave(disparo: dict[str, Any]) -> bool:
    """O disparo ainda toma a chave dele no índice único da 0020?

    Espelha o `WHERE estado <> 'cancelado'` do índice — e é a regra da
    deduplicação da varredura. 'enviado' é terminal mas OCUPA: sem isso, o
    tick seguinte ao envio das 18:00 tentaria recriar o disparo de cada aluno
    e o INSERT quebraria a rodada pelo resto do dia.
    """
    return disparo.get("estado") != "cancelado"


def momento_envio(dia_evento: date, hora_lembrete: time) -> datetime:
    """Véspera, em hora FIXA (não a do evento) — é a janela de silêncio da
    decisão A8, reaberta na P3: prova às 7h mandaria e-mail às 7h da manhã, e
    prova à noite mandaria às 22h."""
    return datetime.combine(
        dia_evento - timedelta(days=DIAS_ANTES), hora_lembrete, tzinfo=FUSO_BRASIL
    )


def escolher_ancora(eventos: list[dict[str, Any]]) -> dict[str, Any]:
    """A regra do evento mais cedo do dia. Empate resolvido pelo id do evento
    — estável entre ticks, que é o que impede re-ancoragem em pingue-pongue."""
    return min(
        eventos,
        key=lambda e: (str(e["evento"].get("hora_evento") or ""), str(e["evento"]["id"])),
    )


def filtrar_audiencia(
    *,
    alunos: list[dict[str, Any]],
    matriculas: list[dict[str, Any]],
    turma_ids: set[str],
    invalidos: set[str],
) -> list[dict[str, str]]:
    """Alunos ativos, com matrícula ativa numa das turmas, com e-mail que
    ainda recebe. Pura: recebe as três tabelas já carregadas."""
    com_matricula = {
        m["aluno_id"]
        for m in matriculas
        if m.get("ativo_ate") is None and m.get("turma_id") in turma_ids
    }
    audiencia: dict[str, dict[str, str]] = {}
    for aluno in alunos:
        if aluno["id"] not in com_matricula or not aluno.get("ativo"):
            continue
        email = (aluno.get("email") or "").strip()
        if not email or supressao.normalizar(email) in invalidos:
            continue
        # dict por id: aluno com duas matrículas ativas não vira dois e-mails
        audiencia[aluno["id"]] = {
            "aluno_id": aluno["id"],
            "email": email,
            "nome": (aluno.get("nome") or "").strip(),
        }
    return list(audiencia.values())


def compor_digest(
    *, nome: str, dia: date, eventos: list[dict[str, Any]], link_descadastro: str
) -> Mensagem:
    """Assunto e corpo, compostos no INSTANTE do envio a partir dos eventos
    vivos do dia. Conteúdo mínimo de propósito: título, data e hora — é e-mail
    de menor de idade saindo em massa, sem nota e sem desempenho."""
    linhas = [
        f"  {str(e.get('hora_evento') or '')[:5]} · {e.get('titulo') or 'Simulado'}"
        for e in eventos
    ]
    data_br = dia.strftime("%d/%m/%Y")
    quantas = (
        "1 prova" if len(eventos) == 1 else f"{len(eventos)} provas"
    )
    primeiro_nome = (nome or "").split(" ")[0]
    saudacao = f"Olá, {primeiro_nome}." if primeiro_nome else "Olá."

    assunto = f"Simulados de amanhã ({dia.strftime('%d/%m')}) — {quantas}"
    corpo = (
        f"{saudacao}\n\n"
        f"Amanhã, {data_br}, você tem:\n\n"
        + "\n".join(linhas)
        + "\n\nBons estudos.\n\n"
        "— SAS · Colégio Ari de Sá\n"
        f"Não quer mais receber estes lembretes? {link_descadastro}"
    )
    return Mensagem(assunto=assunto, corpo=corpo)


# ─── Leitura do banco ────────────────────────────────────────────────────


def _hoje_brt() -> date:
    return datetime.now(timezone.utc).astimezone(FUSO_BRASIL).date()


def _hora_lembrete() -> time:
    return time.fromisoformat(get_settings().lembrete_aluno_hora)


def _eventos_do_dia(cliente: Client, dia: date) -> list[dict[str, Any]]:
    """Regras de aluno ATIVAS cujo evento é `dia` e não foi cancelado.

    É a lista que manda em tudo: nela se escolhe a âncora, dela se compõe o
    corpo, e o seu esvaziamento é a guarda.
    """
    resp = (
        cliente.table("regra_lembrete")
        .select(
            "id, evento_agenda_id, "
            "evento_agenda(id, titulo, data_evento, hora_evento, cancelado_em)"
        )
        .eq("destinatario_tipo", "aluno")
        .is_("cancelada_em", "null")
        .execute()
    )
    do_dia = []
    for regra in resp.data or []:
        evento = regra.get("evento_agenda") or {}
        if not evento or evento.get("cancelado_em"):
            continue
        if str(evento.get("data_evento")) != dia.isoformat():
            continue
        do_dia.append({"regra_id": regra["id"], "evento": evento})
    return sorted(
        do_dia, key=lambda e: (str(e["evento"].get("hora_evento") or ""), str(e["evento"]["id"]))
    )


def _anos_letivos_dos_eventos(cliente: Client, evento_ids: list[str]) -> set[str]:
    """evento → simulado → ciclo → ano letivo. É o único ponto em que esta
    aplicação toca o domínio de simulado — e é por isso que ela não mora no
    motor."""
    simulados = (
        cliente.table("simulado")
        .select("ciclo_id, evento_agenda_id")
        .in_("evento_agenda_id", evento_ids)
        .execute()
    ).data or []
    ciclo_ids = {s["ciclo_id"] for s in simulados if s.get("ciclo_id")}
    if not ciclo_ids:
        return set()
    ciclos = (
        cliente.table("ciclo")
        .select("id, ano_letivo_id")
        .in_("id", list(ciclo_ids))
        .execute()
    ).data or []
    return {c["ano_letivo_id"] for c in ciclos if c.get("ano_letivo_id")}


def resolver_audiencia(
    cliente: Client, *, ano_letivo_ids: set[str], invalidos: set[str]
) -> list[dict[str, str]]:
    """Alunos que recebem o lembrete dos simulados desses anos letivos.

    ⚠️ Carrega as tabelas inteiras e cruza em memória DE PROPÓSITO. Um
    `.in_()` com ~900 ids vai na query string do PostgREST e estoura o limite
    de URL — mesmo motivo pelo qual routes/alunos.py monta os mapas assim.
    São milhares de linhas, não milhões.
    """
    if not ano_letivo_ids:
        return []
    turmas = (
        cliente.table("turma")
        .select("id, ano_letivo_id")
        .in_("ano_letivo_id", list(ano_letivo_ids))
        .execute()
    ).data or []
    turma_ids = {t["id"] for t in turmas}
    if not turma_ids:
        return []

    matriculas = (
        cliente.table("matricula_turma")
        .select("aluno_id, turma_id, ativo_ate")
        .is_("ativo_ate", "null")
        .execute()
    ).data or []
    alunos = (
        cliente.table("aluno")
        .select("id, nome, email, ativo")
        .eq("ativo", True)
        .execute()
    ).data or []

    return filtrar_audiencia(
        alunos=alunos, matriculas=matriculas, turma_ids=turma_ids, invalidos=invalidos
    )


def _disparos_do_dia(cliente: Client, dia: date) -> list[dict[str, Any]]:
    """Todo disparo do dia que ainda OCUPA a chave — inclusive 'enviado'.

    ⚠️ Não filtrar por _ESTADOS_VIVOS aqui: 'enviado' é terminal mas continua
    ocupando a chave no índice único (que só ignora 'cancelado'). Deduplicar
    só contra os vivos faria a varredura tentar recriar, depois do envio das
    18:00, o disparo de cada aluno — e o INSERT quebraria o tick pelo resto do
    dia. Espelhar o índice é a regra.

    Filtro por prefixo da chave (coluna de texto) em vez de operador jsonb: a
    query string do PostgREST já cobrou caro uma vez (armadilha 2 da P2).
    """
    return [
        d
        for d in (
            cliente.table("disparo")
            .select("id, regra_lembrete_id, destinatario, chave_idempotencia, estado")
            .like("chave_idempotencia", f"{CHAVE_PREFIXO}:{dia.isoformat()}:%")
            .execute()
        ).data
        or []
        if ocupa_chave(d)
    ]


def _cancelar(cliente: Client, ids: list[str]) -> None:
    if not ids:
        return
    cliente.table("disparo").update(
        {
            "estado": "cancelado",
            "atualizado_em": datetime.now(timezone.utc).isoformat(),
        }
    ).in_("id", ids).execute()


# ─── Os dois hooks do registry ───────────────────────────────────────────


def materializar(cliente: Client) -> dict[str, Any]:
    """Varredura da véspera — roda em todo tick e CONVERGE.

    Não é "criar uma vez": é reconciliar o estado desejado (um disparo vivo
    por aluno da audiência) com o que existe. Rodar duas vezes não duplica
    (índice único na chave); rodar depois de um remarque conserta.
    """
    settings = get_settings()
    if not settings.lembrete_aluno_ativo:
        return {"status": "desligado"}

    dia = _hoje_brt() + timedelta(days=DIAS_ANTES)
    eventos = _eventos_do_dia(cliente, dia)
    # `ocupados` espelha o índice único (tudo que não é 'cancelado') e serve
    # pra deduplicar; `vivos` é o subconjunto que ainda pode mudar de estado.
    # E-mail já enviado é histórico: não se re-ancora nem se cancela.
    ocupados = _disparos_do_dia(cliente, dia)
    vivos = [d for d in ocupados if d.get("estado") in _ESTADOS_VIVOS]
    resultado = {"dia": dia.isoformat(), "criados": 0, "cancelados": 0, "reancorados": 0}

    if not eventos:
        # O dia esvaziou (cancelado ou remarcado) — o que estiver de pé morre.
        _cancelar(cliente, [d["id"] for d in vivos])
        resultado["cancelados"] = len(vivos)
        return resultado

    ancora = escolher_ancora(eventos)
    regras_do_dia = {e["regra_id"] for e in eventos}

    # Re-ancoragem: disparo cujo dono não é mais uma regra viva do dia passa a
    # pertencer à âncora atual. Sem isso, cancelar a primeira prova do dia
    # deixaria o digest pendurado numa regra morta.
    orfaos = [d["id"] for d in vivos if d["regra_lembrete_id"] not in regras_do_dia]
    if orfaos:
        cliente.table("disparo").update(
            {"regra_lembrete_id": ancora["regra_id"]}
        ).in_("id", orfaos).execute()
        resultado["reancorados"] = len(orfaos)

    invalidos = supressao.carregar_invalidos(cliente)
    ano_letivo_ids = _anos_letivos_dos_eventos(
        cliente, [e["evento"]["id"] for e in eventos]
    )
    audiencia = resolver_audiencia(
        cliente, ano_letivo_ids=ano_letivo_ids, invalidos=invalidos
    )

    ja_tem = {aluno_id_da_chave(d.get("chave_idempotencia") or "") for d in ocupados}
    enviar_em = momento_envio(dia, _hora_lembrete()).isoformat()

    novos = [
        {
            "regra_lembrete_id": ancora["regra_id"],
            "destinatario": alvo["email"],
            "canal": "email",
            "enviar_em": enviar_em,
            "chave_idempotencia": chave_idempotencia(dia, alvo["aluno_id"]),
            "contexto": {
                "dia": dia.isoformat(),
                "aluno_id": alvo["aluno_id"],
                "nome": alvo["nome"],
            },
        }
        for alvo in audiencia
        if alvo["aluno_id"] not in ja_tem
    ]
    for inicio in range(0, len(novos), _LOTE_INSERT):
        cliente.table("disparo").insert(novos[inicio : inicio + _LOTE_INSERT]).execute()
    resultado["criados"] = len(novos)

    # Quem saiu da audiência depois de materializado (trocou de turma, saiu do
    # colégio, e-mail queimou) não recebe.
    na_audiencia = {a["aluno_id"] for a in audiencia}
    sobrando = [
        d["id"]
        for d in vivos
        if aluno_id_da_chave(d.get("chave_idempotencia") or "") not in na_audiencia
    ]
    _cancelar(cliente, sobrando)
    resultado["cancelados"] = len(sobrando)
    return resultado


def preparar(
    cliente: Client, *, regra: dict[str, Any], disparo: dict[str, Any]
) -> Mensagem | None:
    """Guarda + composição, no instante do envio.

    O dia vem do CONTEXTO do disparo, não da regra âncora: a regra pode ter
    sido remarcada pra outro dia entre a materialização e o envio, e o e-mail
    é sobre o dia, não sobre a regra.
    """
    contexto = disparo.get("contexto") or {}
    dia_txt = str(contexto.get("dia") or "")
    if not dia_txt:
        # Rede: a chave carrega o mesmo dia ('aluno-dia:{dia}:{aluno_id}').
        partes = (disparo.get("chave_idempotencia") or "").split(":")
        dia_txt = partes[1] if len(partes) == 3 else ""
    try:
        dia = date.fromisoformat(dia_txt)
    except ValueError:
        return None

    eventos = [e["evento"] for e in _eventos_do_dia(cliente, dia)]
    if not eventos:
        return None   # o dia esvaziou — nada sai, e o disparo vira 'cancelado'

    return compor_digest(
        nome=str(contexto.get("nome") or ""),
        dia=dia,
        eventos=eventos,
        link_descadastro=montar_link(disparo["destinatario"]),
    )
