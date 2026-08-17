"""Fase 3 do Canvas sync: arquivo (PDF) original da prova.

O arquivo não é anexo de Assignment/Quiz — é um Course File do curso
"Simulados", guardado numa pasta por ciclo (ver mapeador.parsear_pasta_ciclo).
Casamento arquivo↔simulado é por nome (rotulo_curto + matéria), não por ID —
não existe esse vínculo na API do Canvas (confirmado ao vivo, sem doc oficial
que garanta o contrário).

Um PDF pode cobrir várias matérias (caderno combinado) e/ou várias linhas de
`ciclo` (ITA e IME compartilhando a mesma prova nos ciclos combinados) — por
isso o casamento é 1 arquivo → N simulados, e o limite por rodada conta
arquivos BAIXADOS, não simulados atualizados.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from supabase import Client

from ..storage import salvar_arquivo_simulado
from . import mapeador
from .cliente import ClienteCanvas


async def sincronizar_arquivos_do_curso(
    cliente: Client,
    canvas: ClienteCanvas,
    *,
    course_id: str,
    simulados_pendentes: list[dict[str, Any]],
    limite_arquivos: int | None,
) -> dict[str, Any]:
    """Casa e sincroniza os PDFs de `simulados_pendentes`.

    Cada item de `simulados_pendentes`: {"id", "ciclo_ordem", "rotulo_curto",
    "materia_codigo"}. `limite_arquivos=None` remove o limite (uso do backfill).
    Devolve {"arquivos_baixados", "simulados_atualizados", "avisos"}.
    """
    if not simulados_pendentes:
        return {"arquivos_baixados": 0, "simulados_atualizados": 0, "avisos": []}

    ciclos_necessarios = {p["ciclo_ordem"] for p in simulados_pendentes}

    pastas = await canvas.listar_pastas(course_id)
    pasta_id_por_ciclo: dict[int, str] = {}
    for pasta in pastas:
        ciclo = mapeador.parsear_pasta_ciclo(pasta.get("full_name") or "")
        if ciclo in ciclos_necessarios:
            pasta_id_por_ciclo[ciclo] = str(pasta["id"])

    # Índice de busca: (ciclo, rotulo_curto, materia) pode ter mais de um
    # pendente (ex.: mesma prova serve ciclo ITA e ciclo IME).
    pendentes_por_chave: dict[tuple[int, str, str], list[dict[str, Any]]] = {}
    for p in simulados_pendentes:
        chave = (p["ciclo_ordem"], p["rotulo_curto"], p["materia_codigo"])
        pendentes_por_chave.setdefault(chave, []).append(p)

    arquivos_baixados = 0
    simulados_atualizados = 0
    avisos: list[str] = []
    ids_atendidos: set[str] = set()
    # Provas reenviadas ficam duplicadas nos Course Files (ex.: uma cópia com
    # sufixo "_protected" e outra sem) — sem isso, a segunda cópia re-baixa e
    # re-atualiza o mesmo simulado, inflando as contagens.
    chave_ja_atendida: dict[tuple[int, str, str], str] = {}
    limite_atingido = False

    for ciclo_ordem in sorted(ciclos_necessarios):
        if limite_arquivos is not None and arquivos_baixados >= limite_arquivos:
            limite_atingido = True
            break
        folder_id = pasta_id_por_ciclo.get(ciclo_ordem)
        if folder_id is None:
            avisos.append(f"Pasta do {ciclo_ordem}º ciclo não encontrada nos Course Files.")
            continue

        arquivos = await canvas.listar_arquivos_da_pasta(folder_id)
        for arquivo in arquivos:
            if limite_arquivos is not None and arquivos_baixados >= limite_arquivos:
                limite_atingido = True
                break
            if arquivo.get("content-type") != "application/pdf":
                continue
            nome_arquivo = arquivo.get("display_name") or ""
            info = mapeador.parsear_nome_arquivo_simulado(nome_arquivo)
            if info is None:
                continue

            alvo: list[dict[str, Any]] = []
            for materia_codigo in info["materias_codigos"]:
                chave = (ciclo_ordem, info["rotulo_curto"], materia_codigo)
                if chave in chave_ja_atendida:
                    avisos.append(
                        f"Arquivo '{nome_arquivo}' também casa com ciclo {ciclo_ordem}/"
                        f"{info['rotulo_curto']}/{materia_codigo}, mas esse slot já foi "
                        f"atendido por '{chave_ja_atendida[chave]}' — ignorado."
                    )
                    continue
                candidatos = pendentes_por_chave.get(chave, [])
                if candidatos:
                    chave_ja_atendida[chave] = nome_arquivo
                alvo.extend(candidatos)
            if not alvo:
                continue  # arquivo não corresponde a nenhum simulado pendente ainda em aberto

            canvas_file_id = str(arquivo["id"])
            conteudo = await canvas.baixar_bytes(arquivo["url"])
            caminho_storage = salvar_arquivo_simulado(
                canvas_file_id=canvas_file_id,
                nome_arquivo=nome_arquivo or f"{canvas_file_id}.pdf",
                conteudo=conteudo,
            )
            arquivos_baixados += 1

            agora = datetime.now(timezone.utc).isoformat()
            for pendente in alvo:
                cliente.table("simulado").update(
                    {
                        "arquivo_storage_path": caminho_storage,
                        "arquivo_canvas_file_id": canvas_file_id,
                        "arquivo_sincronizado_em": agora,
                    }
                ).eq("id", pendente["id"]).execute()
                ids_atendidos.add(pendente["id"])
                simulados_atualizados += 1

    # Só vale reportar "não encontrado" se sobrou pendente por falta de match
    # real — não quando foi o limite da rodada que cortou o processamento.
    if not limite_atingido:
        for p in simulados_pendentes:
            if p["id"] not in ids_atendidos:
                avisos.append(
                    f"Nenhum arquivo casado pro simulado {p['id']} "
                    f"(ciclo {p['ciclo_ordem']}, {p['rotulo_curto']}, {p['materia_codigo']})."
                )

    return {
        "arquivos_baixados": arquivos_baixados,
        "simulados_atualizados": simulados_atualizados,
        "avisos": avisos,
    }
