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
import os
import pathlib
import secrets
import tempfile
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


def _mascarar_email(email: str | None) -> str:
    """`joao.silva@aridesa.com` → `jo***@aridesa.com`.

    A listagem é útil para achar o aluno certo; o e-mail inteiro não é
    necessário para isso e é dado pessoal de menor indo para o stdout.
    """
    if not email or "@" not in email:
        return "—"
    local, _, dominio = email.partition("@")
    return f"{local[:2]}***@{dominio}"


def _listar(cliente, busca: str | None) -> int:
    # `senha_hash` vem só para virar o booleano da coluna SENHA; nunca é
    # impresso. O PostgREST não expressa "is not null" no select, então não dá
    # para evitar trazê-lo — o que importa é que ele não chegue ao stdout, que
    # num Job de cluster é capturado pelo coletor de logs e retido pela
    # política padrão (docs/14 §5, ops).
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
            f"{_mascarar_email(a.get('email'))}"
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

    # Destino resolvido e testado ANTES do banco (ver _destino_da_senha).
    destino = _destino_da_senha(f"senha-{aluno['matricula']}.txt")

    atualizacao = {"senha_hash": hash_senha(senha)}
    if not aluno.get("ativo"):
        # Aluno inativo não passa no login — reativa junto, senão o acesso nasce quebrado.
        atualizacao["ativo"] = True
        print("Aluno estava inativo — reativando para que o login funcione.")

    cliente.table("aluno").update(atualizacao).eq("id", aluno["id"]).execute()

    print("\nAcesso de aluno pronto:")
    print(f"  nome      {aluno['nome']}")
    print(f"  matrícula {aluno['matricula']}")

    # A senha NÃO vai para o stdout. Num Job de cluster isso vira log retido, e
    # a senha de um aluno menor de idade passa a existir num agregador que não
    # foi dimensionado para dado sensível (docs/14 §5, ops). Vai para um arquivo
    # com permissão restrita, que quem provisiona lê e apaga.
    destino.write_text(f"{aluno['matricula']}\t{senha}\n", encoding="utf-8")
    print(f"  senha     gravada em {destino} (chmod 600)")
    print("\nEntregue a senha pelo canal do colégio e APAGUE o arquivo.")
    print("Entre pela aba 'Aluno' da tela de login usando matrícula + senha.")
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
