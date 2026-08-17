#!/usr/bin/env python3
"""Cria (ou redefine) o acesso de um aluno direto pelo banco.

O caminho normal do aluno é o "Primeiro acesso" da tela de login (matrícula +
e-mail do Canvas). Este script serve pros casos em que esse caminho não dá:
aluno sem e-mail sincronizado, conta de demonstração, suporte da coordenação.

O coordenador NÃO passa por aqui — as credenciais dele vêm das variáveis de
ambiente COORDENADOR_EMAIL / COORDENADOR_SENHA (ver api/app/config.py).

Uso (rode em api/, com .venv ativo):
    python -m scripts.criar_acesso --listar
    python -m scripts.criar_acesso --listar --busca "maria"
    python -m scripts.criar_acesso --matricula 12345 --senha "senhaSegura1"
    python -m scripts.criar_acesso --matricula 12345    # sorteia uma senha
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

SENHA_MINIMA = 8  # mesma regra do POST /auth/primeiro-acesso


def _carregar_dotenv(caminho_env: Path) -> None:
    if not caminho_env.exists():
        return
    for linha in caminho_env.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        chave = chave.strip()
        valor = valor.split("#", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(chave, valor)


def _listar(cliente, busca: str | None) -> int:
    consulta = cliente.table("aluno").select("nome, matricula, email, ativo, senha_hash")
    if busca:
        consulta = consulta.ilike("nome", f"%{busca}%")
    alunos = consulta.order("nome").limit(50).execute().data or []

    if not alunos:
        print("Nenhum aluno encontrado.")
        return 0

    print(f"{'MATRÍCULA':<14} {'SENHA':<7} {'ATIVO':<6} {'NOME':<34} E-MAIL")
    for a in alunos:
        print(
            f"{(a.get('matricula') or '—'):<14} "
            f"{('sim' if a.get('senha_hash') else 'não'):<7} "
            f"{('sim' if a.get('ativo') else 'não'):<6} "
            f"{(a.get('nome') or '')[:34]:<34} "
            f"{a.get('email') or '—'}"
        )
    print(f"\n{len(alunos)} aluno(s). Use --matricula <RA> pra definir a senha.")
    return 0


def _definir_senha(cliente, matricula: str, senha: str | None) -> int:
    from app.auth import hash_senha

    resp = (
        cliente.table("aluno")
        .select("id, nome, matricula, email, ativo")
        .eq("matricula", matricula)
        .limit(1)
        .execute()
    )
    if not resp.data:
        print(f"Matrícula {matricula!r} não existe. Rode --listar pra ver as disponíveis.")
        return 1
    aluno = resp.data[0]

    if senha is None:
        senha = secrets.token_urlsafe(9)
    elif len(senha) < SENHA_MINIMA:
        print(f"A senha precisa ter pelo menos {SENHA_MINIMA} caracteres.")
        return 1

    atualizacao = {"senha_hash": hash_senha(senha)}
    if not aluno.get("ativo"):
        # Aluno inativo não passa no login — reativa junto, senão o acesso nasce quebrado.
        atualizacao["ativo"] = True
        print("Aluno estava inativo — reativando para que o login funcione.")

    cliente.table("aluno").update(atualizacao).eq("id", aluno["id"]).execute()

    print("\nAcesso de aluno pronto:")
    print(f"  nome      {aluno['nome']}")
    print(f"  matrícula {aluno['matricula']}")
    print(f"  senha     {senha}")
    print("\nEntre pela aba 'Aluno' da tela de login usando matrícula + senha.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--listar", action="store_true", help="Lista alunos e sai.")
    parser.add_argument("--busca", help="Filtra a listagem por trecho do nome.")
    parser.add_argument("--matricula", help="Matrícula (RA) do aluno que receberá a senha.")
    parser.add_argument("--senha", help="Senha a definir. Omitido = gera uma aleatória.")
    args = parser.parse_args()

    if not args.listar and not args.matricula:
        parser.error("informe --listar ou --matricula")

    dir_api = Path(__file__).resolve().parent.parent
    _carregar_dotenv(dir_api / ".env")

    try:
        from app.supabase_client import criar_cliente_supabase
    except ImportError as exc:
        sys.exit(f"erro importando app: {exc}")

    try:
        cliente = criar_cliente_supabase()
    except RuntimeError as exc:
        sys.exit(f"erro conectando ao Supabase: {exc}")

    if args.listar:
        return _listar(cliente, args.busca)
    return _definir_senha(cliente, args.matricula.strip(), args.senha)


if __name__ == "__main__":
    raise SystemExit(main())
