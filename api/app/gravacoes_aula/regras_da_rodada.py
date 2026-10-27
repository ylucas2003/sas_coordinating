"""Quando a rodada do pipeline de gravações retoma uma aula, e quando desiste.

Moravam em `rotas.py`, como nomes privados do módulo do agendador, e desceram
para cá (revisão paralela de 25/10) porque quem as LÊ não é só a rodada: a
tool do assistente que acompanha as gravações (chat/tools/rotinas.py, docs/43
§4.3) diz "desistiu" e "parada" pelas mesmas regras. Lidas de `rotas.py`, elas
puxavam para o processo do chat e do MCP o router do agendador e o pipeline
inteiro de vídeo de aula com menores (S3, YouTube, ffmpeg, downloader) — o
acoplamento que a regra "tool não importa de rota" existe para evitar.

`rotas.py` importa daqui, e o valor continua num lugar só.
"""

from __future__ import annotations

from datetime import datetime

#: Tentativas antes de a rodada desistir de uma aula com 'erro': daí em diante
#: ela sai do pool, e só volta pela mão de alguém
#: (scripts/reabrir_aulas_com_erro.py).
MAX_TENTATIVAS = 3

# Estados que a rodada só retoma depois de esfriarem (ver HORAS_ATE_ORFAO),
# porque enquanto quentes significam "outra rodada está trabalhando nisto".
#
# 'publicando' está de fora DE PROPÓSITO. Ele significa "pode existir vídeo no
# canal": o upload já começou e ninguém sabe se completou. Retomar às cegas
# publicaria a segunda cópia de menores que este módulo existe para evitar —
# quem recupera essa linha é a consulta ao canal
# (`publicador_youtube.ja_publicado`, chamada em `rotas._processar_uma`), não o
# relógio. Os demais intermediários são seguros de refazer.
STATUS_INTERMEDIARIOS = ("baixando", "baixado", "compondo", "composto")

#: Folga acima do pior caso de uma rodada (baixar ~500 MB + recodificar 93 min).
HORAS_ATE_ORFAO = 3


def mais_velho_que(carimbo: str | None, corte: datetime) -> bool:
    """Sem carimbo legível, trata como órfão: linha sem `atualizado_em` só
    aparece se algo já saiu do script, e ficar presa para sempre é pior."""
    if not carimbo:
        return True
    try:
        return datetime.fromisoformat(carimbo.replace("Z", "+00:00")) < corte
    except ValueError:
        return True
