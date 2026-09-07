"""Barramento de eventos da cantina — o empurrão que evita o F5 (docs/38 §9).

O que ele resolve: cardápio, pedido e direito são escritos por TRÊS pessoas
diferentes e lidos pelas outras duas. A cantina publica e o coordenador precisa
ver; o aluno pede e a cantina precisa contar. Sem empurrão, cada tela só
descobre no próximo `refetch` — e o polling de 60 s que existia cobria o aluno,
não o balcão.

⚠️ **O evento não carrega o dado — carrega o AVISO de que o dado mudou.** Quem
recebe invalida a chave do TanStack Query e busca de novo pela rota normal.
Empurrar o conteúdo pelo stream criaria uma segunda fonte da verdade, com
serialização própria e autorização própria, e as duas divergiriam no primeiro
campo novo. Um `refetch` a mais custa uma requisição; uma cache incoerente
custa uma tela que mente.

⚠️ **Isto depende de `UVICORN_WORKERS=1`**, que é invariante declarada do
projeto (`infra/vps/.env.example`: "NÃO aumente"). As filas vivem na memória do
processo. Com dois workers, cada um teria as suas e **metade dos assinantes
pararia de receber evento, sem erro nenhum** — falha silenciosa, que é
exatamente a classe que a lista de armadilhas do CLAUDE.md existe para
prevenir. Se um dia os workers subirem, isto vira `LISTEN/NOTIFY` do Postgres,
e aí `psycopg` entra nas rotas pela primeira vez.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("sas.cantina.eventos")

#: Teto de eventos enfileirados por assinante. Uma aba parada em segundo plano
#: não pode crescer sem limite; passando disso, o mais VELHO é descartado — o
#: cliente perde um aviso intermediário e continua consistente, porque a
#: próxima invalidação busca o estado inteiro de qualquer jeito.
TETO_DA_FILA = 64

#: Silêncio máximo antes de um comentário SSE. O nginx de produção derruba a
#: conexão com `proxy_read_timeout 300s`, e um stream de cantina fica horas sem
#: nada acontecer — sem heartbeat, ela cairia toda madrugada.
SEGUNDOS_ENTRE_BATIDAS = 25


@dataclass(frozen=True)
class Evento:
    """O que mudou, e o suficiente para quem recebe decidir se lhe interessa.

    Os campos de recorte são todos opcionais porque nem todo evento os tem: uma
    concessão de direito não pertence a nenhuma cantina, e um cardápio não
    pertence a nenhum aluno.
    """

    tipo: str
    cantina_id: str | None = None
    refeicao: str | None = None
    data: str | None = None
    aluno_id: str | None = None

    def para_sse(self) -> str:
        corpo = json.dumps(
            {k: v for k, v in self.__dict__.items() if k != "tipo" and v is not None},
            ensure_ascii=False,
        )
        return f"event: {self.tipo}\ndata: {corpo}\n\n"


# `eq=False` para o dataclass ficar HASHÁVEL por identidade — é o que permite
# guardá-los num `set`. Com o `__eq__` gerado (o padrão), o Python remove o
# `__hash__` e dois assinantes com a mesma fila vazia seriam "iguais": entrar
# duas vezes no set viraria uma, e o segundo cliente nunca receberia nada.
@dataclass(eq=False)
class _Assinante:
    fila: asyncio.Queue[Evento] = field(default_factory=lambda: asyncio.Queue(TETO_DA_FILA))
    #: O que este assinante quer. A filtragem acontece na PUBLICAÇÃO e não na
    #: leitura para uma aba de aluno não acordar a cada pedido dos outros 900.
    interessa: Callable[[Evento], bool] = lambda _: True


class Barramento:
    """Fan-out em memória. Um processo, sem estado durável, sem entrega garantida.

    "Sem entrega garantida" é parte do desenho: o evento é uma dica de que vale
    recarregar. Perder uma dica atrasa uma tela em até um `staleTime`; garantir
    entrega exigiria confirmação, reenvio e ordenação — infraestrutura de fila
    para um produto que já tem a verdade no banco.
    """

    def __init__(self) -> None:
        self._assinantes: set[_Assinante] = set()

    @asynccontextmanager
    async def assinar(
        self, interessa: Callable[[Evento], bool]
    ) -> AsyncIterator[asyncio.Queue[Evento]]:
        assinante = _Assinante(interessa=interessa)
        self._assinantes.add(assinante)
        log.info("assinante entrou (%d ativos)", len(self._assinantes))
        try:
            yield assinante.fila
        finally:
            # `discard` e não `remove`: a saída pode acontecer duas vezes se o
            # cliente cair no meio de um envio, e um KeyError aqui derrubaria o
            # handler durante a limpeza.
            self._assinantes.discard(assinante)
            log.info("assinante saiu (%d ativos)", len(self._assinantes))

    def publicar(self, evento: Evento) -> None:
        """Enfileira para quem se interessa. NUNCA bloqueia e NUNCA levanta.

        É chamada de dentro de rotas de escrita, depois de o banco já ter
        aceitado a mudança. Uma falha aqui não pode desfazer o que foi gravado —
        é a mesma regra da auditoria: telemetria que derruba a operação
        auditada é pior que telemetria ausente.
        """
        for assinante in list(self._assinantes):
            try:
                if not assinante.interessa(evento):
                    continue
                if assinante.fila.full():
                    # Descarta o mais velho para abrir espaço: o aviso recente
                    # vale mais que o antigo, porque ambos levam ao mesmo
                    # refetch.
                    assinante.fila.get_nowait()
                assinante.fila.put_nowait(evento)
            except Exception:
                log.warning("não consegui entregar evento a um assinante", exc_info=True)


#: O barramento do processo. Módulo-nível de propósito — ver o ⚠️ do docstring
#: sobre `UVICORN_WORKERS=1`.
barramento = Barramento()


async def fluxo_sse(fila: asyncio.Queue[Evento]) -> AsyncIterator[str]:
    """Gera o corpo do `text/event-stream`, com batida de coração.

    O `wait_for` com timeout é o que transforma "esperar evento" em "esperar
    evento OU bater o coração": sem ele, uma conexão silenciosa por mais de
    `proxy_read_timeout` é cortada pelo nginx e o cliente reconecta em loop.
    """
    # Um evento de abertura para o cliente saber que o stream subiu — e para o
    # nginx receber bytes imediatamente, em vez de segurar a resposta enquanto
    # decide se ela existe.
    yield "event: pronto\ndata: {}\n\n"
    while True:
        try:
            evento = await asyncio.wait_for(fila.get(), timeout=SEGUNDOS_ENTRE_BATIDAS)
        except TimeoutError:
            yield ": ping\n\n"
            continue
        yield evento.para_sse()


def cabecalhos_sse() -> dict[str, str]:
    """O que a resposta precisa para atravessar o nginx sem ser bufferizada.

    `X-Accel-Buffering: no` é o mesmo do chat (`chat/rotas.py`): sem ele, com
    buffering ligado, o proxy segura a resposta inteira e o streaming não
    acontece.
    """
    return {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


# ─── Os três recortes ─────────────────────────────────────────────────────


def para_a_cantina(cantina_id: str) -> Callable[[Evento], bool]:
    """A cantina recebe o que é dela, mais mudanças de direito.

    O direito entra porque ele muda o PÚBLICO do cardápio dela — é o aviso
    "agora alguém pode pedir" que a tela mostra ao lado do botão de publicar.
    """
    def interessa(evento: Evento) -> bool:
        if evento.tipo == "direito":
            return True
        return evento.cantina_id == cantina_id
    return interessa


def para_a_coordenacao() -> Callable[[Evento], bool]:
    """A coordenação vê tudo — é o papel dela, e são poucas sessões."""
    return lambda _: True


def para_o_aluno(aluno_id: str) -> Callable[[Evento], bool]:
    """O aluno recebe mudança de cardápio, e o que for dele.

    ⚠️ **O pedido dos OUTROS não passa por aqui**, e não é economia de banda: um
    aluno acordando a cada pedido dos outros 900 saberia quantos pediram e
    quando — informação que a tela dele não mostra e que ele não deve ter.

    ⚠️ Mudança de cardápio passa para TODOS, sem filtrar por refeição, e isso é
    decisão. Filtrar exigiria congelar os direitos do aluno no instante da
    assinatura, e um stream que dura horas veria esse recorte envelhecer no
    minuto em que a coordenação concedesse a janta a ele. O evento é só um
    aviso: quem filtra de verdade é `GET /me/cantina`, que relê o direito a cada
    chamada. O custo de acordar à toa é um `refetch` de uma rota que já é barata.
    """
    def interessa(evento: Evento) -> bool:
        if evento.tipo == "cardapio":
            return True
        return evento.aluno_id == aluno_id
    return interessa


def publicar_cardapio_mudou(cardapio: dict[str, Any]) -> None:
    """Atalho para as quatro rotas que mexem em cardápio escreverem uma linha só."""
    barramento.publicar(
        Evento(
            tipo="cardapio",
            cantina_id=str(cardapio.get("cantina_id") or "") or None,
            refeicao=cardapio.get("refeicao"),
            data=str(cardapio.get("data")) if cardapio.get("data") else None,
        )
    )
