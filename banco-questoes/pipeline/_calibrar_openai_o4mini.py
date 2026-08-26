"""Calibração rápida do gpt-5-mini: resolve às cegas (sem ver o gabarito) duas
provas de gabarito oficial conhecido, mede o acerto por confiança declarada.

Provas escolhidas por NÃO terem entrado na calibração do Claude (22/08) — amostra
independente. Custo: ~40 questões, texto só, ~$0.03 estimado.
"""

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

PROJETO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJETO_ROOT.parent / "api" / ".env")

MODELO = "o4-mini"
PRECO_IN, PRECO_OUT = 1.10 / 1e6, 4.40 / 1e6

TAXONOMIA_PATH = {"Física": "config/taxonomia-fisica.json", "Matemática": "config/taxonomia-matematica.json"}
PROVAS = [("ita_2016_fase1", "Física"), ("ita_2018_fase1_mat", "Matemática")]

ESQUEMA = {
    "type": "object", "required": ["respostas"], "additionalProperties": False,
    "properties": {"respostas": {"type": "array", "items": {
        "type": "object", "required": ["numero", "letra", "confianca"], "additionalProperties": False,
        "properties": {
            "numero": {"type": "integer"},
            "letra": {"type": "string", "enum": ["A", "B", "C", "D", "E"]},
            "confianca": {"type": "string", "enum": ["alta", "media", "baixa"]},
        },
    }}},
}


async def resolver(cliente, prova_id, materia):
    base = PROJETO_ROOT / "questoes_json" / prova_id
    blocos = []
    for n in range(1, 21):
        d = json.loads((base / f"q{n:02d}.json").read_text(encoding="utf-8"))
        b = [f"### Q{n}", d["enunciado_md"]]
        for letra, texto in d["alternativas"].items():
            b.append(f"{letra}) {texto}")
        blocos.append("\n".join(b))
    tax = json.loads((PROJETO_ROOT / TAXONOMIA_PATH[materia]).read_text(encoding="utf-8"))

    prompt = f"""Resolva estas 20 questões objetivas de vestibular ({materia}, ITA) do zero,
sem viés algum. Para cada uma, declare confiança honesta:
alta = resolveu por inteiro sem ambiguidade; media = incerteza real;
baixa = não resolveu com segurança. Confiança inflada invalida o experimento.

{chr(10).join(('---'+chr(10)).join(blocos).split(chr(10)))}

Devolva as 20 respostas."""

    resp = await cliente.chat.completions.create(
        model=MODELO, messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_schema", "json_schema": {"name": "respostas", "schema": ESQUEMA, "strict": True}},
    )
    custo = resp.usage.prompt_tokens * PRECO_IN + resp.usage.completion_tokens * PRECO_OUT
    return json.loads(resp.choices[0].message.content)["respostas"], custo


async def main():
    cliente = AsyncOpenAI()
    gabaritos = json.loads((PROJETO_ROOT / "config" / "_gabaritos_oficiais_ita.json").read_text())
    custo_total = 0.0
    por_conf = {"alta": [0, 0], "media": [0, 0], "baixa": [0, 0]}

    for prova_id, materia in PROVAS:
        ano = int(prova_id.split("_")[1])
        chave = f"{ano}|{materia}"
        respostas, custo = await resolver(cliente, prova_id, materia)
        custo_total += custo
        ref = gabaritos[chave]
        acertos_prova = 0
        for r in respostas:
            ok = r["letra"] == ref[str(r["numero"])]
            c = r["confianca"]
            por_conf[c][0] += ok
            por_conf[c][1] += 1
            acertos_prova += ok
        print(f"{chave}: {acertos_prova}/20", file=sys.stderr)

    print(f"\ncusto total: ${custo_total:.4f}", file=sys.stderr)
    tot_ok = sum(v[0] for v in por_conf.values())
    tot = sum(v[1] for v in por_conf.values())
    print(f"GERAL: {tot_ok}/{tot} = {100*tot_ok/tot:.1f}%", file=sys.stderr)
    for c in ("alta", "media", "baixa"):
        o, n = por_conf[c]
        if n:
            print(f"  {c}: {o}/{n} = {100*o/n:.1f}%", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
