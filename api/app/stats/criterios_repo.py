"""As réguas que a coordenação cria — leitura e escrita no banco.

Fica FORA de `criterios.py` de propósito. Aquele arquivo é o vocabulário e o
avaliador, e a primeira linha do seu docstring promete que o avaliador é puro,
sem I/O — é o que o torna testável sem container. Este aqui é a metade que
toca o banco.

**A regra da fonte da verdade** (docs/18 §1.10, comentário da migration 0023):

    embutidas (tio-leo, ita-f1, ita-f2, ime-f1, ime-f2)  →  o ARQUIVO vence
    criadas pela coordenação                             →  a TABELA

O motivo prático de o arquivo vencer: é lá que o artigo do edital está escrito
ao lado do número, e é lá que se lê para entender por que um aluno foi cortado.
A tabela guarda uma cópia dos embutidos como semente, e ela nunca é consultada
para eles. Consequência boa: banco fora do ar não impede o Painel de
classificar pelas cinco réguas que importam.

**Critério é imutável.** Editar insere `versao + 1` e desativa a anterior. Sem
isso, mexer numa régua mudaria retroativamente os números de quem já a usou —
em silêncio, e sem ninguém conseguir explicar a diferença depois.
"""

from __future__ import annotations

import logging
import re

from . import criterios

log = logging.getLogger("sas.stats.criterios_repo")

#: As matérias de `materia` (carga inicial da 0001), mais os dois códigos
#: especiais que o avaliador entende.
MATERIAS_VALIDAS = frozenset(
    {"matematica", "fisica", "quimica", "portugues", "ingles", "redacao"}
)
_ESPECIAIS = {criterios.TODAS, criterios.FASE_1}

_RE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

_SELECT = (
    "id, slug, versao, nome, descricao, combinador, fase, desempate, embutido, ativo, "
    "criado_em, criado_por, predicado_criterio(posicao, materia, operador, valor_nota, "
    "valor_acertos, valor_de, eliminatorio, entra_na_media, peso, fonte)"
)


class CriterioInvalido(ValueError):
    """A régua não é representável. A mensagem vai direto para o 422."""


def _peso(bruto) -> float:
    """Peso do predicado, com 1,0 só quando ele está AUSENTE.

    `float(bruto or 1)` engolia o zero — e zero é um valor que alguém digita de
    propósito, querendo "cobrar sem contar na média". A validação recusa; o que
    não pode é virar 1 em silêncio.
    """
    return 1.0 if bruto is None else float(bruto)


# ─── Leitura ──────────────────────────────────────────────────────────────


def _para_criterio(linha: dict) -> criterios.Criterio:
    """Linha do banco (com predicados embutidos) → `Criterio` do avaliador."""
    brutos = sorted(
        linha.get("predicado_criterio") or [], key=lambda p: p.get("posicao") or 0
    )
    predicados = []
    for p in brutos:
        if p.get("valor_acertos") is not None and p.get("valor_de"):
            valor: float | criterios.Acertos = criterios.Acertos(
                acertos=int(p["valor_acertos"]), de=int(p["valor_de"])
            )
        else:
            valor = float(p.get("valor_nota") or 0)
        predicados.append(
            criterios.Predicado(
                materia=p.get("materia"),
                valor=valor,
                operador=p.get("operador") or ">=",
                eliminatorio=bool(p.get("eliminatorio")),
                entra_na_media=bool(p.get("entra_na_media", True)),
                peso=_peso(p.get("peso")),
                fonte=p.get("fonte") or "",
            )
        )

    return criterios.Criterio(
        slug=linha["slug"],
        nome=linha["nome"],
        combinador=linha["combinador"],
        predicados=tuple(predicados),
        desempate=tuple(linha.get("desempate") or ()),
        fase=linha.get("fase"),
        descricao=linha.get("descricao") or "",
    )


def _linhas_ativas(cliente) -> list[dict]:
    """As réguas CRIADAS que estão valendo — a maior versão ativa de cada slug."""
    try:
        resp = (
            cliente.table("criterio_classificacao")
            .select(_SELECT)
            .eq("embutido", False)
            .eq("ativo", True)
            .execute()
        )
    except Exception:
        # Falha aberto: sem banco, o Painel continua com as cinco embutidas.
        log.warning("não consegui listar critérios do banco", exc_info=True)
        return []

    por_slug: dict[str, dict] = {}
    for linha in resp.data or []:
        atual = por_slug.get(linha["slug"])
        if atual is None or (linha.get("versao") or 1) > (atual.get("versao") or 1):
            por_slug[linha["slug"]] = linha
    return list(por_slug.values())


def listar(cliente) -> list[criterios.Criterio]:
    """Todas as réguas oferecidas: as cinco do arquivo, depois as criadas."""
    return [*criterios.CRITERIOS.values(), *(_para_criterio(l) for l in _linhas_ativas(cliente))]


def resolver(cliente, slug: str) -> criterios.Criterio:
    """A régua pelo slug. Embutida vem do arquivo; o resto, do banco.

    Levanta `KeyError` com a lista do que existe — o mesmo contrato de
    `criterios.por_slug`, para as rotas tratarem os dois casos igual.
    """
    embutida = criterios.CRITERIOS.get(slug)
    if embutida is not None:
        return embutida

    for linha in _linhas_ativas(cliente):
        if linha["slug"] == slug:
            return _para_criterio(linha)

    disponiveis = sorted(criterios.CRITERIOS) + sorted(
        l["slug"] for l in _linhas_ativas(cliente)
    )
    raise KeyError(f"critério {slug!r} não existe. Disponíveis: {', '.join(disponiveis)}")


def versoes(cliente, slug: str) -> list[dict]:
    """Todas as versões de uma régua criada, da mais nova para a mais velha."""
    resp = (
        cliente.table("criterio_classificacao")
        .select(_SELECT)
        .eq("slug", slug)
        .execute()
    )
    linhas = resp.data or []
    linhas.sort(key=lambda l: l.get("versao") or 1, reverse=True)
    return linhas


# ─── Validação ────────────────────────────────────────────────────────────


def validar(payload: dict) -> None:
    """Recusa réguas que o avaliador não sabe aplicar, ou que não fazem sentido.

    Validar aqui e não só no formulário porque o formulário não é a única
    porta: a rota é pública para quem tem token de coordenação, e uma régua
    quebrada não falha — ela classifica errado, em silêncio.
    """
    slug = (payload.get("slug") or "").strip()
    if not _RE_SLUG.match(slug):
        raise CriterioInvalido(
            "slug deve ser minúsculo, sem acento, palavras separadas por hífen "
            "(ex.: 'meta-7-exatas')."
        )
    if slug in criterios.CRITERIOS:
        raise CriterioInvalido(f"'{slug}' é uma régua embutida — escolha outro identificador.")

    if not (payload.get("nome") or "").strip():
        raise CriterioInvalido("a régua precisa de um nome.")

    if payload.get("combinador") not in ("todos", "algum"):
        raise CriterioInvalido("combinador deve ser 'todos' (E) ou 'algum' (OU).")

    if payload.get("fase") not in (None, 1, 2):
        raise CriterioInvalido("fase deve ser 1, 2 ou vazia (vale para as duas).")

    predicados = payload.get("predicados") or []
    if not predicados:
        raise CriterioInvalido("a régua precisa de pelo menos um requisito.")
    if len(predicados) > 20:
        raise CriterioInvalido("no máximo 20 requisitos por régua.")

    # Uma régua só de eliminatórias com combinador 'algum' reprova quem falhar
    # em qualquer um — o que é legítimo. O que NÃO é legítimo é régua sem
    # nenhum requisito classificatório e com combinador 'todos': o `todos` só
    # corta quando TODOS falham, e sem requisito não-eliminatório ele nunca
    # fecha, então a régua aprovaria a base inteira sem ninguém perceber.
    classificatorios = [p for p in predicados if not p.get("eliminatorio")]
    if payload["combinador"] == "todos" and not classificatorios:
        raise CriterioInvalido(
            "com o combinador 'todos', a régua precisa de pelo menos um requisito "
            "não-eliminatório — senão ela nunca corta ninguém."
        )

    for i, p in enumerate(predicados, start=1):
        materia = p.get("materia")
        if materia is not None and materia not in MATERIAS_VALIDAS | _ESPECIAIS:
            raise CriterioInvalido(
                f"requisito {i}: matéria '{materia}' não existe. "
                f"Use uma de {sorted(MATERIAS_VALIDAS)}, '*' (qualquer) ou vazio (média)."
            )
        # Ausente é ">=", como o default da coluna e do `Predicado`. Sem este
        # `or`, um payload sem `operador` (o caminho de quem chama a função
        # direto, sem passar pelo modelo do FastAPI) morria com "operador
        # inválido" — mensagem que não ajuda ninguém a consertar nada.
        if (p.get("operador") or ">=") not in (">=", ">", "<=", "<"):
            raise CriterioInvalido(f"requisito {i}: operador inválido.")

        tem_nota = p.get("valor_nota") is not None
        # "informou acertos" é ter QUALQUER metade do par, não o par completo.
        # Com o `and`, um payload com nota=7 e acertos=5 (sem `de`) passava
        # como "só nota" — e ia morrer no CHECK da 0023, no insert dos
        # predicados, com o critério já gravado e órfão.
        informou_acertos = p.get("valor_acertos") is not None or p.get("valor_de") is not None
        if tem_nota and informou_acertos:
            raise CriterioInvalido(
                f"requisito {i}: informe OU uma nota (0–10) OU 'N de M acertos', nunca os dois."
            )
        if not tem_nota and not informou_acertos:
            raise CriterioInvalido(
                f"requisito {i}: informe uma nota (0–10) ou 'N de M acertos'."
            )
        tem_acertos = p.get("valor_acertos") is not None and p.get("valor_de") is not None
        if informou_acertos and not tem_acertos:
            raise CriterioInvalido(
                f"requisito {i}: 'N de M acertos' precisa dos dois números."
            )
        if tem_nota and not 0 <= float(p["valor_nota"]) <= 10:
            raise CriterioInvalido(f"requisito {i}: a nota mínima tem que estar entre 0 e 10.")
        if tem_acertos:
            acertos, de = int(p["valor_acertos"]), int(p["valor_de"])
            if de <= 0 or not 0 <= acertos <= de:
                raise CriterioInvalido(
                    f"requisito {i}: 'N de M' precisa de M > 0 e 0 ≤ N ≤ M."
                )
        # `p.get("peso") or 1` transformava 0 em 1 ANTES da comparação, então a
        # guarda nunca via o zero que a própria mensagem nomeia — e o critério
        # era gravado com peso 1, mudando a média ponderada sem avisar.
        bruto = p.get("peso")
        peso = 1.0 if bruto is None else float(bruto)
        if peso <= 0:
            raise CriterioInvalido(f"requisito {i}: peso tem que ser maior que zero.")


def de_payload(payload: dict) -> criterios.Criterio:
    """Payload validado → `Criterio`, SEM gravar. É o que a prévia avalia."""
    predicados = []
    for p in payload.get("predicados") or []:
        if p.get("valor_acertos") is not None and p.get("valor_de"):
            valor: float | criterios.Acertos = criterios.Acertos(
                acertos=int(p["valor_acertos"]), de=int(p["valor_de"])
            )
        else:
            valor = float(p.get("valor_nota") or 0)
        predicados.append(
            criterios.Predicado(
                materia=p.get("materia"),
                valor=valor,
                operador=p.get("operador") or ">=",
                eliminatorio=bool(p.get("eliminatorio")),
                entra_na_media=bool(p.get("entra_na_media", True)),
                peso=_peso(p.get("peso")),
                fonte=(p.get("fonte") or "").strip(),
            )
        )
    return criterios.Criterio(
        slug=(payload.get("slug") or "previa").strip(),
        nome=(payload.get("nome") or "Prévia").strip(),
        combinador=payload.get("combinador") or "algum",
        predicados=tuple(predicados),
        desempate=tuple(payload.get("desempate") or ("media",)),
        fase=payload.get("fase"),
        descricao=(payload.get("descricao") or "").strip(),
    )


# ─── Escrita ──────────────────────────────────────────────────────────────


def _gravar(cliente, payload: dict, *, versao: int, criado_por: str | None) -> dict:
    linha = (
        cliente.table("criterio_classificacao")
        .insert({
            "slug": payload["slug"],
            "versao": versao,
            "nome": payload["nome"].strip(),
            "descricao": (payload.get("descricao") or "").strip() or None,
            "combinador": payload["combinador"],
            "fase": payload.get("fase"),
            "desempate": list(payload.get("desempate") or ["media"]),
            "embutido": False,
            "ativo": True,
            "criado_por": criado_por,
        })
        .execute()
    ).data[0]

    predicados = [
        {
            "criterio_id": linha["id"],
            "posicao": i,
            "materia": p.get("materia"),
            "operador": p.get("operador") or ">=",
            "valor_nota": p.get("valor_nota"),
            "valor_acertos": p.get("valor_acertos"),
            "valor_de": p.get("valor_de"),
            "eliminatorio": bool(p.get("eliminatorio")),
            "entra_na_media": bool(p.get("entra_na_media", True)),
            "peso": _peso(p.get("peso")),
            "fonte": (p.get("fonte") or "").strip() or None,
        }
        for i, p in enumerate(payload.get("predicados") or [], start=1)
    ]
    # PostgREST não tem transação entre chamadas, e estas são duas. Se a
    # segunda falhar, sobra um critério ATIVO e sem requisito nenhum — e
    # `avaliar` devolve APROVADO quando não avaliou nada (`avaliou_algum`),
    # então essa régua fantasma aprovaria a base inteira, calada. O `ON DELETE
    # CASCADE` da 0023 limpa o que tiver entrado.
    try:
        if predicados:
            cliente.table("predicado_criterio").insert(predicados).execute()
    except Exception:
        log.exception("predicados falharam; desfazendo o critério %s", linha["id"])
        try:
            cliente.table("criterio_classificacao").delete().eq("id", linha["id"]).execute()
        except Exception:
            # Se nem a compensação passa, é melhor a régua ficar inativa do que
            # ativa e vazia: quem lista filtra por `ativo`.
            log.exception("não consegui apagar o critério %s; desativando", linha["id"])
            cliente.table("criterio_classificacao").update({"ativo": False}).eq(
                "id", linha["id"]
            ).execute()
        raise

    return linha


def criar(cliente, payload: dict, *, criado_por: str | None = None) -> dict:
    """Grava uma régua nova na versão 1."""
    validar(payload)
    if versoes(cliente, payload["slug"]):
        raise CriterioInvalido(
            f"já existe uma régua com o identificador '{payload['slug']}'."
        )
    return _gravar(cliente, payload, versao=1, criado_por=criado_por)


def nova_versao(cliente, slug: str, payload: dict, *, criado_por: str | None = None) -> dict:
    """Edita = grava a versão seguinte e desativa a anterior.

    A anterior fica no banco, inativa: quem quiser explicar um número antigo
    ainda consegue ler sob que régua ele saiu.
    """
    if slug in criterios.CRITERIOS:
        raise CriterioInvalido("réguas embutidas não se editam — elas vêm do arquivo.")
    anteriores = versoes(cliente, slug)
    if not anteriores:
        raise CriterioInvalido(f"régua '{slug}' não existe.")
    if anteriores[0].get("embutido"):
        raise CriterioInvalido("réguas embutidas não se editam — elas vêm do arquivo.")

    # O slug é o da régua existente, não o que veio no corpo: renomear o
    # identificador criaria uma régua nova disfarçada de versão.
    payload = {**payload, "slug": slug}
    validar(payload)

    proxima = (anteriores[0].get("versao") or 1) + 1
    # A nova versão entra INTEIRA antes de a anterior sair de cena: se
    # `_gravar` levantar, a régua que já estava valendo continua valendo.
    nova = _gravar(cliente, payload, versao=proxima, criado_por=criado_por)
    cliente.table("criterio_classificacao").update({"ativo": False}).eq(
        "id", anteriores[0]["id"]
    ).execute()
    return nova


def desativar(cliente, slug: str) -> dict:
    """Tira a régua do seletor. Não apaga: ela nomeia números já lidos.

    A pergunta "é embutida?" vem ANTES de "existe no banco?" de propósito: a
    resposta certa para `desativar('tio-leo')` é "essa não se remove", e não
    "essa não existe" — que é o que sairia se a carga inicial da 0023 ainda não
    tivesse rodado naquele ambiente.
    """
    if slug in criterios.CRITERIOS:
        raise CriterioInvalido(
            "réguas embutidas não podem ser removidas: são a régua do colégio e as dos editais."
        )
    linhas = versoes(cliente, slug)
    if not linhas:
        raise CriterioInvalido(f"régua '{slug}' não existe.")
    if linhas[0].get("embutido"):
        raise CriterioInvalido(
            "réguas embutidas não podem ser removidas: são a régua do colégio e as dos editais."
        )
    for linha in linhas:
        cliente.table("criterio_classificacao").update({"ativo": False}).eq(
            "id", linha["id"]
        ).execute()
    return linhas[0]
