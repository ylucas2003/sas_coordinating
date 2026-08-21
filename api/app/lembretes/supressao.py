"""Endereços que não recebem mais nada — bounce, complaint e descadastro.

Pré-requisito de qualquer envio em volume (docs/13 §4.6): o SES suspende a
conta de quem acumula rejeição, e com ~873 endereços vindos do Canvas alguns
estarão errados. A lista mora em `email_invalido` e é consultada uma vez por
tick do despachante — não por e-mail.

Deliberadamente NÃO é coluna em `aluno`: professor (P4) cai na mesma lista.
"""

from __future__ import annotations

import json
from typing import Any

from supabase import Client

MOTIVOS = ("bounce", "complaint", "descadastro")


def normalizar(endereco: str) -> str:
    return endereco.strip().lower()


def carregar_invalidos(cliente: Client) -> set[str]:
    resp = cliente.table("email_invalido").select("endereco").execute()
    return {normalizar(l["endereco"]) for l in (resp.data or [])}


def registrar_invalido(
    cliente: Client, *, endereco: str, motivo: str, detalhe: str | None = None
) -> None:
    """Idempotente: o SNS re-entrega notificação, e o mesmo endereço pode
    quicar em vários envios antes de sair das listas."""
    if motivo not in MOTIVOS:
        raise ValueError(f"motivo inválido: {motivo}")
    cliente.table("email_invalido").upsert(
        {
            "endereco": normalizar(endereco),
            "motivo": motivo,
            "detalhe": (detalhe or "")[:500] or None,
        },
        on_conflict="endereco",
    ).execute()


def interpretar_evento_ses(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Notificação do SES (via SNS) → [(endereco, motivo, detalhe)].

    Função pura — é o que os testes cobrem. Regras:
      - Bounce/Permanent  → queima o endereço.
      - Bounce/Transient  → IGNORA. Caixa cheia não é endereço errado, e quem
        re-tenta é a máquina de estados do disparo.
      - Complaint         → queima (marcou como spam; insistir é pedir
        suspensão da conta).
      - Qualquer outra coisa → lista vazia, sem explodir. O endpoint é
        público: payload estranho é o caso normal, não a exceção.
    """
    corpo = payload
    # O SNS embrulha a notificação do SES: o JSON de verdade vem em Message,
    # como string.
    if isinstance(payload.get("Message"), str):
        try:
            corpo = json.loads(payload["Message"])
        except (ValueError, TypeError):
            return []
    if not isinstance(corpo, dict):
        return []

    tipo = corpo.get("notificationType") or corpo.get("eventType")

    if tipo == "Bounce":
        bounce = corpo.get("bounce") or {}
        if bounce.get("bounceType") != "Permanent":
            return []
        detalhe = str(bounce.get("bounceSubType") or "Permanent")
        return [
            (d["emailAddress"], "bounce", detalhe)
            for d in bounce.get("bouncedRecipients") or []
            if d.get("emailAddress")
        ]

    if tipo == "Complaint":
        reclamacao = corpo.get("complaint") or {}
        detalhe = str(reclamacao.get("complaintFeedbackType") or "complaint")
        return [
            (d["emailAddress"], "complaint", detalhe)
            for d in reclamacao.get("complainedRecipients") or []
            if d.get("emailAddress")
        ]

    return []
