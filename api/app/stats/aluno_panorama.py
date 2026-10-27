"""O panorama do aluno — "como estou?" numa leitura só (docs/43 §4.2 e §4.3).

A pergunta mais comum ao Tio Léo é aberta, e respondê-la pedia três a cinco
tools: as notas, a zona, a sequência, a agenda. Aqui elas se juntam para a tool
`meu_panorama` (chat/tools_aluno.py) e para quem mais quiser a mesma
composição — o contexto do turno é o candidato natural.

⚠️ **Só compõe.** Cada pedaço é a função de domínio de sempre, a mesma da rota
`/me/...` correspondente: a régua sai de `zona_do_aluno` (que sai de
`stats/criterios.py`), a falta de `aplicar_regra_da_falta`, a sequência de
`contar_sequencia`. Nenhuma comparação de nota com corte acontece aqui —
uma segunda cópia da régua é o defeito que a migration 0037 matou.

O que se economiza é LEITURA, nunca regra. Somadas uma a uma, as seis funções
liam as notas do aluno sete vezes e faziam perto de 36 idas ao PostgREST,
porque sequência, agenda e meta recalculavam o histórico cada uma; aqui o
histórico é lido uma vez e entregue às três (o parâmetro `historico` delas). A
contagem está travada em tests/test_chat_tools_aluno.py.

Leitura pura, sem cache. Parte sem dado vem `None` — quem fala com o modelo
decide o que dizer dela; nada aqui vira `{"erro": ...}`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from supabase import Client

from ..banco.missao import hoje_na_escola
from .aluno_dados import conta_como_desempenho, simulados_do_aluno
from .aluno_jornada import (
    dias_ate,
    historico_com_presenca,
    meta_do_ciclo_do_aluno,
    proximo_simulado_do_aluno,
    sequencia_do_historico,
)
from .aluno_zona import vestibulares_alvo, zona_do_aluno


def panorama_do_aluno(
    cliente: Client,
    aluno_id: str,
    *,
    ultimas_notas: int = 5,
    hoje: date | None = None,
) -> dict[str, Any]:
    """A situação do aluno hoje, com cada pedaço igual ao da rota de origem.

    `{hoje, vestibularesAlvo, zona, ultimasNotas, naoContam, sequencia,
    metaDoCiclo, proximoSimulado, diasAteOProximo}`:

      * `zona` — `zona_do_aluno` inteira (GET /me/zona), ou `None` sem nota que
        conte para a régua;
      * `ultimasNotas` e `naoContam` — as `ultimas_notas` provas mais recentes
        que o aluno FEZ, de `simulados_do_aluno` (GET /me/simulados), partidas
        por `aluno_dados.conta_como_desempenho`. Em `naoContam` vai a prova
        cuja nota o SAS não conta — a provável ausência (`computavel = false`)
        e a prova não confiável —, SEM o número: ele é o zero que o modelo
        leria como "você zerou". A partição é do domínio, e a mesma da zona,
        da trajetória e do insight. ⚠️ Nem assim `ultimasNotas` é a base da
        média da zona, que tem a sua janela (`zona.media` é a média que vale);
      * `sequencia` — a mesma resposta de GET /me/jogo;
      * `metaDoCiclo` e `proximoSimulado` — GET /me/meta e GET /me/agenda;
      * `diasAteOProximo` — contado no dia da escola, o mesmo `hoje`.

    `hoje` é o dia da escola (America/Fortaleza); o parâmetro existe para o
    teste fixar o relógio.
    """
    hoje = hoje or hoje_na_escola()

    # Uma leitura das notas, com a falta, serve as três peças da jornada e a
    # lista das últimas: as provas FEITAS são as mesmas com e sem a falta
    # (`simulados_do_aluno` só acrescenta as ausências, sem nota nem delta).
    itens = simulados_do_aluno(cliente, aluno_id, incluir_faltas=True)
    historico = historico_com_presenca(cliente, aluno_id, itens=itens)
    proximo = proximo_simulado_do_aluno(cliente, aluno_id, historico=historico, hoje=hoje)
    zona = zona_do_aluno(cliente, aluno_id)
    # `simulados_do_aluno` devolve do mais recente para o mais antigo.
    recentes = [item for item in itens if item.get("presente")][: max(0, ultimas_notas)]

    return {
        "hoje": hoje.isoformat(),
        # A zona já leu os alvos para escolher a régua; sem zona, lê-se à parte.
        "vestibularesAlvo": (
            zona["vestibularesAlvo"] if zona is not None else vestibulares_alvo(cliente, aluno_id)
        ),
        "zona": zona,
        "ultimasNotas": [_nota_recente(item) for item in recentes if conta_como_desempenho(item)],
        "naoContam": [_prova_que_nao_conta(item) for item in recentes if not conta_como_desempenho(item)],
        "sequencia": sequencia_do_historico(historico, proximo),
        "metaDoCiclo": meta_do_ciclo_do_aluno(cliente, aluno_id, historico=historico),
        "proximoSimulado": proximo,
        "diasAteOProximo": dias_ate(proximo.get("data"), hoje) if proximo else None,
    }


def _nota_recente(item: dict[str, Any]) -> dict[str, Any]:
    """Uma prova feita que conta, só com o que responde "como fui ultimamente".

    `mediaGeral` já chega pelo piso de anonimato de `simulados_do_aluno`
    (docs/27 §9, regra 4) — o mesmo da ficha da prova e do histograma, e
    aplicado lá, não aqui.
    """
    return {
        "id": item.get("id"),
        "rotulo": item.get("rotulo"),
        "dataAplicacao": item.get("dataAplicacao"),
        "materia": item.get("materia"),
        "tipo": item.get("tipo"),
        "nota": item.get("nota"),
        "deltaSelf": item.get("deltaSelf"),
        "mediaGeral": item.get("mediaGeral"),
    }


def _prova_que_nao_conta(item: dict[str, Any]) -> dict[str, Any]:
    """Uma prova feita cuja nota não conta: o que é, e as marcas que dizem por quê.

    Sem `nota`, `deltaSelf` nem `mediaGeral`, de propósito: o número é o zero
    lançado por quem não fez a prova, e o que não está no resultado o modelo
    não lê como desempenho. O id fica, para a pergunta "e aquela de Química?"
    achar a prova.
    """
    return {
        "id": item.get("id"),
        "rotulo": item.get("rotulo"),
        "dataAplicacao": item.get("dataAplicacao"),
        "materia": item.get("materia"),
        "tipo": item.get("tipo"),
        "computavel": item.get("computavel"),
        "motivoNaoComputavel": item.get("motivoNaoComputavel"),
        "notaConfiavel": item.get("notaConfiavel"),
    }
