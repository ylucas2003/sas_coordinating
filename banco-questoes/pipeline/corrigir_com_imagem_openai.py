"""corrigir_com_imagem_openai.py — 2ª passada: re-resolve, agora VENDO a
imagem, as questões que citam figura/gráfico e foram resolvidas só com texto
na 1ª passada (resolver_via_openai.py ou o workflow do Claude — não importa a
origem, aqui só importa que `resolucao_md` já existe e é possivelmente errado).

Mesmo motivo do achado registrado em docs/23 §4.1: um agente respondendo só
com texto, para uma questão que enuncia "a figura mostra...", ou lê certo por
sorte ou inventa. Isto substitui a resolução por uma que viu a imagem de
verdade.

Saída no mesmo formato de journal que os outros scripts — 1 linha por prova
resolvida — para reaproveitar `aplicar_patch_historico.py --marcar-corrigido`.

Uso:
    python corrigir_com_imagem_openai.py <manifesto.json> --orcamento-usd 2.0
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

PROJETO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJETO_ROOT.parent / "api" / ".env")

MODELO = "o4-mini"
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
                            "gabarito_sugerido", "confianca_gabarito", "mudou"],
                "additionalProperties": False,
                "properties": {
                    "numero": {"type": "integer"},
                    "topicos_ids": {"type": "array", "items": {"type": "string"}},
                    "observacao": {"type": "string"},
                    "gabarito_sugerido": {"type": ["string", "null"], "enum": ["A", "B", "C", "D", "E", None]},
                    "confianca_gabarito": {"type": ["string", "null"], "enum": ["alta", "media", "baixa", None]},
                    "resolucao_md": {"type": "string"},
                    "mudou": {"type": "boolean"},
                },
            },
        }
    },
}


class Orcamento:
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


def montar_conteudo(grupo: dict) -> list[dict]:
    """Mensagem multimodal: texto de instrução + enunciado/resolução anterior
    de cada questão + a imagem correspondente, intercalados na mesma ordem."""
    materia = grupo["materia"]
    tax = json.loads((PROJETO_ROOT / TAXONOMIA_PATH[materia]).read_text(encoding="utf-8"))
    tax_resumo = []
    for bloco in tax["blocos"]:
        subs = "; ".join(f"{s['id']} {s['nome']}" for s in bloco["subareas"])
        tax_resumo.append(f"{bloco['id']}. {bloco['nome']} → {subs}")

    partes: list[dict] = [{"type": "text", "text": f"""Você vai RE-RESOLVER questões de vestibular que citam figura, gráfico ou
diagrama no enunciado. Elas JÁ foram resolvidas uma vez só com TEXTO, sem ver
a figura — o que é arriscado quando a resposta depende do que a figura mostra.
Agora você vê a imagem de verdade, logo depois do texto de cada questão.

TAXONOMIA de {materia}:
{chr(10).join(tax_resumo)}

Para cada questão:
1. Resolva de novo, COM a figura. Não reaproveite a resolução anterior sem
   checar — é exatamente ela que pode estar errada.
2. Se a figura muda resposta, tópico ou algum número: "mudou": true, e
   resolucao_md já reflete a correção.
3. Se a figura só confirma o que já estava escrito: "mudou": false (pode
   manter a resolução ou só polir).
4. Se objetiva com gabarito de banca (marcado abaixo): resolva chegando nele,
   gabarito_sugerido/confianca_gabarito ficam null.
5. Se objetiva sem gabarito: resolva com a figura, preencha os dois
   honestamente ("alta" só sem ambiguidade nenhuma).
6. Se dissertativa: sem letra, só topicos_ids + resolucao_md.

resolucao_md: Markdown, LaTeX em $...$, 3-10 linhas, sem se referir a si
mesmo. topicos_ids: só o código (ex. "7.2"), nunca nome junto.

Devolva TODAS as questões, mesmo as que não mudaram."""}]

    for item in grupo["itens"]:
        d = json.loads((PROJETO_ROOT / "questoes_json" / grupo["prova_id"] / f"q{item['numero']:02d}.json")
                       .read_text(encoding="utf-8"))
        bloco = [f"### Q{item['numero']}", d["enunciado_md"]]
        if d.get("alternativas"):
            for letra, texto in d["alternativas"].items():
                bloco.append(f"{letra}) {texto}")
        if d.get("gabarito"):
            bloco.append(f"[GABARITO DA BANCA: {d['gabarito']}]")
        bloco.append(f"[Resolução anterior, sem ver a figura — pode estar errada: {d.get('resolucao_md', '')[:400]}]")
        partes.append({"type": "text", "text": "\n".join(bloco)})

        imagem_local = Path(item["arquivo_local"])
        b64 = base64.b64encode(imagem_local.read_bytes()).decode()
        partes.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}})

    return partes


async def corrigir_grupo(cliente: AsyncOpenAI, grupo: dict, orcamento: Orcamento, sem: asyncio.Semaphore) -> dict | None:
    if orcamento.estourado():
        return None
    async with sem:
        if orcamento.estourado():
            return None
        try:
            resp = await cliente.chat.completions.create(
                model=MODELO,
                messages=[{"role": "user", "content": montar_conteudo(grupo)}],
                response_format={"type": "json_schema", "json_schema": {"name": "correcao", "schema": ESQUEMA, "strict": True}},
            )
        except Exception as e:
            print(f"  ERRO {grupo['prova_id']}: {e}", file=sys.stderr)
            return None

        u = resp.usage
        gasto_total = await orcamento.registrar(u.prompt_tokens, u.completion_tokens)
        dados = json.loads(resp.choices[0].message.content)
        for q in dados["questoes"]:
            q["topicos_ids"] = [(m.group(0) if (m := re.match(r"\d+\.\d+", t)) else t) for t in q["topicos_ids"]]
        mudaram = sum(1 for q in dados["questoes"] if q.get("mudou"))
        print(f"  ✓ {grupo['prova_id']} ({len(dados['questoes'])}q, {mudaram} mudaram) — "
              f"gasto: ${gasto_total:.4f} / ${orcamento.teto:.2f}", file=sys.stderr)
        return {"prova_id": grupo["prova_id"], "questoes": dados["questoes"]}


async def main_async(manifesto: list[dict], orcamento: Orcamento, saida: Path, concorrencia: int):
    cliente = AsyncOpenAI()
    sem = asyncio.Semaphore(concorrencia)
    tarefas = [corrigir_grupo(cliente, g, orcamento, sem) for g in manifesto]
    with open(saida, "a", encoding="utf-8") as f:
        for coro in asyncio.as_completed(tarefas):
            resultado = await coro
            if resultado:
                f.write(json.dumps({"type": "result", "result": resultado}, ensure_ascii=False) + "\n")
                f.flush()
    print(f"\nGasto final: ${orcamento.gasto:.4f} de ${orcamento.teto:.2f}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifesto", type=Path)
    ap.add_argument("--orcamento-usd", type=float, required=True)
    ap.add_argument("--saida", type=Path, default=Path("journal_correcao.jsonl"))
    ap.add_argument("--concorrencia", type=int, default=8)
    args = ap.parse_args()

    manifesto = json.loads(args.manifesto.read_text())
    orcamento = Orcamento(args.orcamento_usd)
    print(f"Modelo: {MODELO} · {len(manifesto)} grupos · teto ${args.orcamento_usd:.2f}", file=sys.stderr)
    asyncio.run(main_async(manifesto, orcamento, args.saida, args.concorrencia))


if __name__ == "__main__":
    main()
