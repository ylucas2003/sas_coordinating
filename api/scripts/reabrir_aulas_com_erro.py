#!/usr/bin/env python3
"""Devolve à fila as aulas que o pipeline de vídeo largou por falha do S3.

Dentro do container da API, no VPS:

    docker compose exec -T api python -m scripts.reabrir_aulas_com_erro              # ENSAIO
    docker compose exec -T api python -m scripts.reabrir_aulas_com_erro --aplicar
    docker compose exec -T api python -m scripts.reabrir_aulas_com_erro --aplicar --disparar
    docker compose exec -T api python -m scripts.reabrir_aulas_com_erro --todas      # qualquer erro

Da máquina de desenvolvimento, `./infra/vps/reabrir-aulas.sh` com as mesmas
opções faz o ssh por você e manda este arquivo por stdin, então não depende
de deploy.

Por que existe: o S3 falha DEPOIS de baixar e compor o vídeo. A aula vai para
'erro' com `tentativas + 1` e, com 3 (`rotas._MAX_TENTATIVAS`), sai do pool
para sempre. Uma queda do S3 de mais de umas três rodadas esgota as tentativas
de quem estava na fila, e nada as traz de volta sozinho.

O que este script NÃO faz, de propósito:

  - Não processa vídeo. A trava que impede duas rodadas ao mesmo tempo é um
    `threading.Lock` do processo da API. Um segundo processo publicando poderia
    subir a mesma aula duas vezes no canal, e é vídeo de menor de idade (LGPD
    art. 18, VI). Quem processa é a API: `--disparar` só pede uma rodada a ela,
    e a trava dela decide.
  - Só toca em 'erro'. 'publicado', 'publicado_sem_confirmacao' e
    'publicando' podem já ter vídeo no canal.
  - Não reabre aula cuja gravação já saiu do Canvas (~7 dias de retenção do
    BigBlueButton): ela só queimaria três rodadas de 45-90 min falhando no
    download.

Antes de reabrir, confere que o S3 voltou com um PUT de poucos bytes, que é a
mesma operação que falhou. Se ainda está fora, para sem tocar em nada:
reabrir agora só esgotaria as tentativas de novo.

Depois de reabertas, o cron de hora em hora (aos 25) processa UMA por rodada,
da mais antiga para a mais nova, que é também a ordem de quem sai do Canvas
primeiro.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from app.canvas_sync.cliente import ClienteCanvas
from app.config import get_settings
from app.gravacoes_aula import armazenamento_s3
from app.supabase_client import criar_cliente_supabase

# Retenção do BigBlueButton, medida (ver o docstring de gravacoes_aula/rotas.py).
_DIAS_RETENCAO_CANVAS = 7

# O que aparece em `erro_detalhe` quando quem falhou foi o S3. `_descrever`
# grava "Classe: mensagem", e o boto3 não tem uma classe só: com o bucket
# recusando, vem `S3UploadFailedError` ("... when calling the PutObject
# operation: All access to this object has been disabled"); com a rede caída,
# `EndpointConnectionError` com a URL do bucket. O nome do bucket entra na
# lista em tempo de execução.
_MARCAS_DE_S3 = (
    "s3uploadfailederror",
    "s3naoconfigurado",
    "amazonaws.com",
    "putobject",
    "multipartupload",
    "uploadpart",
    "allaccessdisabled",
    "nocredentialserror",
)

_CHAVE_CONFERENCIA = "aulas/_conferencia-de-acesso.txt"


@dataclass
class Triagem:
    reabrir: list[dict[str, Any]] = field(default_factory=list)
    gravacao_expirada: list[dict[str, Any]] = field(default_factory=list)
    #: O Canvas não respondeu para o curso: sem saber se a gravação existe, não
    #: reabre. Rodar de novo resolve.
    nao_conferidas: list[dict[str, Any]] = field(default_factory=list)
    #: Em 'erro' por outro motivo que não o S3; só entram com --todas.
    outro_erro: list[dict[str, Any]] = field(default_factory=list)


def parece_falha_de_s3(erro_detalhe: str | None, bucket: str | None) -> bool:
    texto = (erro_detalhe or "").casefold()
    marcas = (*_MARCAS_DE_S3, bucket.casefold()) if bucket else _MARCAS_DE_S3
    return any(m in texto for m in marcas)


def triar(
    aulas: list[dict[str, Any]],
    gravacoes: dict[str, set[str] | None],
    *,
    bucket: str | None,
    todas: bool,
) -> Triagem:
    """Pura: decide o destino de cada aula em 'erro'.

    `gravacoes[curso_id]` é o conjunto de conferências que AINDA têm gravação
    no Canvas, ou None quando o Canvas não respondeu para aquele curso."""
    t = Triagem()
    for aula in aulas:
        if not todas and not parece_falha_de_s3(aula.get("erro_detalhe"), bucket):
            t.outro_erro.append(aula)
            continue
        com_gravacao = gravacoes.get(aula["curso_id"])
        if com_gravacao is None:
            t.nao_conferidas.append(aula)
        elif str(aula["conferencia_id"]) in com_gravacao:
            t.reabrir.append(aula)
        else:
            t.gravacao_expirada.append(aula)
    return t


def _s3_respondendo() -> str | None:
    """None se o PUT passou; senão, o motivo. O objeto é sobrescrito a cada
    execução, então fica um só no bucket."""
    try:
        armazenamento_s3._cliente().put_object(
            Bucket=get_settings().s3_bucket_gravacoes,
            Key=_CHAVE_CONFERENCIA,
            Body=f"conferido em {datetime.now(UTC).isoformat()}\n".encode(),
            ContentType="text/plain",
        )
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


def _gravacoes_no_canvas(curso_ids: set[str]) -> dict[str, set[str] | None]:
    settings = get_settings()

    async def _ler() -> dict[str, set[str] | None]:
        resultado: dict[str, set[str] | None] = {}
        async with ClienteCanvas(
            base_url=settings.canvas_base_url, token=settings.canvas_api_token
        ) as canvas:
            for curso_id in sorted(curso_ids):
                try:
                    confs = await canvas.listar_conferencias(curso_id)
                # Um curso que falha não esconde os outros.
                except Exception as exc:
                    print(f"  ! Canvas não respondeu para o curso {curso_id}: {type(exc).__name__}")
                    resultado[curso_id] = None
                    continue
                resultado[curso_id] = {str(c["id"]) for c in confs if c.get("recordings")}
        return resultado

    return asyncio.run(_ler())


def _prazo(aula: dict[str, Any]) -> str:
    """Quanto falta para a gravação sair do Canvas, aproximado."""
    try:
        inicio = datetime.fromisoformat(str(aula["iniciada_em"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return "prazo ?"
    restante = inicio + timedelta(days=_DIAS_RETENCAO_CANVAS) - datetime.now(UTC)
    horas = restante.total_seconds() / 3600
    if horas <= 0:
        return "PRAZO ESTOURADO"
    return f"~{horas:.0f} h no Canvas" if horas < 48 else f"~{horas / 24:.0f} dias no Canvas"


def _linha(aula: dict[str, Any], *, com_prazo: bool = False, com_erro: bool = False) -> str:
    data = str(aula.get("iniciada_em") or "")[:10]
    texto = f"    {data}  curso {aula['curso_id']}  {(aula.get('titulo') or '')[:60]}"
    texto += f"  (tentativas: {aula.get('tentativas', 0)})"
    if com_prazo:
        texto += f"  [{_prazo(aula)}]"
    if com_erro:
        texto += f"\n        erro: {(aula.get('erro_detalhe') or '')[:160]}"
    return texto


def reabrir(cliente: Any, aulas: list[dict[str, Any]]) -> int:
    """Volta para 'pendente' com as tentativas zeradas.

    O `.eq("status", "erro")` NÃO é enfeite: se uma rodada pegou a aula entre a
    leitura e esta escrita, o UPDATE sem ele a arrancaria do meio do caminho."""
    reabertas = 0
    for aula in aulas:
        resposta = (
            cliente.table("aula_gravacao")
            .update(
                {
                    "status": "pendente",
                    "tentativas": 0,
                    "erro_detalhe": None,
                    "atualizado_em": datetime.now(UTC).isoformat(),
                }
            )
            .eq("id", aula["id"])
            .eq("status", "erro")
            .execute()
        )
        reabertas += len(resposta.data or [])
    return reabertas


def _disparar_rodada() -> str:
    """Pede à API, de dentro do container, uma rodada agora. A trava dela
    responde 'ignorado' se já houver uma em andamento."""
    import httpx

    settings = get_settings()
    porta = os.environ.get("PORT", "8000")
    resposta = httpx.post(
        f"http://127.0.0.1:{porta}/gravacoes-aula/processar",
        headers={"X-Scheduler-Secret": settings.scheduler_secret},
        timeout=30,
    )
    resposta.raise_for_status()
    corpo = resposta.json()
    return f"{corpo.get('status')}: {corpo.get('motivo')}"


def main() -> int:
    # `prog` explícito: chegando por stdin, o nome do programa seria "-".
    parser = argparse.ArgumentParser(
        prog="reabrir-aulas", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument("--aplicar", action="store_true", help="grava; sem isto é ensaio")
    parser.add_argument(
        "--disparar", action="store_true", help="com --aplicar, já começa uma rodada agora"
    )
    parser.add_argument(
        "--todas", action="store_true", help="qualquer aula em 'erro', não só falha de S3"
    )
    args = parser.parse_args()

    settings = get_settings()
    bucket = settings.s3_bucket_gravacoes
    print(f"\n{'APLICANDO' if args.aplicar else 'ENSAIO (o banco não é alterado; use --aplicar)'}\n")

    print("1. O S3 voltou?")
    falha = _s3_respondendo()
    if falha:
        print(f"  ✗ ainda não: {falha[:300]}")
        print("    Nada foi alterado. Reabrir agora só esgotaria as tentativas de novo.")
        return 1
    print(f"  ✓ PUT em s3://{bucket}/{_CHAVE_CONFERENCIA} passou")

    cliente = criar_cliente_supabase()
    em_erro = (
        cliente.table("aula_gravacao")
        .select("id,curso_id,conferencia_id,titulo,iniciada_em,tentativas,erro_detalhe")
        .eq("status", "erro")
        .order("iniciada_em", desc=False)
        .execute()
        .data
    )
    print(f"\n2. Aulas em 'erro': {len(em_erro)}")
    if not em_erro:
        print("  nada a fazer.")
        return 0

    print("\n3. A gravação ainda está no Canvas?")
    gravacoes = _gravacoes_no_canvas({a["curso_id"] for a in em_erro})
    t = triar(em_erro, gravacoes, bucket=bucket, todas=args.todas)

    print(f"\n  REABRIR ({len(t.reabrir)}), da mais antiga para a mais nova:")
    for a in t.reabrir:
        print(_linha(a, com_prazo=True))
    if t.gravacao_expirada:
        print(f"\n  PERDIDAS ({len(t.gravacao_expirada)}): a gravação já saiu do Canvas.")
        print("    Não há mais o que baixar; ficam em 'erro'.")
        for a in t.gravacao_expirada:
            print(_linha(a))
    if t.nao_conferidas:
        print(f"\n  NÃO CONFERIDAS ({len(t.nao_conferidas)}): o Canvas não respondeu. Rode de novo.")
        for a in t.nao_conferidas:
            print(_linha(a))
    if t.outro_erro:
        print(f"\n  OUTRO ERRO ({len(t.outro_erro)}): não parece S3; ficam como estão (--todas inclui).")
        for a in t.outro_erro:
            print(_linha(a, com_erro=True))

    if not t.reabrir:
        return 0
    horas = len(t.reabrir) * 1.5
    print(
        f"\n  Uma aula por rodada, de 45 a 90 min cada: ~{horas:.0f} h para as "
        f"{len(t.reabrir)} passarem."
    )

    if not args.aplicar:
        print("\nEnsaio: o banco não foi alterado. Rode de novo com --aplicar.")
        return 0

    n = reabrir(cliente, t.reabrir)
    print(f"\n4. Reabertas: {n} de {len(t.reabrir)}")
    if n < len(t.reabrir):
        print("  (as que faltam mudaram de estado entre a leitura e a escrita: alguma rodada as pegou)")

    if args.disparar:
        print(f"\n5. Rodada: {_disparar_rodada()}")
    else:
        print("\n  A próxima rodada do cron (aos 25 de cada hora) começa a processar.")
        print("  Para começar agora: --disparar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
