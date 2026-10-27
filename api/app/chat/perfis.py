"""Perfis do agente de chat — parametrizam o loop de agente.py por sessão sem
duplicá-lo.

- Coordenador: o catálogo de escopo `coordenacao` (lê qualquer aluno) + prompt
  de coordenação + o modelo de `OPENAI_MODELO_COORDENADOR`.
- Aluno: o catálogo de escopo `aluno` (o `aluno_id` vem do JWT, injetado pelo
  registro) + prompt de mentor + gpt-4o-mini (perguntas mais simples, ~800
  alunos).

Quem escolhe e executa as tools é `ferramentas.REGISTRO` (docs/43 §3). O perfil
só amarra uma `Sessao` a ele, a um prompt e a um modelo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..config import get_settings
from .ferramentas import REGISTRO, Registro, Sessao, Volta
from .prompt import system_message
from .prompt_aluno import system_message_aluno


@dataclass(frozen=True)
class PerfilAgente:
    sessao: Sessao
    system_message: dict[str, str]                    # {"role": "system", ...}
    modelo: str
    registro: Registro = REGISTRO

    @property
    def schemas(self) -> list[dict[str, Any]]:
        """O catálogo da sessão, no formato de tools da OpenAI."""
        return self.registro.schemas_openai(self.sessao.escopo)

    async def executar(
        self, nome: str, cliente_db: Any, args: dict, volta: Volta | None = None
    ) -> dict:
        return await self.registro.despachar_async(
            self.sessao, nome, cliente_db, args, volta=volta
        )


def _modelo_coordenador() -> str:
    """Modelo do chat da coordenação — configuração explícita, sem inferência.

    A versão anterior deduzia o modelo a partir de `openai_modelo_insights`:
    se contivesse "mini", assumia que não era potente o bastante e caía em
    gpt-4o. Efeito prático invertido — configurar o barato ligava o caro.
    Trocar por OPENAI_MODELO_COORDENADOR no ambiente (docs/14 §6.4).
    """
    return get_settings().openai_modelo_coordenador


def perfil_coordenador(sessao: Sessao) -> PerfilAgente:
    # A recusa aqui é a segunda camada: `sessao_do_token` já não deixa um token
    # sem `sub` virar coordenação, mas um chamador que montasse a `Sessao` à
    # mão não pode receber o prompt e o modelo errados por engano.
    if sessao.escopo != "coordenacao":
        raise ValueError("perfil de coordenação exige sessão de coordenação")
    return PerfilAgente(
        sessao=sessao,
        system_message=system_message(),
        modelo=_modelo_coordenador(),
    )


def perfil_aluno(sessao: Sessao) -> PerfilAgente:
    if sessao.escopo != "aluno":
        raise ValueError("perfil do aluno exige sessão de aluno")
    return PerfilAgente(
        sessao=sessao,
        system_message=system_message_aluno(sessao.nome),
        # Configuração explícita, como a da coordenação: era a constante
        # MODELO_ALUNO, e trocar o modelo do Tio Léo pedia deploy (docs/43 §6).
        modelo=get_settings().openai_modelo_aluno,
    )
