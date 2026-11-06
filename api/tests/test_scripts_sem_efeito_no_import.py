"""Importar um script de `scripts/` não pode carregar `.env` nenhum.

Dez scripts chamavam `load_dotenv()` no topo, e o `load_dotenv()` sem argumento
sobe a árvore a partir do arquivo até achar um `.env`: o `api/.env` real na
máquina de quem desenvolve ou, num worktree (que não tem o seu), o da raiz do
repositório principal. O que ele acha vai para o `os.environ` e fica lá pelo
resto da suíte.

Bastou `tests/test_mcp_rotas.py` importar `scripts/criar_token_mcp.py` para
cinco testes do guard do MCP (`test_mcp_tokens.py`, `test_oauth_mcp.py`)
reprovarem na suíte inteira e passarem isolados. O guard recusa subir com
segredo da API no ambiente, e o segredo estava lá, vindo do `.env`. O portão de
pytest do `deploy.sh` reprovava por isso, e o deploy de 05/11/2026 saiu com
`--rapido`.

A regra: carregar o `.env` é coisa de quem RODA o script, dentro de
`if __name__ == "__main__":` ou de uma função. Este teste lê o código em vez de
importá-lo, para valer também para o script que nenhum teste importa ainda.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

DIR_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
SCRIPTS = sorted(DIR_SCRIPTS.glob("*.py"))

# O que põe um `.env` no `os.environ`. `_carregar_dotenv` é o leitor à mão de
# `migrate.py`, `recalcular_metricas.py` e companhia: faz o mesmo sem a
# dependência, e por isso segue a mesma regra.
CARREGADORES = {"load_dotenv", "_carregar_dotenv"}


def _e_guarda_do_main(teste: ast.expr) -> bool:
    return (
        isinstance(teste, ast.Compare)
        and isinstance(teste.left, ast.Name)
        and teste.left.id == "__name__"
        and len(teste.comparators) == 1
        and isinstance(teste.comparators[0], ast.Constant)
        and teste.comparators[0].value == "__main__"
    )


def _nome_chamado(chamada: ast.Call) -> str | None:
    if isinstance(chamada.func, ast.Name):
        return chamada.func.id
    if isinstance(chamada.func, ast.Attribute):  # dotenv.load_dotenv()
        return chamada.func.attr
    return None


def _rodam_no_import(no: ast.AST) -> Iterator[ast.Call]:
    """As chamadas que rodam ao importar o módulo.

    Corpo de função não roda no import; corpo de classe roda, e por isso entra.
    Da guarda do `__main__` só o `else` roda no import.
    """
    if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
        return
    if isinstance(no, ast.If) and _e_guarda_do_main(no.test):
        for comando in no.orelse:
            yield from _rodam_no_import(comando)
        return
    if isinstance(no, ast.Call):
        yield no
    for filho in ast.iter_child_nodes(no):
        yield from _rodam_no_import(filho)


def _carregadores_no_import(codigo: str) -> set[str]:
    return {_nome_chamado(c) for c in _rodam_no_import(ast.parse(codigo))} & CARREGADORES


def test_o_glob_achou_os_scripts() -> None:
    """Um glob vazio faria o teste abaixo passar sem conferir nada."""
    assert len(SCRIPTS) > 10
    assert DIR_SCRIPTS / "criar_token_mcp.py" in SCRIPTS


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_importar_o_script_nao_carrega_o_env(script: Path) -> None:
    achados = _carregadores_no_import(script.read_text(encoding="utf-8"))
    assert not achados, (
        f"{script.name} chama {', '.join(sorted(achados))} no import. Ponha dentro de "
        "`if __name__ == '__main__':`; o porquê está no docstring deste arquivo."
    )


@pytest.mark.parametrize(
    ("codigo", "esperado"),
    [
        ("from dotenv import load_dotenv\nload_dotenv()\n", {"load_dotenv"}),
        ("import dotenv\ndotenv.load_dotenv()\n", {"load_dotenv"}),
        ("if True:\n    load_dotenv()\n", {"load_dotenv"}),
        ("class X:\n    _carregar_dotenv('.env')\n", {"_carregar_dotenv"}),
        ("if __name__ == '__main__':\n    pass\nelse:\n    load_dotenv()\n", {"load_dotenv"}),
        ("if __name__ == '__main__':\n    load_dotenv()\n", set()),
        ("def main():\n    _carregar_dotenv('.env')\n", set()),
        ("class X:\n    def m(self):\n        load_dotenv()\n", set()),
    ],
)
def test_o_detector_separa_o_que_roda_no_import(codigo: str, esperado: set[str]) -> None:
    """O detector sem teste próprio poderia não enxergar nada e passar tudo."""
    assert _carregadores_no_import(codigo) == esperado
