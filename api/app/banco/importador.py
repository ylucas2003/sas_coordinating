"""Importador do banco de questões: `banco-questoes/questoes_json/` → Postgres.

Três exigências, todas de docs/22 §1.3, e todas já pagas no projeto de origem:

1. **Idempotente.** Corrigir um JSON e rodar de novo é o ciclo de trabalho
   normal, não operação especial. Tudo é upsert por chave natural, e a ligação
   questão↔tópico ainda perde as linhas que o JSON deixou de citar (ver
   `_sincronizar_ligacao`).
2. **Falha alto.** Tópico que não existe na taxonomia da matéria PARA a
   importação dizendo o arquivo e o código. Aceito em silêncio, esse erro vira
   questão invisível no filtro por assunto — e ninguém descobre.
3. **Relatório no fim.** Os números batem com docs/22 §1.4 ou algo mudou.

Escrita por PostgREST, como o resto do backend (CLAUDE.md). Sem SQL, sem ORM.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .resolucao import url_da_resolucao
from .taxonomia import carregar_taxonomias, codigos_por_materia, raiz_repositorio

# O PostgREST engasga com payload grande: a requisição inteira vira um único
# INSERT ... ON CONFLICT, e o custo cresce mais que linearmente. 200 linhas é o
# tamanho já usado no ingest do Canvas (ingest/upsert.py) e cabe em 5 idas.
TAMANHO_LOTE = 200

_DIRETORIO_QUESTOES = "banco-questoes/questoes_json"

# `assuntos` não é mais coluna de `topico_taxonomia` — virou tabela filha (0028).
_COLUNAS_TOPICO = ("materia", "codigo", "nome", "bloco_codigo", "bloco_nome", "ordem")

# Quantos arquivos ruins listar antes de cortar a mensagem. Sem teto, um erro de
# taxonomia inteira despejaria 900 linhas no terminal e esconderia a primeira.
_MAXIMO_ERROS_LISTADOS = 20

# Controles C0 que sobraram da extração do PDF: 53 dos 934 JSONs têm codepoints
# de 0x00 a 0x1F no lugar de delimitadores grandes (parêntese, colchete, barra de
# fração) que a fonte do PDF não mapeou. Não é a sujeira de OCR do docs/22 §8
# (risco 5), que é palavra a mais e fica registrada para depois — é caractere que
# `text` do Postgres NÃO ACEITA: U+0000 devolve 22P05 e derruba o lote inteiro.
# Some no render, que usa a imagem; sai daqui para não poluir a busca textual nem
# a exportação em DOCX da P5, que é XML e também não carrega controle.
_CONTROLES_C0 = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class ErroImportacao(RuntimeError):
    """Dado de entrada inconsistente. Nada foi escrito no banco."""


@dataclass
class RelatorioImportacao:
    """O que entrou. Comparado com docs/22 §1.4 pelo CLI."""

    total: int = 0
    por_materia: dict[str, int] = field(default_factory=dict)
    sem_classificacao: int = 0
    dissertativas: int = 0
    sem_gabarito: int = 0
    com_imagem: int = 0
    topicos_importados: int = 0
    alternativas: int = 0


def importar(cliente: Any, raiz: Path | None = None) -> RelatorioImportacao:
    """Importa taxonomias e questões. Devolve o relatório do que entrou.

    `raiz` é a raiz do repositório (a que contém `banco-questoes/`); por padrão,
    a deduzida da posição do módulo. Parâmetro existe para o teste apontar para
    um diretório de amostra (docs/22 §10).

    A ordem é obrigatória: `questao_vestibular_topico` tem FK para
    `topico_taxonomia` (materia, codigo) e para `questao_vestibular` (id) — os
    dois lados precisam existir antes da ligação.
    """
    raiz = raiz or raiz_repositorio()

    taxonomias = carregar_taxonomias(raiz)
    questoes, alternativas, ligacoes = _ler_questoes(raiz, codigos_por_materia(taxonomias))

    relatorio = _resumir(questoes, alternativas, ligacoes, taxonomias)

    # Toda a validação acontece na leitura, antes de qualquer escrita: uma
    # importação que morre no meio deixaria o banco com metade das questões
    # novas e metade das antigas, e a contagem não denunciaria isso.
    _upsert_taxonomias(cliente, taxonomias)
    _upsert_questoes(cliente, questoes)
    _sincronizar_alternativas(cliente, questoes, alternativas)
    _sincronizar_ligacao(cliente, questoes, ligacoes)

    return relatorio


# ─── Leitura e validação ──────────────────────────────────────────────────


def _ler_questoes(
    raiz: Path, codigos_validos: dict[str, set[str]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    base = raiz / _DIRETORIO_QUESTOES
    if not base.is_dir():
        raise ErroImportacao(
            f"Diretório de questões não encontrado em {base}. Este importador só roda "
            "com o repositório completo — `banco-questoes/` não entra na imagem da API."
        )

    # `_relatorio.json` e `_classificacao_patch.json` são subprodutos do pipeline
    # e não são questões (docs/22 §1.2). Não deviam estar aqui, mas o pipeline os
    # regenera a cada rodada e ninguém lembra de apagar.
    arquivos = sorted(p for p in base.glob("*/*.json") if not p.name.startswith("_"))
    if not arquivos:
        raise ErroImportacao(f"Nenhum arquivo de questão em {base}.")

    questoes: list[dict[str, Any]] = []
    alternativas: list[dict[str, Any]] = []
    ligacoes: list[dict[str, Any]] = []
    problemas: list[str] = []
    agora = datetime.now(UTC).isoformat()

    for caminho in arquivos:
        origem = caminho.relative_to(raiz).as_posix()
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        prova = dados["prova"]
        materia = prova["materia"]

        if materia not in codigos_validos:
            problemas.append(f"{origem}: matéria desconhecida '{materia}'")
            continue

        questoes.append(_linha_questao(dados, prova, materia, origem, agora))
        for letra, texto in (dados.get("alternativas") or {}).items():
            alternativas.append(
                {"questao_id": dados["id"], "letra": letra, "texto": _sem_controles(texto)}
            )

        classificacao = dados.get("classificacao") or {}
        for codigo in classificacao.get("topicos_ids") or []:
            if codigo not in codigos_validos[materia]:
                problemas.append(f"{origem}: tópico '{codigo}' não existe na taxonomia de {materia}")
                continue
            ligacoes.append(
                {
                    "questao_id": dados["id"],
                    "materia": materia,
                    "topico_codigo": codigo,
                    # A confiança é vazia nas 40 sem classificação; o CHECK da
                    # 0028 só aceita alta/media/baixa ou NULL.
                    "confianca": classificacao.get("confianca") or None,
                    "observacao": _sem_controles(classificacao.get("observacao") or "") or None,
                }
            )

    if problemas:
        raise ErroImportacao(_mensagem_de_problemas(problemas))

    return questoes, alternativas, ligacoes


def _linha_questao(
    dados: dict[str, Any], prova: dict[str, Any], materia: str, origem: str, agora: str
) -> dict[str, Any]:
    """Uma linha de `questao_vestibular`, com TODAS as colunas sempre presentes.

    O PostgREST monta as colunas do INSERT a partir do primeiro objeto do lote e
    recusa o resto com PGRST102 se as chaves divergirem. Como `dissertativa`,
    `usa_imagem_no_render` e `resolucao_url` faltam em parte dos JSONs, o default
    tem que ser resolvido aqui, não omitido.
    """
    status = dados.get("status") or {}
    fonte = dados.get("fonte") or {}
    _resolucao_url = url_da_resolucao(
        prova["vestibular"], prova["ano"], prova["fase"], materia, dados["numero"]
    )
    return {
        "id": dados["id"],
        "vestibular": prova["vestibular"],
        "ano": prova["ano"],
        "fase": prova["fase"],
        "materia": materia,
        "numero": dados["numero"],
        "dissertativa": bool(dados.get("dissertativa", False)),
        # NOT NULL no schema, e um JSON de 2ª fase chegou com o enunciado vazio
        # (a questão é só imagem). Vazio é dado; None derrubaria a importação.
        "enunciado_md": _sem_controles(dados.get("enunciado_md") or ""),
        "gabarito": dados.get("gabarito") or None,
        # Os 934 JSONs de antes da 0031 não têm este campo — e todo gabarito
        # deles veio de PDF de banca (extrair_gabarito.py nunca inventou letra;
        # "sugerido" só existe a partir do acervo histórico). Por isso o default
        # é 'banca', não None: se fosse None, reimportar o banco original
        # apagaria a origem que a migration 0031 preencheu direto no banco.
        "gabarito_origem": (dados.get("gabarito_origem") or "banca") if dados.get("gabarito") else None,
        # Gabarito de banca não carrega confiança (CHECK da 0031 proíbe) — só o
        # sugerido tem, e só quando a letra também existe.
        "gabarito_confianca": (
            dados.get("gabarito_confianca")
            if dados.get("gabarito") and dados.get("gabarito_origem") == "sugerido"
            else None
        ),
        "imagem_url": dados.get("imagem_questao_url") or None,
        "usa_imagem_no_render": bool(dados.get("usa_imagem_no_render", False)),
        # Derivada, não lida do JSON: o arquivo nunca teve este campo — quem o
        # calculava era o gerador do HTML estático, que saiu na migração e
        # levou junto a tabela de galerias do Ari (resolucao.py). Só cobre
        # 2019 em diante — o acervo histórico (0031) usa resolucao_md abaixo.
        "resolucao_url": _resolucao_url,
        "resolucao_md": dados.get("resolucao_md") or None,
        # Mesmo raciocínio do gabarito_origem: os 934 JSONs antigos não têm este
        # campo, mas TÊM resolucao_url (calculada acima) sempre que o Ari
        # comenta a prova — o default segue o dado que já existe, não None, pelo
        # mesmo motivo (reimportar não pode apagar o que a 0031 preencheu).
        "resolucao_origem": dados.get("resolucao_origem") or ("ari" if _resolucao_url else None),
        "extraido_por": dados.get("extraido_por") or "pipeline",
        "arquivo_origem": origem,
        "revisado": bool(status.get("revisado", False)),
        # Proveniência e bastidor do pipeline (0030). Com os JSONs fora do git
        # (docs/22 §13), é o que permite ao exportador refazer o arquivo sem
        # perda — e o que responde "de onde veio isto" sem o arquivo à mão.
        "fonte_pdf": fonte.get("pdf") or None,
        "fonte_pagina": fonte.get("pagina"),
        "classificado_por": (dados.get("classificacao") or {}).get("classificado_por") or None,
        "texto_extraido": bool(status.get("texto_extraido", False)),
        "alternativas_extraidas": bool(status.get("alternativas_extraidas", False)),
        "figuras_recortadas": bool(status.get("figuras_recortadas", False)),
        "possivelmente_tem_figura": bool(status.get("possivelmente_tem_figura", False)),
        # Explícito, e não pela DEFAULT da coluna: no reimport o ON CONFLICT só
        # atualiza as colunas enviadas, então a DEFAULT congelaria a data da
        # primeira passada e `importado_em` mentiria.
        "importado_em": agora,
    }


def _sem_controles(texto: str) -> str:
    """Remove os controles C0 (menos \\n, \\r e \\t). Ver `_CONTROLES_C0`."""
    return _CONTROLES_C0.sub("", texto)


def _mensagem_de_problemas(problemas: list[str]) -> str:
    cabecalho = (
        f"{len(problemas)} questão(ões) com classificação inválida — nada foi importado. "
        "Corrija o JSON (ou a taxonomia) e rode de novo:"
    )
    listadas = problemas[:_MAXIMO_ERROS_LISTADOS]
    corpo = "\n".join(f"  - {p}" for p in listadas)
    if len(problemas) > len(listadas):
        corpo += f"\n  ... e mais {len(problemas) - len(listadas)}."
    return f"{cabecalho}\n{corpo}"


def _resumir(
    questoes: list[dict[str, Any]],
    alternativas: list[dict[str, Any]],
    ligacoes: list[dict[str, Any]],
    taxonomias: dict[str, list[dict[str, Any]]],
) -> RelatorioImportacao:
    """As 40 sem classificação são conta, não defeito (docs/22 §1.4).

    Elas não podem sumir do filtro por tópico: o aluno estudaria um recorte
    incompleto sem saber que é incompleto (docs/22 §8, risco 3). O número existe
    aqui para que crescer sem explicação salte à vista.
    """
    classificadas = {ligacao["questao_id"] for ligacao in ligacoes}
    relatorio = RelatorioImportacao(
        total=len(questoes),
        sem_classificacao=sum(1 for q in questoes if q["id"] not in classificadas),
        topicos_importados=sum(len(linhas) for linhas in taxonomias.values()),
        alternativas=len(alternativas),
    )
    for questao in questoes:
        materia = questao["materia"]
        relatorio.por_materia[materia] = relatorio.por_materia.get(materia, 0) + 1
        if questao["dissertativa"]:
            relatorio.dissertativas += 1
        if not questao["gabarito"]:
            relatorio.sem_gabarito += 1
        if questao["imagem_url"]:
            relatorio.com_imagem += 1
    return relatorio


# ─── Escrita ──────────────────────────────────────────────────────────────


def _em_lotes(itens: list, tamanho: int = TAMANHO_LOTE):
    for inicio in range(0, len(itens), tamanho):
        yield itens[inicio : inicio + tamanho]


def _upsert_taxonomias(cliente: Any, taxonomias: dict[str, list[dict[str, Any]]]) -> None:
    """Tópico que sumiu do edital NÃO é apagado: a FK de `questao_vestibular_topico`
    o segura, e apagar em cascata jogaria fora a classificação de questões antigas
    que continuam válidas para a prova do ano delas."""
    linhas = [linha for materia in taxonomias.values() for linha in materia]
    topicos = [{c: linha[c] for c in _COLUNAS_TOPICO} for linha in linhas]
    for lote in _em_lotes(topicos):
        cliente.table("topico_taxonomia").upsert(
            lote, on_conflict="materia,codigo", returning="minimal"
        ).execute()

    # Os assuntos do edital são tabela filha (0028), não lista dentro do tópico.
    # Substituição total: o edital muda de ano para ano, e um assunto que saiu
    # não pode continuar listado.
    assuntos = [
        {
            "materia": linha["materia"],
            "topico_codigo": linha["codigo"],
            "ordem": posicao,
            "texto": texto,
        }
        for linha in linhas
        for posicao, texto in enumerate(linha.get("assuntos") or [])
    ]
    cliente.table("topico_taxonomia_assunto").delete().neq("materia", "").execute()
    for lote in _em_lotes(assuntos):
        cliente.table("topico_taxonomia_assunto").insert(lote, returning="minimal").execute()


def _upsert_questoes(cliente: Any, questoes: list[dict[str, Any]]) -> None:
    for lote in _em_lotes(questoes):
        cliente.table("questao_vestibular").upsert(
            lote, on_conflict="id", returning="minimal"
        ).execute()


def _sincronizar_alternativas(
    cliente: Any, questoes: list[dict[str, Any]], alternativas: list[dict[str, Any]]
) -> None:
    """Substitui as alternativas das questões desta rodada.

    Apaga por questão antes de inserir, e não upsert: uma prova reprocessada
    pode ter menos alternativas do que antes (extração corrigida de 5 para 4), e
    o upsert deixaria a quinta órfã na tela.
    """
    for lote in _em_lotes([questao["id"] for questao in questoes]):
        cliente.table("questao_vestibular_alternativa").delete().in_("questao_id", lote).execute()
    for lote in _em_lotes(alternativas):
        cliente.table("questao_vestibular_alternativa").insert(lote, returning="minimal").execute()


def _sincronizar_ligacao(
    cliente: Any, questoes: list[dict[str, Any]], ligacoes: list[dict[str, Any]]
) -> None:
    """Upsert das ligações + remoção das que o JSON deixou de citar.

    Upsert sozinho não bastaria para a idempotência que interessa: reclassificar
    uma questão de "7.2" para "7.1" e rodar de novo deixaria as DUAS linhas, e a
    recorrência da P4 contaria a questão em dois tópicos — número errado, sem
    erro. Primeiro grava o que deve existir, depois apaga o resto; nessa ordem,
    uma interrupção no meio deixa linha sobrando (visível e corrigível na próxima
    passada) em vez de classificação faltando.
    """
    for lote in _em_lotes(ligacoes):
        cliente.table("questao_vestibular_topico").upsert(
            lote, on_conflict="questao_id,materia,topico_codigo", returning="minimal"
        ).execute()

    desejadas = {(lig["questao_id"], lig["materia"], lig["topico_codigo"]) for lig in ligacoes}
    for lote in _em_lotes([questao["id"] for questao in questoes]):
        resposta = (
            cliente.table("questao_vestibular_topico")
            .select("questao_id, materia, topico_codigo")
            .in_("questao_id", lote)
            .execute()
        )
        for linha in resposta.data or []:
            chave = (linha["questao_id"], linha["materia"], linha["topico_codigo"])
            if chave in desejadas:
                continue
            (
                cliente.table("questao_vestibular_topico")
                .delete()
                .eq("questao_id", linha["questao_id"])
                .eq("materia", linha["materia"])
                .eq("topico_codigo", linha["topico_codigo"])
                .execute()
            )
