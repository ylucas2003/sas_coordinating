#!/usr/bin/env python3
"""Emite, lista e revoga o token do MCP da coordenação pela linha de comando.

A porta de todo dia é a tela (Administração → Conexões de IA, rotas de
`app/routes/mcp_tokens.py`). Este script é a de operação: o primeiro token do
ambiente de dev, ou o de alguém quando a tela não está à mão (docs/43 §5.3).

Uso (a partir de api/):
    python -m scripts.criar_token_mcp --email coordenacao@exemplo.com.br --nome "Claude Code da coordenação"
    python -m scripts.criar_token_mcp --listar
    python -m scripts.criar_token_mcp --listar --email coordenacao@exemplo.com.br
    python -m scripts.criar_token_mcp --revogar <id>

O token NÃO vai para o stdout: num Job de cluster o stdout é capturado pelo
coletor de logs e retido pela política padrão. Vai para um arquivo que já nasce
com 0600 (O_EXCL, sem janela entre criar e fechar), que quem provisiona entrega
e APAGA — o cuidado de `scripts/criar_coordenador.py`, sem a janela dele.
`SAS_SAIDA_TOKEN` aponta para outro diretório.

Emite para conta de administrador ou de coordenador, como a tela — o padrão
desde 26/10 (decisão do dono). Com MCP_EMISSAO_SO_ADMINISTRADOR=true, que é
opção, só para administrador: a mesma regra da tela, e o MCP recusaria o resto.
A regra é lida do ambiente de QUEM RODA o script, como na API e no MCP — os
três precisam do mesmo valor (app/mcp/configuracao.py).

Roda com a credencial da API (o PostgREST da API, `sas_service`), não com a do
MCP: o `sas_mcp` não lê nem escreve `token_mcp` (0072).
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
import tempfile
import uuid
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

from app.auditoria import registrar as auditar  # noqa: E402
from app.mcp import tokens  # noqa: E402
from app.mcp.auditoria_mcp import (  # noqa: E402
    ACAO_CONEXAO_EMITIDA,
    ACAO_CONEXAO_REVOGADA,
    CANAL,
    recurso_do_token,
)
from app.mcp.configuracao import get_configuracao_mcp  # noqa: E402
from app.supabase_client import get_supabase  # noqa: E402

NOME_MAXIMO = 80  # o CHECK `token_mcp_nome_valido` da 0072


def _abrir_destino_do_token(nome_arquivo: str) -> tuple[pathlib.Path, int]:
    """Cria o arquivo do token, JÁ fechado, antes de tocar no banco.

    Antes do banco porque, se a escrita falhasse DEPOIS do insert, o token
    ficaria valendo e perdido para sempre — só o hash está lá. Por isso o
    arquivo nasce aqui e o descritor fica aberto até o token chegar.

    Num `os.open` só, com O_CREAT|O_EXCL e modo 0600, e não `touch()` seguido
    de `chmod`: entre os dois o arquivo existia com 0644, e no /tmp
    compartilhado (o padrão sem SAS_SAIDA_TOKEN) outro usuário abria nessa
    janela — e o descritor dele continuava valendo depois do chmod, para ler o
    token quando ele fosse escrito (revisão de 24/10). O O_EXCL também recusa
    arquivo ou symlink já plantado com o mesmo nome.
    """
    base = pathlib.Path(os.environ.get("SAS_SAIDA_TOKEN", tempfile.gettempdir()))
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    destino = base / nome_arquivo
    bandeiras = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    return destino, os.open(destino, bandeiras, 0o600)


def _conta(cliente, email: str) -> dict | None:
    linhas = (
        cliente.table("usuario_coordenacao")
        .select("id, nome, ativo, papel")
        .eq("email", email.strip().lower())
        .limit(1)
        .execute()
        .data
    )
    return linhas[0] if linhas else None


def _emitir(cliente, email: str, nome: str) -> int:
    nome = nome.strip()
    if not nome or len(nome) > NOME_MAXIMO:
        print(f"--nome tem de ter de 1 a {NOME_MAXIMO} caracteres.")
        return 1
    conta = _conta(cliente, email)
    if conta is None or not conta.get("ativo"):
        # A RPC do MCP recusaria o token de conta desativada de qualquer jeito.
        print(f"{email} não existe ou está desativado.")
        return 1
    config = get_configuracao_mcp()
    if config.emissao_so_administrador and conta.get("papel") != "administrador":
        # A mesma regra da tela (routes/mcp_tokens.py) — e o MCP recusaria as
        # chamadas desse token de qualquer jeito (`servidor._pode_consultar`).
        print(
            f"{email} não é administrador, e MCP_EMISSAO_SO_ADMINISTRADOR está ligado: "
            "neste ambiente só o administrador conecta uma IA ao SAS (docs/43 §5.4)."
        )
        return 1

    try:
        destino, descritor = _abrir_destino_do_token(
            f"token-mcp-{email.split('@')[0]}-{uuid.uuid4().hex[:6]}.txt"
        )
    except OSError as erro:
        print(f"Não consegui criar o arquivo do token ({erro.strerror}). Nada foi gravado no banco.")
        return 1
    try:
        token, hash_acesso, prefixo = tokens.gerar()
        criado_em = datetime.now(UTC)
        dias = config.validade_do_token_dias
        expira_em = criado_em + timedelta(days=dias) if dias else None
        linha = (
            cliente.table("token_mcp")
            .insert(
                {
                    "usuario_coordenacao_id": conta["id"],
                    "nome": nome,
                    "origem": "pessoal",
                    "hash_acesso": hash_acesso,
                    "prefixo": prefixo,
                    "criado_em": criado_em.isoformat(),
                    "expira_em": expira_em.isoformat() if expira_em else None,
                },
                returning="representation",
            )
            .execute()
        ).data[0]
    except BaseException:
        # Sem linha no banco, o arquivo vazio não serve para nada.
        os.close(descritor)
        destino.unlink(missing_ok=True)
        raise
    with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
        arquivo.write(f"{token}\n")
    auditar(
        cliente, ACAO_CONEXAO_EMITIDA, canal=CANAL, ator_tipo="script",
        recurso=recurso_do_token(str(linha["id"])), detalhe={"nome": nome},
    )

    print(f"Conexão criada para {conta.get('nome')} <{email}>: {nome} ({prefixo}…)")
    print(f"id: {linha['id']}" + (f" · expira em {expira_em:%d/%m/%Y}" if expira_em else " · não expira"))
    print(f"Token gravado em {destino} (chmod 600).")
    print("Entregue pelo canal do colégio e APAGUE o arquivo.")
    return 0


def _listar(cliente, email: str | None) -> int:
    consulta = (
        cliente.table("token_mcp")
        .select("id, usuario_coordenacao_id, nome, origem, prefixo, criado_em, expira_em, ultimo_uso_em, revogado_em")
        .order("criado_em", desc=True)
    )
    if email:
        conta = _conta(cliente, email)
        if conta is None:
            print(f"{email} não existe.")
            return 1
        consulta = consulta.eq("usuario_coordenacao_id", conta["id"])
    linhas = consulta.execute().data or []
    if not linhas:
        print("Nenhuma conexão de IA.")
        return 0
    print(f"{'ID':<36}  {'PREFIXO':<13} {'SITUAÇÃO':<10} {'ÚLTIMO USO':<19} NOME")
    for t in linhas:
        situacao = "revogada" if t.get("revogado_em") else "ativa"
        print(
            f"{t['id']:<36}  {t.get('prefixo') or '':<13} {situacao:<10} "
            f"{(t.get('ultimo_uso_em') or '—')[:19]:<19} {t.get('nome') or ''}"
        )
    print(f"\n{len(linhas)} conexão(ões).")
    return 0


def _revogar(cliente, conexao_id: str) -> int:
    try:
        conexao_id = str(uuid.UUID(conexao_id))
    except ValueError:
        print("--revogar espera o id (uuid) que o --listar mostra.")
        return 1
    revogadas = (
        cliente.table("token_mcp")
        .update({"revogado_em": datetime.now(UTC).isoformat()}, returning="representation")
        .eq("id", conexao_id)
        .is_("revogado_em", "null")
        .execute()
        .data
        or []
    )
    if not revogadas:
        print("Conexão não encontrada, ou já revogada.")
        return 1
    # Sem `revogado_por`: quem roda o script não é uma conta do SAS. A 0072
    # aceita revogação sem autor ("revogação automática").
    auditar(
        cliente, ACAO_CONEXAO_REVOGADA, canal=CANAL, ator_tipo="script",
        recurso=recurso_do_token(conexao_id), detalhe={"nome": revogadas[0].get("nome")},
    )
    print(f"Revogada: {revogadas[0].get('nome')}. A próxima chamada do MCP com ela já é recusada.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Conexões de IA (token do MCP da coordenação).")
    p.add_argument("--email", help="a conta da coordenação dona da conexão")
    p.add_argument("--nome", help='o nome da conexão, ex.: "Claude Code do Leo"')
    p.add_argument("--listar", action="store_true")
    p.add_argument("--revogar", metavar="ID")
    args = p.parse_args()

    cliente = get_supabase()
    if args.listar:
        return _listar(cliente, args.email)
    if args.revogar:
        return _revogar(cliente, args.revogar)
    if not args.email or not args.nome:
        p.error("para emitir, informe --email e --nome (ou use --listar / --revogar)")
    return _emitir(cliente, args.email, args.nome)


if __name__ == "__main__":
    sys.exit(main())
