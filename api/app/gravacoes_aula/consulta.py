"""Leitura do acompanhamento de gravações — GET /gravacoes-aula.

Router SEPARADO de rotas.py de propósito: lá dentro tudo é do scheduler
(`X-Scheduler-Secret`), aqui tudo é do coordenador (JWT). Misturar os dois num
arquivo só é como se esquece um guard numa rota nova.

A leitura é `painel(cliente)`, síncrona e sem `get_supabase()` por dentro, para
a tool do assistente que acompanha as gravações (docs/43 §4.3) ler o mesmo que
a tela, com o cliente dela. A tool lê com `para_ia=True`, que vai à view da 0074
em vez da tabela: a mesma leitura, sem nenhum link de vídeo pelo caminho.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from supabase import Client

from ..auth import get_current_coordenador
from ..supabase_client import get_supabase

router = APIRouter(
    prefix="/gravacoes-aula",
    tags=["gravacoes-aula"],
    dependencies=[Depends(get_current_coordenador)],
)

# Explícito, nunca "*": s3_bucket e s3_chave_composto NÃO saem daqui. São a
# localização do vídeo de aluno menor de idade no bucket privado — não é dado
# de tela, e a tela não precisa deles para nada.
_CAMPOS = (
    "id,curso_id,conferencia_id,titulo,iniciada_em,duracao_minutos,status,"
    "tentativas,youtube_video_id,youtube_titulo,erro_detalhe,"
    "canvas_estado,canvas_pagina_url,canvas_modulo_nome,canvas_erro,criado_em,atualizado_em"
)

#: O que vai a um modelo, no chat e no MCP (0074). A view não tem `s3_*`, e o
#: erro já vem sem o id do vídeo e sem a linha que o Postgres despeja. O link
#: vai, por decisão da coordenação em 30/10: a IA o recebe como a tela o mostra.
VIEW_PARA_IA = "aula_gravacao_para_ia"
_CAMPOS_PARA_IA = (
    "id,curso_id,titulo,iniciada_em,status,tentativas,erro_detalhe,"
    "canvas_estado,canvas_modulo_nome,canvas_erro,atualizado_em,"
    "youtube_video_id,youtube_titulo,canvas_pagina_url"
)
_CAMPOS_DO_CURSO = "curso_id,nome,ativo,publicar_no_canvas,canvas_modulo_id"
_CAMPOS_DO_CURSO_PARA_IA = "curso_id,nome,ativo,publicar_no_canvas"

# ─── Situação: os dez `status` do pipeline em cinco degraus ──────────────
#
# ⚠️ ESPELHO de `POR_STATUS`, `SITUACOES` e do fallback de `situacaoDe` em
# web/src/dominio/gravacoes.ts — é lá que o comentário de cada degrau mora.
# O coordenador não quer saber de "compondo" nem de "baixado", e a tradução
# para o que ele acompanha ("já foi", "está indo", "vai ser") tem de ser a
# MESMA na tela e na boca do assistente. tests/test_dominio_gravacoes.py lê o
# .ts e reprova se os dois divergirem; mudou lá, muda aqui.

#: Na ordem em que acontecem.
SITUACOES = ("aguardando", "na_fila", "processando", "publicado", "erro")

SITUACAO_POR_STATUS: dict[str, str] = {
    "aguardando_gravacao": "aguardando",
    "pendente": "na_fila",
    "baixando": "processando",
    "baixado": "processando",
    "compondo": "processando",
    "composto": "processando",
    "publicando": "processando",
    "publicado": "publicado",
    # Subiu, mas a confirmação do YouTube não voltou. É sucesso: reprocessar
    # geraria segunda cópia no canal (api/CLAUDE.md).
    "publicado_sem_confirmacao": "publicado",
    "erro": "erro",
}

#: Status que o mapa não conhece cai aqui, como no `situacaoDe` do front.
SITUACAO_DESCONHECIDA = "aguardando"

#: Quanto do texto de erro a TELA recebe: uma linha do painel. O texto inteiro
#: continua no banco para quem depura.
LIMITE_DO_ERRO_NA_TELA = 300


def situacao_de(status: str | None) -> str:
    """A situação que a tela mostra para este `status` do pipeline."""
    return SITUACAO_POR_STATUS.get(status or "", SITUACAO_DESCONHECIDA)


def _cortado(texto: str | None, limite: int | None) -> str | None:
    if not texto:
        return None
    return texto if limite is None else texto[:limite]


def _para_camel(a: dict[str, Any], limite_do_erro: int | None = LIMITE_DO_ERRO_NA_TELA) -> dict[str, Any]:
    """O front espelha o backend (web/src/tipos/dominio.ts); a URL do vídeo é
    montada aqui para o front não precisar reinventar o formato."""
    video = a.get("youtube_video_id")
    return {
        "id": a["id"],
        "cursoId": a["curso_id"],
        "conferenciaId": a.get("conferencia_id"),
        "titulo": a["titulo"],
        "iniciadaEm": a.get("iniciada_em"),
        "duracaoMinutos": a.get("duracao_minutos"),
        "status": a["status"],
        "situacao": situacao_de(a["status"]),
        "tentativas": a.get("tentativas") or 0,
        "youtubeVideoId": video,
        "youtubeTitulo": a.get("youtube_titulo"),
        "youtubeUrl": f"https://youtu.be/{video}" if video else None,
        "erroDetalhe": _cortado(a.get("erro_detalhe"), limite_do_erro),
        "canvasEstado": a.get("canvas_estado") or "pendente",
        "canvasUrl": a.get("canvas_pagina_url"),
        # Nulo com a página publicada = fora de módulo: existe, mas o aluno
        # não acha, porque é por módulo que ele navega.
        "canvasModulo": a.get("canvas_modulo_nome"),
        "canvasErro": _cortado(a.get("canvas_erro"), limite_do_erro),
        "atualizadoEm": a.get("atualizado_em"),
    }


@router.get("")
def listar_gravacoes() -> dict:
    """Tudo que o painel precisa numa chamada só — ver `painel`.

    `def`, e não `async def`: o cliente do PostgREST é síncrono, e chamado de
    dentro do event loop ele trava a API inteira enquanto lê (UVICORN_WORKERS=1,
    docs/40 §12.1.1)."""
    return painel(get_supabase())


def painel(
    cliente: Client,
    *,
    limite_do_erro: int | None = LIMITE_DO_ERRO_NA_TELA,
    para_ia: bool = False,
) -> dict:
    """Cursos monitorados e aulas, da mais recente para a mais antiga.

    Sem paginação de propósito: são dezenas de linhas por semestre (uma por
    aula), não as centenas de milhares de `nota` que motivam a dívida de
    paginação descrita no CLAUDE.md da raiz.

    ⚠️ `youtubeUrl` e `youtubeVideoId` abrem vídeo NÃO LISTADO de aula com
    aluno menor de idade — o link é o acesso —, e `canvasUrl` é a página que o
    embute. A coordenação decidiu em 30/10 que eles também vão à IA dela
    (docs/43 §0.3). O S3 é que não sai de jeito nenhum.

    `limite_do_erro=None` entrega `erroDetalhe` e `canvasErro` INTEIROS, para
    quem limpa o texto antes de mostrá-lo: `texto_seguro` limpa e só então
    corta, e um texto que já chega cortado em 300 pode ter partido uma
    credencial ao meio — curta demais para o padrão, ela sairia pela metade
    (revisão paralela de 25/10). A tela continua recebendo os 300.

    `para_ia=True` é a leitura de quem leva isto a um modelo: lê `VIEW_PARA_IA`,
    com o erro já limpo na própria view. É o único caminho que o MCP alcança — o
    `sas_mcp` não lê `aula_gravacao`.
    """
    cursos = (
        cliente.table("curso_monitorado_gravacao")
        .select(_CAMPOS_DO_CURSO_PARA_IA if para_ia else _CAMPOS_DO_CURSO)
        .order("nome")
        .execute()
        .data
    )
    aulas = (
        cliente.table(VIEW_PARA_IA if para_ia else "aula_gravacao")
        .select(_CAMPOS_PARA_IA if para_ia else _CAMPOS)
        .order("iniciada_em", desc=True)
        .execute()
        .data
    )
    return {
        "cursos": [
            {
                "cursoId": c["curso_id"],
                "nome": c["nome"],
                "ativo": c["ativo"],
                "publicarNoCanvas": c["publicar_no_canvas"],
                "canvasModuloId": c.get("canvas_modulo_id"),
            }
            for c in cursos
        ],
        "aulas": [_para_camel(a, limite_do_erro) for a in aulas],
    }
