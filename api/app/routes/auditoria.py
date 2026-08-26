"""Leitura da trilha de auditoria — a linha do tempo da coordenação.

A coordenação pediu (21/08, 19h06) "puxar na linha do tempo todas as
alterações que foram feitas… para rodar algum script depois caso alguém faça
merda". Esta rota é a leitura; a escrita é `app/auditoria.registrar`, e o
compartimento por `canal` é a migration 0025 (docs/18 §3).

Só leitura, só coordenação. O que está aqui nunca tem senha, hash, token ou
corpo de mensagem — regra da casa em auditoria.py — então não há o que
mascarar na saída.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..auth import get_current_coordenador
from ..supabase_client import get_supabase

router = APIRouter(
    prefix="/auditoria",
    tags=["auditoria"],
    dependencies=[Depends(get_current_coordenador)],
)

CANAIS = ("acesso", "nota", "simulado", "ciclo", "canvas")

# Entrar no sistema não muda nada. A linha do tempo é "o que foi criado ou
# alterado" (coordenação, 22/08); login fica gravado para forense, mas só
# aparece se pedirem.
ACOES_DE_ACESSO = ("login_ok", "login_falhou", "primeiro_acesso_bloqueado")

# Sem paginação em lugar nenhum do projeto (CLAUDE.md, armadilha 2) — aqui
# ela existe porque a tabela só cresce e a tela mostra a cauda recente.
_LIMITE_MAXIMO = 500


@router.get("")
async def listar_eventos(
    canal: str | None = Query(None, description="acesso | nota | simulado | ciclo | canvas"),
    ator_id: str | None = Query(None),
    recurso: str | None = Query(None, description="prefixo, ex.: nota/<aluno_id>"),
    desde: str | None = Query(None, description="ISO 8601"),
    ate: str | None = Query(None, description="ISO 8601"),
    limite: int = Query(100, ge=1, le=_LIMITE_MAXIMO),
    antes_de_id: int | None = Query(None, description="cursor: eventos com id menor"),
    incluir_logins: bool = Query(False, description="Traz login_ok/login_falhou junto. Default: só criações e alterações."),
) -> dict:
    """Eventos mais recentes primeiro, filtráveis por canal, ator, recurso e
    período. Cursor por `id` (bigserial) para paginar sem offset. Por padrão
    só o que criou ou alterou algo — logins não entram."""
    cliente = get_supabase()
    q = (
        cliente.table("evento_auditoria")
        .select("id, ocorrido_em, acao, canal, ator_tipo, ator_id, recurso, ip, detalhe, request_id")
        .order("id", desc=True)
        .limit(limite)
    )
    if not incluir_logins:
        q = q.not_.in_("acao", list(ACOES_DE_ACESSO))
    if canal:
        q = q.eq("canal", canal)
    if ator_id:
        q = q.eq("ator_id", ator_id)
    if recurso:
        q = q.like("recurso", f"{recurso}%")
    if desde:
        q = q.gte("ocorrido_em", desde)
    if ate:
        q = q.lte("ocorrido_em", ate)
    if antes_de_id is not None:
        q = q.lt("id", antes_de_id)
    eventos = q.execute().data or []

    # Nome de quem fez, para a tela não mostrar uuid. Melhor-esforço: um
    # ator que não existe mais continua aparecendo pelo id.
    nomes, tem_foto = _nomes_dos_atores(cliente, eventos)
    for e in eventos:
        e["ator_nome"] = nomes.get(e.get("ator_id") or "")
        # Sinal barato (uma coluna a mais no mesmo select) pro front decidir
        # se vale buscar a foto — sem isso, cada linha da lista tentaria
        # `/foto` mesmo para quem nunca teve uma.
        e["ator_tem_foto"] = tem_foto.get(e.get("ator_id") or "", False)

    return {
        "eventos": eventos,
        "canais": list(CANAIS),
        "proximo_antes_de_id": eventos[-1]["id"] if len(eventos) == limite else None,
    }


def _nomes_dos_atores(cliente, eventos: list[dict]) -> tuple[dict[str, str], dict[str, bool]]:
    coord_ids = sorted({
        e["ator_id"] for e in eventos
        if e.get("ator_tipo") == "coordenador" and e.get("ator_id") and len(e["ator_id"]) == 36
    })
    aluno_ids = sorted({
        e["ator_id"] for e in eventos
        if e.get("ator_tipo") == "aluno" and e.get("ator_id") and len(e["ator_id"]) == 36
    })
    nomes: dict[str, str] = {}
    tem_foto: dict[str, bool] = {}
    if coord_ids:
        linhas = (
            cliente.table("usuario_coordenacao")
            .select("id, nome, foto_perfil_storage")
            .in_("id", coord_ids)
            .execute()
            .data
            or []
        )
        for u in linhas:
            nomes[u["id"]] = u["nome"]
            tem_foto[u["id"]] = u.get("foto_perfil_storage") is not None
    if aluno_ids:
        linhas = (
            cliente.table("aluno")
            .select("id, nome, foto_perfil_storage")
            .in_("id", aluno_ids)
            .execute()
            .data
            or []
        )
        for a in linhas:
            nomes[a["id"]] = a["nome"]
            tem_foto[a["id"]] = a.get("foto_perfil_storage") is not None
    return nomes, tem_foto
