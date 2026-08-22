"""Taxonomias dos editais: JSON de `banco-questoes/config/` → linhas de `topico_taxonomia`.

Os três arquivos vêm do projeto de origem com uma hierarquia de dois níveis
(bloco → subárea → lista de assuntos). A tabela é plana, com uma linha por
**subárea**, porque é a subárea que a classificação referencia: o
`classificacao.topicos_ids` de cada questão guarda códigos como "7.2", que são
`subareas[].id`. O bloco vira duas colunas desnormalizadas (`bloco_codigo`,
`bloco_nome`) para a árvore da API sair de uma leitura só.

Ver docs/22 §1.2 e migration 0028.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# `banco-questoes/` mora na raiz do repositório, fora de `api/` — o pipeline que
# gera esses JSONs lê PDF, faz OCR e fala com o S3, e não tem por que entrar na
# imagem da API (docs/22 §7.1). Daí subir quatro níveis a partir deste arquivo:
# app/banco/taxonomia.py → app/banco → app → api → raiz.
_RAIZ_PADRAO = Path(__file__).resolve().parents[3]

# Explícito de propósito: o nome antigo era `taxonomia.json` para Física — a
# primeira a ser feita — e sufixo só nas outras duas. Acidente histórico que já
# virou armadilha uma vez (docs/22 §7.1); aqui as três aparecem lado a lado.
ARQUIVO_POR_MATERIA: dict[str, str] = {
    "Física": "taxonomia-fisica.json",
    "Química": "taxonomia-quimica.json",
    "Matemática": "taxonomia-matematica.json",
}


def raiz_repositorio() -> Path:
    """Raiz do repositório SAS, deduzida da posição deste arquivo."""
    return _RAIZ_PADRAO


def carregar_taxonomias(raiz: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """Lê os três JSONs e devolve, por matéria, as linhas de `topico_taxonomia`.

    Cada linha já vem no formato da tabela: materia, codigo, nome, bloco_codigo,
    bloco_nome, assuntos, ordem.

    `ordem` é a posição no arquivo, não o código: ordenar por `codigo` como texto
    colocaria "10.1" antes de "2.1", e a árvore da tela sairia fora da ordem do
    edital. Como a leitura é sequencial, a numeração é estável entre execuções —
    só muda se o edital mudar, que é exatamente quando deve mudar.
    """
    base = (raiz or _RAIZ_PADRAO) / "banco-questoes" / "config"
    if not base.is_dir():
        raise FileNotFoundError(
            f"Taxonomias não encontradas em {base}. Este importador só roda com o "
            "repositório completo — `banco-questoes/` não entra na imagem da API."
        )

    taxonomias: dict[str, list[dict[str, Any]]] = {}
    for materia, nome_arquivo in ARQUIVO_POR_MATERIA.items():
        caminho = base / nome_arquivo
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        taxonomias[materia] = _achatar(materia, dados, caminho)
    return taxonomias


def codigos_por_materia(taxonomias: dict[str, list[dict[str, Any]]]) -> dict[str, set[str]]:
    """{materia: {códigos válidos}} — o que o importador usa para validar a classificação."""
    return {materia: {linha["codigo"] for linha in linhas} for materia, linhas in taxonomias.items()}


def _achatar(materia: str, dados: dict[str, Any], caminho: Path) -> list[dict[str, Any]]:
    linhas: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for bloco in dados.get("blocos") or []:
        for subarea in bloco.get("subareas") or []:
            codigo = str(subarea["id"])
            # A PK é (materia, codigo). Um código repetido dentro do mesmo arquivo
            # faria o upsert sobrescrever silenciosamente a primeira ocorrência —
            # e a questão classificada nela apareceria no tópico errado.
            if codigo in vistos:
                raise ValueError(f"{caminho}: código de tópico duplicado '{codigo}' em {materia}.")
            vistos.add(codigo)
            linhas.append(
                {
                    "materia": materia,
                    "codigo": codigo,
                    "nome": subarea["nome"],
                    "bloco_codigo": str(bloco["id"]),
                    "bloco_nome": bloco["nome"],
                    "assuntos": list(subarea.get("topicos") or []),
                    "ordem": len(linhas),
                }
            )
    return linhas
