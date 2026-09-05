"""
classificar.py — Etapa 4 do pipeline.

Lê JSONs de questões pendentes de classificação e exibe todas as informações
necessárias para que você (via Claude Code no VSCode) faça a classificação
temática conforme a taxonomia do edital.

Dois modos de uso:

Modo 1 — LISTAR (para o Claude ler e você confirmar):
    python classificar.py listar ita_2019_fase1

Esse modo imprime, para cada questão pendente, o enunciado + alternativas +
caminho da imagem + a taxonomia completa. Você copia esse output para o
Claude Code (ou deixa o Claude ler esse arquivo diretamente) e peça para
ele preencher um patch JSON com as classificações.

Modo 2 — APLICAR (aplica classificações de um arquivo patch):
    python classificar.py aplicar ita_2019_fase1 patch.json

Onde patch.json tem o formato:
    {
      "q01": {
        "topicos_ids": ["7.1", "7.2", "6.1"],
        "confianca": "alta",
        "observacao": "Questão mista: reflexão total, natureza da luz, calor específico"
      },
      ...
    }

Regras de classificação (tags):
  - Cada questão precisa de pelo menos 1 tópico (topicos_ids).
  - As tags devem pertencer a no máximo 3 BLOCOS DISTINTOS (assuntos).
  - Dentro de cada bloco, pode-se usar quantos tópicos (subáreas) forem
    necessários. Ex.: ["7.1", "7.2", "6.1"] é válido (2 blocos: Óptica,
    Termodinâmica). Já ["2.1", "3.1", "5.1", "6.1"] é inválido (4 blocos).

Esse fluxo de duas etapas — listar depois aplicar — permite que a classificação
seja revisada antes de ser gravada.
"""

import argparse
import json
from pathlib import Path


PROJETO_ROOT = Path(__file__).resolve().parent.parent
DIR_QUESTOES_JSON = PROJETO_ROOT / "questoes_json"

# ⚠️ Estes nomes JÁ ESTIVERAM ERRADOS, e o erro custou caro: o mapa ficou com os
# nomes de antes da migração de 22/08 (`taxonomia.json`, `taxonomia_quimica.json`,
# `taxonomia_matematica.json`) enquanto o disco passou a ter os três com hífen e
# sufixo de matéria. Resultado: `FileNotFoundError` em QUALQUER matéria — a
# ferramenta emudeceu, ninguém percebeu, e as provas que chegaram depois disso
# entraram no banco sem classificação (docs/35 §3.1).
#
# Continuam escritos à mão porque são três e mudam de década em década — o que
# mudou é que `carregar_taxonomia` agora falha DIZENDO o que existe em config/,
# em vez de estourar um FileNotFoundError cru.
TAXONOMIA_POR_MATERIA = {
    "Física":     "taxonomia-fisica.json",
    "Química":    "taxonomia-quimica.json",
    "Matemática": "taxonomia-matematica.json",
}


def materia_da_prova(prova_id: str) -> str:
    """Detecta a matéria lendo o primeiro JSON de questão da prova."""
    dir_prova = DIR_QUESTOES_JSON / prova_id
    for jp in sorted(dir_prova.glob("q*.json")):
        with open(jp, encoding="utf-8") as f:
            return json.load(f)["prova"]["materia"]
    return "Física"


def carregar_taxonomia(materia: str = "Física") -> dict:
    nome_arquivo = TAXONOMIA_POR_MATERIA.get(materia, "taxonomia-fisica.json")
    path = PROJETO_ROOT / "config" / nome_arquivo
    # Erro explícito em vez de FileNotFoundError cru: foi um arquivo renomeado
    # sem o mapa acompanhar que deixou esta ferramenta muda por duas semanas
    # (docs/35 §3.1). Quem cair aqui de novo lê o que existe no diretório.
    if not path.exists():
        existentes = sorted(p.name for p in (PROJETO_ROOT / "config").glob("taxonomia*.json"))
        raise SystemExit(
            f"Taxonomia de {materia} não encontrada: {path}\n"
            f"O diretório config/ tem: {', '.join(existentes) or '(nenhuma)'}\n"
            f"Se um arquivo foi renomeado, atualize TAXONOMIA_POR_MATERIA."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def indice_topicos(taxonomia: dict) -> dict[str, dict]:
    """
    Achata a taxonomia em um índice {id: {nome, bloco}} para lookup rápido.
    """
    indice = {}
    for bloco in taxonomia["blocos"]:
        for sub in bloco["subareas"]:
            indice[sub["id"]] = {
                "nome": sub["nome"],
                "bloco": bloco["nome"],
                "bloco_id": bloco["id"],
            }
    return indice


def imprimir_taxonomia_resumida(taxonomia: dict, materia: str = "Física"):
    """Imprime a taxonomia em formato compacto, pronto para quem for classificar.

    ⚠️ TODA subárea sai com o id VISÍVEL, mesmo quando é a única do bloco e
    repete o nome dele. Antes a linha era omitida nesse caso, e o que sobrava na
    tela era só o cabeçalho do bloco — "6. Termoquímica". Quem lia copiava `6`,
    que **não é código de tópico**: `indice_topicos` monta o índice só com as
    subáreas, então `aplicar` rejeitava, e no banco a FK de
    `questao_vestibular_topico` recusaria de qualquer jeito.

    O bloco é agrupamento, a subárea é o código. Imprimir os dois no mesmo
    formato numérico convidava a confundir um com o outro — por isso o
    cabeçalho do bloco agora não termina em ponto (docs/35 §3.1).
    """
    print(f"### TAXONOMIA DE {materia.upper()} — use SEMPRE o código X.Y da subárea ###")
    for bloco in taxonomia["blocos"]:
        print(f"\n[bloco {bloco['id']}] {bloco['nome']}")
        for sub in bloco["subareas"]:
            print(f"   {sub['id']} {sub['nome']}")


def modo_listar(prova_id: str):
    dir_prova = DIR_QUESTOES_JSON / prova_id
    materia = materia_da_prova(prova_id)
    taxonomia = carregar_taxonomia(materia)

    imprimir_taxonomia_resumida(taxonomia, materia)

    print(f"\n\n### QUESTÕES PENDENTES DE CLASSIFICAÇÃO — {prova_id} ###\n")

    pendentes = 0
    for json_path in sorted(dir_prova.glob("q*.json")):
        with open(json_path, encoding="utf-8") as f:
            q = json.load(f)

        if q["status"]["classificado"]:
            continue

        pendentes += 1
        print(f"\n---- Q{q['numero']:02d} ----")
        print(f"Imagem: {q.get('imagem_questao', '—')}")
        print(f"Página: {q['fonte']['pagina']}")
        print(f"Enunciado: {q['enunciado_md'][:500]}")
        if q["alternativas"]:
            print("Alternativas:")
            for k, v in q["alternativas"].items():
                print(f"  {k}) {v[:150]}")

    print(f"\n\nTotal pendente: {pendentes}")
    print("\nCOMO CLASSIFICAR (para o Claude Code):")
    print("Para cada questão acima, retorne um patch JSON atribuindo IDs")
    print("da taxonomia. Trate os IDs como TAGS: use todos os tópicos que a")
    print("questão aborda, respeitando o limite de 3 BLOCOS distintos (assuntos).")
    print("Ex.: ['7.1', '7.2', '6.1'] é válido (2 blocos). ['2.1','3.1','5.1','6.1'] não (4 blocos).")
    print("Formato: { 'qNN': { 'topicos_ids': [...], 'confianca': 'alta|media|baixa', 'observacao': '...' } }")


def modo_aplicar(prova_id: str, patch_path: Path):
    dir_prova = DIR_QUESTOES_JSON / prova_id
    materia = materia_da_prova(prova_id)
    taxonomia = carregar_taxonomia(materia)
    indice = indice_topicos(taxonomia)

    with open(patch_path, encoding="utf-8") as f:
        patch = json.load(f)

    aplicados = 0
    avisos = []
    for chave, dados in patch.items():
        # Ignora chaves de metadados (comentários começam com _)
        if chave.startswith("_"):
            continue
        # Chave pode ser "q01", "Q01", "1", etc.
        num = int("".join(c for c in chave if c.isdigit()))
        json_path = dir_prova / f"q{num:02d}.json"
        if not json_path.exists():
            avisos.append(f"Questão {chave} não existe em {prova_id}")
            continue

        with open(json_path, encoding="utf-8") as f:
            q = json.load(f)

        # Valida IDs
        ids = dados.get("topicos_ids", [])
        if not ids:
            avisos.append(f"Q{num}: precisa de pelo menos 1 tópico")
            continue
        ids_invalidos = [i for i in ids if i not in indice]
        if ids_invalidos:
            avisos.append(f"Q{num}: IDs inválidos: {ids_invalidos}")
            continue

        blocos_ids_distintos = {indice[i]["bloco_id"] for i in ids}
        if len(blocos_ids_distintos) > 3:
            blocos_nomes = sorted({indice[i]["bloco"] for i in ids})
            avisos.append(
                f"Q{num}: tags cobrem {len(blocos_ids_distintos)} blocos "
                f"({', '.join(blocos_nomes)}); máximo permitido é 3"
            )
            continue

        nomes = [indice[i]["nome"] for i in ids]
        blocos = list({indice[i]["bloco"] for i in ids})

        q["classificacao"]["topicos_ids"] = ids
        q["classificacao"]["topicos_nomes"] = nomes
        q["classificacao"]["blocos"] = blocos
        q["classificacao"]["classificado_por"] = dados.get("classificado_por", "claude")
        q["classificacao"]["confianca"] = dados.get("confianca", "media")
        q["classificacao"]["observacao"] = dados.get("observacao", "")
        q["status"]["classificado"] = True

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(q, f, ensure_ascii=False, indent=2)
        aplicados += 1

    print(f"Classificações aplicadas: {aplicados}")
    if avisos:
        print("⚠ Avisos:")
        for a in avisos:
            print(f"  - {a}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="modo", required=True)

    p_list = sub.add_parser("listar")
    p_list.add_argument("prova_id")

    p_apl = sub.add_parser("aplicar")
    p_apl.add_argument("prova_id")
    p_apl.add_argument("patch", type=Path)

    args = parser.parse_args()

    if args.modo == "listar":
        modo_listar(args.prova_id)
    else:
        modo_aplicar(args.prova_id, args.patch)


if __name__ == "__main__":
    main()
