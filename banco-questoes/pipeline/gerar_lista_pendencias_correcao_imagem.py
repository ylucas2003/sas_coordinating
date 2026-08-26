"""Gera a lista de questões candidatas à correção-com-imagem (docs/23 §11.1,
§15 do dia 24/08): têm sinal de conteúdo truncado no texto E têm imagem no S3
E nunca passaram pela correção-com-imagem (`_corrigido_com_imagem` != true).

Heurística de truncamento (não é regex perfeito, é o texto do §11.1):
  - dissertativa (IME) cujo enunciado termina pendurado em conectivo/':'/'='
    sem nada depois — sempre anômalo, dissertativa não tem alternativa à
    parte que explique o corte;
  - dissertativa curta demais (<150 caracteres) pra uma questão discursiva
    de vestibular;
  - menção a termo matemático (equação/expressão/fórmula/sistema/matriz/...)
    sem quase nenhum símbolo matemático por perto no resto do enunciado —
    objetiva só conta se o termo aparece longe do fim (perto do fim é normal,
    é a frase-ponte pra alternativa que fica em campo separado).

Uso:
    python gerar_lista_pendencias_correcao_imagem.py
Escreve `_pendencias_correcao_imagem.json` nesta mesma pasta.
"""
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "questoes_json"
SAIDA = Path(__file__).resolve().parent / "_pendencias_correcao_imagem.json"

TERMINA_PENDURADO = re.compile(
    r"(?:^|[\s])(de|e|sendo|igual a|em que|onde|com|para|tal que|tais que|é|será|"
    r"sejam|seja|dado por|dada por|dados por|dadas por|tem-se|obtém-se|onde\s*:|"
    r"sistema|condições|dados|determinante|matriz|função|equação|inequação)\s*[:=]?\s*$",
    re.IGNORECASE,
)

PALAVRAS_MATEMATICAS = re.compile(
    r"\b(equaç[aã]o|equaç[oõ]es|express[aã]o|express[oõ]es|f[oó]rmula|f[oó]rmulas|"
    r"sistema|matriz|matrizes|determinante|polin[oô]mio|integral|"
    r"deriva(da|r)|somat[oó]rio)\b",
    re.IGNORECASE,
)

SIMBOLOS_MATEMATICOS = re.compile(r"[=<>≤≥∫∑∏√±×÷$^_]|\\[a-zA-Z]+|\d")


def candidatas_truncadas():
    resultado = []
    for arq in sorted(RAIZ.glob("*/q*.json")):
        dados = json.loads(arq.read_text(encoding="utf-8"))
        enunciado = (dados.get("enunciado_md") or "").strip()
        if not enunciado:
            resultado.append(dados)
            continue

        motivos = []
        dissertativa = dados.get("dissertativa") is True

        if dissertativa:
            if TERMINA_PENDURADO.search(enunciado) or len(enunciado) < 150:
                motivos.append("suspeita")
            else:
                termos = PALAVRAS_MATEMATICAS.findall(enunciado)
                if termos and len(SIMBOLOS_MATEMATICOS.findall(enunciado)) < 2:
                    motivos.append("suspeita")
        else:
            corpo = enunciado[:-40] if len(enunciado) > 40 else ""
            termos = PALAVRAS_MATEMATICAS.findall(corpo)
            if termos and len(SIMBOLOS_MATEMATICOS.findall(enunciado)) < 2:
                motivos.append("suspeita")

        if motivos:
            resultado.append(dados)
    return resultado


def main():
    pendentes = []
    for dados in candidatas_truncadas():
        if not dados.get("imagem_questao_url"):
            continue  # sem imagem: não é candidata a correção-com-imagem, é candidata a visão no PDF
        if dados.get("_corrigido_com_imagem"):
            continue  # já passou pela correção
        pendentes.append(dados["id"])

    pendentes.sort()
    SAIDA.write_text(json.dumps({
        "descricao": (
            "IDs de questoes com sinal de conteudo truncado que TEM imagem no S3 "
            "mas NUNCA passaram pela correcao-com-imagem. Ver docs/23 §11.1 e §15."
        ),
        "total": len(pendentes),
        "ids": pendentes,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(pendentes)} questões pendentes escritas em {SAIDA}")


if __name__ == "__main__":
    main()
