"""
reclassificar.py — Reset em massa da classificação do banco.

Zera o campo `classificacao` e `status.classificado` de todas as questões
(ou de uma prova específica), preparando o banco para ser reclassificado
do zero com a nova semântica de TAGS:

  - 1+ tópicos por questão (topicos_ids);
  - no máximo 3 BLOCOS distintos (assuntos);
  - dentro de cada bloco, quantos tópicos forem necessários.

Depois de rodar este script, use o fluxo normal em classificar.py:

    python pipeline/reclassificar.py                 # reseta tudo
    python pipeline/reclassificar.py --prova ita_2019_fase1
    python pipeline/reclassificar.py --dry-run       # só mostra o que faria

    # para cada prova resetada, rodar:
    python pipeline/classificar.py listar  <prova_id>
    python pipeline/classificar.py aplicar <prova_id> patch.json
"""

import argparse
import json
from pathlib import Path

PROJETO_ROOT = Path(__file__).resolve().parent.parent
DIR_QUESTOES_JSON = PROJETO_ROOT / "questoes_json"

if not DIR_QUESTOES_JSON.is_dir():
    raise SystemExit(
        f"Diretório não encontrado: {DIR_QUESTOES_JSON}\n"
        f"Rode o script a partir da raiz do projeto ou verifique a estrutura."
    )

CLASSIFICACAO_VAZIA = {
    "topicos_ids": [],
    "topicos_nomes": [],
    "blocos": [],
    "classificado_por": "",
    "confianca": "",
    "observacao": "",
}


def descobrir_provas() -> list[str]:
    return sorted(
        d.name for d in DIR_QUESTOES_JSON.iterdir()
        if d.is_dir() and any(d.glob("q*.json"))
    )


def resetar_prova(prova_id: str, dry_run: bool) -> tuple[int, int]:
    """Reseta as questões de uma prova. Retorna (resetadas, ja_pendentes)."""
    dir_prova = DIR_QUESTOES_JSON / prova_id
    if not dir_prova.exists():
        print(f"  ⚠ prova não encontrada: {prova_id}")
        return (0, 0)

    resetadas = 0
    ja_pendentes = 0
    for json_path in sorted(dir_prova.glob("q*.json")):
        with open(json_path, encoding="utf-8") as f:
            q = json.load(f)

        if not q.get("status", {}).get("classificado"):
            ja_pendentes += 1
            continue

        if dry_run:
            resetadas += 1
            continue

        q["classificacao"] = dict(CLASSIFICACAO_VAZIA)
        q["status"]["classificado"] = False

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(q, f, ensure_ascii=False, indent=2)
        resetadas += 1

    return (resetadas, ja_pendentes)


def main():
    parser = argparse.ArgumentParser(
        description="Reseta classificações para reclassificar o banco do zero."
    )
    parser.add_argument(
        "--prova",
        help="Reseta apenas uma prova (ex.: ita_2019_fase1). Omita para resetar todas.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria feito sem gravar nada.",
    )
    args = parser.parse_args()

    provas = [args.prova] if args.prova else descobrir_provas()

    total_resetadas = 0
    total_pendentes = 0
    print(f"{'[DRY-RUN] ' if args.dry_run else ''}Resetando {len(provas)} prova(s)...\n")
    for pid in provas:
        resetadas, pendentes = resetar_prova(pid, args.dry_run)
        total_resetadas += resetadas
        total_pendentes += pendentes
        if resetadas or pendentes:
            print(f"  {pid}: {resetadas} resetadas, {pendentes} já pendentes")

    print(f"\nTotal: {total_resetadas} questões resetadas · {total_pendentes} já estavam pendentes")
    if args.dry_run:
        print("(dry-run — nenhuma alteração gravada)")
        return

    if len(provas) == 1:
        pid = provas[0]
        print("\nPróximos passos:")
        print(f"  python pipeline/classificar.py listar  {pid}")
        print(f"  python pipeline/classificar.py aplicar {pid} patch.json")
    else:
        print(f"\nPróximos passos — classifique cada uma das {len(provas)} provas:")
        print("  python pipeline/classificar.py listar  <prova_id>")
        print("  python pipeline/classificar.py aplicar <prova_id> patch.json")
        preview = ", ".join(provas[:3])
        print(f"\n  Primeiras provas: {preview}, ... ({len(provas)} total)")


if __name__ == "__main__":
    main()
