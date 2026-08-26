"""resolver_via_openai.py — Classifica/resolve o acervo histórico via API da
OpenAI, em vez de agentes do Claude Code.

Por quê existe: o workflow de agentes (wf_classificar_resolver.js) bate na
cota de uso do Claude Code (semanal, depois de sessão) várias vezes por dia de
trabalho — cada parada exige aplicar o patch parcial, remontar o manifesto do
que falta e relançar. A API paga da OpenAI não tem esse teto por sessão; o
teto aqui é só o de gasto, que o próprio script aplica.

Saída no MESMO formato de journal que os workflows do Claude Code produzem —
uma linha JSON por questão resolvida, {"type":"result","result":{"prova_id",
"questoes"}} — para que `aplicar_patch_historico.py` funcione sem alteração
nenhuma, venha o resultado de onde vier.

Orçamento é HARD CAP em dólar, checado a cada resposta usando o `usage` real
devolvido pela API (não estimativa a priori) — para antes de estourar, nunca
depois.

Uso:
    python resolver_via_openai.py <manifesto.json> --orcamento-usd 3.5 [--calibrar]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

PROJETO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJETO_ROOT.parent / "api" / ".env")

MODELO = "o4-mini"
# USD por 1M tokens (platform.openai.com/docs/pricing, conferido 23/08/2026).
# Custo REAL medido do gpt-5 completo ($0,0213/questão) cobria só 31% das 539
# restantes dentro do teto de R$20 — trocado por decisão do usuário. Calibrado
# contra 40 questões de gabarito conhecido: 96,8% em confiança alta (30/31),
# contra 94,1% do gpt-5-mini (32/34) e 99,5% do Claude (22/08) — não chega no
# mesmo patamar, aceito pelo usuário em troca de cobrir o lote inteiro dentro
# do orçamento. Custo medido na calibração: $0,00287/questão — cobre as 539
# restantes com folga.
PRECO_IN = 1.10 / 1_000_000
PRECO_OUT = 4.40 / 1_000_000

TAXONOMIA_PATH = {
    "Física": "config/taxonomia-fisica.json",
    "Química": "config/taxonomia-quimica.json",
    "Matemática": "config/taxonomia-matematica.json",
}

ESQUEMA = {
    "type": "object",
    "required": ["questoes"],
    "additionalProperties": False,
    "properties": {
        "questoes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["numero", "topicos_ids", "observacao", "resolucao_md",
                            "gabarito_sugerido", "confianca_gabarito"],
                "additionalProperties": False,
                "properties": {
                    "numero": {"type": "integer"},
                    "topicos_ids": {"type": "array", "items": {"type": "string"}},
                    "observacao": {"type": "string"},
                    "gabarito_sugerido": {"type": ["string", "null"], "enum": ["A", "B", "C", "D", "E", None]},
                    "confianca_gabarito": {"type": ["string", "null"], "enum": ["alta", "media", "baixa", None]},
                    "resolucao_md": {"type": "string"},
                },
            },
        }
    },
}


class Orcamento:
    """Teto de gasto em dólar, checado com o `usage` real de cada resposta —
    não com estimativa antes de chamar. Compartilhado entre todas as chamadas
    concorrentes; um `asyncio.Lock` evita duas coroutines lendo/escrevendo o
    total ao mesmo tempo (perderia incremento sem isso)."""

    def __init__(self, teto_usd: float):
        self.teto = teto_usd
        self.gasto = 0.0
        self._lock = asyncio.Lock()

    async def registrar(self, tokens_in: int, tokens_out: int) -> float:
        custo = tokens_in * PRECO_IN + tokens_out * PRECO_OUT
        async with self._lock:
            self.gasto += custo
            return self.gasto

    def estourado(self) -> bool:
        return self.gasto >= self.teto


def montar_prompt(p: dict) -> str:
    materia = p["materia"]
    tax_path = TAXONOMIA_PATH[materia]
    base = PROJETO_ROOT / "questoes_json" / p["prova_id"]
    numeros = p.get("numeros") or list(range(1, p["n_questoes"] + 1))

    questoes_texto = []
    for n in numeros:
        d = json.loads((base / f"q{n:02d}.json").read_text(encoding="utf-8"))
        bloco = [f"### Q{n}", d["enunciado_md"]]
        if d.get("alternativas"):
            for letra, texto in d["alternativas"].items():
                bloco.append(f"{letra}) {texto}")
        if d.get("gabarito"):
            bloco.append(f"[GABARITO DA BANCA: {d['gabarito']} — não precisa adivinhar, resolva chegando aí]")
        questoes_texto.append("\n".join(bloco))

    taxonomia = json.loads((PROJETO_ROOT / tax_path).read_text(encoding="utf-8"))
    tax_resumo = []
    for bloco in taxonomia["blocos"]:
        subs = "; ".join(f"{s['id']} {s['nome']}" for s in bloco["subareas"])
        tax_resumo.append(f"{bloco['id']}. {bloco['nome']} → {subs}")

    tipo = "DISSERTATIVA (sem alternativa nem gabarito por natureza)" if p["dissertativa"] else \
           "OBJETIVA (múltipla escolha A-E)"

    return f"""Você vai CLASSIFICAR por assunto do edital e RESOLVER questões de vestibular
(ITA/IME, {materia}). Prova {tipo}.

TAXONOMIA — códigos válidos de {materia}:
{chr(10).join(tax_resumo)}
Regra: 1 tópico se a questão é pura, 2 se é combinação natural, 3 no máximo.

Para cada questão abaixo:
- topicos_ids: 1-3 códigos da taxonomia acima — **só o código, nunca o nome
  junto** (certo: "13.1" — errado: "13.1 Números Complexos"). O nome já está
  registrado na taxonomia; repeti-lo aqui quebra a busca por código exato.
- observacao: 1 frase justificando a classificação
- resolucao_md: resolução comentada em Markdown para o aluno estudar, LaTeX
  em $...$, 3-10 linhas, começando pelo princípio que destrava a questão. Não
  se refira a si mesmo nem mencione ter calculado — é texto de resolução, não
  relato de processo.
- Se a questão TEM "[GABARITO DA BANCA: X]": resolva chegando em X.
  gabarito_sugerido e confianca_gabarito ficam null (já tem oficial).
- Se NÃO tem gabarito marcado e é objetiva: resolva do zero, sem viés, e
  preencha gabarito_sugerido (a letra) e confianca_gabarito HONESTAMENTE
  ("alta" só se não houver ambiguidade nenhuma — confiança inflada é pior que
  admitir incerteza). Se dissertativa: os dois ficam null sempre.

QUESTÕES:

{chr(10).join(("---" + chr(10)).join(questoes_texto).split(chr(10)))}

Devolva TODAS as {len(numeros)} questões, mesmo as de confiança baixa."""


async def resolver_prova(cliente: AsyncOpenAI, p: dict, orcamento: Orcamento, sem: asyncio.Semaphore) -> dict | None:
    if orcamento.estourado():
        return None
    async with sem:
        if orcamento.estourado():
            return None
        try:
            resp = await cliente.chat.completions.create(
                model=MODELO,
                messages=[{"role": "user", "content": montar_prompt(p)}],
                response_format={"type": "json_schema", "json_schema": {"name": "resolucao", "schema": ESQUEMA, "strict": True}},
            )
        except Exception as e:
            print(f"  ERRO {p['prova_id']}: {e}", file=sys.stderr)
            return None

        u = resp.usage
        gasto_total = await orcamento.registrar(u.prompt_tokens, u.completion_tokens)
        dados = json.loads(resp.choices[0].message.content)
        # Saneamento defensivo: apesar da instrução, o modelo às vezes devolve
        # "13.1 Números Complexos" em vez de só "13.1" — o código exato é o
        # único formato que bate com a taxonomia depois, no patch.
        for q in dados["questoes"]:
            q["topicos_ids"] = [
                (m.group(0) if (m := re.match(r"\d+\.\d+", t)) else t) for t in q["topicos_ids"]
            ]
        print(f"  ✓ {p['prova_id']} ({len(dados['questoes'])}q) — "
              f"gasto acumulado: ${gasto_total:.4f} / ${orcamento.teto:.2f}", file=sys.stderr)
        return {"prova_id": p["prova_id"], "questoes": dados["questoes"]}


async def main_async(manifesto: list[dict], orcamento: Orcamento, saida: Path, concorrencia: int):
    cliente = AsyncOpenAI()
    sem = asyncio.Semaphore(concorrencia)
    tarefas = [resolver_prova(cliente, p, orcamento, sem) for p in manifesto]

    with open(saida, "a", encoding="utf-8") as f:
        for coro in asyncio.as_completed(tarefas):
            resultado = await coro
            if resultado:
                f.write(json.dumps({"type": "result", "result": resultado}, ensure_ascii=False) + "\n")
                f.flush()

    print(f"\nGasto final: ${orcamento.gasto:.4f} de ${orcamento.teto:.2f}", file=sys.stderr)
    if orcamento.estourado():
        print("⚠ Orçamento esgotado — pode haver provas do manifesto não processadas.", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifesto", type=Path)
    ap.add_argument("--orcamento-usd", type=float, required=True)
    ap.add_argument("--saida", type=Path, default=Path("journal_openai.jsonl"))
    ap.add_argument("--concorrencia", type=int, default=8)
    args = ap.parse_args()

    manifesto = json.loads(args.manifesto.read_text())
    orcamento = Orcamento(args.orcamento_usd)
    print(f"Modelo: {MODELO} · {len(manifesto)} provas · teto ${args.orcamento_usd:.2f}", file=sys.stderr)
    asyncio.run(main_async(manifesto, orcamento, args.saida, args.concorrencia))


if __name__ == "__main__":
    main()
