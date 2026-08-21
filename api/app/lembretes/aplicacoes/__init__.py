"""Aplicações do motor — quem sabe de domínio.

O requisito de docs/10 §2.2.2: o motor não conhece o domínio. A P2 sustentou
isso com uma aplicação só (o coordenador) e a guarda escrita à mão dentro do
despachante. A P3 quebrou o disfarce: a guarda do aluno NÃO é "o evento está
de pé" (cancelar uma das três provas do dia não pode calar o e-mail) e o texto
não é o de um evento só.

Então a fronteira virou código (docs/13 §1.1):

    motor / despachante / email   →  fila, claim, retry, ritmo, envio
    aplicacoes/*                  →  quando materializar, se ainda vale enviar,
                                     e o que está escrito

Dois hooks, e o despachante só conhece estes dois:

    materializar(cliente) -> dict      (opcional) roda no início do tick
    preparar(cliente, regra, disparo)  guarda + composição, no instante do envio
                                       None = o mundo mudou → disparo cancelado
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from supabase import Client


@dataclass(frozen=True)
class Mensagem:
    assunto: str
    corpo: str


class Aplicacao(Protocol):
    def preparar(
        self, cliente: Client, *, regra: dict[str, Any], disparo: dict[str, Any]
    ) -> Mensagem | None: ...


from . import aluno_simulado, coordenador  # noqa: E402  (evita import circular)

_APLICACOES: dict[str, Any] = {
    "coordenador": coordenador,
    "aluno": aluno_simulado,
}


def materializar_pendentes(cliente: Client) -> dict[str, Any]:
    """Chama o `materializar` de quem tiver. Roda ANTES da fila, no mesmo tick:
    é o que garante que o digest da véspera exista (e esteja reconciliado)
    antes de o despachante olhar o relógio."""
    resultado: dict[str, Any] = {}
    for tipo, aplicacao in _APLICACOES.items():
        materializar = getattr(aplicacao, "materializar", None)
        if materializar is None:
            continue
        resultado[tipo] = materializar(cliente)
    return resultado


def preparar(
    cliente: Client, *, regra: dict[str, Any], disparo: dict[str, Any]
) -> Mensagem | None:
    """Guarda + composição do disparo, delegadas à aplicação do tipo.

    Tipo desconhecido → None: o disparo é cancelado em vez de sair com texto
    que ninguém compôs. Só acontece se um CHECK for alargado sem aplicação
    correspondente — e aí calar é o comportamento certo.
    """
    aplicacao = _APLICACOES.get(str(regra.get("destinatario_tipo")))
    if aplicacao is None:
        return None
    return aplicacao.preparar(cliente, regra=regra, disparo=disparo)
