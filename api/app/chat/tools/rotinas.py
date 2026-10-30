"""Tools das rotinas automáticas — sync do Canvas, gravações e lembretes (docs/43 §4.3).

São as partes do SAS que trabalham sozinhas, e por isso as que ninguém vê
parar: o sync de 5 em 5 minutos, a escrita SAS → Canvas, a publicação das
aulas gravadas e o motor de lembretes. A coordenação só descobria um problema
quando um aluno reclamava; estas tools respondem "está funcionando?" com o
mesmo dado que as telas e o /health/ready leem.

  estado_do_sync_canvas       a integração inteira: último sync, rodadas, escrita pendente
  pendencias_canvas_do_ciclo  o que de UM ciclo ainda não está no Canvas
  estado_das_gravacoes        Canvas → YouTube → página da aula
  lembretes_agendados         o que o motor de lembretes vai mandar, e se pode

Quatro regras valem para tudo aqui:

  * ERRO DE ROTINA é o `str(exc)` gravado no banco (canvas_erro,
    erro_mensagem, erro_detalhe) e pode trazer a URL do PostgREST ou do
    Canvas: sai SEMPRE por `texto_seguro` (docs/43 §3.2, invariante 6);
  * TABELA DE LOG (`canvas_sync_execucao`, `disparo`) só se lê com order +
    limit, ou como contagem (`count` + limit 1): uma linha por rodada de 5
    min, ~288 por dia, e nenhuma poda no código;
  * TIMESTAMPTZ em filtro vai no formato 'Z' (`despachante.filtro_ts`): o
    '+' de '+00:00' viraria espaço na URL e o Postgres recusaria;
  * ID que vai a coluna uuid é conferido ANTES da consulta (`_uuid`): torto,
    ele vira 22P02 no PostgREST, e o despacho responde a qualquer exceção com
    "falhou do nosso lado, não repita" — o modelo diria "indisponível" quando
    quem errou foi o id.

Da linha de `disparo` sai só contagem, nunca linha: ela guarda o e-mail do
destinatário, o corpo com o primeiro nome do aluno e o contexto com o nome
(lembretes/aplicacoes/aluno_simulado.py). Da gravação nunca sai link: o vídeo é
NÃO LISTADO e tem aluno menor de idade — o link é o acesso (consulta.py).

As quatro vão ao MCP desde 30/10: a decisão de 24/10 as deixava fora (docs/43
§6), e a coordenação a reverteu. O que muda por isso, e só isso:

  * o `sas_mcp` lê coluna por coluna (0074), e essas regras viraram piso no
    banco: `disparo` sem destinatário, corpo nem contexto; `evento_agenda` sem
    `criado_por`; a aula só por `aula_gravacao_para_ia`, sem link e com o erro
    já sem o id do vídeo;
  * `lembretes_agendados` lê o ambiente da API, que o processo do MCP não tem,
    e lá diz que não sabe em vez de repetir o valor de fábrica
    (chat/superficie.py).

Só `pendencias_canvas_do_ciclo` devolve nome de aluno, sempre com `alunoId` ao
lado: passa pelo pseudônimo.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from supabase import Client

from ...canvas_sync import agendamento, pendencias
from ...canvas_sync import estado as estado_do_sync
from ...canvas_sync.escrita import DIVERGENTE
from ...config import get_settings
from ...gravacoes_aula import consulta as gravacoes
from ...gravacoes_aula import regras_da_rodada
from ...lembretes import despachante, motor
from ...lembretes import email as email_ses
from ...lembretes.aplicacoes import aluno_simulado
from ...texto_seguro import texto_seguro
from .. import superficie

#: Uma linha de diagnóstico dentro de uma resposta, não o log: o texto inteiro
#: continua no banco para quem depura.
LIMITE_DO_TEXTO = 160
MAX_EXEMPLOS = 5

TETO_DE_EXECUCOES = 10
TETO_DE_NOTAS_PENDENTES = 30
TETO_DE_SIMULADOS_PENDENTES = 10
TETO_DE_AULAS = 30
TETO_DE_DIAS = 30
TETO_DE_EVENTOS = 50


def _erro(texto: Any) -> str | None:
    return texto_seguro(texto, LIMITE_DO_TEXTO) or None


def _uuid(valor: Any, campo: str, onde_achar: str) -> tuple[str | None, dict[str, str] | None]:
    """O id normalizado, ou o erro de argumento que o modelo lê (revisão
    paralela de 25/10). O mesmo que `historico_de_alteracoes` já fazia
    (trilha.py), com a dica de onde achar o id certo."""
    try:
        return str(uuid.UUID(str(valor).strip())), None
    except ValueError:
        return None, {"erro": f"{campo} deve ser um UUID; {onde_achar}"}


def _contar(consulta: Any) -> int:
    """Quantas linhas, sem trazer nenhuma: `count='exact'` com uma linha só —
    o mesmo truque do teto diário do despachante (`enviados_nas_ultimas_24h`)."""
    resposta = consulta.limit(1).execute()
    if resposta.count is not None:
        return int(resposta.count)
    return len(resposta.data or [])


# ─── estado_do_sync_canvas ───────────────────────────────────────────────


def estado_do_sync_canvas(cliente: Client, *, limite: int = 5) -> dict:
    """O sync do Canvas está fazendo o trabalho dele, e o que não subiu."""
    limite = min(max(1, limite), TETO_DE_EXECUCOES)
    agora = datetime.now(UTC)

    # A regra do "atrasado" é a do /health/ready, num lugar só
    # (canvas_sync/estado.py): copiar os 30 minutos seria a segunda definição.
    saida: dict[str, Any] = dict(estado_do_sync.ultimo_sync(cliente, agora))

    execucoes = (
        cliente.table("canvas_sync_execucao")
        .select("tipo, status, iniciado_em, finalizado_em, resumo, erro_mensagem")
        .order("iniciado_em", desc=True)
        .limit(limite)
        .execute()
        .data
        or []
    )
    saida["errosNasUltimas24h"] = _contar(
        cliente.table("canvas_sync_execucao")
        .select("id", count="exact")
        .eq("status", "erro")
        .gte("iniciado_em", despachante.filtro_ts(agora - timedelta(hours=24)))
    )
    saida["execucoes"] = [_execucao(e) for e in execucoes]
    saida["escritaNoCanvas"] = _escrita_pendente(cliente)
    return saida


def _execucao(linha: dict[str, Any]) -> dict[str, Any]:
    # `resumo` é jsonb: o formato é o de `como_dict`, mas nada no banco o garante.
    resumo = linha.get("resumo") if isinstance(linha.get("resumo"), dict) else {}
    avisos = resumo.get("avisos") if isinstance(resumo.get("avisos"), list) else []
    return {
        "tipo": linha.get("tipo"),
        "status": linha.get("status"),
        "iniciadoEm": linha.get("iniciado_em"),
        "finalizadoEm": linha.get("finalizado_em"),
        # As contagens de `ResumoSincronizacao.como_dict` (sincronizar.py),
        # sem os zeros: são dez números por rodada, e o zero não informa.
        "numeros": {
            chave: valor
            for chave, valor in resumo.items()
            if isinstance(valor, int) and not isinstance(valor, bool) and valor
        },
        "nAvisos": len(avisos),
        # Aviso cita nome de section e de assignment digitado no Canvas, e
        # alguns embutem a exceção: é texto de fora, e sai limpo.
        "avisos": [texto_seguro(aviso, LIMITE_DO_TEXTO) for aviso in avisos[:3]],
        "erro": _erro(linha.get("erro_mensagem")),
    }


def _escrita_pendente(cliente: Client) -> dict[str, Any]:
    """O que o SAS criou e o Canvas ainda não tem, separado como o retry o vê.

    'pendente' e 'falhou' tentam de novo sozinhos enquanto as tentativas não
    passam de `agendamento.MAX_TENTATIVAS`; daí em diante só pelo botão
    (canvas_sync/agendamento.py). 'divergente' é escolha do coordenador.
    """
    simulados = (
        cliente.table("simulado")
        .select("id, nome, rotulo_curto, canvas_estado, canvas_tentativas, canvas_erro")
        .eq("origem", "sas")
        .in_("canvas_estado", ["pendente", "falhou", DIVERGENTE])
        .execute()
        .data
        or []
    )
    desistiu, tentando, divergentes = [], [], []
    for s in simulados:
        if s.get("canvas_estado") == DIVERGENTE:
            divergentes.append(s)
        elif (s.get("canvas_tentativas") or 0) >= agendamento.MAX_TENTATIVAS:
            desistiu.append(s)
        else:
            tentando.append(s)

    ciclos = (
        cliente.table("ciclo")
        .select("id, nome, canvas_estado")
        .in_("canvas_estado", ["falhou", DIVERGENTE])
        .execute()
        .data
        or []
    )

    exemplos = [
        {
            "id": s["id"],
            "nome": s.get("rotulo_curto") or s.get("nome"),
            "situacao": situacao,
            "tentativas": s.get("canvas_tentativas") or 0,
            "erro": _erro(s.get("canvas_erro")),
        }
        # Quem desistiu primeiro: é o único caso que precisa de alguém.
        for situacao, grupo in (("desistiu", desistiu), ("tentando", tentando), ("divergente", divergentes))
        for s in grupo
    ]
    return {
        "simulados": {
            "tentandoDeNovo": len(tentando),
            "desistiu": len(desistiu),
            "divergente": len(divergentes),
            "exemplos": exemplos[:MAX_EXEMPLOS],
        },
        "ciclos": {
            "falhou": sum(1 for c in ciclos if c.get("canvas_estado") == "falhou"),
            "divergente": sum(1 for c in ciclos if c.get("canvas_estado") == DIVERGENTE),
            "exemplos": [
                {"id": c["id"], "nome": c.get("nome"), "estado": c.get("canvas_estado")}
                for c in ciclos[:MAX_EXEMPLOS]
            ],
        },
    }


_SCHEMA_SYNC = {
    "name": "estado_do_sync_canvas",
    "description": (
        "Quando usar: 'o Canvas está sincronizando?', 'por que a nota do P22 não apareceu?', "
        "'quando foi o último sync?', 'tem simulado que não subiu para o Canvas?'. Mostra a "
        "integração inteira; para um ciclo só, use pendencias_canvas_do_ciclo.\n"
        "Antes de chamar, confirme: nada — a tool não tem argumento obrigatório.\n"
        "Definições: o SAS lê o Canvas sozinho a cada 5 minutos (rodada 'incremental'); "
        "'backfill' inclui o recálculo completo da madrugada. atrasado = nenhuma rodada com "
        "sucesso há mais de limiteMinutos, e aí as notas param de chegar. avisos = o que a "
        "rodada pulou (assignment fora do padrão, quiz sem resposta): não é erro. Escrita SAS "
        "→ Canvas: tentandoDeNovo = vai sozinho na próxima rodada; desistiu = esgotou as "
        "tentativas e precisa do botão na tela; divergente = o coordenador escolheu não "
        "mandar, não é falha.\n"
        "Exemplo: estado_do_sync_canvas() → 'último sync bem-sucedido há 4 min; 2 rodadas com "
        "erro nas últimas 24 h; 1 simulado desistiu de subir'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limite": {
                "type": "integer",
                "default": 5,
                "description": f"Quantas rodadas recentes detalhar, até {TETO_DE_EXECUCOES}.",
            },
        },
        "required": [],
    },
}


# ─── pendencias_canvas_do_ciclo ──────────────────────────────────────────


def pendencias_canvas_do_ciclo(cliente: Client, *, ciclo_id: str, limite: int = 10) -> dict:
    """O que deste ciclo não está refletido no Canvas — a lista do envio em lote."""
    ciclo_id, erro = _uuid(ciclo_id, "ciclo_id", "descubra-o com listar_ciclos")
    if erro:
        return erro
    p = pendencias.pendencias_do_ciclo(cliente, ciclo_id)
    if p is None:
        return {"erro": f"ciclo {ciclo_id} não encontrado"}
    limite = min(max(1, limite), TETO_DE_NOTAS_PENDENTES)

    notas = p["notas"]
    # `notas` já vem cortada no teto do lote; o resto é `notasAlemDoTeto`.
    total_de_notas = len(notas) + p["notasAlemDoTeto"]
    return {
        "cicloId": p["cicloId"],
        "nome": p["nome"],
        "grupo": {
            "pendente": p["grupo"]["pendente"],
            "estado": p["grupo"]["estado"],
            "erro": _erro(p["grupo"]["erro"]),
        },
        "totalSimulados": len(p["simulados"]),
        "simulados": [
            {"id": s["id"], "nome": s["nome"], "estado": s["estado"], "erro": _erro(s["erro"])}
            for s in p["simulados"][:TETO_DE_SIMULADOS_PENDENTES]
        ],
        "totalNotas": total_de_notas,
        "notas": [
            {
                "alunoId": n["alunoId"],
                "alunoNome": n["aluno"],
                "simuladoId": n["simuladoId"],
                "simulado": n["simulado"],
                "noSas": n["noSas"],
                "noCanvas": n["noCanvas"],
            }
            for n in notas[:limite]
        ],
        "nadaPendente": not p["grupo"]["pendente"] and not p["simulados"] and total_de_notas == 0,
    }


_SCHEMA_PENDENCIAS = {
    "name": "pendencias_canvas_do_ciclo",
    "description": (
        "Quando usar: 'o que deste ciclo ainda não está no Canvas?', 'tem nota editada no SAS "
        "que o Canvas não tem?'.\n"
        "Antes de chamar, confirme: o ciclo_id (listar_ciclos).\n"
        "Definições: grupo = o Assignment Group do ciclo no Canvas. simulados = os criados no "
        "SAS que ainda não estão lá. notas = editadas no SAS (noSas) e diferentes do Canvas "
        "(noCanvas); totalNotas pode ser maior que a lista. Nada sobe sozinho: quem envia é o "
        "coordenador, pelo botão da ficha do ciclo. Esta tool só lê — nunca diga que enviou.\n"
        "Exemplo: pendencias_canvas_do_ciclo(ciclo_id='…') → 'o grupo existe; 1 simulado "
        "falhou ao subir; 14 notas editadas no SAS ainda não estão no Canvas'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "ciclo_id": {"type": "string", "description": "UUID do ciclo (listar_ciclos)."},
            "limite": {
                "type": "integer",
                "default": 10,
                "description": f"Quantas notas divergentes nomear, até {TETO_DE_NOTAS_PENDENTES}.",
            },
        },
        "required": ["ciclo_id"],
    },
}


# ─── estado_das_gravacoes ────────────────────────────────────────────────

#: O que pede mão humana na página da aula (CHECK da 0035): 'ignorado' é a
#: publicação desligada para o curso, e 'pendente' é a rodada que ainda vem.
_CANVAS_COM_PROBLEMA = ("falhou", "ambiguo", "conflito")

#: O `Failing row contains (…)` do Postgres despeja a LINHA inteira da aula na
#: mensagem de erro — id do vídeo, bucket e chave do S3, justamente o que a
#: leitura nunca seleciona (consulta.py, `_CAMPOS`). Fica só o rótulo, e dali
#: até o FIM do texto tudo sai: o Postgres escreve os valores sem aspas, e um
#: título com parêntese solto ("Aula 3 :)") ou aninhado ("Aula (parte (1))")
#: engana qualquer pareamento — o de um nível, que vinha antes, deixava passar
#: o resto da linha, com o S3 e o vídeo (correção da revisão paralela, 26/10).
#: Perde-se a cauda do APIError (`hint`, `message`); o texto inteiro continua
#: no banco para quem depura.
_LINHA_DESPEJADA = re.compile(r"(Failing row contains )\(.*", re.S)


def estado_das_gravacoes(
    cliente: Client,
    *,
    curso_id: str | None = None,
    so_problemas: bool = True,
    limite: int = 10,
) -> dict:
    """A rotina gravação do Canvas → YouTube → página da aula, como a tela a lê.

    O painel vem com o erro INTEIRO (`limite_do_erro=None`): a tela recebe os
    300 primeiros caracteres, e limpar depois desse corte deixaria passar meia
    credencial — `texto_seguro` limpa antes de cortar, e o corte daqui é o
    dele (`_erro_da_aula`). E vem da view (`para_ia=True`): a tool nem pede a
    coluna do link, nem no chat, para ter um caminho só."""
    painel = gravacoes.painel(cliente, limite_do_erro=None, para_ia=True)
    cursos = {str(c["cursoId"]): c for c in painel["cursos"]}
    aulas = painel["aulas"]
    if curso_id:
        if str(curso_id) not in cursos:
            return {
                "erro": (
                    f"o curso {curso_id} não é monitorado. Os que são: "
                    + ", ".join(f"{c['nome']} ({cid})" for cid, c in cursos.items())
                )
            }
        aulas = [a for a in aulas if str(a["cursoId"]) == str(curso_id)]

    corte = datetime.now(UTC) - timedelta(hours=regras_da_rodada.HORAS_ATE_ORFAO)
    lista = []
    com_problema = 0
    for aula in aulas:
        motivos = _motivos(aula, corte)
        com_problema += bool(motivos)
        if so_problemas and not motivos:
            continue
        lista.append(_aula(aula, cursos, motivos))

    limite = min(max(1, limite), TETO_DE_AULAS)
    por_situacao = Counter(a["situacao"] for a in aulas)
    return {
        "totalAulas": len(aulas),
        "porSituacao": {s: por_situacao.get(s, 0) for s in gravacoes.SITUACOES},
        "porCanvasEstado": dict(Counter(a["canvasEstado"] for a in aulas).most_common()),
        "comProblema": com_problema,
        "mostradas": min(len(lista), limite),
        "truncado": len(lista) > limite,
        "aulas": lista[:limite],
        "cursos": [
            {
                "cursoId": cid,
                "nome": c["nome"],
                "ativo": c["ativo"],
                "publicarNoCanvas": c["publicarNoCanvas"],
            }
            for cid, c in cursos.items()
        ],
    }


def _motivos(aula: dict[str, Any], corte: datetime) -> list[str]:
    """Por que esta aula pede atenção — cada motivo com a regra de onde sai.

    As regras são as da rodada (gravacoes_aula/regras_da_rodada.py), as mesmas
    que o pipeline usa: 'desistiu' é erro que a rodada não pega mais, e
    'parada' é intermediário que a rodada considera órfão.
    'publicado_sem_confirmacao' é terminal de propósito — reprocessar geraria
    segunda cópia de vídeo de menores.
    """
    motivos = []
    status = aula["status"]
    if status == "erro":
        desistiu = (aula.get("tentativas") or 0) >= regras_da_rodada.MAX_TENTATIVAS
        motivos.append("desistiu" if desistiu else "erro")
    elif status == "publicado_sem_confirmacao":
        motivos.append("sem_confirmacao")
    elif status in (
        *regras_da_rodada.STATUS_INTERMEDIARIOS,
        "publicando",
    ) and regras_da_rodada.mais_velho_que(aula.get("atualizadoEm"), corte):
        motivos.append("parada")
    if aula.get("canvasEstado") in _CANVAS_COM_PROBLEMA:
        motivos.append(f"canvas_{aula['canvasEstado']}")
    # Página publicada sem módulo: existe, mas o aluno não a acha, porque é
    # por módulo que ele navega (consulta.py; `foraDeModulo` em
    # web/src/dominio/gravacoes.ts).
    if aula.get("canvasEstado") == "publicado" and not aula.get("canvasModulo"):
        motivos.append("fora_de_modulo")
    return motivos


def _aula(aula: dict[str, Any], cursos: dict[str, dict], motivos: list[str]) -> dict[str, Any]:
    """A aula sem link nenhum: youtubeUrl, youtubeVideoId e canvasUrl ficam de
    fora (vídeo não listado com menores), e youtubeTitulo também — o título da
    aula já identifica, sem repetir o nome do professor duas vezes."""
    curso = cursos.get(str(aula["cursoId"])) or {}
    return {
        "id": aula["id"],
        "titulo": aula.get("titulo"),
        "curso": curso.get("nome"),
        "iniciadaEm": aula.get("iniciadaEm"),
        "status": aula["status"],
        "situacao": aula["situacao"],
        "tentativas": aula.get("tentativas") or 0,
        "canvasEstado": aula.get("canvasEstado"),
        "motivos": motivos,
        "erro": _erro_da_aula(aula.get("erroDetalhe")),
        "erroNoCanvas": _erro_da_aula(aula.get("canvasErro")),
    }


def _erro_da_aula(texto: str | None) -> str | None:
    """O erro da aula sem a linha despejada, e só então limpo e cortado.

    `texto_seguro` tira URL e credencial, não id de vídeo solto. Em
    'publicado_sem_confirmacao' o erro é o da escrita que não gravou o id
    (gravacoes_aula/rotas.py), e o Postgres cita a linha inteira no `Failing row
    contains (…)` — com o id, que sozinho abre o vídeo não listado
    (`youtu.be/<id>`). Os dois saem antes da limpeza (revisão paralela de 25/10).

    Quem tira o id é a view da 0074, que é a única que o enxerga: aqui ele já
    chega como `[vídeo]`, porque o MCP não pode ler a coluna do id nem para
    apagá-lo do texto. O corte da linha continua aqui além de lá: é o último
    passo antes de o texto sair, e cortar de novo não muda nada.
    """
    if not texto:
        return None
    return _erro(_LINHA_DESPEJADA.sub(r"\1(…)", texto))


_SCHEMA_GRAVACOES = {
    "name": "estado_das_gravacoes",
    "description": (
        "Quando usar: 'as aulas de ontem já estão no YouTube?', 'alguma gravação deu erro?', "
        "'a aula de Física apareceu no Canvas?'. Acompanha a rotina gravação do Canvas → "
        "YouTube → página da aula no Canvas.\n"
        "Antes de chamar, confirme: curso_id só se a pessoa falou de um curso; o id aparece em "
        "`cursos` desta mesma resposta.\n"
        "Definições: situacao aguardando = a gravação ainda não ficou pronta; na_fila = espera "
        "a rodada de hora em hora; processando = baixando, compondo ou enviando (45 a 90 "
        "min); publicado = está no YouTube; erro = falhou e tenta de novo. motivos: desistiu "
        "= esgotou as tentativas e precisa de alguém; sem_confirmacao = o vídeo subiu e o "
        "banco não confirmou — nunca sugira reprocessar, geraria uma segunda cópia; parada = "
        "etapa intermediária sem avançar há horas; canvas_ambiguo e canvas_conflito pedem mão "
        "humana; fora_de_modulo = a página existe, mas o aluno não a encontra. O link do "
        "vídeo não vem, de propósito: são aulas com alunos menores.\n"
        "Exemplo: estado_das_gravacoes() → '38 aulas: 35 no YouTube, 1 processando, 2 com "
        "erro — uma já desistiu'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "curso_id": {
                "type": "string",
                "description": "Id do curso do Canvas como aparece em `cursos` desta tool. Omitido, todos.",
            },
            "so_problemas": {
                "type": "boolean",
                "default": True,
                "description": "true lista só as aulas que pedem atenção; as contagens vêm sempre.",
            },
            "limite": {"type": "integer", "default": 10, "description": f"Quantas aulas listar, até {TETO_DE_AULAS}."},
        },
        "required": [],
    },
}


# ─── lembretes_agendados ─────────────────────────────────────────────────

_COLUNAS_DO_EVENTO = "id, titulo, data_evento, hora_evento, cancelado_em"


def lembretes_agendados(
    cliente: Client, *, dias: int = 7, simulado_id: str | None = None, limite: int = 30
) -> dict:
    """O que o motor de lembretes vai mandar na janela, e se ele pode mandar.

    Só contagem e horário. Nada de `disparo` sai em linha (destinatário,
    corpo e contexto têm e-mail e nome), e `evento_agenda.criado_por` — que é
    o e-mail de quem agendou (0018) — não é nem selecionado.
    """
    if simulado_id:
        simulado_id, erro = _uuid(
            simulado_id, "simulado_id",
            "chame lembretes_agendados sem ele e use o simuladoId da resposta",
        )
        if erro:
            return erro
    dias = min(max(0, dias), TETO_DE_DIAS)
    limite = min(max(1, limite), TETO_DE_EVENTOS)
    agora = datetime.now(UTC)
    hoje = agora.astimezone(motor.FUSO_BRASIL).date()

    # O que sai do ambiente do processo só vale no processo que manda o e-mail:
    # no do MCP, `get_settings()` devolve o valor de fábrica (chat/superficie.py).
    configuracao, hora_do_aluno = _configuracao_de_envio(cliente)

    if simulado_id:
        simulado = (
            cliente.table("simulado")
            .select("id, nome, rotulo_curto, evento_agenda_id")
            .eq("id", simulado_id)
            .limit(1)
            .execute()
            .data
        )
        if not simulado:
            return {"erro": f"simulado {simulado_id} não encontrado"}
        if not simulado[0].get("evento_agenda_id"):
            return {
                "configuracao": configuracao,
                "eventos": [],
                "aviso": "Esse simulado não foi agendado pelo SAS: não tem lembrete.",
            }
        eventos = (
            cliente.table("evento_agenda")
            .select(_COLUNAS_DO_EVENTO)
            .eq("id", simulado[0]["evento_agenda_id"])
            .execute()
            .data
            or []
        )
    else:
        eventos = (
            cliente.table("evento_agenda")
            .select(_COLUNAS_DO_EVENTO)
            .gte("data_evento", hoje.isoformat())
            .lte("data_evento", (hoje + timedelta(days=dias)).isoformat())
            .order("data_evento")
            .order("hora_evento")
            .execute()
            .data
            or []
        )

    total_de_eventos = len(eventos)
    eventos = eventos[:limite]
    ids = [e["id"] for e in eventos]
    simulados = (
        cliente.table("simulado")
        .select("id, nome, rotulo_curto, evento_agenda_id")
        .in_("evento_agenda_id", ids)
        .execute()
        .data
        or []
    ) if ids else []
    regras = (
        cliente.table("regra_lembrete")
        .select("id, evento_agenda_id, destinatario_tipo, dias_antes, cancelada_em")
        .in_("evento_agenda_id", ids)
        .execute()
        .data
        or []
    ) if ids else []

    simulado_do_evento = {s["evento_agenda_id"]: s for s in simulados}
    regras_do_evento: dict[str, list[dict[str, Any]]] = {}
    for regra in regras:
        regras_do_evento.setdefault(regra["evento_agenda_id"], []).append(regra)

    saida_eventos = []
    dias_com_aluno: set[date] = set()
    for evento in eventos:
        dia = date.fromisoformat(str(evento["data_evento"]))
        hora = time.fromisoformat(str(evento["hora_evento"]))
        sim = simulado_do_evento.get(evento["id"]) or {}
        lembretes = []
        for regra in regras_do_evento.get(evento["id"], []):
            cancelado = bool(regra.get("cancelada_em"))
            if regra["destinatario_tipo"] == "aluno":
                # Véspera, em hora fixa, um e-mail por aluno por DIA — o
                # horário é o da aplicação do aluno, não o do evento.
                lembretes.append({
                    "para": "alunos", "enviarEm": _envio_aos_alunos(dia, hora_do_aluno), "cancelado": cancelado,
                })
                if not cancelado and not evento.get("cancelado_em"):
                    dias_com_aluno.add(dia)
            else:
                enviar_em = motor.calcular_enviar_em(dia, hora, int(regra.get("dias_antes") or 0))
                lembretes.append({
                    "para": regra["destinatario_tipo"],
                    "diasAntes": regra.get("dias_antes"),
                    "enviarEm": enviar_em.isoformat(),
                    "cancelado": cancelado,
                })
        saida_eventos.append({
            "eventoId": evento["id"],
            "titulo": evento.get("titulo"),
            "data": dia.isoformat(),
            "hora": hora.strftime("%H:%M"),
            "cancelado": bool(evento.get("cancelado_em")),
            "simuladoId": sim.get("id"),
            "simulado": sim.get("rotulo_curto") or sim.get("nome"),
            "lembretes": lembretes,
        })

    return {
        "hoje": hoje.isoformat(),
        "janelaDias": dias,
        "configuracao": configuracao,
        "totalEventos": total_de_eventos,
        "truncado": total_de_eventos > limite,
        "eventos": saida_eventos,
        "alunosPorDia": [_alunos_do_dia(cliente, dia, hora_do_aluno) for dia in sorted(dias_com_aluno)],
        "fila": _fila(cliente, agora, hoje, dias),
    }


def _configuracao_de_envio(cliente: Client) -> tuple[dict[str, Any], time | None]:
    """A configuração do motor, e a hora do lembrete dos alunos.

    Pelo MCP, o que mora no ambiente vem `None`, com o aviso: "desligado" e
    "não sei daqui" são coisas diferentes, e o valor de fábrica diria que o
    e-mail não está configurado com o SES ligado. O envio das últimas 24 h vem
    do banco, e vale nas duas superfícies.
    """
    enviados = despachante.enviados_nas_ultimas_24h(cliente)
    if superficie.pelo_mcp():
        return {
            "emailConfigurado": None,
            "lembretesDeAlunoLigados": None,
            "horaLembreteAluno": None,
            "tetoDiario": None,
            "enviadosNasUltimas24h": enviados,
            "aviso": (
                "Esta conexão não enxerga a configuração de envio, que mora no servidor do SAS: "
                "os campos null não querem dizer desligado. A fila e os envios vêm do banco e valem."
            ),
        }, None
    settings = get_settings()
    return {
        "emailConfigurado": email_ses.email_configurado(),
        "lembretesDeAlunoLigados": settings.lembrete_aluno_ativo,
        "horaLembreteAluno": settings.lembrete_aluno_hora,
        "tetoDiario": settings.email_teto_diario,
        "enviadosNasUltimas24h": enviados,
    }, time.fromisoformat(settings.lembrete_aluno_hora)


def _envio_aos_alunos(dia: date, hora_do_aluno: time | None) -> str | None:
    """Véspera, em hora fixa. Sem a hora (pelo MCP), não se chuta o horário."""
    return aluno_simulado.momento_envio(dia, hora_do_aluno).isoformat() if hora_do_aluno else None


def _alunos_do_dia(cliente: Client, dia: date, hora_do_aluno: time | None) -> dict[str, Any]:
    """Os disparos de aluno já montados para o dia — só a contagem.

    A chave é a da própria aplicação (`chave_idempotencia` com '%' no lugar
    do aluno), e "montado" é o que ainda ocupa a chave: tudo que não é
    'cancelado' (`aluno_simulado.ocupa_chave`). Antes da véspera é normal ser
    zero: o disparo de aluno só nasce lá (aluno_simulado.py, docstring).
    """
    prefixo = aluno_simulado.chave_idempotencia(dia, "%")
    return {
        "dia": dia.isoformat(),
        "enviarEm": _envio_aos_alunos(dia, hora_do_aluno),
        "disparosMontados": _contar(
            cliente.table("disparo")
            .select("id", count="exact")
            .like("chave_idempotencia", prefixo)
            .neq("estado", "cancelado")
        ),
        "enviados": _contar(
            cliente.table("disparo")
            .select("id", count="exact")
            .like("chave_idempotencia", prefixo)
            .eq("estado", "enviado")
        ),
    }


def _fila(cliente: Client, agora: datetime, hoje: date, dias: int) -> dict[str, Any]:
    """A fila inteira do motor (todos os lembretes, não só os da janela), contada."""
    fim_da_janela = datetime.combine(
        hoje + timedelta(days=dias + 1), time.min, tzinfo=motor.FUSO_BRASIL
    ).astimezone(UTC)
    um_dia_atras = despachante.filtro_ts(agora - timedelta(hours=24))

    def disparos() -> Any:
        return cliente.table("disparo").select("id", count="exact")

    return {
        "agendadosNaJanela": _contar(
            disparos()
            .eq("estado", "agendado")
            .gte("enviar_em", despachante.filtro_ts(agora))
            .lt("enviar_em", despachante.filtro_ts(fim_da_janela))
        ),
        "falhasNasUltimas24h": {
            "vaoTentarDeNovo": _contar(
                disparos()
                .eq("estado", "falhou")
                .lt("tentativas", despachante.MAX_TENTATIVAS)
                .gte("atualizado_em", um_dia_atras)
            ),
            "desistiram": _contar(
                disparos()
                .eq("estado", "falhou")
                .gte("tentativas", despachante.MAX_TENTATIVAS)
                .gte("atualizado_em", um_dia_atras)
            ),
        },
        # 'enviando' parado há mais que isto = processo morreu no meio do
        # envio; o próprio tick resgata (despachante._resgatar_claims_orfaos).
        "enviandoParados": _contar(
            disparos()
            .eq("estado", "enviando")
            .lt(
                "atualizado_em",
                despachante.filtro_ts(agora - timedelta(minutes=despachante.ENVIANDO_ORFAO_MINUTOS)),
            )
        ),
    }


_SCHEMA_LEMBRETES = {
    "name": "lembretes_agendados",
    "description": (
        "Quando usar: 'os alunos vão receber lembrete do simulado de amanhã?', 'que lembretes "
        "estão marcados para esta semana?', 'algum e-mail falhou?'.\n"
        "Antes de chamar, confirme: a janela em dias. Para um simulado só, o id — simulado "
        "futuro não aparece em listar_simulados: chame primeiro sem ele e use o simuladoId "
        "desta resposta.\n"
        "Definições: lembrete do coordenador = um e-mail para quem agendou, diasAntes antes, na "
        "hora da prova. Lembrete dos alunos = um e-mail por aluno por DIA de prova, enviado na "
        "véspera às horaLembreteAluno e montado só na véspera — antes disso é normal "
        "disparosMontados ser 0. lembretesDeAlunoLigados=false = nada sai para alunos, mesmo "
        "com regra. emailConfigurado=false = nenhum e-mail sai. tetoDiario = limite de envios "
        "em 24 h; o que passar espera. desistiram = falharam em todas as tentativas e saíram "
        "da fila. null na configuração, ou em enviarEm dos alunos = esta conexão não enxerga a "
        "configuração de envio: não diga que está desligado nem cite um horário. A resposta "
        "nunca traz e-mail nem nome de destinatário.\n"
        "Exemplo: lembretes_agendados(dias=3) → 'amanhã há 2 provas com aviso aos alunos; os "
        "e-mails saem hoje às 18:00; nenhum envio falhou nas últimas 24 h'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "dias": {
                "type": "integer",
                "default": 7,
                "description": f"Janela à frente, a partir de hoje (0 = só hoje), até {TETO_DE_DIAS}.",
            },
            "simulado_id": {
                "type": "string",
                "description": "UUID de um simulado: só os lembretes dele. Use o simuladoId que esta tool devolve.",
            },
            "limite": {
                "type": "integer",
                "default": 30,
                "description": f"Quantos eventos detalhar, até {TETO_DE_EVENTOS}; a fila vem sempre inteira, contada.",
            },
        },
        "required": [],
    },
}


# ─── Registry ─────────────────────────────────────────────────────────────

TOOLS: list[tuple[dict, Callable]] = [
    (_SCHEMA_SYNC, estado_do_sync_canvas),
    (_SCHEMA_PENDENCIAS, pendencias_canvas_do_ciclo),
    (_SCHEMA_GRAVACOES, estado_das_gravacoes),
    (_SCHEMA_LEMBRETES, lembretes_agendados),
]

METADADOS: dict[str, dict[str, Any]] = {
    "estado_do_sync_canvas": {"expor_no_mcp": True},
    "pendencias_canvas_do_ciclo": {"expor_no_mcp": True},
    "estado_das_gravacoes": {"expor_no_mcp": True},
    "lembretes_agendados": {"expor_no_mcp": True},
}
