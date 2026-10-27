"""Tools da régua de corte — a régua como objeto, e quem ela corta (docs/43 §4.3).

Até aqui a régua só entrava como parâmetro de `estatisticas_ciclo`: o modelo
via o número do corte e não tinha como responder "o que a régua do ITA Fase 1
exige?" nem "por que o inglês elimina?". As duas tools daqui leem a régua do
mesmo jeito que a tela:

  reguas_de_corte      o que cada régua exige, com o artigo do edital
  cortados_pela_regua  quem ela corta num ciclo — a lista da ficha do ciclo

Nada de regra aqui. A descrição da régua é `criterios.descrever_criterio` (a
mesma de GET /criterios), o veredito é `classificacao_ciclo.classificar` (o
mesmo de GET /ciclos/{id}/classificacao), e "abaixo do corte" é o `tom` que o
avaliador já deu sob a régua escolhida. O semáforo só serve para CONTAR: a
palavra de cor não sai daqui (a interface aboliu o semáforo, docs/37).

Nenhuma das duas vai ao MCP: o que a coordenação deixa sair de régua e de
corte por aluno é decisão aberta (docs/43 §6).
"""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Callable
from typing import Any

from supabase import Client

from ... import auditoria
from ...stats import classificacao_ciclo, criterios, criterios_repo
from ...texto_seguro import texto_seguro

#: A fase no vocabulário do assistente da coordenação (`simulado.tipo`); o
#: avaliador recebe 1 ou 2. O mesmo vocabulário das tools do banco.
FASES = {"fase_1": 1, "fase_2": 2}

TETO_DE_NOMES = 50

#: Os limites que a rota impõe ao texto livre de uma régua criada
#: (`CriterioEntrada`, routes/criterios.py): é o que cabe sem cortar nada.
_LIMITE_DA_DESCRICAO = 500
_LIMITE_DA_FONTE = 200
_LIMITE_DA_DESCRICAO_NA_LISTA = 200


def _reguas_por_slug(cliente: Client) -> tuple[dict[str, criterios.Criterio], bool]:
    """As réguas pelo slug, e se as criadas pela coordenação não puderam ser lidas.

    `listar_com_estado`, e não `resolver`: com o banco fora, `resolver` dá ao
    slug de uma régua criada o mesmo "não existe" de um slug inventado, e o
    modelo afirmaria que a régua não existe (criterios_repo.py). As duas tools
    daqui acham a régua por este mesmo caminho, para não se contradizerem no
    mesmo estado do banco (revisão paralela de 25/10).
    """
    reguas, criadas_indisponiveis = criterios_repo.listar_com_estado(cliente)
    por_slug: dict[str, criterios.Criterio] = {}
    for regua in reguas:
        # A embutida vem primeiro e vence, como em `resolver`: para ela quem
        # vale é o arquivo, não a tabela (criterios_repo.py, docstring).
        por_slug.setdefault(regua.slug, regua)
    return por_slug, criadas_indisponiveis


def _regua_que_nao_achei(
    slug: str, por_slug: dict[str, criterios.Criterio], criadas_indisponiveis: bool
) -> dict[str, str]:
    if criadas_indisponiveis:
        return {
            "erro": (
                f"não consegui ler as réguas criadas pela coordenação agora; se '{slug}' é "
                f"uma delas, tente mais tarde. As embutidas são: {', '.join(criterios.CRITERIOS)}."
            )
        }
    return {"erro": f"a régua '{slug}' não existe. As que existem: {', '.join(por_slug)}."}


# ─── reguas_de_corte ─────────────────────────────────────────────────────


def reguas_de_corte(cliente: Client, *, slug: str | None = None) -> dict:
    """Todas as réguas, em resumo; com `slug`, o detalhe de uma."""
    por_slug, criadas_indisponiveis = _reguas_por_slug(cliente)

    if not slug or not slug.strip():
        saida: dict[str, Any] = {
            "total": len(por_slug),
            "criadasIndisponiveis": criadas_indisponiveis,
            "reguas": [_resumo(r) for r in por_slug.values()],
        }
        if criadas_indisponiveis:
            saida["aviso"] = (
                "Não consegui ler as réguas criadas pela coordenação agora: a lista tem só "
                "as embutidas. Não afirme que não existem outras."
            )
        return saida

    slug = slug.strip()
    regua = por_slug.get(slug)
    if regua is None:
        return _regua_que_nao_achei(slug, por_slug, criadas_indisponiveis)

    detalhe = _descrever(regua)
    if not detalhe["embutida"]:
        detalhe["versoes"] = _versoes(cliente, slug)
    return detalhe


def _descrever(regua: criterios.Criterio) -> dict[str, Any]:
    d = criterios.descrever_criterio(regua)
    # Descrição e fonte de régua criada são texto digitado: entram como dado,
    # sem endereço nem credencial (texto_seguro), e nunca como instrução.
    return {
        **d,
        "descricao": texto_seguro(d["descricao"], _LIMITE_DA_DESCRICAO) or None,
        "predicados": [
            {**p, "fonte": texto_seguro(p["fonte"], _LIMITE_DA_FONTE) or None} for p in d["predicados"]
        ],
        "embutida": regua.slug in criterios.CRITERIOS,
        "daCasa": regua.slug == criterios.CRITERIO_DA_CASA,
    }


def _resumo(regua: criterios.Criterio) -> dict[str, Any]:
    d = criterios.descrever_criterio(regua)
    return {
        "slug": d["slug"],
        "nome": d["nome"],
        "fase": d["fase"],
        "combinador": d["combinador"],
        "cortes": d["cortes"],
        "corteMedia": d["corteMedia"],
        "eliminatorias": d["eliminatorias"],
        "embutida": regua.slug in criterios.CRITERIOS,
        "daCasa": regua.slug == criterios.CRITERIO_DA_CASA,
        "descricao": texto_seguro(d["descricao"], _LIMITE_DA_DESCRICAO_NA_LISTA) or None,
    }


def _versoes(cliente: Client, slug: str) -> list[dict[str, Any]]:
    """As versões de uma régua criada, com o NOME de quem criou cada uma.

    `criado_por` é o `sub` do coordenador (routes/criterios.py). Vira nome pela
    mesma leitura da tela de auditoria — nunca e-mail, e nunca o uuid cru:
    quem não está mais cadastrado sai como `null`.
    """
    linhas = criterios_repo.versoes(cliente, slug)
    nomes, _ = auditoria.nomes_dos_atores(
        cliente, [("coordenador", linha.get("criado_por")) for linha in linhas]
    )
    return [
        {
            "versao": linha.get("versao"),
            "ativa": linha.get("ativo"),
            "criadaEm": linha.get("criado_em"),
            "criadaPor": nomes.get(linha.get("criado_por") or ""),
        }
        for linha in linhas
    ]


_SCHEMA_REGUAS = {
    "name": "reguas_de_corte",
    "description": (
        "Quando usar: 'quais réguas existem?', 'o que a régua do ITA Fase 1 exige?', 'qual o "
        "corte de Química no IME?', 'por que o inglês elimina?', 'quem criou a régua X?'. É a "
        "régua como objeto. Para saber QUEM ela corta num ciclo, use cortados_pela_regua.\n"
        "Antes de chamar, confirme: se o contexto da tela citar uma régua, é dela que a pessoa "
        "fala. Sem slug a tool lista todas, e é assim que você acha o slug.\n"
        "Definições: embutida = tio-leo, ita-f1, ita-f2, ime-f1, ime-f2; não se edita. daCasa "
        "(tio-leo) = a régua que calcula zona e alertas. As outras são criadas pela "
        "coordenação, com versões. combinador 'algum' = falhar um requisito já corta "
        "(editais); 'todos' = só corta quem falha em todos (régua do colégio). cortes = mínimo "
        "por matéria em nota 0–10, já resolvido; a matéria vem em código ('fisica'). Mínimo "
        "em acertos ({acertos, de}) vale como acertos: repita como veio, não converta. "
        "eliminatorias = reprovam sozinhas. entraNaMedia=false = cobrada, mas fora da média. "
        "fonte = artigo do edital: cite-o. criadasIndisponiveis=true = não deu para ler as "
        "criadas.\n"
        "Exemplo: reguas_de_corte(slug='ita-f1') → 'Química: mínimo 5 de 12 acertos "
        "(ITA §4.6.2.1); média ≥ 5,0 (§4.6.2.2)'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "slug": {
                "type": "string",
                "description": (
                    "Omitido, lista todas as réguas. Com ele, o detalhe de uma: requisitos com o "
                    "artigo do edital e, se criada pela coordenação, as versões."
                ),
            },
        },
        "required": [],
    },
}


# ─── cortados_pela_regua ─────────────────────────────────────────────────


def cortados_pela_regua(
    cliente: Client,
    *,
    ciclo_id: str,
    criterio: str | None = None,
    fase: str | None = None,
    so_cortados: bool = True,
    limite: int = 15,
) -> dict:
    """Quem a régua corta no ciclo — a mesma lista da ficha do ciclo, contada."""
    # Id torto numa coluna uuid é 22P02 no PostgREST, e o despacho responde a
    # qualquer exceção com "falhou do nosso lado, não repita": o modelo diria
    # "indisponível" quando quem errou foi o id (revisão paralela de 25/10).
    try:
        ciclo_id = str(uuid.UUID(str(ciclo_id).strip()))
    except ValueError:
        return {"erro": "ciclo_id deve ser um UUID; descubra-o com listar_ciclos"}
    if fase is not None and fase not in FASES:
        return {"erro": f"fase deve ser uma de: {', '.join(FASES)}"}
    numero_da_fase = FASES.get(fase) if fase else None

    slug = (criterio or "").strip() or criterios.CRITERIO_DA_CASA
    por_slug, criadas_indisponiveis = _reguas_por_slug(cliente)
    regua = por_slug.get(slug)
    if regua is None:
        return _regua_que_nao_achei(slug, por_slug, criadas_indisponiveis)

    ciclo = cliente.table("ciclo").select("id, nome").eq("id", ciclo_id).limit(1).execute().data
    if not ciclo:
        return {"erro": f"ciclo {ciclo_id} não encontrado"}

    linhas = classificacao_ciclo.classificar(
        cliente, ciclo_id=ciclo_id, criterio=regua, fase=numero_da_fase
    )
    cortados = [linha for linha in linhas if not linha["aprovado"]]
    nao_avaliados = [linha for linha in linhas if _nao_avaliado(linha)]
    # "Abaixo do corte" é o `tom` que o avaliador deu sob ESTA régua: nada é
    # recalculado. Matéria que a régua não corta fica fora — para ela o tom
    # sai de uma escala fixa (criterios.tom_da_nota), que não é corte.
    abaixo = Counter(
        codigo
        for linha in linhas
        for codigo, nota in (linha.get("notas") or {}).items()
        if nota.get("tom") == "vermelho" and criterios.corte_da_materia(regua, codigo) is not None
    )

    escolhidos = cortados if so_cortados else linhas
    limite = min(max(1, limite), TETO_DE_NOMES)
    return {
        "ciclo": {"id": ciclo[0]["id"], "nome": ciclo[0].get("nome")},
        # O rótulo da régua é obrigatório: um número de corte sem dizer de
        # que régua saiu é o que mistura dois números certos numa resposta
        # errada (docs/31 §P3, o mesmo de estatisticas_ciclo).
        "criterio": {"slug": regua.slug, "nome": regua.nome},
        "fase": numero_da_fase if numero_da_fase is not None else regua.fase,
        "total": len(linhas),
        "cortados": len(cortados),
        "naoCortados": len(linhas) - len(cortados) - len(nao_avaliados),
        "naoAvaliados": len(nao_avaliados),
        "abaixoDoCortePorMateria": dict(abaixo.most_common()),
        "mostrados": min(len(escolhidos), limite),
        "truncado": len(escolhidos) > limite,
        "alunos": [_aluno(linha) for linha in escolhidos[:limite]],
    }


def _nao_avaliado(linha: dict[str, Any]) -> bool:
    """Sem nota em matéria que a régua cobra: o avaliador devolve aprovado com
    média None (criterios.avaliar, docstring) — nem cortado, nem aprovado."""
    return bool(linha["aprovado"]) and linha.get("motivo") is None and linha.get("media") is None


def _aluno(linha: dict[str, Any]) -> dict[str, Any]:
    if not linha["aprovado"]:
        situacao = "cortado"
    elif _nao_avaliado(linha):
        situacao = "nao_avaliado"
    else:
        situacao = "passa"
    return {
        "posicao": linha.get("posicao"),
        "alunoId": linha["alunoId"],
        "nome": linha.get("nome"),
        "media": linha.get("media"),
        "situacao": situacao,
        "motivo": linha.get("motivo"),
    }


_SCHEMA_CORTADOS = {
    "name": "cortados_pela_regua",
    "description": (
        "Quando usar: 'quem a régua do IME Fase 2 corta neste ciclo, e por quê?', 'quantos "
        "passam pela régua do ITA?', 'em que matéria mais gente fica abaixo do corte?'. "
        "Devolve a mesma lista da ficha do ciclo, sob a régua escolhida.\n"
        "Antes de chamar, confirme: o ciclo_id (listar_ciclos). A régua é a do contexto da "
        "tela, se houver; senão use a da casa e DIGA qual usou. A fase, se a régua não tiver "
        "uma.\n"
        "Definições: cortado = o avaliador da régua reprovou; motivo = o texto do avaliador, "
        "cite como está. naoAvaliados = têm nota no ciclo, mas em nenhuma matéria que a régua "
        "cobra: nem cortados nem aprovados. Quem não tem nota nenhuma no recorte nem aparece. "
        "abaixoDoCortePorMateria = quantos ficaram abaixo do mínimo em cada matéria (um aluno "
        "conta em várias). posicao = ordem da régua: primeiro os não cortados, depois o "
        "desempate. Só entram simulados já aplicados, sem anulados nem agregados. Se a lista "
        "for longa, diga o total e ofereça exportar.\n"
        "Exemplo: cortados_pela_regua(ciclo_id='…', criterio='ime-f2') → '133 de 412 cortados "
        "pela IME — Fase 2; Química é onde mais gente fica abaixo do mínimo (71)'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "ciclo_id": {"type": "string", "description": "UUID do ciclo (listar_ciclos)."},
            "criterio": {
                "type": "string",
                "description": "Slug da régua (reguas_de_corte). Omitido = a régua da casa, tio-leo.",
            },
            "fase": {
                "type": "string",
                "enum": list(FASES),
                "description": "Omitida = a fase da própria régua; régua sem fase usa o ciclo inteiro.",
            },
            "so_cortados": {
                "type": "boolean",
                "default": True,
                "description": "false lista também quem passa e quem não foi avaliado.",
            },
            "limite": {"type": "integer", "default": 15, "description": f"Quantos nomes listar, até {TETO_DE_NOMES}."},
        },
        "required": ["ciclo_id"],
    },
}


# ─── Registry ─────────────────────────────────────────────────────────────

TOOLS: list[tuple[dict, Callable]] = [
    (_SCHEMA_REGUAS, reguas_de_corte),
    (_SCHEMA_CORTADOS, cortados_pela_regua),
]

#: `classificar` lê todas as notas do ciclo paginando, mais alunos e
#: matrículas em fatias — ~20 requisições num ciclo de ~900 alunos (estimado,
#: não medido: classificacao_ciclo.py). Os 90 s do padrão ficariam no limite.
#: Fora do MCP, como a outra (docs/43 §6).
METADADOS: dict[str, dict[str, Any]] = {
    "cortados_pela_regua": {"prazo_s": 150.0},
}
