"""Pipeline de publicação de aula gravada — POST /gravacoes-aula/{verificar,processar}.

Duas rotas, ambas chamadas pelo cron do VPS (infra/vps/crontab-sas) com o
header X-Scheduler-Secret, mesmo padrão de canvas_sync/rotas.py:

  verificar  — varre os cursos de curso_monitorado_gravacao e registra em
               aula_gravacao toda conferência que JÁ tem gravação disponível
               e ainda não está rastreada. Barato, roda de hora em hora.
  processar  — pega o que está pendente e roda o caminho completo: baixar do
               Canvas → compor com o template → subir pro S3 → publicar no
               YouTube. Caro (vídeo de ~500 MB, 93 min de aula), por isso
               limita quantas aulas processa por rodada.

Separar as duas é o que dá idempotência: `verificar` só escreve linha nova
(UNIQUE curso_id+conferencia_id), e `processar` avança uma linha por vez,
gravando o status a cada etapa. Se o cron reentregar no meio de um upload, a
trava ignora a segunda chamada; se o processo morrer, a linha fica no último
status salvo e a rodada seguinte retoma dali.

Lembrete de contexto: a gravação some do Canvas em ~7 dias (retenção do
BigBlueButton confirmada empiricamente), então o atraso entre a aula e a
publicação precisa caber nessa janela.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
import tempfile
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends

from ..auth import exigir_scheduler_secret
from ..canvas_sync.cliente import ClienteCanvas
from ..config import get_settings
from ..supabase_client import criar_cliente_supabase
from . import armazenamento_s3, compositor, downloader, publicador_youtube, titulo

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/gravacoes-aula", tags=["gravacoes-aula"])

_trava_verificacao = threading.Lock()
_trava_processamento = threading.Lock()

# UMA por rodada: baixar ~500 MB, recodificar 93 min de 1080p com 2 threads e
# subir pro YouTube leva de 45 a 90 min. Com o cron de hora em hora e a trava,
# a fila drena sozinha com folga dentro da janela de ~7 dias de retenção.
_MAX_POR_RODADA = 1
_MAX_TENTATIVAS = 3

# Quantas linhas a consulta traz antes do corte por esfriamento (ver
# _rodada_em_background). Folgado: são linhas pequenas, e o custo de trazer
# algumas a mais é irrelevante perto de errar a vaga da rodada.
_JANELA_CANDIDATAS = 20

# Persistir o id do YouTube é a escrita mais importante do módulo: sem ela, o
# vídeo existe no canal e o banco não sabe. Backoff de 1s dobrando até o teto
# de 30s, somando ~3 min de insistência — dimensionado para atravessar um
# `restart postgrest` ou um deploy, não só um soluço de rede. Mesmo esgotado,
# nada se perde: `ja_publicado()` recupera o id na rodada seguinte.
_TENTATIVAS_PERSISTIR_ID = 8
_TETO_ESPERA_PERSISTIR = 30

# Estados que a rodada pode pegar. Os INICIAIS são elegíveis na hora; os
# INTERMEDIÁRIOS só depois de esfriarem (ver _HORAS_ATE_ORFAO), porque
# enquanto quentes significam "outra rodada está trabalhando nisto".
#
# 'publicado' e 'publicado_sem_confirmacao' NÃO entram: são terminais. O vídeo
# já está no canal, e reprocessar geraria uma segunda cópia de menores.
_STATUS_INICIAIS = ("pendente", "erro")

# 'publicando' está de fora DE PROPÓSITO. Ele significa "pode existir vídeo no
# canal": o upload já começou e ninguém sabe se completou. Retomar às cegas
# publicaria a segunda cópia de menores que este módulo existe para evitar —
# quem recupera essa linha é a consulta ao canal em `_id_ja_publicado`, não o
# relógio. Os demais intermediários são seguros de refazer.
_STATUS_INTERMEDIARIOS = ("baixando", "baixado", "compondo", "composto")
_STATUS_RETENTAVEIS = [*_STATUS_INICIAIS, *_STATUS_INTERMEDIARIOS, "publicando"]

# Folga acima do pior caso de uma rodada (baixar ~500 MB + recodificar 93 min).
_HORAS_ATE_ORFAO = 3


_PREFIXO_TRABALHO = "aula-"


def _agora() -> str:
    return datetime.now(UTC).isoformat()


def _descrever(exc: BaseException) -> str:
    """Sempre inclui a CLASSE da exceção.

    Várias exceções de rede (httpx.ReadTimeout, entre outras) têm `str()`
    vazio: gravar só a mensagem produz um erro_detalhe em branco, que é
    exatamente o que aconteceu no primeiro teste real e deixou a falha
    indepurável."""
    texto = str(exc).strip()
    return f"{type(exc).__name__}: {texto}" if texto else type(exc).__name__


def _varrer_trabalhos_orfaos() -> int:
    """Apaga diretórios de trabalho que um processo morto deixou para trás.

    Não é higiene de disco: é LGPD. Cada diretório desses guarda até ~1 GB de
    vídeo com rosto e voz de aluno menor de idade, e o `finally` de
    `_processar_uma` só roda se o processo sobreviver — um deploy, um OOM kill
    ou um reboot no meio da composição deixa a pasta inteira em /tmp para
    sempre. Só remove o que já esfriou, para não apagar o trabalho de uma
    rodada viva."""
    corte = time.time() - _HORAS_ATE_ORFAO * 3600
    removidos = 0
    for caminho in Path(tempfile.gettempdir()).glob(f"{_PREFIXO_TRABALHO}*"):
        try:
            if caminho.is_dir() and caminho.stat().st_mtime < corte:
                shutil.rmtree(caminho, ignore_errors=True)
                removidos += 1
        except OSError:
            continue  # sumiu no meio do caminho, ou sem permissão: não é fatal
    if removidos:
        _log.warning(
            "gravacoes-aula: %d diretório(s) de trabalho órfão(s) removido(s) do /tmp",
            removidos,
        )
    return removidos


def _mais_velho_que(carimbo: str | None, corte: datetime) -> bool:
    """Sem carimbo legível, trata como órfão: linha sem `atualizado_em` só
    aparece se algo já saiu do script, e ficar presa para sempre é pior."""
    if not carimbo:
        return True
    try:
        return datetime.fromisoformat(carimbo.replace("Z", "+00:00")) < corte
    except ValueError:
        return True


async def _listar_conferencias_com_gravacao(curso_id: str) -> list[dict[str, Any]]:
    settings = get_settings()
    async with ClienteCanvas(
        base_url=settings.canvas_base_url, token=settings.canvas_api_token
    ) as canvas:
        conferencias = await canvas.listar_conferencias(curso_id)
    return [c for c in conferencias if c.get("recordings")]


@router.post("/verificar")
def verificar_gravacoes(_: None = Depends(exigir_scheduler_secret)) -> dict:
    if not _trava_verificacao.acquire(blocking=False):
        return {"status": "ignorado", "motivo": "verificação anterior ainda em andamento"}
    try:
        cliente = criar_cliente_supabase()
        cursos = (
            cliente.table("curso_monitorado_gravacao")
            .select("curso_id")
            .eq("ativo", True)
            .execute()
            .data
        )
        novas = 0
        erros: list[dict[str, str]] = []
        for curso in cursos:
            curso_id = curso["curso_id"]
            # Um curso que falha (arquivado no Canvas, permissão revogada,
            # timeout) NÃO pode abortar a detecção dos outros — senão um curso
            # ruim esconde aula nova de todos os demais até alguém notar, e a
            # janela de retenção é de só ~7 dias.
            try:
                for conf in asyncio.run(_listar_conferencias_com_gravacao(curso_id)):
                    rec = (conf.get("recordings") or [{}])[0]
                    resposta = (
                        cliente.table("aula_gravacao")
                        .upsert(
                            {
                                "curso_id": curso_id,
                                "conferencia_id": str(conf["id"]),
                                "titulo": conf.get("title") or f"Aula {conf['id']}",
                                "iniciada_em": conf.get("started_at"),
                                "duracao_minutos": rec.get("duration_minutes"),
                            },
                            on_conflict="curso_id,conferencia_id",
                            ignore_duplicates=True,
                        )
                        .execute()
                    )
                    novas += len(resposta.data or [])
            except Exception as exc:
                erros.append({"curso_id": curso_id, "detalhe": _descrever(exc)[:200]})
        return {
            "status": "ok",
            "cursos_verificados": len(cursos),
            "aulas_novas": novas,
            "erros": erros,
        }
    finally:
        _trava_verificacao.release()


def _processar_uma(cliente: Any, aula: dict[str, Any]) -> dict[str, Any]:
    """Caminho completo de uma aula. Cada etapa grava o status antes de
    começar — se o processo morrer no meio, dá pra saber onde parou."""
    aula_id = aula["id"]

    def marcar(**campos: Any) -> None:
        cliente.table("aula_gravacao").update(
            {**campos, "atualizado_em": _agora()}
        ).eq("id", aula_id).execute()

    # ─── Dois cintos de segurança contra publicar a mesma aula duas vezes ──
    #
    # Primeiro o barato: o id já está na linha, então só o estado se perdeu.
    if aula.get("youtube_video_id"):
        marcar(status="publicado", erro_detalhe=None)
        return {
            "aula_id": aula_id,
            "status": "publicado",
            "youtube_video_id": aula["youtube_video_id"],
            "observacao": "já estava publicado; só o estado foi reconciliado",
        }

    # Depois o que custa uma chamada de API, mas fecha a janela que o banco não
    # enxerga: o upload pode ter sido COMITADO pelo YouTube com a resposta
    # perdida no caminho (socket caído, 503 pós-commit) — aí o vídeo está no
    # canal e o id nunca chegou aqui. Perguntar ao canal é a única forma de
    # saber; sem isto, retomar uma linha em 'publicando' criaria a segunda
    # cópia de menores que este módulo existe para evitar (LGPD art. 18, VI).
    # Roda ANTES do download: se já publicou, poupa ~500 MB e uma recodificação.
    try:
        ja = publicador_youtube.ja_publicado(aula["curso_id"], aula["conferencia_id"])
    except publicador_youtube.YouTubeNaoConfigurado:
        ja = None  # sem credencial não há canal para consultar nem para duplicar
    except Exception as exc:
        # Não dá para distinguir "não publicado" de "não consegui perguntar".
        # Diante da dúvida, NÃO publica: repetir um vídeo de menor é pior do
        # que atrasar uma aula que a próxima rodada pega.
        marcar(
            status="erro",
            erro_detalhe=f"não foi possível conferir se já estava publicado: {_descrever(exc)[:400]}",
            tentativas=aula["tentativas"] + 1,
        )
        return {"aula_id": aula_id, "status": "erro", "detalhe": "consulta ao canal falhou"}
    if ja:
        marcar(status="publicado", youtube_video_id=ja, erro_detalhe=None)
        return {
            "aula_id": aula_id,
            "status": "publicado",
            "youtube_video_id": ja,
            "observacao": "já estava no canal; id recuperado e estado reconciliado",
        }

    # Nome do curso e professor padrão saem daqui para montar o título no
    # padrão do canal. Falhar isso não pode derrubar a publicação: sem a
    # linha, o título só perde o "Prof X" quando a conferência também não traz.
    curso: dict[str, Any] | None = None
    with contextlib.suppress(Exception):
        achados = (
            cliente.table("curso_monitorado_gravacao")
            .select("nome,professor_padrao")
            .eq("curso_id", aula["curso_id"])
            .execute()
            .data
        )
        curso = achados[0] if achados else None

    trabalho = Path(
        tempfile.mkdtemp(prefix=f"{_PREFIXO_TRABALHO}{aula['conferencia_id']}-")
    )
    try:
        settings = get_settings()
        marcar(status="baixando")

        async def _baixar() -> downloader.VideoBaixado:
            async with ClienteCanvas(
                base_url=settings.canvas_base_url, token=settings.canvas_api_token
            ) as canvas:
                return await downloader.baixar_video(
                    canvas, aula["curso_id"], aula["conferencia_id"], trabalho
                )

        baixado = asyncio.run(_baixar())
        marcar(status="baixado")

        marcar(status="compondo")
        composto = compositor.compor(
            webcam=baixado.webcam,
            tela_compartilhada=baixado.tela_compartilhada,
            destino=trabalho / "composto.mp4",
        )
        marcar(status="composto")

        bucket, chave = armazenamento_s3.enviar_video(
            composto, curso_id=aula["curso_id"], conferencia_id=aula["conferencia_id"]
        )
        marcar(s3_bucket=bucket, s3_chave_composto=chave)

        marcar(status="publicando")
        # O título da conferência no Canvas é datilografado à mão e não segue
        # padrão nenhum; o canal segue. Ver titulo.py.
        titulo_video = titulo.compor_titulo(
            titulo_canvas=aula["titulo"],
            nome_curso=curso.get("nome", "") if curso else "",
            iniciada_em=datetime.fromisoformat(aula["iniciada_em"].replace("Z", "+00:00")),
            professor_padrao=(curso or {}).get("professor_padrao"),
        )
        video_id = publicador_youtube.publicar(
            composto,
            titulo=titulo_video,
            curso_id=aula["curso_id"],
            conferencia_id=aula["conferencia_id"],
        )
    except Exception as exc:
        # O erro vira estado na linha (status='erro' + tentativas+1), não
        # derruba a rodada: as outras aulas pendentes ainda são processadas.
        cliente.table("aula_gravacao").update(
            {
                "status": "erro",
                "erro_detalhe": _descrever(exc)[:500],
                "tentativas": aula["tentativas"] + 1,
                "atualizado_em": _agora(),
            }
        ).eq("id", aula_id).execute()
        return {"aula_id": aula_id, "status": "erro", "detalhe": _descrever(exc)[:200]}
    finally:
        shutil.rmtree(trabalho, ignore_errors=True)

    # Daqui pra baixo o vídeo JÁ ESTÁ no YouTube. Esta escrita fica FORA do
    # try acima de propósito: se ela caísse no `except`, a linha voltaria pro
    # pool de pendentes e a rodada seguinte publicaria uma segunda cópia —
    # vídeo de menor de idade duplicado no canal, sem registro no banco que
    # permitisse apagá-lo num pedido de eliminação (LGPD art. 18, VI).
    # Por isso o id é persistido com retry próprio, e o fracasso final vira um
    # status TERMINAL (nunca retentável), não 'erro'.
    for tentativa in range(_TENTATIVAS_PERSISTIR_ID):
        try:
            marcar(status="publicado", youtube_video_id=video_id, erro_detalhe=None)
            return {"aula_id": aula_id, "status": "publicado", "youtube_video_id": video_id}
        except Exception as exc:
            if tentativa == _TENTATIVAS_PERSISTIR_ID - 1:
                # Se nem o status terminal grava, o log é a última linha de
                # defesa — é o único rastro de que existe vídeo no canal.
                with contextlib.suppress(Exception):
                    marcar(
                        status="publicado_sem_confirmacao",
                        youtube_video_id=video_id,
                        erro_detalhe=f"publicado mas o id não persistiu: {_descrever(exc)[:400]}",
                    )
                _log.error(
                    "aula %s publicada no YouTube como %s mas o banco não confirmou — "
                    "NÃO reprocessar: geraria cópia duplicada",
                    aula_id,
                    video_id,
                )
                return {
                    "aula_id": aula_id,
                    "status": "publicado_sem_confirmacao",
                    "youtube_video_id": video_id,
                }
            time.sleep(min(2**tentativa, _TETO_ESPERA_PERSISTIR))
    return {"aula_id": aula_id, "status": "publicado", "youtube_video_id": video_id}


@router.post("/processar")
def processar_gravacoes(
    tarefas: BackgroundTasks, _: None = Depends(exigir_scheduler_secret)
) -> dict:
    """Dispara a rodada e responde NA HORA.

    Uma aula leva de 45 a 90 min (baixar ~500 MB + recodificar 93 min de 1080p
    + subir pro YouTube) — muito além de qualquer `--max-time` de curl
    razoável. Se o trabalho fosse feito dentro da requisição, o cron registraria
    fracasso justamente nas rodadas que funcionam, e o operador aprenderia a
    ignorar o log. Mesmo padrão de routes/uploads.py.

    A trava é adquirida AQUI (para a resposta já dizer "ignorado" quando outra
    rodada está viva) e liberada dentro da tarefa de fundo.
    """
    if not _trava_processamento.acquire(blocking=False):
        return {"status": "ignorado", "motivo": "processamento anterior ainda em andamento"}
    tarefas.add_task(_rodada_em_background)
    return {"status": "aceito", "motivo": "rodada iniciada em segundo plano"}


def _rodada_em_background() -> None:
    """Chamado pelo BackgroundTasks depois que a resposta já foi enviada.

    Cliente NOVO (não cacheado) pelo mesmo motivo de routes/uploads.py: o
    postgrest-py força HTTP/2 e um GOAWAY numa stream derrubaria as outras —
    e esta rodada segura a conexão ociosa por dezenas de minutos.
    """
    try:
        _varrer_trabalhos_orfaos()
        cliente = criar_cliente_supabase()
        # A janela é MAIOR que _MAX_POR_RODADA de propósito: o corte por
        # esfriamento é aplicado depois, em Python, e se o `limit` cortasse
        # antes, uma única linha quente (rodada anterior ainda viva) ocuparia a
        # vaga e a rodada não processaria NADA — de hora em hora, enquanto a
        # janela de 7 dias de retenção corre.
        candidatas = (
            cliente.table("aula_gravacao")
            .select("*")
            .in_("status", _STATUS_RETENTAVEIS)
            .lt("tentativas", _MAX_TENTATIVAS)
            .order("iniciada_em", desc=False)
            .limit(_JANELA_CANDIDATAS)
            .execute()
            .data
        )
        # Um estado INTERMEDIÁRIO só é retomável depois de esfriar: enquanto a
        # rodada anterior ainda está viva (ela pode levar dezenas de minutos),
        # 'baixando'/'compondo' significam "alguém está trabalhando nisto".
        # Sem esse corte, uma linha órfã de processo morto ficaria presa para
        # sempre — junto com ~1 GB de vídeo de aluno esquecido no /tmp.
        corte = datetime.now(UTC) - timedelta(hours=_HORAS_ATE_ORFAO)
        frias = [
            a
            for a in candidatas
            if a["status"] in _STATUS_INICIAIS
            or _mais_velho_que(a.get("atualizado_em"), corte)
        ]
        elegiveis = frias[:_MAX_POR_RODADA]
        # Duas razões DIFERENTES para uma linha não entrar nesta rodada, e
        # confundi-las esconde problema: "na fila" é o funcionamento normal do
        # teto de uma por rodada; "quente" significa que outra rodada está
        # mexendo nela — e se esse número não zerar, é sinal de rodada travada.
        na_fila = len(frias) - len(elegiveis)
        quentes = len(candidatas) - len(frias)
        # Ninguém lê o retorno aqui (a resposta HTTP já foi enviada): o
        # resultado de cada aula vive na própria linha de aula_gravacao, e o
        # log é o que o operador acompanha.
        for aula in elegiveis:
            resultado = _processar_uma(cliente, aula)
            _log.info("gravacoes-aula: %s", resultado)
        _log.info(
            "gravacoes-aula: rodada terminou — %d processada(s), %d na fila, "
            "%d ainda quente(s)",
            len(elegiveis),
            na_fila,
            quentes,
        )
    except Exception:
        # Sem isto, uma falha antes do laço (ex.: banco fora) sobe como
        # exceção não tratada de background task e some do log da rodada.
        _log.exception("gravacoes-aula: rodada abortou antes de terminar")
    finally:
        _trava_processamento.release()
