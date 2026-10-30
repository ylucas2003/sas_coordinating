"""Tool da trilha de auditoria — quem mudou o quê (docs/43 §4.3).

"Quem mudou a nota da aluna no P22?" é pergunta de coordenação que só a
trilha (`evento_auditoria`, migration 0022) responde. A leitura é a da tela
de auditoria, pelas mesmas funções (`auditoria.consultar`, com `so_alteracoes`,
e `auditoria.nomes_da_coordenacao`), e a tool só faz duas coisas que a tela não
precisa fazer:

  * FECHA OS CANAIS numa lista positiva — nota, simulado, ciclo, canvas,
    criterio e, desde 30/10, cantina e captacao (a IA lê o que o coordenador
    lê). O canal 'acesso' nunca entra: em `login_falhou` o `ator_id` é o e-mail
    DIGITADO (e há quem digite a senha no campo errado), em
    `coordenador_criado` o detalhe leva e-mail e nome, e toda linha tem IP
    (routes/auth.py, routes/administracao.py). O canal `mcp` também fica fora:
    é o uso da própria IA. A constante `CANAIS` da rota é a lista da tela, não
    lista permitida;
  * FECHA O DETALHE numa lista de chaves por ação. `detalhe` é jsonb livre e
    cada ponto de chamada grava o seu; o que não está na lista não sai. Nunca
    saem `ip`, `request_id` nem `ator_id` cru.

O recurso do filtro é montado AQUI, a partir de id validado (uuid ou slug):
o prefixo é LIKE, e um '%' vindo do modelo alargaria a busca
(`auditoria.consultar`, docstring).

A trilha é melhor-esforço (`auditoria.py`): a falta de evento não prova que a
ação não aconteceu, e a descrição diz isso ao modelo.

Vai ao MCP desde 30/10: a decisão de 24/10 a deixava fora (docs/43 §6), e a
coordenação a reverteu. As duas listas acima continuam valendo, e ganharam um
piso no banco: GRANT por coluna não corta linha, e a tabela tem o canal
'acesso', então o MCP não a lê. Lê `trilha_de_alteracoes`, a view da 0074, com
os canais de `CANAIS_DA_TRILHA` e o detalhe na união de `DETALHE_POR_ACAO`;
tests/test_migrations_do_mcp.py reprova se a view e este módulo divergirem. O
nome de quem fez vem de `nome_da_coordenacao`, da mesma migration. Nome de aluno
só sai em `alunoNome`, com `alunoId` ao lado, e passa pelo pseudônimo.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from supabase import Client

from ... import auditoria
from ...lembretes import despachante, motor
from ...stats import criterios_repo
from ...texto_seguro import texto_seguro

#: Os canais que esta tool lê — e só estes, por construção.
CANAIS_DA_TRILHA = ("nota", "simulado", "ciclo", "canvas", "criterio", "cantina", "captacao")

#: As ações que nem a view da 0074 entrega, mesmo vindo de um canal da lista. O
#: canal `cantina` grava também os LOGINS, e em `login_falhou` o `ator_id` é o que
#: a pessoa digitou (routes/auth.py). E a edição da restrição alimentar, com o id
#: do aluno no recurso, diria quem tem restrição mesmo com a tool dela desligada:
#: o dado de saúde sai por uma tool só (0075).
ACOES_FORA_DA_TRILHA = (*auditoria.ACOES_DE_ACESSO, "restricao_alimentar_editada")

#: As chaves de `detalhe` que saem, por ação, tiradas de quem grava cada uma
#: (routes/notas.py, simulados.py, ciclos.py, criterios.py, banco.py, cantina.py
#: e captacao.py). Ação fora daqui aparece com o detalhe vazio: o que ninguém
#: revisou não sai.
#:
#: Da cantina, as contas ficam com o detalhe vazio de propósito: o de
#: `conta_cantina_criada` leva o e-mail. `alunos` sai como contagem: um lote de
#: 900 são 36 KB de uuids por evento. Da captação, o `nome_normalizado` fica
#: fora: a trilha continua no catálogo com o pseudônimo, e o nome de gente de
#: fora voltaria por aqui.
DETALHE_POR_ACAO: dict[str, tuple[str, ...]] = {
    "nota_editada": (
        "aluno", "valor_antes", "valor_depois", "valor_canvas", "presente",
        "sincronizar_canvas", "canvas_ok", "canvas_erro",
    ),
    "simulado_criado": ("nome", "data_aplicacao", "sincronizar_canvas", "canvas_estado"),
    "simulado_editado": ("campos", "origem", "sincronizar_canvas", "canvas_estado"),
    "simulado_removido": ("sincronizar_canvas", "apagado_no_canvas"),
    "ciclo_criado": ("nome", "sincronizar_canvas", "canvas_estado", "canvas_erro"),
    "enviado_ao_canvas": ("canvas_estado", "ok", "erro", "enviados", "falhas", "total"),
    "criterio_criado": ("nome", "versao", "requisitos"),
    "criterio_versionado": ("versao", "requisitos"),
    "criterio_desativado": (),
    "importancia_recalibrada": ("versao", "de", "para"),
    "cardapio_criado": ("data", "refeicao"),
    "cardapio_editado": ("data", "blocos"),
    "cardapio_publicado": ("data", "refeicao"),
    "cardapio_copiado": ("origem",),
    "retirada_confirmada": ("aluno_id", "cardapio_id", "refeicao"),
    "direito_refeicao_concedido": ("refeicao", "alunos"),
    "direito_refeicao_revogado": ("refeicao", "alunos"),
    "cantina_criada": ("nome",),
    "cantina_editada": (),
    "conta_cantina_criada": (),
    "conta_cantina_editada": (),
    "senha_cantina_redefinida": (),
    "captacao_status_alterado": ("valor_antes", "valor_depois"),
    "captacao_perfil_criado": (),
    "captacao_conquista_movida": ("conquista_id", "de", "para"),
    "captacao_perfil_removido": (),
}

#: Texto de exceção gravado no detalhe (o `str(exc)` da escrita no Canvas).
_CHAVES_DE_ERRO = frozenset({"erro", "canvas_erro"})

TETO_DE_EVENTOS = 30
_LIMITE_DO_TEXTO = 160


def _uuid(valor: str | None, campo: str) -> tuple[str | None, str | None]:
    if valor is None or not str(valor).strip():
        return None, None
    try:
        return str(uuid.UUID(str(valor).strip())), None
    except ValueError:
        return None, f"{campo} deve ser um UUID; descubra-o com a tool de busca correspondente"


def _dia(valor: str | None, campo: str) -> tuple[date | None, str | None]:
    if valor is None or not str(valor).strip():
        return None, None
    try:
        return date.fromisoformat(str(valor).strip()), None
    except ValueError:
        return None, f"{campo} deve ser uma data AAAA-MM-DD"


def _instante(dia: date, *, fim_do_dia: bool = False) -> str:
    """O começo (ou o último instante) do dia no calendário da escola, BRT,
    como filtro de timestamptz no formato 'Z' — o '+' de '+00:00' viraria
    espaço na URL (`despachante.filtro_ts`)."""
    momento = datetime.combine(dia, time.min, tzinfo=motor.FUSO_BRASIL)
    if fim_do_dia:
        momento += timedelta(days=1) - timedelta(microseconds=1)
    return despachante.filtro_ts(momento.astimezone(UTC))


def historico_de_alteracoes(
    cliente: Client,
    *,
    canal: str | None = None,
    acao: str | None = None,
    aluno_id: str | None = None,
    simulado_id: str | None = None,
    ciclo_id: str | None = None,
    regua_slug: str | None = None,
    ator_nome: str | None = None,
    desde: str | None = None,
    ate: str | None = None,
    limite: int = 20,
) -> dict:
    """Os eventos da trilha que respondem "quem mudou o quê", do mais recente."""
    if canal is not None and canal not in CANAIS_DA_TRILHA:
        return {"erro": f"canal deve ser um de: {', '.join(CANAIS_DA_TRILHA)}"}
    if acao is not None and acao not in DETALHE_POR_ACAO:
        return {"erro": f"acao deve ser uma de: {', '.join(DETALHE_POR_ACAO)}"}

    aluno, erro_aluno = _uuid(aluno_id, "aluno_id")
    simulado, erro_simulado = _uuid(simulado_id, "simulado_id")
    ciclo, erro_ciclo = _uuid(ciclo_id, "ciclo_id")
    inicio, erro_desde = _dia(desde, "desde")
    fim, erro_ate = _dia(ate, "ate")
    erro = erro_aluno or erro_simulado or erro_ciclo or erro_desde or erro_ate
    if erro:
        return {"erro": erro}
    slug = regua_slug.strip() if regua_slug and regua_slug.strip() else None
    if slug is not None and not criterios_repo.RE_SLUG.match(slug):
        return {"erro": "regua_slug deve ser o slug de uma régua (reguas_de_corte), ex.: 'meta-7-exatas'"}

    prefixos, erro = _prefixos(aluno, simulado, ciclo, slug)
    if erro:
        return {"erro": erro}

    ator_ids: list[str] | None = None
    if ator_nome and ator_nome.strip():
        ator_ids = _ids_da_coordenacao(cliente, ator_nome)
        if ator_ids is None:
            return {"erro": "ator_nome precisa de pelo menos 2 letras"}
        if not ator_ids:
            return {"total": 0, "eventos": [], "aviso": f"Ninguém da coordenação com nome parecido com '{ator_nome.strip()}'."}

    limite = min(max(1, limite), TETO_DE_EVENTOS)
    linhas = auditoria.consultar(
        cliente,
        canais=[canal] if canal else list(CANAIS_DA_TRILHA),
        acao=acao,
        recurso_prefixos=prefixos,
        ator_ids=ator_ids,
        desde=_instante(inicio) if inicio else None,
        # `ate` inclusivo: até o fim do dia pedido, em BRT.
        ate=_instante(fim, fim_do_dia=True) if fim else None,
        limite=limite,
        so_alteracoes=True,
    )
    # Defesa em profundidade: a lista de canais vai na consulta, a view corta as
    # ações de `ACOES_FORA_DA_TRILHA`, e um canal
    # fora dela não sai nem que a leitura mude por baixo.
    linhas = [
        linha for linha in linhas
        if linha.get("canal") in CANAIS_DA_TRILHA and linha.get("acao") not in ACOES_FORA_DA_TRILHA
    ]

    # Só nome de COORDENADOR: ator aluno nesses canais seria dado de menor
    # que ninguém pediu, e a view nem o resolve.
    nomes = auditoria.nomes_da_coordenacao(
        cliente, [l.get("ator_id") for l in linhas if l.get("ator_tipo") == "coordenador"]
    )
    eventos = [_evento(linha, nomes) for linha in linhas]
    saida: dict[str, Any] = {"total": len(eventos), "haMais": len(linhas) >= limite, "eventos": eventos}
    if not eventos:
        saida["aviso"] = (
            "Nenhum evento no recorte. A trilha é melhor-esforço: isso não prova que nada "
            "aconteceu."
        )
    return saida


def _prefixos(
    aluno: str | None, simulado: str | None, ciclo: str | None, slug: str | None
) -> tuple[list[str] | None, str | None]:
    """Os prefixos de `recurso`, no formato de quem grava (`nota/<aluno>/<simulado>`,
    `simulado/<id>`, `ciclo/<id>` e `ciclo/<id>/lote`, `criterio/<slug>`).

    O '%' do meio, em `nota/%/<simulado>`, é posto aqui, entre dois pedaços
    validados — nunca vem do modelo.
    """
    if aluno and simulado and not (ciclo or slug):
        return [f"nota/{aluno}/{simulado}"], None
    dados = [x for x in (aluno, simulado, ciclo, slug) if x]
    if len(dados) > 1:
        return None, "use um filtro de entidade por vez (aluno e simulado juntos valem: a nota do aluno naquele simulado)"
    if aluno:
        return [f"nota/{aluno}"], None
    if simulado:
        return [f"simulado/{simulado}", f"nota/%/{simulado}"], None
    if ciclo:
        return [f"ciclo/{ciclo}"], None
    if slug:
        return [f"criterio/{slug}"], None
    return None, None


def _ids_da_coordenacao(cliente: Client, nome: str) -> list[str] | None:
    """Os ids de quem, na coordenação, tem esse trecho no nome. Nunca e-mail.

    Os curingas do LIKE saem do termo: o trecho é de nome, e '%' ou '*' vindo
    do modelo transformaria "um nome" em "todo mundo".
    """
    termo = "".join(c for c in nome.strip() if c not in "%_*")
    if len(termo) < 2:
        return None
    linhas = (
        cliente.table(auditoria.VIEW_DOS_NOMES)
        .select("id, nome")
        .ilike("nome", f"%{termo}%")
        .limit(20)
        .execute()
        .data
        or []
    )
    return [linha["id"] for linha in linhas]


def _evento(linha: dict[str, Any], nomes: dict[str, str]) -> dict[str, Any]:
    ator_id = linha.get("ator_id")
    if linha.get("ator_tipo") == "coordenador" and ator_id:
        # Conta que não existe mais: diz que era alguém, sem mostrar o id.
        quem = nomes.get(ator_id) or "conta da coordenação não encontrada"
    elif not ator_id:
        quem = "sistema"
    else:
        # Outro tipo de ator: o tipo, nunca o id nem o nome.
        quem = str(linha.get("ator_tipo") or "não identificado")

    recurso = linha.get("recurso") or ""
    tipo, _, ident = recurso.partition("/")
    return {
        "quando": linha.get("ocorrido_em"),
        "acao": linha.get("acao"),
        "canal": linha.get("canal"),
        "quem": quem,
        "recurso": {"tipo": tipo or None, "id": ident or None},
        "detalhe": _detalhe(linha.get("acao"), linha.get("detalhe"), tipo, ident),
    }


def _detalhe(acao: Any, bruto: Any, tipo: str, ident: str) -> dict[str, Any]:
    if not isinstance(bruto, dict):
        return {}
    permitidas = DETALHE_POR_ACAO.get(acao, ()) if isinstance(acao, str) else ()
    saida: dict[str, Any] = {}
    for chave in permitidas:
        if chave not in bruto:
            continue
        valor = bruto[chave]
        if chave in _CHAVES_DE_ERRO:
            valor = texto_seguro(valor, _LIMITE_DO_TEXTO) or None
        if chave == "aluno":
            # O nome do aluno vai junto do id dele, tirado do recurso
            # (`nota/<aluno>/<simulado>`): nome de aluno sem chave de
            # identidade ao lado é o que o pseudonimizador do MCP recusa.
            saida["alunoId"] = ident.split("/", 1)[0] if tipo == "nota" and ident else None
            saida["alunoNome"] = valor
            continue
        if chave == "alunos" and isinstance(valor, list):
            saida["totalDeAlunos"] = len(valor)
            continue
        saida[chave] = valor
    return saida


_SCHEMA_HISTORICO = {
    "name": "historico_de_alteracoes",
    "description": (
        "Quando usar: 'quem mudou a nota da aluna no P22?', 'o que alteraram no simulado X?', "
        "'quem criou ou mudou a régua Y?', 'o que mudou ontem?', 'quem publicou o cardápio?', "
        "'quem mudou o status do candidato?'. É a trilha de auditoria de notas, simulados, "
        "ciclos, envios ao Canvas, réguas, calibração do banco, cantina (cardápios, retiradas, "
        "direitos) e captação externa.\n"
        "Antes de chamar, confirme: o id da entidade (aluno por buscar_aluno_por_nome, "
        "simulado por listar_simulados, ciclo por listar_ciclos, régua por reguas_de_corte) e "
        "o período, se a pergunta tiver data.\n"
        "Definições: quem = a pessoa da coordenação que fez ('sistema' = rotina automática; "
        "'cantina' = uma conta da cantina). "
        "detalhe traz antes → depois quando existe (valor_antes, valor_depois, valor_canvas). "
        "A trilha é melhor-esforço: não achar evento não prova que nada aconteceu. Logins e o "
        "uso do próprio assistente não estão aqui de propósito, nem a edição da restrição "
        "alimentar; diga que essa parte não é consultável pelo assistente.\n"
        "Exemplo: historico_de_alteracoes(aluno_id='…', acao='nota_editada') → 'em 12/10, às "
        "14:03, <nome> mudou a nota de 4,0 para 5,5 (no Canvas estava 4,0)'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "canal": {"type": "string", "enum": list(CANAIS_DA_TRILHA)},
            "acao": {"type": "string", "enum": list(DETALHE_POR_ACAO)},
            "aluno_id": {"type": "string", "description": "UUID do aluno: as alterações de nota dele."},
            "simulado_id": {"type": "string", "description": "UUID do simulado: o simulado e as notas dele."},
            "ciclo_id": {"type": "string", "description": "UUID do ciclo."},
            "regua_slug": {"type": "string", "description": "Slug de régua criada pela coordenação."},
            "ator_nome": {"type": "string", "description": "Trecho do nome de quem fez (coordenação)."},
            "desde": {"type": "string", "description": "Data AAAA-MM-DD, inclusive."},
            "ate": {"type": "string", "description": "Data AAAA-MM-DD, inclusive."},
            "limite": {"type": "integer", "default": 20, "description": f"Quantos eventos, até {TETO_DE_EVENTOS}."},
        },
        "required": [],
    },
}


# ─── Registry ─────────────────────────────────────────────────────────────

TOOLS: list[tuple[dict, Callable]] = [
    (_SCHEMA_HISTORICO, historico_de_alteracoes),
]

METADADOS: dict[str, dict[str, Any]] = {
    "historico_de_alteracoes": {"expor_no_mcp": True},
}
