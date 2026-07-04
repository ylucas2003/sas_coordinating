"""Endpoints de simulados.

As métricas (media, mediana, desvioPadrao, nPresentes) vêm da tabela de cache
`metrica_simulado` (recorte_tipo='geral'), preenchida pelo stats engine ao
fim de cada upload — frontend nunca calcula nada.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import Client

from ..schemas.domain import MateriaResumo, Simulado
from ..stats.classificacao import recalcular_tudo as recalcular_classificacoes
from ..stats.metricas import (
    carregar_metrica_geral,
    corte_aplicavel,
    mapa_metrica_geral_por_simulado,
    recalcular_simulado,
    recalcular_tudo as recalcular_metricas,
)
from ..stats.utils import como_float, nota_real
from ..supabase_client import get_supabase

router = APIRouter(prefix="/simulados", tags=["simulados"])


_CAMPOS_SIMULADO = (
    "id, nome, rotulo_curto, tipo, data_aplicacao, ciclo_id, materia_id, "
    "nota_maxima, anulado"
)


def _mapa_materias(cliente: Client) -> dict[str, MateriaResumo]:
    resp = cliente.table("materia").select("id, codigo, nome").execute()
    return {
        m["id"]: MateriaResumo(codigo=m["codigo"], nome=m["nome"])
        for m in (resp.data or [])
    }


def _mapa_ciclos(cliente: Client) -> dict[str, dict]:
    resp = cliente.table("ciclo").select("id, ordem, vestibular_alvo").execute()
    return {c["id"]: c for c in (resp.data or [])}


def _linha_para_simulado(
    linha: dict,
    metrica: dict | None,
    materias: dict[str, MateriaResumo],
    ciclos: dict[str, dict],
) -> Simulado:
    ciclo = ciclos.get(linha["ciclo_id"], {})
    materia_id = linha.get("materia_id")
    return Simulado(
        id=linha["id"],
        nome=linha["nome"],
        rotuloCurto=linha.get("rotulo_curto"),
        tipo=linha.get("tipo"),
        materia=materias.get(materia_id) if materia_id else None,
        dataAplicacao=linha["data_aplicacao"],
        cicloId=linha["ciclo_id"],
        cicloOrdem=ciclo.get("ordem"),
        vestibularAlvo=ciclo.get("vestibular_alvo"),
        notaMaxima=float(linha.get("nota_maxima") or 0),
        anulado=bool(linha.get("anulado")),
        media=como_float((metrica or {}).get("media")),
        mediana=como_float((metrica or {}).get("mediana")),
        desvioPadrao=como_float((metrica or {}).get("desvio_padrao")),
        nPresentes=(metrica or {}).get("n_presentes"),
    )


@router.get("", response_model=list[Simulado])
async def listar_simulados() -> list[Simulado]:
    cliente = get_supabase()
    metricas = mapa_metrica_geral_por_simulado(cliente)
    materias = _mapa_materias(cliente)
    ciclos = _mapa_ciclos(cliente)
    resp = (
        cliente.table("simulado")
        .select(_CAMPOS_SIMULADO)
        .order("data_aplicacao", desc=True)
        .execute()
    )
    return [
        _linha_para_simulado(linha, metricas.get(linha["id"]), materias, ciclos)
        for linha in (resp.data or [])
    ]


@router.get("/{simulado_id}", response_model=Simulado)
async def obter_simulado(simulado_id: str) -> Simulado:
    cliente = get_supabase()
    resp = (
        cliente.table("simulado")
        .select(_CAMPOS_SIMULADO)
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail=f"simulado {simulado_id} não encontrado")
    metrica = carregar_metrica_geral(cliente, simulado_id)
    materias = _mapa_materias(cliente)
    ciclos = _mapa_ciclos(cliente)
    return _linha_para_simulado(resp.data[0], metrica, materias, ciclos)


@router.get("/{simulado_id}/histograma")
async def histograma_simulado(simulado_id: str) -> dict:
    """Distribuição de notas em bins de 0,5 ponto. Lê direto de metrica_simulado."""
    cliente = get_supabase()
    metrica = carregar_metrica_geral(cliente, simulado_id)
    if metrica is None:
        raise HTTPException(status_code=404, detail=f"métrica de {simulado_id} ainda não calculada")
    return {
        "histograma": metrica.get("histograma"),
        "media": como_float(metrica.get("media")),
        "mediana": como_float(metrica.get("mediana")),
        "desvioPadrao": como_float(metrica.get("desvio_padrao")),
        "quartil1": como_float(metrica.get("quartil_1")),
        "quartil3": como_float(metrica.get("quartil_3")),
        "nPresentes": metrica.get("n_presentes"),
        "nAusentes": metrica.get("n_ausentes"),
    }


@router.get("/{simulado_id}/notas")
async def listar_notas_simulado(simulado_id: str) -> list[dict]:
    """Tabela completa: aluno × nota (em escala 0–10). Usada na ficha do simulado.

    Também devolve `acertos` (pontuação bruta) e `total` (nota_maxima) caso
    a UI queira mostrar "12/20" ao lado da nota.
    """
    cliente = get_supabase()
    base = (
        cliente.table("simulado")
        .select("nota_maxima")
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    if not base.data:
        raise HTTPException(status_code=404, detail=f"simulado {simulado_id} não encontrado")
    nota_maxima_sim = como_float(base.data[0].get("nota_maxima"))

    resp = (
        cliente.table("nota")
        .select("pontuacao, presente, aluno(id, nome)")
        .eq("simulado_id", simulado_id)
        .execute()
    )
    saida: list[dict] = []
    for linha in resp.data or []:
        aluno = linha.get("aluno") or {}
        pontuacao_bruta = como_float(linha.get("pontuacao"))
        nota = nota_real(pontuacao_bruta, nota_maxima_sim)
        saida.append(
            {
                "alunoId": aluno.get("id"),
                "nome": aluno.get("nome", ""),
                "nota": round(nota, 2) if nota is not None else None,   # 0–10
                "acertos": pontuacao_bruta,                              # bruto
                "total": nota_maxima_sim,
                "presente": bool(linha.get("presente")),
            }
        )
    saida.sort(key=lambda r: (not r["presente"], -(r["nota"] or 0)))
    return saida


@router.get("/{simulado_id}/por-materia")
async def metricas_por_materia(simulado_id: str) -> list[dict]:
    """Quebra por matéria.

    No schema atual, cada simulado tem uma única `materia_id` (ou None se
    agregado). Pra uma quebra real "por matéria dentro de uma prova de dia",
    olhamos os simulados irmãos do mesmo ciclo+data e exibimos lado a lado.
    """
    cliente = get_supabase()
    base = (
        cliente.table("simulado")
        .select("id, ciclo_id, data_aplicacao, materia_id")
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    if not base.data:
        raise HTTPException(status_code=404, detail=f"simulado {simulado_id} não encontrado")

    alvo = base.data[0]
    irmaos = (
        cliente.table("simulado")
        .select("id, nome, materia_id, anulado")
        .eq("ciclo_id", alvo["ciclo_id"])
        .eq("data_aplicacao", alvo["data_aplicacao"])
        .eq("anulado", False)
        .execute()
    )

    materias = cliente.table("materia").select("id, nome").execute()
    nome_materia = {m["id"]: m["nome"] for m in (materias.data or [])}

    metricas = mapa_metrica_geral_por_simulado(cliente)
    linhas: list[dict] = []
    for s in irmaos.data or []:
        if not s.get("materia_id"):
            continue
        m = metricas.get(s["id"]) or {}
        linhas.append(
            {
                "simuladoId": s["id"],
                "nome": s["nome"],
                "materia": nome_materia.get(s["materia_id"], "?"),
                "media": como_float(m.get("media")),
                "mediana": como_float(m.get("mediana")),
                "desvioPadrao": como_float(m.get("desvio_padrao")),
                "nPresentes": m.get("n_presentes"),
            }
        )
    linhas.sort(key=lambda r: r["materia"])
    return linhas


@router.get("/{simulado_id}/por-sede")
async def metricas_por_sede(simulado_id: str) -> list[dict]:
    """Quebra do simulado por sede (a partir de metrica_simulado)."""
    cliente = get_supabase()
    metricas_resp = (
        cliente.table("metrica_simulado")
        .select("recorte_id, media, mediana, desvio_padrao, n_presentes")
        .eq("simulado_id", simulado_id)
        .eq("recorte_tipo", "sede")
        .execute()
    )
    sedes = cliente.table("sede").select("id, nome").execute()
    nome_sede = {s["id"]: s["nome"] for s in (sedes.data or [])}

    linhas: list[dict] = []
    for linha in metricas_resp.data or []:
        sid = linha.get("recorte_id")
        linhas.append(
            {
                "sedeId": sid,
                "sede": nome_sede.get(sid, "?"),
                "media": como_float(linha.get("media")),
                "mediana": como_float(linha.get("mediana")),
                "desvioPadrao": como_float(linha.get("desvio_padrao")),
                "nPresentes": linha.get("n_presentes"),
            }
        )
    linhas.sort(key=lambda r: -(r["media"] or 0))
    return linhas


# ─── Edição manual ────────────────────────────────────────────────────────


class PatchSimuladoBody(BaseModel):
    anulado: bool | None = None
    nota_maxima: float | None = None
    rotulo_curto: str | None = None
    nome: str | None = None


@router.patch("/{simulado_id}", response_model=Simulado)
async def editar_simulado(simulado_id: str, body: PatchSimuladoBody) -> Simulado:
    """Edita campos de um simulado.

    Campos aceitos: anulado, nota_maxima, rotulo_curto, nome.

    - anulado=true  → métricas do simulado são removidas do cache; classificações
                       recalculadas (o simulado sai das janelas de notas).
    - anulado=false → simulado reativado; métricas e classificações recalculadas.
    - nota_maxima   → escala de normalização muda; métricas e classificações
                       recalculadas.
    - rotulo_curto / nome → sem impacto em estatísticas.
    """
    cliente = get_supabase()

    resp = (
        cliente.table("simulado")
        .select(_CAMPOS_SIMULADO)
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail=f"simulado {simulado_id} não encontrado")

    simulado_atual = resp.data[0]
    anulado_antes = bool(simulado_atual.get("anulado"))

    atualizacao: dict = {}
    if body.anulado is not None:
        atualizacao["anulado"] = body.anulado
    if body.nota_maxima is not None:
        if body.nota_maxima <= 0:
            raise HTTPException(status_code=422, detail="nota_maxima deve ser positiva")
        atualizacao["nota_maxima"] = body.nota_maxima
    if body.rotulo_curto is not None:
        atualizacao["rotulo_curto"] = body.rotulo_curto
    if body.nome is not None:
        atualizacao["nome"] = body.nome

    if not atualizacao:
        raise HTTPException(status_code=422, detail="Nenhum campo informado para atualizar")

    cliente.table("simulado").update(atualizacao).eq("id", simulado_id).execute()

    anulado_novo = atualizacao.get("anulado", anulado_antes)
    muda_stats = "anulado" in atualizacao or "nota_maxima" in atualizacao

    if muda_stats:
        if anulado_novo:
            # Remove cache de métricas — recalcular_tudo ignora anulados mas
            # não limpa registros anteriores. Limpamos manualmente.
            cliente.table("metrica_simulado").delete().eq("simulado_id", simulado_id).execute()
        else:
            # Reativado ou nota_maxima mudou: recalcula métricas deste simulado.
            simulado_para_corte = {**simulado_atual, **atualizacao}
            nota_maxima = como_float(simulado_para_corte.get("nota_maxima")) or 10.0
            corte = corte_aplicavel(simulado_para_corte)
            recalcular_simulado(
                cliente,
                simulado_id=simulado_id,
                nota_maxima=nota_maxima,
                corte=corte,
            )
        recalcular_classificacoes(cliente)

    resp_novo = (
        cliente.table("simulado")
        .select(_CAMPOS_SIMULADO)
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    metrica = carregar_metrica_geral(cliente, simulado_id)
    materias = _mapa_materias(cliente)
    ciclos = _mapa_ciclos(cliente)
    return _linha_para_simulado(resp_novo.data[0], metrica, materias, ciclos)
