"""Link para a resolução comentada da questão, nos sites do Ari.

O aluno lê o enunciado no banco e, quando quer a resolução, vai para onde o
colégio já a publicou — com deep-link no slide da questão, não na capa da prova.

⚠️ **Isto é mapeamento empírico, não fórmula.** O Ari mudou de plataforma três
vezes em oito anos, e cada uma numera as galerias de um jeito:

    2018–2021  login.aridesa.com.br      → só a capa da prova, sem deep-link
    2021–2024  servicos.aridesa.com.br   → galeria por matéria, slide por questão
    2023–      comentarios.aridesa.com.br → reference_id por prova, slide por questão

Os `reference_id` do IME não seguem regra nenhuma (2023→3, 2024→2, 2025→4) e os
offsets de slide da 2ª fase do ITA dependem de quantas questões foram comentadas
naquele ano. Tudo isso foi descoberto conferindo link a link, e **não se
reconstrói lendo o site**: se um valor aqui parecer arbitrário, é porque é.

Proveniência: veio de `pipeline/gerar_banco_unificado.py` do projeto
`ita-por-assunto`, que montava o HTML estático. Aquele arquivo saiu na migração
(docs/22 §1.2) por gerar os 2,2 MB que a API substituiu — e levou junto esta
tabela, que é domínio e não renderização. Recuperado em 23/08.

Onde isto roda: no importador, uma vez, gravando em `questao_vestibular.resolucao_url`.
Não é calculado por requisição — a URL de uma prova de 2019 não muda mais.
"""

from __future__ import annotations

# A pasta da prova sufixa a matéria (`ita_2019_fase1_mat`), e as galerias do Ari
# são numeradas por esse sufixo. Aqui a chave é a matéria, que é o conceito do
# domínio; o sufixo era acidente de nome de diretório.
_SUFIXO_POR_MATERIA = {"Física": "", "Matemática": "_mat", "Química": "_qui"}

# ─── ITA ────────────────────────────────────────────────────────────────

# 1ª fase, 2022–2024 (servicos): id da galeria e deslocamento do número
# absoluto da questão para o número dentro da matéria.
_ITA_F1_GALERIA = {"": 1, "_mat": 4, "_qui": 5}
_ITA_F1_OFFSET = {"": 0, "_mat": 36, "_qui": 48}

# 2ª fase, 2022–2023 (servicos): galerias próprias, separadas das da 1ª fase.
_ITA_F2_GALERIA_2022_2023 = {"_mat": 6, "_qui": 7, "": 8}

# 2ª fase, 2025+ (comentarios): Matemática Q1 no slide 1, Química Q1 no 11.
# Onde Física começa depende de quantas de Química foram comentadas naquele ano
# — por isso 2026 difere de 2025 em uma unidade.
_ITA_F2_OFFSET_2025_MAIS = {
    2025: {"_mat": 0, "_qui": 10, "": 20},
    2026: {"_mat": 0, "_qui": 10, "": 19},
}

# ─── IME ────────────────────────────────────────────────────────────────

# Sem fórmula: a plataforma numera as provas na ordem em que foram cadastradas.
_IME_REFERENCE_ID = {2023: 3, 2024: 2, 2025: 4}

# 1ª fase, 2021–2022 (servicos): galeria 1 = Matemática (1–15),
# 2 = Física (16–30), 3 = Química (31–40).
_IME_F1_GALERIA = {"_mat": 1, "": 2, "_qui": 3}
_IME_F1_OFFSET = {"_mat": 0, "": 15, "_qui": 30}

# Provas antigas do IME: uma landing page por biênio, sem link por questão.
_IME_LANDING_ANTIGA = {
    2020: "http://login.aridesa.com.br/vestibular/ime2020_2021/index.aspx",
    2019: "http://login.aridesa.com.br/vestibular/ime2019_2020/index.aspx",
    2018: "http://login.aridesa.com.br/vestibular/ime2018_2019/index.aspx",
}


def _fase1(sufixo: str, vestibular: str, ano: int, numero: int) -> str:
    if vestibular == "IME":
        if ano in _IME_REFERENCE_ID:
            # 2023–2025: as 40 questões dividem a galeria 1, indexada pelo número.
            return (
                f"https://comentarios.aridesa.com.br/ime"
                f"?reference_id={_IME_REFERENCE_ID[ano]}#gallery-1-{numero}"
            )
        if ano in (2021, 2022):
            galeria = _IME_F1_GALERIA.get(sufixo, 1)
            dentro = numero - _IME_F1_OFFSET.get(sufixo, 0)
            return (
                f"https://servicos.aridesa.com.br/comentario/ime/"
                f"{ano}-{ano + 1}/#gallery-{galeria}-{dentro}"
            )
        return _IME_LANDING_ANTIGA.get(ano, "")

    if vestibular != "ITA":
        return ""

    if ano >= 2025:
        return (
            f"https://comentarios.aridesa.com.br/ita"
            f"?reference_id={ano - 2024}#gallery-1-{numero}"
        )
    if ano >= 2022:
        galeria = _ITA_F1_GALERIA.get(sufixo, 1)
        dentro = numero - _ITA_F1_OFFSET.get(sufixo, 0)
        return f"https://servicos.aridesa.com.br/comentario/ita/{ano}/#gallery-{galeria}-{dentro}"
    if ano >= 2019:
        # Sem deep-link nessa plataforma: cai na capa da prova.
        return f"http://login.aridesa.com.br/vestibular/ita{ano}/index.aspx"
    return ""


def _fase2(sufixo: str, vestibular: str, ano: int, numero: int) -> str:
    # O IME não publica resolução comentada da 2ª fase — 210 questões sem link,
    # e é assim mesmo, não dado faltando.
    if vestibular != "ITA":
        return ""

    if ano >= 2025:
        offsets = _ITA_F2_OFFSET_2025_MAIS.get(ano, _ITA_F2_OFFSET_2025_MAIS[2025])
        slide = numero + offsets.get(sufixo, 0)
        return (
            f"https://comentarios.aridesa.com.br/ita"
            f"?reference_id={ano - 2024}&stage=2#gallery-1-{slide}"
        )
    if ano == 2024:
        # Mesmas galerias da 1ª fase, mas a Q1 da 2ª começa no slide 13.
        galeria = _ITA_F1_GALERIA.get(sufixo, 1)
        return f"https://servicos.aridesa.com.br/comentario/ita/2024/#gallery-{galeria}-{numero + 12}"
    if ano in (2022, 2023):
        galeria = _ITA_F2_GALERIA_2022_2023.get(sufixo, 6)
        return f"https://servicos.aridesa.com.br/comentario/ita/{ano}/#gallery-{galeria}-{numero}"
    if 2019 <= ano <= 2021:
        # A plataforma antiga usa a mesma landing da 1ª fase.
        return f"http://login.aridesa.com.br/vestibular/ita{ano}/index.aspx"
    return ""


def url_da_resolucao(vestibular: str, ano: int, fase: int, materia: str, numero: int) -> str | None:
    """A URL da resolução comentada, ou None quando o Ari não publicou.

    None e não string vazia: a coluna é anulável e o front decide mostrar o
    botão pela ausência. Vazio obrigaria toda leitura a testar as duas coisas.
    """
    sufixo = _SUFIXO_POR_MATERIA.get(materia, "")
    url = _fase2(sufixo, vestibular, ano, numero) if fase == 2 else _fase1(sufixo, vestibular, ano, numero)
    return url or None
