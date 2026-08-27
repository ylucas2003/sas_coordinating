#!/usr/bin/env python3
"""Obtém o refresh token do YouTube — roda UMA vez, na máquina de quem administra o canal.

    ./.venv/bin/python -m scripts.obter_refresh_token_youtube <client_id> <client_secret>

Abre o consentimento do Google no navegador, recebe o retorno num servidor
local efêmero e imprime o refresh token para colar no .env.

Usa só a stdlib + httpx (já é dependência do projeto): o fluxo OAuth é
simples o bastante para não valer uma biblioteca a mais numa tarefa que roda
uma vez por ano.

ANTES DE RODAR, confira na tela de consentimento (Google Auth Platform):
  · audiência "Internal" (se o colégio tem Workspace), OU
  · botão "Publish app" já clicado (status "In production")
Token gerado com a tela em "Testing" + "External" EXPIRA EM 7 DIAS e a
automação quebra na semana seguinte. Arrume a tela primeiro, gere depois.

O client_id/secret devem ser de uma credencial OAuth do tipo "Desktop app" —
é ela que aceita o redirecionamento para localhost usado aqui.
"""

from __future__ import annotations

import http.server
import secrets
import sys
import time
import urllib.parse
import webbrowser

import httpx

from app.config import get_settings
from app.gravacoes_aula.publicador_youtube import ESCOPOS

# Fonte única com o publicador: o token PRECISA nascer com os mesmos escopos
# que o backend vai usar. Duplicar a lista aqui já causou o bug de gerar token
# só com `youtube.upload`, que faz a checagem antiduplicata falhar com 403 —
# e o único conserto seria refazer o consentimento.
_ESCOPO = " ".join(ESCOPOS)
_AUTORIZACAO = "https://accounts.google.com/o/oauth2/v2/auth"
_TROCA = "https://oauth2.googleapis.com/token"  # endpoint público, não é segredo
_PORTA = 8765

# Quanto esperar o usuário consentir no navegador antes de desistir.
_ESPERA_MAXIMA = 300


class _Captura(http.server.BaseHTTPRequestHandler):
    """Recebe o redirecionamento do Google e guarda o `code` da URL."""

    codigo: str | None = None
    estado_recebido: str | None = None
    erro: str | None = None

    # O nome em maiúsculas é exigido pelo BaseHTTPRequestHandler.
    def do_GET(self) -> None:
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _Captura.codigo = (params.get("code") or [None])[0]
        _Captura.estado_recebido = (params.get("state") or [None])[0]
        erro = (params.get("error") or [None])[0]
        if erro:
            _Captura.erro = erro

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if erro:
            corpo = f"<h1>Autorizacao recusada</h1><p>{erro}</p>"
        elif _Captura.codigo:
            corpo = "<h1>Pronto</h1><p>Pode fechar esta aba e voltar ao terminal.</p>"
        else:
            corpo = "<h1>Nada recebido</h1><p>Tente de novo.</p>"
        self.wfile.write(corpo.encode("utf-8"))

    def log_message(self, *_args: object) -> None:
        pass  # o servidor é detalhe interno; o terminal é do usuário


def main() -> int:
    # Sem argumento, lê do .env — evita ter as credenciais no histórico do
    # shell, que é onde elas menos deveriam ficar. Passar na linha de comando
    # continua valendo para o primeiro uso, antes de o .env existir.
    if len(sys.argv) == 3:
        client_id, client_secret = sys.argv[1], sys.argv[2]
    elif len(sys.argv) == 1:
        settings = get_settings()
        client_id = settings.youtube_client_id
        client_secret = settings.youtube_client_secret
        if not client_id or not client_secret:
            print(
                "YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET não estão no .env.\n"
                "Preencha-os, ou passe os dois na linha de comando:\n"
                "  python -m scripts.obter_refresh_token_youtube <client_id> <client_secret>"
            )
            return 1
        print(f"Usando as credenciais do .env (client {client_id[:18]}…)")
    else:
        print(__doc__)
        return 1
    redirect_uri = f"http://localhost:{_PORTA}"
    estado = secrets.token_urlsafe(24)  # protege contra resposta forjada

    url = f"{_AUTORIZACAO}?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _ESCOPO,
            # offline + consent = é isto que faz o Google devolver refresh
            # token. Sem `prompt=consent`, uma conta que já autorizou antes
            # recebe só access token e o script não teria o que imprimir.
            "access_type": "offline",
            "prompt": "consent",
            "state": estado,
        }
    )

    servidor = http.server.HTTPServer(("localhost", _PORTA), _Captura)
    # Faz handle_request() devolver o controle de tempos em tempos, para o
    # laço abaixo poder reavaliar o prazo em vez de bloquear para sempre.
    servidor.timeout = 1

    print("\nAbrindo o navegador para autorizar…")
    print("Entre com a conta que ADMINISTRA o canal do colégio.\n")
    print(f"Se não abrir sozinho, acesse:\n{url}\n")
    webbrowser.open(url)

    # Atende ATÉ chegar o `code`. São duas armadilhas em uma: fechar o socket
    # logo após abrir o navegador derruba a resposta do Google
    # (ERR_CONNECTION_REFUSED), e atender uma requisição só não basta porque o
    # navegador costuma pedir /favicon.ico antes — essa consumiria a vaga.
    print(f"Aguardando o retorno do Google (até {_ESPERA_MAXIMA // 60} min)…")
    prazo = time.monotonic() + _ESPERA_MAXIMA
    while (
        _Captura.codigo is None
        and _Captura.erro is None
        and time.monotonic() < prazo
    ):
        servidor.handle_request()
    servidor.server_close()

    if _Captura.erro:
        print(f"✗ o Google recusou a autorização: {_Captura.erro}")
        return 1
    if not _Captura.codigo:
        print("✗ nenhum código recebido — autorização cancelada ou expirada.")
        return 1
    if _Captura.estado_recebido != estado:
        print("✗ `state` não confere — resposta não veio deste pedido. Abortado.")
        return 1

    resposta = httpx.post(
        _TROCA,
        data={
            "code": _Captura.codigo,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    if resposta.status_code != 200:
        print(f"✗ troca do código falhou ({resposta.status_code}): {resposta.text[:300]}")
        return 1

    dados = resposta.json()
    refresh = dados.get("refresh_token")
    if not refresh:
        print("✗ o Google não devolveu refresh_token.")
        print("  Costuma acontecer quando a conta já autorizou este app antes.")
        print("  Remova o acesso em https://myaccount.google.com/permissions e repita.")
        return 1

    print("\n" + "─" * 64)
    print("Cole no api/.env (e no infra/vps/.env do servidor):\n")
    print(f"YOUTUBE_CLIENT_ID={client_id}")
    print(f"YOUTUBE_CLIENT_SECRET={client_secret}")
    print(f"YOUTUBE_REFRESH_TOKEN={refresh}")
    print("─" * 64)
    print("\nDepois confira com:  python -m scripts.verificar_youtube")
    print("Trate estas três linhas como senha: quem as tem publica no canal.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
