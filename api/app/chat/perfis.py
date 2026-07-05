"""Perfis do agente de chat — parametrizam o loop de agente.py por tipo de
usuário sem duplicá-lo.

- Coordenador: 21 tools staff (lê qualquer aluno) + prompt de coordenação.
- Aluno: tools restritas aos próprios dados (aluno_id injetado do JWT) +
  prompt de mentor + gpt-4o-mini (perguntas mais simples, ~800 alunos).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..config import get_settings
from .prompt import system_message
from .prompt_aluno import system_message_aluno
from .tools import SCHEMAS, executar
from .tools_aluno import SCHEMAS_ALUNO, executar_para_aluno

MODELO_COORDENADOR_PADRAO = "gpt-4o"   # Sweet spot custo/raciocínio.
MODELO_ALUNO = "gpt-4o-mini"


@dataclass(frozen=True)
class PerfilAgente:
    schemas: list[dict[str, Any]]                     # formato OpenAI tools
    executar: Callable[[str, Any, dict], dict]        # (nome, cliente_db, args) -> dict
    system_message: dict[str, str]                    # {"role": "system", ...}
    modelo: str


def _modelo_coordenador() -> str:
    settings = get_settings()
    # Reusa o setting do insights se ele apontar pra um modelo "potente";
    # senão, default seguro.
    modelo = (settings.openai_modelo_insights or "").lower()
    if modelo and "mini" not in modelo:
        return settings.openai_modelo_insights
    return MODELO_COORDENADOR_PADRAO


def perfil_coordenador() -> PerfilAgente:
    return PerfilAgente(
        schemas=SCHEMAS,
        executar=executar,
        system_message=system_message(),
        modelo=_modelo_coordenador(),
    )


def perfil_aluno(aluno_id: str, nome: str) -> PerfilAgente:
    def _executar(nome_tool: str, cliente_db, args: dict) -> dict:
        return executar_para_aluno(nome_tool, cliente_db, args, aluno_id=aluno_id)

    return PerfilAgente(
        schemas=SCHEMAS_ALUNO,
        executar=_executar,
        system_message=system_message_aluno(nome),
        modelo=MODELO_ALUNO,
    )
