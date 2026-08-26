"""Gera a página de conferência do piloto: como as questões de 1973 ficariam no site.

Reproduz o cartão real do SAS (web/styles/banco.css + CartaoQuestao.tsx) para que o
julgamento seja sobre o CONTEÚDO extraído, não sobre um layout inventado. O que é
novo aqui — e é o que está em avaliação — são duas peças que o cartão de hoje não
tem: o gabarito quando ele é sugestão e não veio da banca, e a caixa de resolução.
"""

import base64
import html
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
PROVA = BASE / "visao" / "1973"

# ─── LaTeX mínimo → HTML ──────────────────────────────────────────────────
# O site não tem renderizador de fórmula (docs/22 §8, risco 5: o enunciado é
# mostrado como texto cru). As resoluções escritas agora trazem LaTeX, e exibi-lo
# cru — "$\frac{mv^2}{2}$" no meio da frase — seria ilegível. Isto aproxima o que um
# renderizador real entregaria, o bastante para julgar a resolução; a decisão de
# adotar um renderizador de verdade fica registrada como pendência.
_GREGAS = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "Delta": "Δ",
    "epsilon": "ε", "theta": "θ", "lambda": "λ", "mu": "μ", "nu": "ν",
    "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "phi": "φ", "omega": "ω",
    "Omega": "Ω", "sqrt": "√", "cdot": "·", "times": "×", "approx": "≈",
    "leq": "≤", "geq": "≥", "neq": "≠", "pm": "±", "infty": "∞", "circ": "°",
    "rightarrow": "→", "Rightarrow": "⇒", "propto": "∝", "int": "∫", "sum": "Σ",
}


def _formula(tex: str) -> str:
    t = tex
    # Antes das gregas: "30^\\circ" tem que virar "30°", não "30^°".
    t = re.sub(r"\^\s*\\circ", "°", t)
    t = re.sub(r"\^\{\s*\\circ\s*\}", "°", t)
    t = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", t)
    t = re.sub(r"\\sqrt\{([^{}]*)\}", r"√(\1)", t)
    t = re.sub(r"\\text\{([^{}]*)\}", r"\1", t)
    t = re.sub(r"\\mathrm\{([^{}]*)\}", r"\1", t)
    t = re.sub(r"\\underline\{([^{}]*)\}", r"\1", t)
    for nome, simbolo in _GREGAS.items():
        t = t.replace("\\" + nome, simbolo)
    t = re.sub(r"\^\{([^{}]*)\}", lambda m: f"<sup>{html.escape(m.group(1))}</sup>", t)
    t = re.sub(r"_\{([^{}]*)\}", lambda m: f"<sub>{html.escape(m.group(1))}</sub>", t)
    t = re.sub(r"\^(-?\w)", lambda m: f"<sup>{html.escape(m.group(1))}</sup>", t)
    t = re.sub(r"_(-?\w)", lambda m: f"<sub>{html.escape(m.group(1))}</sub>", t)
    t = t.replace("\\,", " ").replace("\\;", " ").replace("\\!", "")
    t = t.replace("\\left", "").replace("\\right", "")
    t = t.replace("{", "").replace("}", "").replace("\\", "")
    return f'<span class="formula">{t}</span>'


def markdown_leve(texto: str) -> str:
    """Escapa HTML, resolve $…$ e **negrito**, quebra parágrafos."""
    partes = re.split(r"(\$[^$]+\$)", texto)
    saida = []
    for parte in partes:
        if parte.startswith("$") and parte.endswith("$") and len(parte) > 2:
            saida.append(_formula(parte[1:-1]))
        else:
            escapado = html.escape(parte)
            escapado = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escapado)
            saida.append(escapado)
    junto = "".join(saida)
    paragrafos = [p.strip() for p in junto.split("\n\n") if p.strip()]
    return "".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragrafos)


# ─── Dados ────────────────────────────────────────────────────────────────

NOME_TOPICO = {
    "1.1": "Fundamentos", "2.1": "Cinemática", "3.1": "Estática e Equilíbrio",
    "4.1": "Dinâmica", "5.1": "Energia", "6.1": "Gravitação",
    "7.1": "Movimento Harmônico Simples", "7.2": "Ondas e Acústica",
    "8.1": "Hidrostática e Hidrodinâmica", "9.1": "Termodinâmica",
    "10.1": "Óptica Geométrica", "10.2": "Óptica Física", "11.1": "Eletrostática",
    "12.1": "Eletrodinâmica", "13.1": "Magnetismo",
    "13.2": "Indução Eletromagnética e Ondas EM", "14.1": "Física Quântica",
    "14.2": "Relatividade Restrita",
}


def carregar() -> list[dict]:
    transcricoes: dict[int, dict] = {}
    for arq in sorted(PROVA.glob("transcricao_*.json")):
        for q in json.loads(arq.read_text())["questoes"]:
            n = q["numero"]
            if n not in transcricoes or len(q.get("enunciado_md", "")) > len(
                transcricoes[n].get("enunciado_md", "")
            ):
                transcricoes[n] = q
    analises: dict[int, dict] = {}
    for arq in sorted(PROVA.glob("analise_*.json")):
        for a in json.loads(arq.read_text())["questoes"]:
            analises[a["numero"]] = a

    questoes = []
    for n in sorted(transcricoes):
        q = dict(transcricoes[n])
        q.update(analises.get(n, {}))
        jpg = PROVA / "web" / f"ita_1973_q{n:02d}.jpg"
        q["imagem_b64"] = (
            base64.b64encode(jpg.read_bytes()).decode() if jpg.exists() else None
        )
        questoes.append(q)
    return questoes


# ─── Render ───────────────────────────────────────────────────────────────


def cartao(q: dict) -> str:
    n = q["numero"]
    conf = q.get("confianca", "baixa")
    topicos = q.get("topicos_ids") or []
    letra = q.get("gabarito_sugerido")

    chips = "".join(
        f'<span class="topico">{html.escape(c)} · {html.escape(NOME_TOPICO.get(c, c))}</span>'
        for c in topicos
    ) or '<span class="topico topico--incerto">Sem assunto classificado</span>'
    if conf in ("media", "baixa"):
        chips += f'<span class="topico topico--incerto">confiança {conf}</span>'

    imagem = (
        f'<img class="imagem" src="data:image/jpeg;base64,{q["imagem_b64"]}" '
        f'alt="Enunciado da questão — ITA 1973 Física nº {n}" loading="lazy" decoding="async">'
        if q.get("imagem_b64")
        else f'<p class="texto">{markdown_leve(q.get("enunciado_md", ""))}</p>'
    )

    # O gabarito sugerido veste âmbar, não o verde do oficial. Cor é linguagem neste
    # projeto (banco.css): verde = confirmado. Uma sugestão pintada de verde diria
    # ao aluno que a banca respondeu isso — e ninguém respondeu.
    if letra:
        gabarito = f"""
        <div class="gab-linha">
          <button class="gabarito gabarito--sugerido" type="button" aria-expanded="false"
                  onclick="revelar(this, {n})">
            <span class="gab-rotulo">sugestão de gabarito</span>
          </button>
        </div>
        <div class="gab-revelado" id="gab{n}" hidden>
          <span class="gab-letra">{html.escape(letra)}</span>
          <span class="gab-aviso">Sugestão de gabarito — a banca não publicou o oficial desta prova.</span>
        </div>"""
    else:
        gabarito = '<span class="gabarito gabarito--indisponivel">Sem gabarito</span>'

    resolucao = ""
    if q.get("resolucao_md"):
        resolucao = f"""
        <details class="resolucao">
          <summary><span class="res-titulo">Sugestão de resolução</span><span class="res-abrir">ver</span></summary>
          <div class="res-corpo">
            {markdown_leve(q["resolucao_md"])}
            <p class="res-aviso">Sugestão de resolução — não é a resolução oficial da banca.</p>
          </div>
        </details>"""

    return f"""
    <article class="questao">
      <header class="topo">
        <span class="selo">ITA</span>
        <span class="referencia">ITA 1973 · Fase 1 · nº {n}</span>
        <div class="acoes">
          <button class="acao" type="button">Marcar resolvida</button>
          <button class="acao" type="button">Anotar</button>
          <button class="acao" type="button">+ Lista</button>
        </div>
      </header>
      <div class="corpo">
        {imagem}
        {gabarito}
        {resolucao}
        <div class="topicos">{chips}</div>
      </div>
    </article>"""


def main() -> None:
    questoes = carregar()
    total = len(questoes)
    por_conf = {"alta": 0, "media": 0, "baixa": 0}
    for q in questoes:
        c = q.get("confianca")
        if c in por_conf:
            por_conf[c] += 1
    com_resolucao = sum(1 for q in questoes if q.get("resolucao_md"))
    com_imagem = sum(1 for q in questoes if q.get("imagem_b64"))

    cartoes = "\n".join(cartao(q) for q in questoes)

    corpo = f"""<title>Piloto ITA 1973</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600&display=swap">
<style>
:root {{
  --navy-deep:#122f6a; --navy:#1b3f8b; --navy-mid:#2952a3; --navy-light:#4a78c9;
  --green:#2e8c5a; --green-soft:#def0e4; --amber:#d4a82e; --amber-soft:#fbefc6;
  --surface:#ffffff; --surface-inset:#f5f7fb; --ground:#eef1f7;
  --text-primary:#1a1d24; --text-secondary:rgba(26,29,36,.65); --text-tertiary:rgba(26,29,36,.45);
  --border:rgba(20,30,80,.06); --border-strong:rgba(20,30,80,.12);
  --shadow-card:0 1px 2px rgba(20,30,80,.02), 0 4px 14px rgba(20,30,80,.05);
  --radius-sm:8px; --radius-md:12px; --radius-pill:999px;
}}
:root:not([data-theme="light"]) {{
  @media (prefers-color-scheme: dark) {{
    --surface:#171a21; --surface-inset:#1e222b; --ground:#101318;
    --text-primary:#eceef3; --text-secondary:rgba(236,238,243,.68); --text-tertiary:rgba(236,238,243,.46);
    --border:rgba(160,180,230,.12); --border-strong:rgba(160,180,230,.22);
    --navy:#7ba0e0; --navy-mid:#6f95d8; --navy-light:#8fb0e8;
    --green:#5cc48b; --green-soft:rgba(92,196,139,.16);
    --amber:#e5bf52; --amber-soft:rgba(229,191,82,.15);
    --shadow-card:0 1px 2px rgba(0,0,0,.3), 0 4px 14px rgba(0,0,0,.28);
  }}
}}
:root[data-theme="dark"] {{
  --surface:#171a21; --surface-inset:#1e222b; --ground:#101318;
  --text-primary:#eceef3; --text-secondary:rgba(236,238,243,.68); --text-tertiary:rgba(236,238,243,.46);
  --border:rgba(160,180,230,.12); --border-strong:rgba(160,180,230,.22);
  --navy:#7ba0e0; --navy-mid:#6f95d8; --navy-light:#8fb0e8;
  --green:#5cc48b; --green-soft:rgba(92,196,139,.16);
  --amber:#e5bf52; --amber-soft:rgba(229,191,82,.15);
  --shadow-card:0 1px 2px rgba(0,0,0,.3), 0 4px 14px rgba(0,0,0,.28);
}}

*,*::before,*::after {{ box-sizing:border-box; }}
body {{
  margin:0; padding:0 16px 72px;
  background:var(--ground); color:var(--text-primary);
  font-family:'Plus Jakarta Sans',-apple-system,system-ui,sans-serif;
  font-size:15px; line-height:1.6;
}}
.pagina {{ max-width:760px; margin:0 auto; }}

/* ── Cabeçalho da conferência (não faz parte do site) ── */
.aviso {{
  margin:28px 0 22px; padding:16px 18px;
  background:var(--surface); border:1px solid var(--border-strong);
  border-left:3px solid var(--navy); border-radius:var(--radius-md);
}}
.aviso h1 {{ margin:0 0 6px; font-size:17px; font-weight:600; letter-spacing:-.01em; }}
.aviso p {{ margin:0; font-size:13.5px; color:var(--text-secondary); }}
.numeros {{ display:flex; flex-wrap:wrap; gap:8px; margin:14px 0 26px; }}
.numero {{
  flex:1 1 120px; padding:10px 12px; background:var(--surface);
  border:1px solid var(--border); border-radius:var(--radius-sm);
}}
.numero b {{ display:block; font-size:20px; font-weight:600; font-variant-numeric:tabular-nums; }}
.numero span {{ font-size:11.5px; color:var(--text-tertiary); letter-spacing:.03em; }}

/* ── Cartão: espelha web/styles/banco.css ── */
.lista {{ display:flex; flex-direction:column; gap:14px; }}
.questao {{
  min-width:0; background:var(--surface); border:1px solid var(--border);
  border-radius:var(--radius-md); box-shadow:var(--shadow-card);
  overflow:hidden; display:flex; flex-direction:column;
}}
.topo {{
  display:flex; flex-wrap:wrap; align-items:center; gap:8px 10px;
  padding:10px 14px; background:var(--surface-inset); border-bottom:1px solid var(--border);
}}
.selo {{
  flex-shrink:0; padding:3px 10px; border-radius:var(--radius-sm);
  background:var(--navy); color:#fff; font-size:11px; font-weight:500; letter-spacing:.06em;
}}
:root[data-theme="dark"] .selo {{ color:#0f1319; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) .selo {{ color:#0f1319; }} }}
.referencia {{
  flex:1 0 auto; min-width:0; font-size:13px; color:var(--text-secondary);
  font-variant-numeric:tabular-nums; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}}
.acoes {{ display:flex; flex-wrap:wrap; align-items:center; gap:6px; margin-left:auto; }}
.acao {{
  display:inline-flex; align-items:center; justify-content:center;
  min-height:36px; padding:6px 12px; border:1px solid var(--border);
  border-radius:var(--radius-sm); background:var(--surface); color:var(--text-secondary);
  font-family:inherit; font-size:12px; font-weight:500; cursor:pointer;
  transition:background 120ms, border-color 120ms, color 120ms;
}}
.acao:hover {{ border-color:var(--border-strong); color:var(--navy); }}
.corpo {{ min-width:0; padding:16px 14px; display:flex; flex-direction:column; gap:12px; }}
.imagem {{ max-width:100%; height:auto; display:block; border-radius:var(--radius-sm); }}
.texto {{ margin:0; font-size:15px; line-height:1.7; white-space:pre-wrap; overflow-wrap:anywhere; }}

/* ── Gabarito ── */
.gab-linha {{ display:flex; flex-wrap:wrap; gap:8px; }}
.gabarito {{
  align-self:flex-start; display:inline-flex; align-items:center; justify-content:center;
  gap:8px; min-height:52px; min-width:168px; padding:10px 18px;
  border:1px dashed var(--border-strong); border-radius:var(--radius-sm);
  background:var(--surface); color:var(--text-tertiary);
  font-family:inherit; font-size:12px; font-weight:500; letter-spacing:.04em; cursor:pointer;
  transition:background 150ms, border-color 150ms, color 150ms;
}}
.gabarito:hover {{ border-color:var(--amber); color:var(--amber); }}
.gabarito--sugerido .gab-rotulo {{ text-transform:none; }}
.gabarito--indisponivel {{
  border-style:solid; background:var(--surface-inset); color:var(--text-tertiary); cursor:default;
}}
.gab-revelado {{
  display:flex; align-items:center; gap:14px; padding:12px 16px;
  background:var(--amber-soft); border-radius:var(--radius-sm);
}}
.gab-letra {{ font-size:26px; font-weight:600; line-height:1; color:var(--amber); }}
.gab-aviso {{ font-size:12.5px; color:var(--text-secondary); }}

/* ── Resolução ── */
.resolucao {{ border:1px solid var(--border-strong); border-radius:var(--radius-sm); background:var(--surface-inset); }}
.resolucao summary {{
  display:flex; align-items:center; justify-content:space-between; gap:10px;
  padding:12px 16px; cursor:pointer; list-style:none; min-height:48px;
}}
.resolucao summary::-webkit-details-marker {{ display:none; }}
.res-titulo {{ font-size:13px; font-weight:500; color:var(--text-secondary); }}
.res-abrir {{ font-size:12px; color:var(--navy); }}
.resolucao[open] .res-abrir {{ visibility:hidden; }}
.res-corpo {{ padding:0 16px 14px; font-size:14.5px; line-height:1.75; }}
.res-corpo p {{ margin:0 0 10px; }}
.res-aviso {{
  margin-top:12px !important; padding-top:10px; border-top:1px solid var(--border);
  font-size:12px; color:var(--text-tertiary);
}}
.formula {{ font-style:italic; font-variant-numeric:tabular-nums; white-space:nowrap; }}

/* ── Tópicos ── */
.topicos {{ display:flex; flex-wrap:wrap; gap:6px; }}
.topico {{
  display:inline-flex; align-items:center; padding:4px 10px; border-radius:var(--radius-pill);
  background:rgba(27,63,139,.08); color:var(--navy); font-size:12px; font-weight:500;
}}
:root[data-theme="dark"] .topico {{ background:rgba(123,160,224,.14); }}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) .topico {{ background:rgba(123,160,224,.14); }}
}}
.topico--incerto {{ background:var(--amber-soft); color:var(--amber); }}

button:focus-visible, summary:focus-visible {{ outline:2px solid var(--navy-light); outline-offset:2px; }}
@media (prefers-reduced-motion:reduce) {{ * {{ transition:none !important; }} }}
</style>

<div class="pagina">
  <div class="aviso">
    <h1>Como a prova de 1973 fica no banco</h1>
    <p>Prova de Física do ITA, 1973 — escaneada, datilografada, sem gabarito publicado.
       O cartão é o mesmo do banco hoje; o que muda é a origem da resposta.</p>
  </div>

  <div class="numeros">
    <div class="numero"><b>{total}</b><span>QUESTÕES EXTRAÍDAS</span></div>
    <div class="numero"><b>{com_imagem}</b><span>COM RECORTE</span></div>
    <div class="numero"><b>{com_resolucao}</b><span>COM RESOLUÇÃO</span></div>
    <div class="numero"><b>{por_conf['alta']}</b><span>CONFIANÇA ALTA</span></div>
  </div>

  <div class="lista">
{cartoes}
  </div>
</div>

<script>
function revelar(botao, n) {{
  var caixa = document.getElementById('gab' + n);
  var aberto = !caixa.hidden;
  caixa.hidden = aberto;
  botao.setAttribute('aria-expanded', String(!aberto));
  botao.querySelector('.gab-rotulo').textContent = aberto ? 'sugestão de gabarito' : 'ocultar';
}}
</script>
"""
    saida = BASE / "conferencia_1973.html"
    saida.write_text(corpo, encoding="utf-8")
    print(f"→ {saida}  ({saida.stat().st_size / 1024 / 1024:.2f} MB)")
    print(f"   {total} questões · {com_imagem} com recorte · {com_resolucao} com resolução")
    print(f"   confiança: alta {por_conf['alta']} · media {por_conf['media']} · baixa {por_conf['baixa']}")


if __name__ == "__main__":
    main()
