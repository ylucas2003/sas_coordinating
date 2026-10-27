"""Leitura da trilha de auditoria — a linha do tempo da coordenação.

A coordenação pediu (21/08, 19h06) "puxar na linha do tempo todas as
alterações que foram feitas… para rodar algum script depois caso alguém faça
merda". Esta rota é a leitura; a escrita é `app/auditoria.registrar`, e o
compartimento por `canal` é a migration 0025 (docs/18 §3).

Só leitura, só coordenação. O que está aqui nunca tem senha, hash, token ou
corpo de mensagem — regra da casa em auditoria.py — então não há o que
mascarar na saída.

A consulta e os nomes são `auditoria.consultar` e `auditoria.nomes_dos_atores`,
os mesmos que a tool do assistente chama (docs/43 §4.3); aqui só a fronteira.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from .. import auditoria
from ..auth import get_current_coordenador
from ..supabase_client import get_supabase

router = APIRouter(
    prefix="/auditoria",
    tags=["auditoria"],
    dependencies=[Depends(get_current_coordenador)],
)

#: Os canais que a linha do tempo oferece. São os que `auditoria.registrar`
#: recebe hoje (migrations 0025, 0038 e 0049; routes/captacao.py), mais `mcp`,
#: onde o MCP da coordenação registra cada chamada (docs/43 §5.3; 0072).
CANAIS = ("acesso", "nota", "simulado", "ciclo", "canvas", "criterio", "cantina", "captacao", "mcp")


@router.get("")
def listar_eventos(
    canal: str | None = Query(None, description=" | ".join(CANAIS)),
    ator_id: str | None = Query(None),
    recurso: str | None = Query(None, description="prefixo, ex.: nota/<aluno_id>"),
    desde: str | None = Query(None, description="ISO 8601"),
    ate: str | None = Query(None, description="ISO 8601"),
    limite: int = Query(100, ge=1, le=auditoria.LIMITE_MAXIMO),
    antes_de_id: int | None = Query(None, description="cursor: eventos com id menor"),
    incluir_logins: bool = Query(False, description="Traz login_ok/login_falhou junto. Default: só criações e alterações."),
) -> dict:
    """Eventos mais recentes primeiro, filtráveis por canal, ator, recurso e
    período. Cursor por `id` (bigserial) para paginar sem offset. Por padrão
    só o que criou ou alterou algo — logins não entram.

    `def`, e não `async def`: o cliente do PostgREST é síncrono, e chamado de
    dentro do event loop ele trava a API inteira enquanto lê (UVICORN_WORKERS=1,
    docs/40 §12.1.1)."""
    cliente = get_supabase()
    eventos = auditoria.consultar(
        cliente,
        canais=[canal] if canal else None,
        recurso_prefixos=[recurso] if recurso else None,
        ator_ids=[ator_id] if ator_id else None,
        desde=desde,
        ate=ate,
        limite=limite,
        antes_de_id=antes_de_id,
        incluir_logins=incluir_logins,
    )

    # Nome de quem fez, para a tela não mostrar uuid. Melhor-esforço: um
    # ator que não existe mais continua aparecendo pelo id.
    nomes, tem_foto = auditoria.nomes_dos_atores(
        cliente, ((e.get("ator_tipo"), e.get("ator_id")) for e in eventos)
    )
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
