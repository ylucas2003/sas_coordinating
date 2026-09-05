"""Aplica ao banco os patches de classificação de `banco-questoes/patches/`.

**Por que este script existe, e por que ele não é o importador.**

O caminho normal de classificar é o pipeline: `classificar.py listar` → patch
JSON → `classificar.py aplicar` → `importar_banco_questoes.py`. Ele funciona em
desenvolvimento e não funciona em produção, por três motivos que se somam:

  1. `banco-questoes/questoes_json/` está no `.gitignore` (linha 35), e o rsync
     do deploy usa `--filter=':- .gitignore'` — os JSONs corrigidos **nunca
     chegam ao servidor**;
  2. rodar o importador do laptop contra a produção também não dá: só o serviço
     `web` publica porta na stack de produção, por desenho (CLAUDE.md,
     armadilha 4), então não existe endereço de PostgREST para apontar;
  3. rodar de dentro da imagem também não: o contexto de build da API é
     `../../api`, então `banco-questoes/` não está no container.

O resultado é que uma classificação feita em desenvolvimento fica presa lá. Foi
o que quase aconteceu com as 44 questões órfãs de 04/09 (docs/35 §3): o plano
prometia "o banco não tem prova inteira sem classificação" e o deploy não
carregava o conserto.

Este script fecha o buraco pelo lado do DADO: os patches são pequenos, são a
decisão em si (que tópicos a questão cobra, e por quê), e por isso passam a ser
**versionados** em `banco-questoes/patches/`. O que não é versionado continua
não sendo — o acervo mora no Postgres, e é ele a fonte da verdade (docs/22 §13).

Uso:

    python -m scripts.aplicar_patches_de_classificacao              # relatório, não grava
    python -m scripts.aplicar_patches_de_classificacao --aplicar

Em produção, de dentro do container (o `-T </dev/null` não é opcional quando
isto roda por `ssh bash -s`; CLAUDE.md, armadilha 5):

    docker compose run --rm -T api \\
        python -m scripts.aplicar_patches_de_classificacao --aplicar </dev/null

⚠️ Ele NÃO apaga classificação que já existe em questão fora dos patches, e não
mexe em questão que já tem tópico — ver `_ja_classificadas`. Rodar duas vezes
não muda nada na segunda.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.supabase_client import criar_cliente_supabase

# O diretório dos patches é irmão de `api/`, não filho — o pipeline vive fora da
# API de propósito (nada ali roda em requisição; ver banco-questoes/README.md).
_RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
_PATCHES = _RAIZ / "banco-questoes" / "patches"

# O prefixo do id de uma questão é o nome da pasta da prova, e o sufixo é o
# número com dois dígitos: `ita_2008_fase1` + `q11` → `ita_2008_fase1_q11`.
# É a mesma convenção que `exportar_banco_questoes.py` usa para nomear a pasta.


def _questoes_do_patch(arquivo: pathlib.Path) -> dict[str, dict]:
    """{id_da_questao: dados} de um patch, ignorando chaves de metadado."""
    prova = arquivo.stem
    bruto = json.loads(arquivo.read_text(encoding="utf-8"))
    return {
        f"{prova}_{chave}": dados
        for chave, dados in bruto.items()
        if not chave.startswith("_")
    }


def _ja_classificadas(cliente, ids: list[str]) -> set[str]:
    """Quais desses ids JÁ têm ligação — são as que este script não toca.

    A regra é conservadora de propósito: o patch é de uma leva específica de
    questões órfãs, e sobrescrever uma classificação feita depois (à mão, ou por
    uma releitura melhor) seria perder trabalho sem avisar.
    """
    achadas: set[str] = set()
    for i in range(0, len(ids), 200):
        resposta = (
            cliente.table("questao_vestibular_topico")
            .select("questao_id")
            .in_("questao_id", ids[i : i + 200])
            .execute()
        )
        achadas.update(linha["questao_id"] for linha in resposta.data or [])
    return achadas


def _materia_por_questao(cliente, ids: list[str]) -> dict[str, str]:
    """A matéria de cada questão. A ligação é (questao, materia, codigo).

    A matéria vem do BANCO e não do patch: o código do tópico só tem sentido
    dentro de uma matéria (`1.1` é "Fundamentos" em Física e "Conjuntos e
    Lógica" em Matemática), e deixar o patch declarar a matéria abriria espaço
    para o par sair errado — que é exatamente o defeito que a missão do dia
    tinha (docs/35 §9).
    """
    mapa: dict[str, str] = {}
    for i in range(0, len(ids), 200):
        resposta = (
            cliente.table("questao_vestibular")
            .select("id, materia")
            .in_("id", ids[i : i + 200])
            .execute()
        )
        mapa.update({linha["id"]: linha["materia"] for linha in resposta.data or []})
    return mapa


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="grava. Sem esta flag o script só relata, como o recalcular_resolucao_url.",
    )
    args = parser.parse_args()

    if not _PATCHES.is_dir():
        print(f"✗ diretório de patches não encontrado: {_PATCHES}", file=sys.stderr)
        return 1

    patches = sorted(_PATCHES.glob("*.json"))
    if not patches:
        print(f"Nenhum patch em {_PATCHES}. Nada a fazer.")
        return 0

    desejadas: dict[str, dict] = {}
    for arquivo in patches:
        desejadas.update(_questoes_do_patch(arquivo))

    cliente = criar_cliente_supabase()
    ids = sorted(desejadas)
    materias = _materia_por_questao(cliente, ids)
    classificadas = _ja_classificadas(cliente, ids)

    ausentes = [i for i in ids if i not in materias]
    pular = [i for i in ids if i in classificadas]
    aplicar = [i for i in ids if i in materias and i not in classificadas]

    print(f"{len(patches)} patch(es), {len(ids)} questão(ões) descritas.")
    if ausentes:
        print(f"  ! {len(ausentes)} não existem neste banco (ignoradas):")
        for i in ausentes[:5]:
            print(f"      {i}")
    if pular:
        print(f"  · {len(pular)} já classificadas — não serão tocadas.")
    print(f"  → {len(aplicar)} a classificar.")

    if not aplicar:
        print("\nNada a fazer.")
        return 0

    ligacoes = [
        {"questao_id": i, "materia": materias[i], "topico_codigo": codigo}
        for i in aplicar
        for codigo in desejadas[i].get("topicos_ids") or []
    ]
    sem_topico = [i for i in aplicar if not (desejadas[i].get("topicos_ids") or [])]
    if sem_topico:
        print(f"\n✗ {len(sem_topico)} questão(ões) no patch sem `topicos_ids`:", file=sys.stderr)
        for i in sem_topico:
            print(f"    {i}", file=sys.stderr)
        return 1

    exemplo = aplicar[0]
    print(f"\n  exemplo — {exemplo} ({materias[exemplo]})")
    print(f"    tópicos: {', '.join(desejadas[exemplo]['topicos_ids'])}")

    if not args.aplicar:
        print(f"\n  → {len(ligacoes)} ligação(ões) seriam gravadas. Rode com --aplicar.")
        return 0

    for i in range(0, len(ligacoes), 500):
        cliente.table("questao_vestibular_topico").upsert(
            ligacoes[i : i + 500],
            on_conflict="questao_id,materia,topico_codigo",
            returning="minimal",
        ).execute()

    # A procedência fica na questão, não só na ligação: é o que permite separar
    # depois o que foi lido por gente do que foi lido por agente.
    for questao_id in aplicar:
        dados = desejadas[questao_id]
        cliente.table("questao_vestibular").update(
            {"classificado_por": dados.get("classificado_por") or "claude"}
        ).eq("id", questao_id).execute()

    print(f"\n✓ {len(ligacoes)} ligação(ões) gravadas em {len(aplicar)} questão(ões).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
