"""Mandar uma notificação para os aparelhos de alguém — e manter a tabela limpa.

A porta de entrada de todo evento futuro é `enviar_para_dono` (ou
`enviar_para_inscricoes`, quando o evento já tiver as linhas). Hoje só o botão
"Testar" a chama (routes/push.py).

Síncrono de propósito. A camada de dados do projeto é síncrona (api/CLAUDE.md,
"Convenções"), e um `async def` que fizesse `.execute()` rodaria no event loop do
único worker. O paralelismo que importa — vários POSTs ao fabricante de uma vez —
fica num pool de threads AQUI DENTRO, e as escritas no banco acontecem DEPOIS, na
thread de quem chamou: o cliente PostgREST divide uma conexão HTTP/2 entre todas
as requisições, e um GOAWAY numa stream derruba as outras
(app/supabase_client.py). Quem chamar isto de dentro de um `async def` usa
`asyncio.to_thread`.

O que cada resposta do fabricante quer dizer (docs/45 §5.4):

  2xx        entregue ao fabricante              zera as falhas
  404, 410   inscrição morta (permissão revogada,  APAGA a linha
             app desinstalado, navegador limpo)
  429, 5xx,  transitório                         conta falha; com 10 seguidas e
  rede                                           nada entregue em 7 dias, apaga
  outro 4xx  ERRO NOSSO: chave VAPID, assinatura, só registra e loga alto
             corpo grande demais                 — nunca conta contra o aparelho

A última linha é a que mais importa: se a nossa chave estiver errada, TODO envio
volta 403. Contar isso como falha do aparelho apagaria, em dez envios, a inscrição
de todo mundo — por um erro que é nosso.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import httpx

from ..config import get_settings
from . import endpoints
from .chaves import ChaveVapid, chave_do_servidor, de_b64url
from .cifra import cifrar
from .vapid import cabecalho_authorization

log = logging.getLogger("sas.push")

TABELA = "inscricao_push"

#: POSTs simultâneos ao fabricante. Um evento para todos os alunos dá ~1.500; em
#: série, minutos. Dez é folga sem parecer ataque a ninguém.
CONCORRENCIA = 10
PRAZO_DO_POST_S = 10.0

FALHAS_PARA_DESISTIR = 10
SEM_ENTREGA_HA = timedelta(days=7)

#: TTL máximo que os serviços aceitam (FCM: 4 semanas).
TTL_MAXIMO = 28 * 24 * 3600

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
#: RFC 8030 §5.4: no máximo 32 caracteres do alfabeto base64url.
_TOPICO = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


@dataclass(frozen=True)
class Dono:
    """De quem são os aparelhos. A coluna é o tipo; nunca vem do corpo da requisição."""

    coluna: Literal["aluno_id", "usuario_coordenacao_id"]
    id: str


@dataclass(frozen=True)
class Notificacao:
    """O que aparece no aparelho — e as regras que todo evento herda.

    ⚠️ **A tela bloqueada é pública** (docs/45 §2, regra 4): `titulo` e `corpo`
    nunca levam nota, posição, desempenho nem nome de outro aluno. Dizem que há
    algo, não o quê. Isto não se valida por código; é contrato de quem chama.

    O `topico` vai EM CLARO no cabeçalho `Topic`, legível pelo fabricante: slug
    genérico, nunca dado de aluno (regra 2).
    """

    tipo: str
    titulo: str
    corpo: str
    url: str = "/"
    tag: str | None = None
    ttl_segundos: int = 86_400
    urgencia: Literal["very-low", "low", "normal", "high"] = "normal"
    topico: str | None = None

    def __post_init__(self) -> None:
        if not _SLUG.match(self.tipo):
            raise ValueError("tipo precisa ser um slug curto (a-z, 0-9, -)")
        if not self.titulo.strip() or len(self.titulo) > 80:
            raise ValueError("título vazio ou com mais de 80 caracteres")
        if len(self.corpo) > 200:
            raise ValueError("corpo com mais de 200 caracteres")
        if not url_interna(self.url):
            raise ValueError("url precisa ser um caminho interno do SAS")
        if self.tag is not None and not _SLUG.match(self.tag):
            raise ValueError("tag precisa ser um slug curto")
        if not 0 <= self.ttl_segundos <= TTL_MAXIMO:
            raise ValueError("ttl fora de 0..28 dias")
        if self.topico is not None and not _TOPICO.match(self.topico):
            raise ValueError("topico: até 32 caracteres base64url")

    def texto(self) -> bytes:
        """O JSON que o service worker lê (web/public/sw.js). Curto: menos de 300 bytes."""
        return json.dumps(
            {"titulo": self.titulo, "corpo": self.corpo, "url": self.url, "tag": self.tag},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")


def url_interna(url: str) -> bool:
    """A mesma regra de `web/src/dominio/voltaDoLogin.ts`: começa com `/`, nunca `//`.

    O service worker confere de novo antes de abrir — as duas pontas, como no login.
    """
    return (
        url.startswith("/")
        and not url.startswith("//")
        and "\\" not in url
        and not any(ord(c) < 0x20 for c in url)
        and len(url) <= 512
    )


@dataclass
class ResultadoDoEnvio:
    tentadas: int = 0
    entregues: int = 0
    removidas: int = 0
    falhas: int = 0

    def como_dict(self) -> dict[str, int]:
        return {
            "tentadas": self.tentadas,
            "entregues": self.entregues,
            "removidas": self.removidas,
            "falhas": self.falhas,
        }


Leitura = Literal["ok", "morta", "transitoria", "erro_nosso"]


def ler_status(status: int | None) -> Leitura:
    if status is None:
        return "transitoria"  # rede, DNS, prazo
    if 200 <= status < 300:
        return "ok"
    if status in (404, 410):
        return "morta"
    if status == 429 or status >= 500:
        return "transitoria"
    return "erro_nosso"


def _agora() -> datetime:
    return datetime.now(UTC)


def _post(
    http: httpx.Client, chave: ChaveVapid, contato: str, inscricao: dict[str, Any], n: Notificacao, texto: bytes
) -> tuple[int | None, str | None]:
    endpoint = inscricao["endpoint"]
    try:
        # De novo aqui, e não só na rota: a linha pode ter entrado por outro
        # caminho (script, restauração de backup). O POST é o que faz o SSRF.
        endpoints.validar(endpoint)
        corpo = cifrar(texto, ua_public=de_b64url(inscricao["chave_p256dh"]), auth_secret=de_b64url(inscricao["chave_auth"]))
    except ValueError as erro:
        return 410, f"inscrição inutilizável: {type(erro).__name__}"
    cabecalhos = {
        "Authorization": cabecalho_authorization(endpoint, chave, contato),
        "TTL": str(n.ttl_segundos),
        "Urgency": n.urgencia,
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
    }
    if n.topico:
        cabecalhos["Topic"] = n.topico
    try:
        # `follow_redirects=False` é o default do httpx e fica explícito: um
        # redirect para dentro da rede desfaria a lista fechada de hosts.
        resposta = http.post(endpoint, content=corpo, headers=cabecalhos, follow_redirects=False)
    except httpx.HTTPError as erro:
        return None, type(erro).__name__
    if resposta.status_code < 300:
        return resposta.status_code, None
    return resposta.status_code, resposta.text[:200]


def enviar_para_dono(cliente: Any, dono: Dono, notificacao: Notificacao, *, http: httpx.Client | None = None) -> ResultadoDoEnvio:
    """Manda para TODOS os aparelhos de uma pessoa."""
    inscricoes = (
        cliente.table(TABELA)
        .select("id, endpoint, chave_p256dh, chave_auth, falhas_seguidas, ultimo_envio_ok_em, criada_em")
        .eq(dono.coluna, dono.id)
        .execute()
    ).data or []
    return enviar_para_inscricoes(cliente, inscricoes, notificacao, http=http)


def enviar_para_inscricoes(
    cliente: Any, inscricoes: list[dict[str, Any]], notificacao: Notificacao, *, http: httpx.Client | None = None
) -> ResultadoDoEnvio:
    resultado = ResultadoDoEnvio(tentadas=len(inscricoes))
    if not inscricoes:
        return resultado
    chave = chave_do_servidor()
    if chave is None:
        raise RuntimeError("push desligado: PUSH_VAPID_CHAVE_PRIVADA vazia")
    contato = get_settings().push_vapid_contato
    texto = notificacao.texto()

    proprio = http is None
    http = http or httpx.Client(timeout=PRAZO_DO_POST_S)
    try:
        with ThreadPoolExecutor(max_workers=min(CONCORRENCIA, len(inscricoes))) as pool:
            respostas = list(pool.map(lambda i: _post(http, chave, contato, i, notificacao, texto), inscricoes))
    finally:
        if proprio:
            http.close()

    _registrar(cliente, inscricoes, respostas, notificacao, resultado)
    return resultado


def _registrar(
    cliente: Any,
    inscricoes: list[dict[str, Any]],
    respostas: list[tuple[int | None, str | None]],
    notificacao: Notificacao,
    resultado: ResultadoDoEnvio,
) -> None:
    agora = _agora()
    entregues_por_status: dict[int, list[str]] = defaultdict(list)
    mortas: list[str] = []

    for inscricao, (status, erro) in zip(inscricoes, respostas, strict=True):
        leitura = ler_status(status)
        host = endpoints.host_do_endpoint(inscricao["endpoint"])
        if leitura == "ok":
            entregues_por_status[status or 201].append(inscricao["id"])
            resultado.entregues += 1
        elif leitura == "morta":
            mortas.append(inscricao["id"])
            resultado.removidas += 1
            log.info("push: inscrição %s morta em %s (%s) — apagada", inscricao["id"], host, status)
        elif leitura == "transitoria":
            resultado.falhas += 1
            falhas = int(inscricao.get("falhas_seguidas") or 0) + 1
            if falhas >= FALHAS_PARA_DESISTIR and _sem_entrega_ha_tempo(inscricao, agora):
                mortas.append(inscricao["id"])
                resultado.removidas += 1
                log.info("push: inscrição %s com %d falhas seguidas em %s — apagada", inscricao["id"], falhas, host)
                continue
            cliente.table(TABELA).update(
                {"falhas_seguidas": falhas, "ultimo_status_http": status, "ultimo_erro": erro}
            ).eq("id", inscricao["id"]).execute()
        else:
            resultado.falhas += 1
            # Alto, porque é bug nosso e vale para todo aparelho daquele fabricante.
            log.error(
                "push: %s recusou o envio '%s' com %s — chave VAPID, assinatura ou corpo (%s)",
                host, notificacao.tipo, status, (erro or "")[:120],
            )
            cliente.table(TABELA).update(
                {"ultimo_status_http": status, "ultimo_erro": erro}
            ).eq("id", inscricao["id"]).execute()

    for status, ids in entregues_por_status.items():
        cliente.table(TABELA).update(
            {"ultimo_envio_ok_em": agora.isoformat(), "falhas_seguidas": 0, "ultimo_status_http": status, "ultimo_erro": None}
        ).in_("id", ids).execute()
    if mortas:
        cliente.table(TABELA).delete().in_("id", mortas).execute()


def _sem_entrega_ha_tempo(inscricao: dict[str, Any], agora: datetime) -> bool:
    referencia = inscricao.get("ultimo_envio_ok_em") or inscricao.get("criada_em")
    if not referencia:
        return True
    try:
        momento = datetime.fromisoformat(str(referencia))
    except ValueError:
        return True
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=UTC)
    return agora - momento > SEM_ENTREGA_HA
