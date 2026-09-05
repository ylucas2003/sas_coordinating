"""A zona do aluno e as barras de matéria contra o corte — GET /me/zona.

Duas fontes do inventário numa rota só (`zonaEDistancia` e `cortePorMateria`),
porque as duas respondem a mesma pergunta com a mesma régua e separá-las
convidaria a segunda cópia da regra de corte.

⚠️ **Nada aqui reimplementa o corte.** A zona sai de
`classificacao._classificar_zona_por_materia`, que é o mesmo avaliador que o
Painel usa; os cortes saem de `criterios.corte_da_materia` / `corte_da_media`.
Foi exatamente a segunda implementação da regra que a migration 0037 matou —
`thresholds.py` tinha matérias core fixas e mínimo 4,0 fixo, e discordava do
Painel sobre o mesmo aluno. Uma terceira cópia aqui repetiria o defeito num
lugar novo: a tela do próprio aluno.

Os helpers de carga vêm de `classificacao.py` com o underscore e tudo. É de
propósito: eles carregam a MESMA definição de "notas que contam" (janela,
anulado, agregado, não-confiável) que a classificação em lote usa, e duplicar
essa definição é o mesmo defeito por outro caminho.
"""

from __future__ import annotations

from typing import Any

from supabase import Client

from . import criterios
from . import thresholds as th
from .classificacao import (
    _classificar_zona_por_materia,
    _mapa_codigo_materia,
    _notas_fase2_por_aluno_materia,
    _notas_recentes_por_aluno,
    _resumir_notas_por_materia,
)
from .criterios_repo import resolver

#: A régua de cada vestibular alvo, por fase. A fase escolhida é a 2ª quando o
#: aluno tem nota de Fase 2 por matéria — que é onde o corte por matéria vale —
#: e a 1ª quando não tem. É o mesmo desvio que
#: `_classificar_zona_por_materia` já faz sozinho ao cair para a média.
_REGUA_POR_VESTIBULAR = {
    "ITA": ("ita-f1", "ita-f2"),
    "IME": ("ime-f1", "ime-f2"),
}

#: A ordem de dureza das zonas. Serve ao desempate de quem mira ITA e IME:
#: vale a régua que dá o pior veredito (docs/36 §1.4).
_DUREZA = {"risco": 0, "cinzenta": 1, "top": 2}


def vestibulares_alvo(cliente: Client, aluno_id: str) -> list[str]:
    """Os vestibulares que o aluno declarou no onboarding."""
    resp = (
        cliente.table("vestibular_alvo_aluno")
        .select("vestibular")
        .eq("aluno_id", aluno_id)
        .execute()
    )
    return sorted({linha["vestibular"] for linha in (resp.data or [])})


def _criterio_do_alvo(cliente: Client, vestibular: str, *, tem_fase2: bool):
    slugs = _REGUA_POR_VESTIBULAR.get(vestibular)
    if not slugs:
        return None
    try:
        return resolver(cliente, slugs[1] if tem_fase2 else slugs[0])
    except KeyError:
        return None


def cortes_na_regua(
    criterio: criterios.Criterio, zona: str, media: float
) -> tuple[float | None, float | None]:
    """(corte já cruzado, fronteira da zona seguinte) na escala da MÉDIA.

    Os dois números respondem perguntas diferentes, e misturá-los já produziu
    dois defeitos — os dois só visíveis rodando contra o banco:

    - **`corteProximaZona` sai da ZONA**, porque é a linha que a escada desenha
      no topo da faixa do aluno. Tirá-la da média punha o rótulo "CORTE 6,0"
      sobre a fronteira risco→cinzenta, que vale 5,0.
    - **`corteAtual` sai da MÉDIA**, porque é uma afirmação sobre o aluno: "você
      já passou disto". O critério da casa combina com "todos" e só corta quem
      falha em TUDO (docs/18 §1.7), então alguém com média 4,67 fica em
      `cinzenta` sem ter passado o mínimo de 5,0 — anunciar que passou é falso.

    ⚠️ E os dois PODEM discordar de propósito: um aluno com média 5,1 em `risco`
    já cruzou o 5,0 e continua cortado, porque quem o corta é uma MATÉRIA, não a
    média. Nesse caso `distancia` sai `None` e a tela esconde a cota — medir uma
    distância de média que não é o que o segura seria apontar para o lugar
    errado. Quem nomeia o problema aí é `materiaMaisCurta` e as barras.
    """
    corte_media = criterios.corte_da_media(criterio)
    if corte_media is None:
        return None, None
    confortavel = corte_media + criterios.MARGEM_CONFORTAVEL

    if zona == "risco":
        proxima = corte_media
    elif zona == "cinzenta":
        proxima = confortavel
    else:
        proxima = None  # `top` é terminal: não existe zona acima.

    cruzadas = [f for f in (corte_media, confortavel) if media >= f]
    return (max(cruzadas) if cruzadas else None, proxima)


def zona_do_aluno(cliente: Client, aluno_id: str) -> dict[str, Any] | None:
    """Mesma resposta de GET /me/zona. `None` quando o aluno não tem nota.

    Não lê `classificacao_aluno`. A tabela é cache de lote e só cobre 568 dos
    1.229 alunos com nota — devolver 404 para os outros 661 seria transformar
    "o job ainda não passou por você" em "você não existe". O avaliador é
    barato para um aluno só, então a rota calcula.
    """
    janela = th.JANELA_CLASSIFICACAO

    recentes = _notas_recentes_por_aluno(cliente, janela=janela, aluno_ids=[aluno_id])
    notas = recentes.get(aluno_id) or []
    if not notas:
        return None
    media_recente = sum(n["pontuacao"] for n in notas) / len(notas)

    por_materia_id = (
        _notas_fase2_por_aluno_materia(cliente, janela=janela, aluno_ids=[aluno_id])
    ).get(aluno_id) or {}
    por_codigo = _resumir_notas_por_materia(por_materia_id, _mapa_codigo_materia(cliente))

    alvos = vestibulares_alvo(cliente, aluno_id)
    candidatos = [
        c
        for c in (
            _criterio_do_alvo(cliente, v, tem_fase2=bool(por_codigo)) for v in alvos
        )
        if c is not None
    ]
    # Sem alvo declarado — aluno que ainda não passou pelo onboarding — vale a
    # régua da casa, que é a mesma que `classificacao_aluno` grava.
    if not candidatos:
        candidatos = [resolver(cliente, criterios.CRITERIO_DA_CASA)]

    # Quem mira ITA e IME é avaliado contra os dois, e vale o pior veredito:
    # a boa notícia de uma régua não apaga o corte da outra.
    avaliados = [
        (
            _classificar_zona_por_materia(
                notas_por_materia_codigo=por_codigo,
                media_recente=media_recente,
                criterio=criterio,
            ),
            criterio,
        )
        for criterio in candidatos
    ]
    # Empate entre ITA e IME vale para a régua que CONSEGUE responder. As duas
    # dizendo "cinzenta" é comum, e `ime-f2` não cobra média (Art. 37, III:
    # mínimos só por matéria) — escolhê-la no empate entregaria ao aluno uma
    # zona sem cota nenhuma quando a outra régua tinha o número. Só depois
    # disso a ordem alfabética desempata, para a resposta ser estável.
    zona, criterio = min(
        avaliados,
        key=lambda par: (
            _DUREZA[par[0]],
            criterios.corte_da_media(par[1]) is None,
            par[1].slug,
        ),
    )

    corte_atual, corte_proxima = cortes_na_regua(criterio, zona, media_recente)
    # `None` e não zero quando a média já passou a fronteira: zero seria lido
    # como "está empatado com o corte", e o que acontece é outra coisa — a
    # média não é o que segura este aluno.
    falta = None if corte_proxima is None else corte_proxima - media_recente
    distancia = round(falta, 2) if falta is not None and falta > 0 else None

    materias = _materias_contra_corte(criterio, por_codigo, cliente)
    faltando = [
        (m["corte"] - m["nota"], m["materia"]) for m in materias if m["nota"] < m["corte"]
    ]

    return {
        "zona": zona,
        "media": round(media_recente, 2),
        "corteProximaZona": round(corte_proxima, 2) if corte_proxima is not None else None,
        "corteAtual": round(corte_atual, 2) if corte_atual is not None else None,
        "distancia": distancia,
        "materiaMaisCurta": min(faltando)[1] if faltando else None,
        "regua": criterio.nome,
        "materias": materias,
    }


def _materias_contra_corte(
    criterio: criterios.Criterio,
    notas_por_codigo: dict[str, float],
    cliente: Client,
) -> list[dict[str, Any]]:
    """As barras de "onde você está" — uma matéria, a nota e o corte DELA.

    O corte é por matéria porque ele É por matéria: 4,0 no geral e 5,0 no
    inglês da Fase 1 do ITA, que é o único eliminatório (docs/24 §2).
    """
    nomes = _nome_por_codigo_materia(cliente)
    saida: list[dict[str, Any]] = []
    for codigo, nota in sorted(notas_por_codigo.items()):
        corte = criterios.corte_da_materia(criterio, codigo)
        if corte is None:
            continue
        saida.append(
            {
                "materia": nomes.get(codigo, codigo),
                "nota": round(nota, 2),
                "corte": round(corte, 2),
                "eliminatoria": criterios.e_eliminatoria(criterio, codigo),
            }
        )
    return saida


def _nome_por_codigo_materia(cliente: Client) -> dict[str, str]:
    resp = cliente.table("materia").select("codigo, nome").execute()
    return {linha["codigo"]: linha["nome"] for linha in (resp.data or [])}
