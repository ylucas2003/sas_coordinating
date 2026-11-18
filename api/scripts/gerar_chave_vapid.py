"""Gera a chave VAPID do servidor — UMA vez por ambiente (docs/45 §5.1).

    cd api && ./.venv/bin/python -m scripts.gerar_chave_vapid

Escreve um arquivo 0600 com a linha `PUSH_VAPID_CHAVE_PRIVADA=…`, para colar no
`.env` do ambiente (o `infra/vps/.env` em produção, o `api/.env` em dev), e
imprime só a chave PÚBLICA e o caminho do arquivo. A privada não vai para o
stdout: terminal com histórico e log de CI guardam o que passa por ele. Mesmo
cuidado de `scripts/criar_token_mcp.py` — O_CREAT|O_EXCL com modo 0600 num
`os.open` só, sem janela em que o arquivo exista legível por outro usuário.
`SAS_SAIDA_CHAVE` troca o diretório (o padrão é o temporário do sistema).

⚠️ **Não rode de novo num ambiente que já tem chave.** Trocar a chave invalida
TODAS as inscrições: cada aparelho precisa ativar os avisos outra vez
(app/push/chaves.py). Apague o arquivo depois de copiar a linha.

Sem efeito no import (tests/test_scripts_sem_efeito_no_import.py): nada aqui lê
`.env` nem toca o disco fora de `main()`.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
from datetime import UTC, datetime

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.push.chaves import b64url


def gerar() -> tuple[str, str]:
    """(privada, pública), as duas em base64url sem `=`."""
    privada = ec.generate_private_key(ec.SECP256R1())
    escalar = privada.private_numbers().private_value.to_bytes(32, "big")
    publica = privada.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return b64url(escalar), b64url(publica)


def _abrir_exclusivo(nome: str) -> tuple[pathlib.Path, int]:
    base = pathlib.Path(os.environ.get("SAS_SAIDA_CHAVE", tempfile.gettempdir()))
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    destino = base / nome
    bandeiras = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    return destino, os.open(destino, bandeiras, 0o600)


def main() -> int:
    privada, publica = gerar()
    carimbo = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destino, descritor = _abrir_exclusivo(f"sas-vapid-{carimbo}.env")
    with os.fdopen(descritor, "w") as arquivo:
        arquivo.write(
            "# Chave VAPID do SAS (docs/45 §5.1). Cole no .env do ambiente e APAGUE este arquivo.\n"
            "# Trocar esta chave depois invalida todas as inscrições de push.\n"
            f"PUSH_VAPID_CHAVE_PRIVADA={privada}\n"
        )
    print(f"Chave privada gravada em {destino} (0600). Copie a linha para o .env e apague o arquivo.")
    print(f"Chave pública (não é segredo): {publica}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
