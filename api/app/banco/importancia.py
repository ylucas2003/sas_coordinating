"""O índice de importância do assunto — "o que mais cai", em uma unidade honesta.

Responde *"esse tópico vale ~4% da prova, hoje"*. É o passo 2 e o passo 3 do
desenho de [docs/24 §4.2]; os passos 1 e 4 já existiam quando este arquivo foi
escrito, e é por isso que ele é curto:

    passo 1 · p(t,a) = ocorrências do tópico no ano ÷ questões do ano
              → já vem pronto: `estatisticas.recorrencia` devolve `porAno`
                (numerador) e `questoesPorAno` (denominador)
    passo 2 · w(a) = 0,5^((ref − a)/H)                       ← aqui
    passo 3 · I(t) = Σ w(a)·p(t,a) ÷ Σ w(a)                  ← aqui
    passo 4 · T(t) = média recente − média anterior
              → já existe em `web/src/dominio/serieDoAssunto.ts::tendenciaDaSerie`

⚠️ **A unidade é fatia da prova, não contagem.** ITA e IME têm número de
questões diferente por ano, e o formato do ITA muda em 2019 — contagem bruta não
compara bancas nem anos. Como `I` é média ponderada de percentuais, ele CONTINUA
sendo um percentual: é isso que vai à tela. Um ranking 0–100 pode acompanhar,
mas como segunda linha — percentual da prova é informação, índice normalizado é
só ordenação.

⚠️ **Meia-vida, não janela.** A janela joga fora sinal e cria um degrau: quando
2019 sai dela, o número pula sem que nada tenha acontecido no mundo. A
exponencial decai liso e nenhum ano some (docs/24 §4.2).

⚠️ **A tendência fica FORA do índice**, e é decisão de produto, não de código: o
índice diz quanto estudar, a tendência diz por quê. Embutir a segunda no
primeiro esconderia justamente o que ele ponderou.

Funções puras, sem I/O — o mesmo contrato de `stats/criterios.py`, e pelo mesmo
motivo: testável sem container. A única função que toca o banco é
`carregar_parametro`, no fim do arquivo, e ela recebe o cliente por argumento.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger("sas.banco.importancia")

#: Os valores de fábrica, decididos em 29/08/2026 (docs/24 §4.2 e §9.2).
#:
#: ⚠️ Eles existem para o índice NUNCA depender de o banco responder. É a mesma
#: escolha que faz o arquivo vencer para as réguas embutidas em
#: `criterios_repo.py`: um índice que some porque uma linha de configuração
#: falhou é pior que um índice com o valor de fábrica (docs/34 §5 · D2).
MEIA_VIDA_PADRAO = 5.0
JANELA_TENDENCIA_PADRAO = 5


@dataclass(frozen=True)
class ParametroImportancia:
    """A calibração do índice. Imutável de propósito: quem quer outro valor
    constrói outro, e assim um cálculo em andamento não muda no meio."""

    meia_vida_anos: float = MEIA_VIDA_PADRAO
    janela_tendencia_anos: int = JANELA_TENDENCIA_PADRAO
    #: `None` = veio de fábrica, não do banco. A tela usa isto para dizer se a
    #: coordenação já girou o botão ou se está no valor original.
    versao: int | None = None


def peso_do_ano(ano: int, ano_referencia: int, meia_vida_anos: float) -> float:
    """`w(a) = 0,5^((ref − a)/H)`.

    Um ano `meia_vida_anos` mais velho que a referência pesa metade; o dobro
    disso, um quarto. Anos posteriores à referência pesam MAIS que 1, e isso é
    correto — a referência é só a origem da régua, não um teto (ver a nota
    sobre invariância em `indice_de_importancia`).
    """
    return 0.5 ** ((ano_referencia - ano) / meia_vida_anos)


def fatia_do_ano(ocorrencias: int, questoes_no_ano: int) -> float:
    """`p(t,a)`, em percentual da prova daquele ano.

    Zero quando não há prova no ano: dividir por zero é o caso de um ano que
    existe no recorte mas não tem questão classificada, e ele não deve
    contribuir nem inflar o denominador do índice.
    """
    if questoes_no_ano <= 0:
        return 0.0
    return 100.0 * ocorrencias / questoes_no_ano


def indice_de_importancia(
    por_ano: dict[int, int],
    questoes_por_ano: dict[int, int],
    parametro: ParametroImportancia | None = None,
) -> float:
    """`I(t) = Σ w(a)·p(t,a) ÷ Σ w(a)`, em percentual da prova.

    `por_ano` é o `RecorrenciaTopico.porAno` de um tópico; `questoes_por_ano` é
    o `EstatisticasBanco.questoesPorAno` do MESMO recorte.

    ⚠️ **O domínio é o de `questoes_por_ano`, não o de `por_ano`.** Um ano em
    que o tópico não caiu vale `p = 0` e PRECISA entrar na média — é informação
    de estudo ("não apareceu em oito anos"). Iterar sobre `por_ano` puxaria o
    índice para cima exatamente nos tópicos raros, que são os que mais somem.

    ⚠️ **Numerador e denominador têm de vir do mesmo recorte.** É a armadilha
    que `estatisticas.recorrencia` já documenta: filtrar só o de cima faz a
    fatia de uma questão de 2ª fase ser dividida pela prova inteira, e o número
    sai menor que a verdade **sem nenhum erro na tela**. Aqui isso vem de graça,
    porque os dois dicionários saem da mesma chamada.

    ⚠️ **O ano de referência não altera o resultado, e é por isso que ele não é
    parâmetro.** Como `w(a) = 0,5^(ref/H) · 0,5^(−a/H)`, o fator que depende de
    `ref` é constante e aparece nos DOIS lados da divisão — ele cancela. Trocar
    a referência de 2025 para 2026 não move o índice em nada. Adotamos o ano
    mais recente do recorte só para os pesos ficarem legíveis num debug (o ano
    mais novo pesa 1,0).
    """
    p = parametro or ParametroImportancia()
    anos = [ano for ano, total in questoes_por_ano.items() if total > 0]
    if not anos:
        return 0.0

    referencia = max(anos)
    soma_pesada = 0.0
    soma_dos_pesos = 0.0
    for ano in anos:
        peso = peso_do_ano(ano, referencia, p.meia_vida_anos)
        soma_pesada += peso * fatia_do_ano(por_ano.get(ano, 0), questoes_por_ano[ano])
        soma_dos_pesos += peso

    if soma_dos_pesos == 0:
        return 0.0
    return soma_pesada / soma_dos_pesos


def ranking_0_a_100(indices: dict[str, float]) -> dict[str, float]:
    """O índice reescalado para 0–100 pelo máximo do recorte.

    **Segunda linha, nunca a primeira.** Percentual da prova é informação — "vale
    4% da prova" se lê sozinho e compara entre matérias. O 0–100 é só ordenação:
    ele diz que um tópico é o maior DAQUELE recorte, e um "100" de Química não
    significa o mesmo que um "100" de Física.
    """
    if not indices:
        return {}
    maior = max(indices.values())
    if maior <= 0:
        return {codigo: 0.0 for codigo in indices}
    return {codigo: 100.0 * valor / maior for codigo, valor in indices.items()}


# ─── A metade que toca o banco ───────────────────────────────────────────
# Fica no mesmo arquivo, e não num `_repo` separado como os critérios, porque
# são vinte linhas contra as quatrocentas de lá. O contrato de pureza acima
# continua valendo: o cliente entra por argumento, então o teste passa um fake.


def carregar_parametro(cliente) -> ParametroImportancia:
    """A linha ativa de `parametro_importancia`, ou os valores de fábrica.

    ⚠️ **Nunca levanta.** Qualquer falha — tabela ausente, PostgREST fora,
    schema cache velho depois de uma migration (armadilha 1 do CLAUDE.md) —
    devolve o padrão e registra. O índice de importância não pode sumir da tela
    porque uma linha de configuração não respondeu; ele pode, no máximo, voltar
    ao valor com que foi desenhado.
    """
    try:
        resposta = (
            cliente.table("parametro_importancia")
            .select("versao, meia_vida_anos, janela_tendencia_anos")
            .eq("ativo", True)
            .limit(1)
            .execute()
        )
    except Exception:
        log.warning("parametro_importancia ilegível; usando os valores de fábrica", exc_info=True)
        return ParametroImportancia()

    linhas = resposta.data or []
    if not linhas:
        return ParametroImportancia()

    linha = linhas[0]
    try:
        return ParametroImportancia(
            meia_vida_anos=float(linha["meia_vida_anos"]),
            janela_tendencia_anos=int(linha["janela_tendencia_anos"]),
            versao=int(linha["versao"]),
        )
    except (KeyError, TypeError, ValueError):
        # Linha existe mas está malformada. O CHECK da 0044 impede isso pelo
        # caminho normal; se chegou aqui, alguém escreveu direto no banco.
        log.warning("parametro_importancia com linha inválida: %r", linha)
        return ParametroImportancia()


def historico(cliente) -> list[dict]:
    """Todas as versões, da mais nova para a mais velha.

    A tela mostra isto ao lado do formulário: quem girou o botão, quando, e de
    quanto para quanto. Um número que reordena o que ~900 alunos veem precisa
    de rastro legível, não só de linha na auditoria.
    """
    resposta = (
        cliente.table("parametro_importancia")
        .select("versao, meia_vida_anos, janela_tendencia_anos, ativo, criado_em, criado_por")
        .order("versao", desc=True)
        .execute()
    )
    return resposta.data or []


class ParametroInvalido(ValueError):
    """Valor que o CHECK do banco recusaria — barrado antes de chegar lá, para
    a tela poder dizer o que está errado em vez de devolver um 500."""


#: Teto de sanidade da meia-vida. Não é regra de edital, é calibração: acima de
#: um século o peso vira constante e o índice deixa de ser "pesado por
#: recência" — melhor recusar do que aceitar um número que anula a feature em
#: silêncio.
MEIA_VIDA_MAXIMA = 100.0


def validar(meia_vida_anos: float, janela_tendencia_anos: int) -> None:
    if not (0 < meia_vida_anos <= MEIA_VIDA_MAXIMA):
        raise ParametroInvalido(
            f"meia-vida precisa estar entre 0 e {MEIA_VIDA_MAXIMA:g} anos"
        )
    if janela_tendencia_anos < 1:
        raise ParametroInvalido("a janela da tendência precisa ser de pelo menos 1 ano")


def nova_versao(
    cliente, meia_vida_anos: float, janela_tendencia_anos: int, *, criado_por: str | None
) -> dict:
    """Grava a versão seguinte e desativa a anterior.

    ⚠️ **Nunca edita no lugar**, e é a mesma razão de `criterios_repo`: mexer no
    valor mudaria retroativamente todo ranking que alguém já leu — em silêncio,
    e sem ninguém conseguir explicar a diferença depois. Aqui o efeito é maior
    que numa régua, porque um `H` novo reordena a lista inteira de uma vez.

    ⚠️ A ordem importa: **desativa primeiro, insere depois.** O índice parcial
    `parametro_importancia_uma_ativa` recusa duas ativas, então inserir antes
    falharia. E se a inserção falhar depois de desativar, a leitura cai no valor
    de fábrica — degradação prevista, não quebra (ver `carregar_parametro`).
    """
    validar(meia_vida_anos, janela_tendencia_anos)

    versoes = historico(cliente)
    proxima = max((int(v["versao"]) for v in versoes), default=0) + 1

    cliente.table("parametro_importancia").update({"ativo": False}).eq("ativo", True).execute()
    resposta = (
        cliente.table("parametro_importancia")
        .insert(
            {
                "versao": proxima,
                "meia_vida_anos": meia_vida_anos,
                "janela_tendencia_anos": janela_tendencia_anos,
                "ativo": True,
                "criado_por": criado_por,
            }
        )
        .execute()
    )
    linhas = resposta.data or []
    return linhas[0] if linhas else {"versao": proxima}
