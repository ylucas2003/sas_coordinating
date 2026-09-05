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

⚠️ **O nome da galeria é a exceção: esse a página declara, e tem que ser lido
dela.** As duas plataformas nomeiam diferente, e até 04/09/2026 este módulo
tratava as duas como iguais:

    servicos.aridesa.com.br     data-fancybox="gallery-1" … "gallery-8"
    comentarios.aridesa.com.br  data-fancybox="gallery-stage-1" (e "-stage-2")

O hash do Fancybox é `#<nome-da-galeria>-<índice>`. Com `gallery-1` na
plataforma nova nenhuma galeria casa e o lightbox abre na capa, não no slide —
foi o defeito de 146 questões consertado em 04/09 (docs/35 §2).

**A conferência de 04/09 foi feita contra a PÁGINA baixada, não contra este
módulo.** É a distinção que importa: o teste que existia lia o código e cravava
o que ele já produzia, então passava com o link quebrado. Índice 36 da ITA 2025
fase 1 → `QUI-1_Q36.gif`, rótulo `36 - C` na página, e o gabarito da q36 no
nosso banco é C — na plataforma nova só o nome da galeria estava errado; os
offsets e índices dela conferem. A releitura das páginas antigas, porém, achou
um segundo erro que ninguém tinha visto: a 1ª fase do ITA de 2022 tem 70
questões e régua própria, e a Química daquele ano não cabe em régua nenhuma —
a q60 foi anulada e ficou fora da galeria, que salta de 59 para 61. As duas
coisas passam por `_indice_f1_do_ita`: a régua do ano ele lê de
`_ITA_F1_OFFSET_POR_ANO`, descrita ali; o buraco ele desconta, e está descrito
nele mesmo. Quem for mexer num valor deste arquivo, abra a página do Ari antes:
comparar com o código só confirma o que o código já acha.

Proveniência: veio de `pipeline/gerar_banco_unificado.py` do projeto
`ita-por-assunto`, que montava o HTML estático. Aquele arquivo saiu na migração
(docs/22 §1.2) por gerar os 2,2 MB que a API substituiu — e levou junto esta
tabela, que é domínio e não renderização. Recuperado em 23/08.

Onde isto roda: no importador, uma vez, gravando em `questao_vestibular.resolucao_url`.
Não é calculado por requisição — a URL de uma prova de 2019 não muda mais.
Consequência: **corrigir uma regra aqui não corrige o banco.** Para as linhas já
gravadas existe `scripts/recalcular_resolucao_url.py`, que reaplica esta função
sobre `questao_vestibular` (docs/35 §2).
"""

from __future__ import annotations

# A pasta da prova sufixa a matéria (`ita_2019_fase1_mat`), e as galerias do Ari
# são numeradas por esse sufixo. Aqui a chave é a matéria, que é o conceito do
# domínio; o sufixo era acidente de nome de diretório.
_SUFIXO_POR_MATERIA = {"Física": "", "Matemática": "_mat", "Química": "_qui"}

# ─── ITA ────────────────────────────────────────────────────────────────

# 1ª fase, 2022–2024 (servicos): id da galeria por matéria. A galeria NÃO muda
# com o ano — conferido em 04/09/2026 lendo o `data-fancybox` de cada botão das
# três páginas (`/comentario/ita/2022/`, `/2023/` e `/2024/`): Física sempre em
# `gallery-1`, Matemática em `gallery-4`, Química em `gallery-5`. O que muda com
# o ano é o índice do slide, e quem cuida dele é `_indice_f1_do_ita`.
_ITA_F1_GALERIA = {"": 1, "_mat": 4, "_qui": 5}

# ⚠️ O OFFSET MUDA COM O ANO, porque a prova mudou de tamanho. As galerias são as
# mesmas (Física 1, Matemática 4, Química 5) — o que muda é onde cada matéria
# começa na numeração corrida da prova. Conferido em 04/09/2026 abrindo as
# páginas e lendo o alvo de todos os botões de cada galeria — atenção ao ler:
# 2022 e 2023 põem o .gif em `data-src`, 2024 põe em `href`:
#
#   2022 (70 questões)  Fís 1–15 · Port 16–30 · Ing 31–40 · Mat 41–55 · Quí 56–70
#   2023–2024 (60)      Fís 1–12 · Port 13–24 · Ing 25–36 · Mat 37–48 · Quí 49–60
#
# Uma tabela só, com a régua de 2023, mandava a Matemática de 2022 para o slide
# errado (q41 caía no índice 5, que é a q45). Não quebrou link vivo porque o
# acervo não tem questão de ITA 2022 · 1ª fase: em 04/09/2026 `questao_vestibular`
# tinha de 2022 só as 30 da 2ª fase — contagem do banco LOCAL, que docs/35 §0.4
# mostrou divergir do de produção. Mas quebraria no dia em que ela entrasse, e
# em silêncio (docs/35 §2).
_ITA_F1_OFFSET_POR_ANO: dict[int, dict[str, int]] = {
    # Atenção: 55 é a régua da Química de 2022 **só até a q59**. Depois do
    # buraco da q60 ela vira 56, e quem sabe disso é `_indice_f1_do_ita`.
    2022: {"": 0, "_mat": 40, "_qui": 55},
}
_ITA_F1_OFFSET_PADRAO = {"": 0, "_mat": 36, "_qui": 48}

# A q60 de Química de 2022 foi anulada e o Ari não a comentou: na página o botão
# `60-N` é o único `disabled` e o único botão de QUESTÃO sem `data-fancybox` —
# fora dele, só as duas abas de fase e o link da redação não têm o atributo.
# Como é o `data-fancybox` que enfileira o slide, a `gallery-5` fica com 14
# slides para 15 questões e salta da q59 (índice 4) para a q61 (índice 5).
# Nenhum offset fixo cobre os dois lados desse buraco — daí a subtração virar
# função (docs/35 §2).
_ITA_F1_2022_QUIMICA_ANULADA = 60


def _offset_f1_do_ita(ano: int) -> dict[str, int]:
    """O deslocamento da 1ª fase do ITA no ano — a régua de 2023 é o padrão."""
    return _ITA_F1_OFFSET_POR_ANO.get(ano, _ITA_F1_OFFSET_PADRAO)


def _indice_f1_do_ita(ano: int, sufixo: str, numero: int) -> int | None:
    """O slide da questão dentro da galeria da matéria, ou None se não existir.

    Quase sempre é uma subtração — o número é absoluto na prova e a galeria
    começa em 1. A exceção é a Química de 2022: a q60 não tem slide (devolve
    None, que `url_da_resolucao` transforma em "sem resolução"), e as que vêm
    depois dela andam um slide para trás. É a única questão sem slide nas
    galerias da 1ª fase de 2022, 2023 e 2024, todas relidas em 04/09/2026.
    """
    indice = numero - _offset_f1_do_ita(ano).get(sufixo, 0)
    if ano == 2022 and sufixo == "_qui":
        if numero == _ITA_F1_2022_QUIMICA_ANULADA:
            return None
        if numero > _ITA_F1_2022_QUIMICA_ANULADA:
            return indice - 1
    return indice

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

# ⚠️ A Física de 2022 desloca UM slide, e o motivo é um erro na página do Ari,
# não uma regra nossa. Conferido em 04/09/2026 baixando
# `servicos.aridesa.com.br/comentario/ime/2022-2023/`: a `gallery-2` tem 16
# botões, e o PRIMEIRO é `FIS-2_Q01.gif` rotulado "15-C" — uma imagem da 2ª FASE
# encravada no topo da galeria da 1ª. A q16, que é a primeira de verdade, cai no
# índice 2.
#
# O Fancybox numera pela ordem no DOM, então o intruso empurra as 15 questões
# uma casa. Sem este ajuste, a q16 abre a prova errada e as outras quatorze
# abrem a questão anterior. Em 2021 a mesma galeria tem 15 botões e começa em
# `FIS-1_Q16` — por isso o desconto é por ANO, e não por matéria.
#
# Diferente do buraco da Química do ITA 2022, este quebra link VIVO: as 15
# questões estão no acervo (docs/35 §2).
_IME_F1_OFFSET_POR_ANO: dict[int, dict[str, int]] = {
    2022: {"_mat": 0, "": 14, "_qui": 30},
}


def _offset_f1_do_ime(ano: int) -> dict[str, int]:
    """O deslocamento da 1ª fase do IME no ano — 2021 é a régua limpa."""
    return _IME_F1_OFFSET_POR_ANO.get(ano, _IME_F1_OFFSET)

# Provas antigas do IME: uma landing page por biênio, sem link por questão.
_IME_LANDING_ANTIGA = {
    2020: "http://login.aridesa.com.br/vestibular/ime2020_2021/index.aspx",
    2019: "http://login.aridesa.com.br/vestibular/ime2019_2020/index.aspx",
    2018: "http://login.aridesa.com.br/vestibular/ime2018_2019/index.aspx",
}


def _fase1(sufixo: str, vestibular: str, ano: int, numero: int) -> str:
    if vestibular == "IME":
        if ano in _IME_REFERENCE_ID:
            # 2023–2025: as 40 questões dividem uma galeria só, indexada pelo
            # número. O nome dela na plataforma nova é `gallery-stage-1`, não
            # `gallery-1` — este é o `stage` da 1ª fase, não um índice (docs/35 §2).
            return (
                f"https://comentarios.aridesa.com.br/ime"
                f"?reference_id={_IME_REFERENCE_ID[ano]}#gallery-stage-1-{numero}"
            )
        if ano in (2021, 2022):
            galeria = _IME_F1_GALERIA.get(sufixo, 1)
            dentro = numero - _offset_f1_do_ime(ano).get(sufixo, 0)
            return (
                f"https://servicos.aridesa.com.br/comentario/ime/"
                f"{ano}-{ano + 1}/#gallery-{galeria}-{dentro}"
            )
        return _IME_LANDING_ANTIGA.get(ano, "")

    if vestibular != "ITA":
        return ""

    if ano >= 2025:
        # Galeria única na plataforma nova, indexada pelo número absoluto da
        # prova — sem offset por matéria, ao contrário de 2022–2024. Conferido
        # em 04/09 contra a página: índice 36 → `QUI-1_Q36.gif`, rótulo `36 - C`.
        return (
            f"https://comentarios.aridesa.com.br/ita"
            f"?reference_id={ano - 2024}#gallery-stage-1-{numero}"
        )
    if ano >= 2022:
        indice = _indice_f1_do_ita(ano, sufixo, numero)
        if indice is None:
            # Questão que a galeria não tem. Vazio aqui é o None de
            # `url_da_resolucao`, e o front esconde o botão pela ausência.
            return ""
        galeria = _ITA_F1_GALERIA.get(sufixo, 1)
        return f"https://servicos.aridesa.com.br/comentario/ita/{ano}/#gallery-{galeria}-{indice}"
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
        # O nome da galeria acompanha o `stage` da query — `gallery-stage-2` na
        # 2ª fase, `gallery-stage-1` na 1ª. Conferido em 04/09 contra a página:
        # 46 âncoras na ordem Mat 1–10 · Quí 11–20 · Fís 21–30 · Port 31–45 ·
        # Redação 46, que é exatamente o que os offsets acima assumem (docs/35 §2).
        return (
            f"https://comentarios.aridesa.com.br/ita"
            f"?reference_id={ano - 2024}&stage=2#gallery-stage-2-{slide}"
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
