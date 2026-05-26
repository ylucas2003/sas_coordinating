#!/usr/bin/env python3
"""Migration runner — aplica .sql contra o Postgres do Supabase.

Convenções:
  - Migrations vivem em `api/migrations/NNNN_descricao.sql` (UP).
  - Pareadas com `api/migrations/NNNN_descricao.down.sql` (DOWN).
  - O prefixo numérico de 4 dígitos define a ordem cronológica.
  - Estado é rastreado em `_migracoes_aplicadas` (criada na primeira execução).

Comandos:
  python -m scripts.migrate up          → aplica todas pendentes
  python -m scripts.migrate up --to NNNN → aplica até a versão NNNN
  python -m scripts.migrate down        → reverte a última aplicada
  python -m scripts.migrate down --to NNNN → reverte até a versão NNNN (inclusiva ou não — ver --inclusive)
  python -m scripts.migrate status      → lista o que foi aplicado e o que está pendente

Conexão: usa SUPABASE_DB_URL do .env (ver api/.env.example).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import psycopg
except ImportError as exc:
    sys.exit(
        "psycopg não instalado. Rode: ./.venv/bin/pip install -r requirements.txt"
        f"\n(detalhe: {exc})"
    )


# ─── Setup ────────────────────────────────────────────────────────────────


def _carregar_dotenv(caminho_env: Path) -> None:
    """Carrega .env minimalista (KEY=VALUE por linha). Evita dep extra."""
    if not caminho_env.exists():
        return
    for linha in caminho_env.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        chave = chave.strip()
        # Aceita "VALOR  # comentário" no final
        valor = valor.split("#", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(chave, valor)


# Diretório raiz do api/ (3 níveis: scripts → api)
DIR_API = Path(__file__).resolve().parent.parent
DIR_MIGRATIONS = DIR_API / "migrations"
PADRAO_MIGRACAO = re.compile(r"^(?P<versao>\d{4})_(?P<slug>[a-z0-9_]+)\.sql$")


@dataclass(frozen=True)
class Migracao:
    versao: str          # "0001"
    slug: str            # "schema_inicial"
    caminho_up: Path
    caminho_down: Path | None  # pode não existir (avisa)

    @property
    def nome(self) -> str:
        return f"{self.versao}_{self.slug}"


def listar_migracoes() -> list[Migracao]:
    if not DIR_MIGRATIONS.exists():
        sys.exit(f"diretório de migrations não encontrado: {DIR_MIGRATIONS}")
    migs: list[Migracao] = []
    for arquivo in sorted(DIR_MIGRATIONS.iterdir()):
        if not arquivo.is_file() or arquivo.name.endswith(".down.sql"):
            continue
        m = PADRAO_MIGRACAO.match(arquivo.name)
        if not m:
            continue
        versao = m.group("versao")
        slug = m.group("slug")
        caminho_down = DIR_MIGRATIONS / f"{versao}_{slug}.down.sql"
        migs.append(
            Migracao(
                versao=versao,
                slug=slug,
                caminho_up=arquivo,
                caminho_down=caminho_down if caminho_down.exists() else None,
            )
        )
    return migs


# ─── Conexão ──────────────────────────────────────────────────────────────


def _normalizar_url(url: str) -> str:
    """URL-encoda usuário/senha da connection string.

    O libpq (usado pelo psycopg) é mais estrito que o `urllib.parse`: caracteres
    como `@`, `:`, `/`, `#`, `?` na senha precisam vir percent-encoded, senão
    o parser confunde o `@` da senha com o separador antes do host.

    Aceita o copia-e-cola cru do Supabase (que vem com a senha em claro) e
    devolve uma URL segura pro libpq.
    """
    from urllib.parse import quote, urlparse, urlunparse

    p = urlparse(url)
    if not p.username or not p.password:
        return url   # nada a reencodar
    user_enc = quote(p.username, safe="")
    pwd_enc = quote(p.password, safe="")
    porta = f":{p.port}" if p.port else ""
    netloc = f"{user_enc}:{pwd_enc}@{p.hostname}{porta}"
    return urlunparse((p.scheme, netloc, p.path, p.params, p.query, p.fragment))


def conectar() -> psycopg.Connection:
    url = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not url or "<" in url:
        sys.exit(
            "SUPABASE_DB_URL não configurada no .env. Veja api/.env.example pra "
            "saber onde pegar a connection string do Postgres no dashboard do "
            "Supabase."
        )
    url = _normalizar_url(url)
    try:
        # autocommit=False — cada migration roda em sua própria transação.
        return psycopg.connect(url, autocommit=False)
    except psycopg.OperationalError as exc:
        sys.exit(f"falha ao conectar no Postgres: {exc}")


def garantir_tabela_estado(conn: psycopg.Connection) -> None:
    """Cria a tabela de rastreamento de migrations se não existir."""
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS _migracoes_aplicadas (
                versao        text PRIMARY KEY,
                slug          text NOT NULL,
                aplicada_em   timestamptz NOT NULL DEFAULT now()
            );
            """
        )
        conn.commit()


def versoes_aplicadas(conn: psycopg.Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT versao FROM _migracoes_aplicadas;")
        return {linha[0] for linha in cur.fetchall()}


# ─── Comandos ─────────────────────────────────────────────────────────────


def cmd_status(conn: psycopg.Connection) -> None:
    aplicadas = versoes_aplicadas(conn)
    migs = listar_migracoes()
    print(f"Migrations · {len(migs)} no disco · {len(aplicadas)} aplicadas\n")
    for m in migs:
        if m.versao in aplicadas:
            sinal = "✓ aplicada"
        else:
            sinal = "  pendente"
        sufixo_down = "" if m.caminho_down else "  (sem .down.sql)"
        print(f"  {sinal}  {m.nome}{sufixo_down}")
    pendentes = [m.versao for m in migs if m.versao not in aplicadas]
    if pendentes:
        print(f"\n→ {len(pendentes)} migration(s) pendente(s): {', '.join(pendentes)}")
    else:
        print("\n→ tudo em dia.")


def aplicar_uma(conn: psycopg.Connection, migracao: Migracao) -> None:
    sql = migracao.caminho_up.read_text(encoding="utf-8")
    print(f"→ aplicando {migracao.nome} …", end=" ", flush=True)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO _migracoes_aplicadas (versao, slug) VALUES (%s, %s);",
                (migracao.versao, migracao.slug),
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print("FALHOU")
        sys.exit(f"erro ao aplicar {migracao.nome}: {exc}")
    print("ok")


def reverter_uma(conn: psycopg.Connection, migracao: Migracao) -> None:
    if not migracao.caminho_down:
        sys.exit(
            f"{migracao.nome} não tem .down.sql — downgrade não suportado. "
            f"Crie {migracao.versao}_{migracao.slug}.down.sql antes."
        )
    sql = migracao.caminho_down.read_text(encoding="utf-8")
    print(f"← revertendo {migracao.nome} …", end=" ", flush=True)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "DELETE FROM _migracoes_aplicadas WHERE versao = %s;",
                (migracao.versao,),
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print("FALHOU")
        sys.exit(f"erro ao reverter {migracao.nome}: {exc}")
    print("ok")


def cmd_up(conn: psycopg.Connection, ate: str | None) -> None:
    aplicadas = versoes_aplicadas(conn)
    migs = listar_migracoes()
    pendentes = [m for m in migs if m.versao not in aplicadas]
    if ate is not None:
        pendentes = [m for m in pendentes if m.versao <= ate]
    if not pendentes:
        print("nada a aplicar — banco já está na versão alvo.")
        return
    print(f"vou aplicar {len(pendentes)} migration(s):")
    for m in pendentes:
        print(f"  · {m.nome}")
    print()
    for m in pendentes:
        aplicar_uma(conn, m)


def cmd_wipe_dados(conn: psycopg.Connection) -> None:
    """Esvazia todos os dados importados via planilha. Mantém o schema e os
    seeds (matérias). Reusa `scripts/limpar_dados_importados.sql`."""
    caminho = DIR_API / "scripts" / "limpar_dados_importados.sql"
    if not caminho.exists():
        sys.exit(f"script não encontrado: {caminho}")
    sql = caminho.read_text(encoding="utf-8")
    print(f"→ esvaziando dados importados …", end=" ", flush=True)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print("FALHOU")
        sys.exit(f"erro ao limpar dados: {exc}")
    print("ok")


def cmd_bootstrap(conn: psycopg.Connection) -> None:
    """Marca como aplicadas as migrations cujos efeitos já existem no banco.

    Útil quando migrations antigas foram rodadas via dashboard antes do runner
    existir. Cada migration declara abaixo uma query de detecção; se a query
    devolve true, marcamos como aplicada (sem rodar o SQL).
    """
    DETECTORES = {
        "0001": "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='sede')",
        "0002": "SELECT EXISTS (SELECT 1 FROM information_schema.views WHERE table_name='v_nota_dimensoes')",
        "0003": "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='simulado' AND column_name='tipo')",
        "0004": "SELECT EXISTS (SELECT 1 FROM information_schema.table_constraints WHERE constraint_name='metrica_simulado_chave_natural')",
    }
    aplicadas = versoes_aplicadas(conn)
    migs_por_versao = {m.versao: m for m in listar_migracoes()}

    registradas = []
    with conn.cursor() as cur:
        for versao, query in DETECTORES.items():
            if versao in aplicadas:
                continue
            mig = migs_por_versao.get(versao)
            if not mig:
                continue
            cur.execute(query)
            if cur.fetchone()[0]:
                cur.execute(
                    "INSERT INTO _migracoes_aplicadas (versao, slug) VALUES (%s, %s);",
                    (versao, mig.slug),
                )
                registradas.append(mig.nome)
    conn.commit()

    if registradas:
        print(f"✓ marcadas como já-aplicadas (detectadas no schema):")
        for nome in registradas:
            print(f"  · {nome}")
    else:
        print("nada a registrar — todas as migrations detectáveis já estão no estado correto.")


def cmd_down(conn: psycopg.Connection, ate: str | None) -> None:
    aplicadas = versoes_aplicadas(conn)
    migs = listar_migracoes()
    # Aplicadas em ordem cronológica reversa.
    candidatas = [m for m in reversed(migs) if m.versao in aplicadas]
    if ate is None:
        # Reverte só a última.
        candidatas = candidatas[:1]
    else:
        # Reverte todas com versao > ate.
        candidatas = [m for m in candidatas if m.versao > ate]
    if not candidatas:
        print("nada a reverter.")
        return
    print(f"vou reverter {len(candidatas)} migration(s):")
    for m in candidatas:
        print(f"  · {m.nome}")
    print()
    for m in candidatas:
        reverter_uma(conn, m)


# ─── Entry point ──────────────────────────────────────────────────────────


def main() -> None:
    _carregar_dotenv(DIR_API / ".env")

    parser = argparse.ArgumentParser(description="Migration runner do SAS.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="lista o que foi aplicado e o que está pendente")
    sub.add_parser(
        "bootstrap",
        help="detecta migrations já aplicadas via dashboard e marca no _migracoes_aplicadas",
    )
    sub.add_parser(
        "wipe-dados",
        help="TRUNCATE em todas as tabelas de dados importados (mantém schema e seeds)",
    )

    p_up = sub.add_parser("up", help="aplica migrations pendentes")
    p_up.add_argument("--to", dest="ate", help="aplica até essa versão (inclusivo)")

    p_down = sub.add_parser("down", help="reverte a última migration aplicada (ou até --to)")
    p_down.add_argument("--to", dest="ate", help="reverte tudo acima dessa versão (exclusivo)")

    args = parser.parse_args()

    with conectar() as conn:
        garantir_tabela_estado(conn)
        if args.cmd == "status":
            cmd_status(conn)
        elif args.cmd == "bootstrap":
            cmd_bootstrap(conn)
        elif args.cmd == "wipe-dados":
            cmd_wipe_dados(conn)
        elif args.cmd == "up":
            cmd_up(conn, args.ate)
        elif args.cmd == "down":
            cmd_down(conn, args.ate)


if __name__ == "__main__":
    main()
