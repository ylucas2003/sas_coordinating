"""Para onde o servidor aceita fazer POST — a lista FECHADA de serviços de push.

⚠️ **O endpoint é uma URL que o CLIENTE manda e que o SERVIDOR vai chamar.** Sem
este filtro, qualquer sessão autenticada registraria `http://postgrest:3000/aluno`
como "aparelho" e faria a API mandar POST para dentro da rede do compose — onde o
papel anônimo do PostgREST tem acesso total ao schema (armadilha 4 do CLAUDE.md).
É SSRF de manual, e a defesa é não aceitar destino que não seja um dos serviços
de push que os navegadores de fato usam (docs/45 §5.3).

Só `https`, porta 443, sem usuário/senha na URL, e host EXATO ou sufixo da lista.
Navegador com outro serviço falha fechado: a inscrição é recusada com 422 e o host
entra aqui quando alguém de fato o pedir — com o nome do navegador no comentário.
"""

from __future__ import annotations

from urllib.parse import urlsplit

#: Host exato → quem o usa.
HOSTS = {
    # Chrome (desktop e Android), Edge-Chromium em parte, Samsung Internet, Opera, Brave.
    "fcm.googleapis.com": "Google (FCM)",
    # Safari no macOS 13+ e app instalado na Tela de Início do iPhone (iOS 16.4+).
    "web.push.apple.com": "Apple (APNs)",
    # Firefox, desktop e Android.
    "updates.push.services.mozilla.com": "Mozilla (autopush)",
}

#: Sufixo → quem o usa. O Edge recebe um host por região (`wns2-bl2p.notify.windows.com`).
SUFIXOS = {
    ".notify.windows.com": "Microsoft (WNS)",
}

#: Endpoint real tem algumas centenas de caracteres; o teto é para um corpo
#: absurdo não virar linha de banco.
TAMANHO_MAXIMO = 2048


class EndpointRecusado(ValueError):
    pass


def validar(endpoint: str) -> str:
    """Devolve o endpoint se ele for de um serviço conhecido; senão levanta."""
    if not endpoint or len(endpoint) > TAMANHO_MAXIMO:
        raise EndpointRecusado("endereço de inscrição vazio ou longo demais")
    try:
        partes = urlsplit(endpoint)
        porta = partes.port
    except ValueError as erro:
        raise EndpointRecusado("endereço de inscrição malformado") from erro
    if partes.scheme != "https":
        raise EndpointRecusado("o serviço de push precisa ser https")
    if partes.username is not None or partes.password is not None:
        raise EndpointRecusado("endereço de inscrição com credencial embutida")
    if porta not in (None, 443):
        raise EndpointRecusado("o serviço de push precisa estar na porta 443")
    host = (partes.hostname or "").lower()
    if not servico_do_host(host):
        raise EndpointRecusado("serviço de push desconhecido para este navegador")
    return endpoint


def servico_do_host(host: str) -> str | None:
    """Nome do fabricante, ou `None` se o host não está na lista."""
    if host in HOSTS:
        return HOSTS[host]
    for sufixo, nome in SUFIXOS.items():
        # `host.endswith(".notify.windows.com")` — com o ponto na frente, para
        # `evilnotify.windows.com` não passar.
        if host.endswith(sufixo) and len(host) > len(sufixo):
            return nome
    return None


def host_do_endpoint(endpoint: str) -> str:
    """Só o host, para log. O endpoint inteiro identifica o aparelho e não vai para log."""
    return (urlsplit(endpoint).hostname or "?").lower()
