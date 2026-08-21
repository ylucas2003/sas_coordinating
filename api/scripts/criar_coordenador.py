#!/usr/bin/env python3
"""Cria ou atualiza um usuário da coordenação (docs/15 §Etapa 7, item 7.1).

Substitui a credencial única de COORDENADOR_EMAIL/COORDENADOR_SENHA por uma
conta por pessoa, na tabela `usuario_coordenacao` (migration 0021).

Uso (a partir de api/):
    python -m scripts.criar_coordenador --listar
    python -m scripts.criar_coordenador --email leo@aridesa.com --nome "Leonardo"
    python -m scripts.criar_coordenador --email leo@aridesa.com --nome "Leonardo" --senha "..."
    python -m scripts.criar_coordenador --email leo@aridesa.com --desativar

Sem --senha, uma é sorteada. Ela NÃO vai para o stdout: num Job de cluster o
stdout é capturado pelo coletor de logs e retido pela política padrão. Vai para
um arquivo com chmod 600, que quem provisiona lê e apaga.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import secrets
import sys
import tempfile

from dotenv import load_dotenv

load_dotenv()

from app.auth import hash_senha          # noqa: E402
from app.supabase_client import get_supabase  # noqa: E402

SENHA_MINIMA = 12   # mais exigente que a de aluno (8): esta conta lê a base toda


def _destino_da_senha(nome_arquivo: str) -> pathlib.Path:
    """Escolhe onde gravar a senha, e prova que dá para escrever ANTES do banco.

    A imagem de produção roda como uid 10001 e não é dona de /app: gravar no
    diretório de trabalho levanta PermissionError. Se isso acontecesse DEPOIS
    do update no banco — que era o caso — uma senha sorteada ficaria gravada
    como hash e perdida para sempre, sem ninguém conseguir entrar.

    Por isso: resolve o destino, testa a escrita, e só então o chamador toca no
    banco. `SAS_SAIDA_SENHA` permite apontar para um volume montado.
    """
    base = pathlib.Path(os.environ.get("SAS_SAIDA_SENHA", tempfile.gettempdir()))
    base.mkdir(parents=True, exist_ok=True)
    destino = base / nome_arquivo
    destino.touch()          # levanta aqui, antes de qualquer escrita no banco
    destino.chmod(0o600)
    return destino


def _mascarar_email(email: str) -> str:
    local, _, dominio = (email or "").partition("@")
    return f"{local[:2]}***@{dominio}" if dominio else "—"


def _listar(cliente) -> int:
    linhas = (
        cliente.table("usuario_coordenacao")
        .select("email, nome, ativo, criado_em, ultimo_login_em")
        .order("nome")
        .execute()
        .data
        or []
    )
    if not linhas:
        print("Nenhum usuário de coordenação. O login da coordenação NÃO vai funcionar.")
        print("Crie o primeiro com --email e --nome.")
        return 0
    print(f"{'ATIVO':<6} {'NOME':<28} {'E-MAIL':<28} ÚLTIMO LOGIN")
    for u in linhas:
        print(
            f"{('sim' if u.get('ativo') else 'não'):<6} "
            f"{(u.get('nome') or '')[:28]:<28} "
            f"{_mascarar_email(u.get('email')):<28} "
            f"{(u.get('ultimo_login_em') or '—')[:19]}"
        )
    print(f"\n{len(linhas)} usuário(s).")
    return 0


def _gravar(cliente, email: str, nome: str, senha: str | None, desativar: bool) -> int:
    email = email.strip().lower()
    existente = (
        cliente.table("usuario_coordenacao")
        .select("id, nome")
        .eq("email", email)
        .limit(1)
        .execute()
        .data
    )

    if desativar:
        if not existente:
            print(f"{email} não existe.")
            return 1
        cliente.table("usuario_coordenacao").update({"ativo": False}).eq(
            "id", existente[0]["id"]
        ).execute()
        print(f"{email} desativado. Os tokens já emitidos continuam valendo até expirar (8h).")
        return 0

    if senha is None:
        senha = secrets.token_urlsafe(12)
    elif len(senha) < SENHA_MINIMA:
        print(f"A senha precisa ter pelo menos {SENHA_MINIMA} caracteres.")
        return 1

    # Destino resolvido e testado ANTES do banco (ver _destino_da_senha).
    destino = _destino_da_senha(f"senha-coord-{email.split('@')[0]}.txt")

    dados = {"email": email, "nome": nome, "senha_hash": hash_senha(senha), "ativo": True}
    if existente:
        cliente.table("usuario_coordenacao").update(dados).eq("id", existente[0]["id"]).execute()
        acao = "atualizado"
    else:
        cliente.table("usuario_coordenacao").insert(dados).execute()
        acao = "criado"

    destino.write_text(f"{email}\t{senha}\n", encoding="utf-8")
    print(f"Usuário {acao}: {nome} <{email}>")
    print(f"Senha gravada em {destino} (chmod 600).")
    print("Entregue pelo canal do colégio e APAGUE o arquivo.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Usuários da coordenação do SAS.")
    p.add_argument("--listar", action="store_true")
    p.add_argument("--email")
    p.add_argument("--nome")
    p.add_argument("--senha")
    p.add_argument("--desativar", action="store_true")
    args = p.parse_args()

    cliente = get_supabase()
    if args.listar:
        return _listar(cliente)
    if not args.email:
        p.error("informe --listar ou --email")
    if not args.nome and not args.desativar:
        p.error("--nome é obrigatório ao criar ou atualizar")
    return _gravar(cliente, args.email, args.nome or "", args.senha, args.desativar)


if __name__ == "__main__":
    sys.exit(main())
