"""Loader do disco — lê a pasta da questão e da resposta do aluno, seguindo
a convenção documentada no README.md desta pasta.

Sem chamadas de rede/LLM aqui — puro filesystem + dataclasses, fácil de
conferir na mão.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

EXTENSOES_IMAGEM = (".jpg", ".jpeg", ".png")


@dataclass
class Questao:
    id: str
    enunciado_texto: str
    caminho_figura: Path | None
    gabarito_texto: str
    materia: str | None
    nota_maxima: float
    anulada: bool


@dataclass
class RespostaAluno:
    aluno_id: str
    caminhos_paginas: list[Path]
    resposta_texto: str | None
    nota_humana: float | None  # None => ainda não há nota humana pra comparar
    nota_maxima: float
    observacoes: str | None


def _ler_texto_obrigatorio(pasta: Path, nome_arquivo: str) -> str:
    caminho = pasta / nome_arquivo
    if not caminho.is_file():
        raise FileNotFoundError(
            f"Arquivo obrigatório não encontrado: {caminho}. "
            f"Veja a convenção de dados em grading_prototype/README.md."
        )
    texto = caminho.read_text(encoding="utf-8").strip()
    if not texto:
        raise ValueError(
            f"Arquivo obrigatório está vazio: {caminho}. "
            f"Preencha-o antes de rodar o pipeline."
        )
    return texto


def _ler_texto_opcional(pasta: Path, nome_arquivo: str) -> str | None:
    caminho = pasta / nome_arquivo
    if not caminho.is_file():
        return None
    texto = caminho.read_text(encoding="utf-8").strip()
    return texto or None


def _ler_metadata(pasta: Path) -> dict:
    caminho = pasta / "metadata.json"
    if not caminho.is_file():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"metadata.json malformado em {pasta}: {exc}") from exc


def _buscar_arquivo_por_prefixo(pasta: Path, prefixo: str) -> Path | None:
    candidatos = sorted(
        p for p in pasta.glob(f"{prefixo}.*") if p.suffix.lower() in EXTENSOES_IMAGEM
    )
    return candidatos[0] if candidatos else None


def _chave_ordem_natural(caminho: Path) -> tuple:
    """Ordena pagina_2 antes de pagina_10 mesmo sem zero-padding."""
    numeros = re.findall(r"\d+", caminho.stem)
    return (int(numeros[-1]) if numeros else 0, caminho.name)


def questao_esta_anulada(pasta: Path) -> bool:
    """Checagem barata (só o metadata.json), usável ANTES de carregar a
    questão inteira — questão anulada pode nem ter gabarito válido."""
    try:
        return bool(_ler_metadata(pasta).get("anulada", False))
    except ValueError:
        log.warning("metadata.json malformado em %s — tratando como não anulada.", pasta)
        return False


def carregar_questao(pasta: Path) -> Questao:
    """Lê enunciado.txt, gabarito.txt, enunciado_figura.* e metadata.json (opcional)."""
    if not pasta.is_dir():
        raise FileNotFoundError(f"Pasta da questão não encontrada: {pasta}")

    enunciado_texto = _ler_texto_obrigatorio(pasta, "enunciado.txt")
    gabarito_texto = _ler_texto_obrigatorio(pasta, "gabarito.txt")

    caminho_figura = _buscar_arquivo_por_prefixo(pasta, "enunciado_figura")
    if caminho_figura is None:
        log.info(
            "Nenhuma figura (enunciado_figura.jpg/.png) encontrada em %s — "
            "questão tratada como texto-only (comum em Matemática analítica).",
            pasta,
        )

    metadata = _ler_metadata(pasta)

    return Questao(
        id=pasta.name,
        enunciado_texto=enunciado_texto,
        caminho_figura=caminho_figura,
        gabarito_texto=gabarito_texto,
        materia=metadata.get("materia"),
        nota_maxima=float(metadata.get("nota_maxima", 10.0)),
        anulada=bool(metadata.get("anulada", False)),
    )


def listar_alunos_disponiveis(pasta_questao: Path) -> list[str]:
    """Lista os ids de aluno disponíveis em <pasta_questao>/respostas/."""
    pasta_respostas = pasta_questao / "respostas"
    if not pasta_respostas.is_dir():
        return []
    return sorted(p.name for p in pasta_respostas.iterdir() if p.is_dir())


def carregar_resposta_aluno(pasta_questao: Path, aluno_id: str) -> RespostaAluno:
    """Lê a resposta de um aluno: fotos (`pagina_*.jpg/png`, em ordem natural)
    e/ou texto já transcrito (`resposta.txt`) — pelo menos um dos dois precisa
    existir. `nota_humana.json` é OPCIONAL: ausente significa que ainda não
    há correção humana pra comparar (caso de uso de correção real, não só
    validação — ver `corrigir_prova.py`)."""
    pasta_aluno = pasta_questao / "respostas" / aluno_id
    if not pasta_aluno.is_dir():
        disponiveis = listar_alunos_disponiveis(pasta_questao)
        raise FileNotFoundError(
            f"Resposta do aluno '{aluno_id}' não encontrada em {pasta_aluno}. "
            f"Alunos disponíveis: {disponiveis or '(nenhum)'}"
        )

    caminhos_paginas = sorted(
        (
            p
            for p in pasta_aluno.glob("pagina_*.*")
            if p.suffix.lower() in EXTENSOES_IMAGEM
        ),
        key=_chave_ordem_natural,
    )
    resposta_texto = _ler_texto_opcional(pasta_aluno, "resposta.txt")
    if not caminhos_paginas and resposta_texto is None:
        raise FileNotFoundError(
            f"Nenhuma resposta encontrada em {pasta_aluno} "
            f"(esperado pagina_01.jpg ou resposta.txt)."
        )

    nota_humana = None
    nota_maxima = 10.0
    observacoes = None
    caminho_nota = pasta_aluno / "nota_humana.json"
    if caminho_nota.is_file():
        try:
            nota_dados = json.loads(caminho_nota.read_text(encoding="utf-8"))
            nota_humana = float(nota_dados["nota"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"nota_humana.json inválido em {pasta_aluno}: esperado "
                f'{{"nota": 7.5, "nota_maxima": 10.0}} — erro: {exc}'
            ) from exc
        nota_maxima = float(nota_dados.get("nota_maxima", 10.0))
        observacoes = nota_dados.get("observacoes")

    return RespostaAluno(
        aluno_id=aluno_id,
        caminhos_paginas=caminhos_paginas,
        resposta_texto=resposta_texto,
        nota_humana=nota_humana,
        nota_maxima=nota_maxima,
        observacoes=observacoes,
    )
