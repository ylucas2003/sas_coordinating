"""Geração de insights pedagógicos por LLM a partir das estatísticas de ciclo.

Dois tipos de leitura:
  - "pratico": linguagem acessível pro coordenador (visível por default na UI).
  - "tecnico": linguagem com jargão estatístico (skewness, curtose, etc.),
               aparece só na seção "dados estatísticos avançados".

Cache em `insight_ciclo` chaveado por (ciclo_id, fase, materia_codigo,
tipo_insight, hash_payload). Hash muda quando os números mudam → cache
invalida automaticamente.

Falha graciosamente: sem `OPENAI_API_KEY` ou sem o SDK, retorna `[]`.

Modelo: `gpt-4o-mini` (default). Usa Structured Outputs em modo `strict`.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from supabase import Client

from ..config import get_settings
from .utils import hash_payload_estavel

try:
    from openai import OpenAI
    _SDK_DISPONIVEL = True
except ImportError:
    _SDK_DISPONIVEL = False

log = logging.getLogger("sas.stats.insights")

MAX_TOKENS = 800
N_BULLETS_MAX = 5

TipoInsight = Literal["pratico", "tecnico"]


# ─── Prompts ──────────────────────────────────────────────────────────────


PROMPT_PRATICO = """Você é um analista pedagógico do Colégio Ari de Sá. Lê estatísticas de turmas em ciclos de simulados ITA/IME e gera observações ACESSÍVEIS para coordenadores que NÃO têm formação em estatística.

# Estilo OBRIGATÓRIO

- Gere de 3 a 5 bullets, cada um com no máximo 22 palavras.
- LINGUAGEM SIMPLES — fale como um colega explicando, não como um estatístico.
- TRADUZA todo número técnico para algo concreto:
  · NÃO: "skewness 1.2 indica assimetria à direita"
  · SIM: "Poucos alunos com notas altas estão puxando a média — a turma típica está abaixo do que parece."
  · NÃO: "Bimodalidade detectada"
  · SIM: "A turma se divide em dois grupos bem diferentes de desempenho."
  · NÃO: "Curtose elevada"
  · SIM: "Há alunos com desempenhos muito fora do padrão da turma."
- Cite números só quando ajudam o coordenador a AGIR ("42% abaixo do corte" sim; "p90 = 8,3" não).
- Foque em: quem precisa de atenção, o que melhorou ou piorou, onde há risco.
- Se houver dados do ciclo anterior, faça pelo menos um bullet comparativo.
- Se for matéria eliminatória com baixa aprovação, isso é PRIORITÁRIO — destaque.

# Contexto do domínio

Notas 0–10. Cortes: 4,0 padrão; 5,0 só para Inglês na Fase 1 do ITA (única eliminatória).
"Zona crítica" = passou mas perigosamente perto do corte.
"Excelência" = nota ≥ 7,0.

Devolva exclusivamente JSON no schema."""


PROMPT_TECNICO = """Você é um analista de dados especializado em educação. Lê estatísticas de turmas em ciclos de simulados ITA/IME e gera observações TÉCNICAS para coordenadores que querem entender a forma da distribuição.

# Estilo

- Gere de 3 a 5 bullets, cada um com no máximo 25 palavras.
- USE TERMINOLOGIA ESTATÍSTICA — quem lê isto quer detalhes técnicos.
- Cite NÚMEROS específicos sempre: média, mediana, desvio padrão, skewness, curtose, quantis, taxas.
- Comente sobre forma da distribuição: simetria, caudas, modalidade, dispersão.
- Compare matematicamente quando houver ciclo anterior (delta numérico).

# Como interpretar

- `skewness` positiva = cauda à direita; |valor| > 1 é forte assimetria.
- `curtose` positiva = caudas pesadas (outliers); negativa = distribuição achatada.
- `bimodal: true` = ≥2 picos significativos no histograma.
- Gap entre `p90` e `p50` grande = poucos alunos puxando topo.

# Contexto

Notas 0–10. Cortes: 4,0 (5,0 para Inglês ITA F1, eliminatória).

Devolva exclusivamente JSON no schema."""


SCHEMA_SAIDA = {
    "type": "object",
    "properties": {
        "bullets": {
            "type": "array",
            "items": {"type": "string"},
        }
    },
    "required": ["bullets"],
    "additionalProperties": False,
}


# ─── Interface pública ────────────────────────────────────────────────────


def gerar_para_recorte(
    cliente_db: Client,
    *,
    ciclo_id: str,
    fase: str,                    # 'fase_1' | 'fase_2' | 'todas'
    materia_codigo: str | None,
    tipo: TipoInsight,            # 'pratico' | 'tecnico'
    stats_payload: dict[str, Any],
    contexto: dict[str, Any],
) -> list[str]:
    """Devolve bullets para (ciclo × fase × materia × tipo)."""
    hash_p = hash_payload_estavel(
        {"stats": stats_payload, "ctx": contexto, "tipo": tipo}
    )

    cache = _consultar_cache(cliente_db, ciclo_id, fase, materia_codigo, tipo, hash_p)
    if cache is not None:
        return cache

    settings = get_settings()
    if not _disponivel(settings.openai_api_key):
        log.info(
            "openai indisponível (sdk=%s, key=%s) — pulando insights",
            _SDK_DISPONIVEL,
            bool(settings.openai_api_key),
        )
        return []

    try:
        bullets = _chamar_llm(
            api_key=settings.openai_api_key,
            modelo=settings.openai_modelo_insights,
            tipo=tipo,
            stats_payload=stats_payload,
            contexto=contexto,
        )
    except Exception:
        log.exception(
            "erro gerando insights ciclo=%s fase=%s mat=%s tipo=%s",
            ciclo_id, fase, materia_codigo, tipo,
        )
        return []

    _salvar_cache(
        cliente_db,
        ciclo_id=ciclo_id,
        fase=fase,
        materia_codigo=materia_codigo,
        tipo=tipo,
        hash_payload=hash_p,
        bullets=bullets,
        modelo=settings.openai_modelo_insights,
    )
    return bullets


# ─── Internals ────────────────────────────────────────────────────────────


def _disponivel(api_key: str) -> bool:
    return _SDK_DISPONIVEL and bool(api_key)


def _chamar_llm(
    *,
    api_key: str,
    modelo: str,
    tipo: TipoInsight,
    stats_payload: dict,
    contexto: dict,
) -> list[str]:
    client = OpenAI(api_key=api_key)
    user_payload = json.dumps(
        {"contexto": contexto, "estatisticas": stats_payload},
        ensure_ascii=False,
        indent=2,
    )
    system_prompt = PROMPT_TECNICO if tipo == "tecnico" else PROMPT_PRATICO

    response = client.chat.completions.create(
        model=modelo,
        max_tokens=MAX_TOKENS,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Gere os bullets para o recorte abaixo. Compare com o ciclo "
                    "anterior quando houver dados.\n\n"
                    f"{user_payload}"
                ),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "InsightsCiclo",
                "strict": True,
                "schema": SCHEMA_SAIDA,
            },
        },
    )

    texto = response.choices[0].message.content
    if not texto:
        return []

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        log.warning("LLM devolveu JSON inválido (tipo=%s): %s", tipo, texto[:200])
        return []

    bullets = [b for b in dados.get("bullets") or [] if isinstance(b, str) and b.strip()]
    return bullets[:N_BULLETS_MAX]


def _consultar_cache(
    cliente: Client,
    ciclo_id: str,
    fase: str,
    materia_codigo: str | None,
    tipo: str,
    hash_payload: str,
) -> list[str] | None:
    query = (
        cliente.table("insight_ciclo")
        .select("bullets")
        .eq("ciclo_id", ciclo_id)
        .eq("fase", fase)
        .eq("tipo_insight", tipo)
        .eq("hash_payload", hash_payload)
    )
    query = (
        query.is_("materia_codigo", "null")
        if materia_codigo is None
        else query.eq("materia_codigo", materia_codigo)
    )
    resp = query.limit(1).execute()
    if not resp.data:
        return None
    bullets = resp.data[0].get("bullets")
    return bullets if isinstance(bullets, list) else []


def _salvar_cache(
    cliente: Client,
    *,
    ciclo_id: str,
    fase: str,
    materia_codigo: str | None,
    tipo: str,
    hash_payload: str,
    bullets: list[str],
    modelo: str,
) -> None:
    if not bullets:
        return
    cliente.table("insight_ciclo").upsert(
        {
            "ciclo_id": ciclo_id,
            "fase": fase,
            "materia_codigo": materia_codigo,
            "tipo_insight": tipo,
            "hash_payload": hash_payload,
            "bullets": bullets,
            "modelo": modelo,
        },
        on_conflict="ciclo_id,fase,materia_codigo,tipo_insight,hash_payload",
    ).execute()
