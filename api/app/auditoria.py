"""Trilha de auditoria — quem fez o quê (docs/15 §Etapa 8, migration 0022).

Regra da casa: **nunca** grave senha, hash, token ou corpo de mensagem aqui.
A tabela existe para responder "quem" e "quando", não para reproduzir conteúdo.

Toda gravação é melhor-esforço e engole a própria exceção: auditoria que
derruba a operação auditada é pior que auditoria ausente — um login não pode
falhar porque o INSERT do registro falhou.
"""

from __future__ import annotations

import logging
from typing import Any

from .observabilidade import request_id_atual

log = logging.getLogger("sas.auditoria")


def registrar(
    cliente,
    acao: str,
    *,
    canal: str = "acesso",
    ator_tipo: str | None = None,
    ator_id: str | None = None,
    recurso: str | None = None,
    ip: str | None = None,
    detalhe: dict[str, Any] | None = None,
) -> None:
    evento = {
        "acao": acao,
        # Compartimento da linha do tempo: acesso | nota | simulado | ciclo |
        # canvas (migration 0025). Quem grava diz de que assunto é o evento.
        "canal": canal,
        "ator_tipo": ator_tipo,
        "ator_id": ator_id,
        "recurso": recurso,
        "ip": ip,
        "detalhe": detalhe,
        "request_id": request_id_atual(),
    }
    # No log também: se a escrita no banco falhar, o evento não se perde.
    log.info("auditoria: %s", acao, extra={"usuario": ator_id, "rota": recurso})
    try:
        cliente.table("evento_auditoria").insert(evento).execute()
    except Exception:
        log.warning("não consegui gravar evento de auditoria", exc_info=True)
