#!/usr/bin/env python3
"""Diagnóstico da credencial do YouTube — diz em qual porta a publicação está travada.

    ./.venv/bin/python -m scripts.verificar_youtube

Existe porque as duas travas do YouTube falham de formas que se parecem, mas
têm consertos completamente diferentes:

  PORTA 1 (OAuth)     — o refresh token expira em 7 dias enquanto a tela de
                        consentimento estiver em "Testing" + "External".
                        Sintoma: invalid_grant. Conserto: audiência "Internal"
                        (se houver Workspace) ou botão "Publish app".

  PORTA 2 (auditoria) — projeto de API criado depois de 28/07/2020 e ainda não
                        auditado tem TODO upload por videos.insert forçado a
                        "private", mesmo pedindo "unlisted". A API responde 200
                        e o vídeo fica privado. Conserto: formulário
                        "YouTube API Services - Audit and Quota Extension".
                        https://developers.google.com/youtube/v3/docs/videos/insert

Este script não altera nada: só lê e informa.
"""

from __future__ import annotations

import sys

from app.config import get_settings
from app.gravacoes_aula import publicador_youtube

# videos.insert custa 1600 unidades; a cota padrão de um projeto novo é 10.000
# por dia. Serve para dizer quantas aulas cabem por dia sem pedir aumento.
_CUSTO_UPLOAD = 1600
_COTA_PADRAO = 10_000


def _titulo(texto: str) -> None:
    print(f"\n{texto}\n{'─' * len(texto)}")


def main() -> int:
    settings = get_settings()

    _titulo("1. Credenciais no ambiente")
    faltando = [
        nome
        for nome, valor in (
            ("YOUTUBE_CLIENT_ID", settings.youtube_client_id),
            ("YOUTUBE_CLIENT_SECRET", settings.youtube_client_secret),
            ("YOUTUBE_REFRESH_TOKEN", settings.youtube_refresh_token),
        )
        if not valor
    ]
    if faltando:
        print("  ✗ faltando: " + ", ".join(faltando))
        print("    → ainda não dá para testar nada. Ver o guia de configuração.")
        return 1
    print("  ✓ as três variáveis estão preenchidas")

    _titulo("2. PORTA 1 — o refresh token ainda vale?")
    try:
        servico = publicador_youtube._servico()
        canais = servico.channels().list(part="snippet,contentDetails", mine=True).execute()
    # Diagnóstico: qualquer falha interessa, e a mensagem é o produto.
    except Exception as exc:
        texto = str(exc)
        print(f"  ✗ falhou: {type(exc).__name__}: {texto[:200]}")
        if "invalid_grant" in texto:
            print("    → invalid_grant = token expirado ou revogado.")
            print("      Causa mais provável: a tela de consentimento está em")
            print("      'Testing' + 'External', onde o token morre em 7 dias.")
            print("      Conserte a tela ANTES de gerar um token novo — token")
            print("      emitido em Testing já nasce com o prazo colado.")
        return 1

    itens = canais.get("items") or []
    if not itens:
        print("  ✗ o token é válido, mas não há canal associado a esta conta.")
        print("    → autorize com a conta que administra o canal do colégio.")
        return 1
    canal = itens[0]
    print("  ✓ token válido")
    print(f"    canal: {canal['snippet']['title']}  (id {canal['id']})")

    _titulo("3. PORTA 2 — o projeto já foi auditado?")
    print("  A API não expõe esse status diretamente; o jeito de saber é olhar")
    print("  a privacidade REAL dos vídeos que o SAS já enviou.")
    playlist = canal["contentDetails"]["relatedPlaylists"]["uploads"]
    enviados = (
        servico.playlistItems()
        .list(part="snippet", playlistId=playlist, maxResults=50)
        .execute()
    ).get("items", [])
    nossos = [
        i
        for i in enviados
        if "[sas:" in ((i.get("snippet") or {}).get("description") or "")
    ]
    if not nossos:
        print("  … nenhuma aula publicada pelo SAS ainda — nada a conferir.")
        print("    A primeira publicação vai avisar no log se voltar 'private'.")
    else:
        ids = [i["snippet"]["resourceId"]["videoId"] for i in nossos[:20]]
        detalhes = servico.videos().list(part="status,snippet", id=",".join(ids)).execute()
        privados = 0
        for v in detalhes.get("items", []):
            privacidade = (v.get("status") or {}).get("privacyStatus")
            marca = "✓" if privacidade == publicador_youtube.PRIVACIDADE_PRETENDIDA else "✗"
            if marca == "✗":
                privados += 1
            print(f"    {marca} {privacidade:9s} {v['snippet']['title'][:52]}")
        if privados:
            print(f"\n  ✗ {privados} vídeo(s) NÃO ficaram como "
                  f"'{publicador_youtube.PRIVACIDADE_PRETENDIDA}'.")
            print("    → projeto provavelmente ainda não auditado. O aluno com o")
            print("      link NÃO consegue assistir. Vídeo travado assim não tem")
            print("      apelação: precisa ser reenviado após a auditoria.")
        else:
            print("\n  ✓ todos como esperado — auditoria em ordem.")

    _titulo("4. Cota")
    print(f"  Cota padrão: {_COTA_PADRAO:,} unidades/dia".replace(",", "."))
    print(f"  Cada upload: {_CUSTO_UPLOAD:,} unidades".replace(",", "."))
    print(f"  → cabem ~{_COTA_PADRAO // _CUSTO_UPLOAD} uploads por dia sem pedir aumento.")
    print("  Para 5-15 aulas por semana, sobra folga. O consumo real aparece em")
    print("  Google Cloud Console → APIs e serviços → YouTube Data API v3 → Cotas.")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
